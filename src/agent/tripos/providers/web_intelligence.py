"""Web-grounded trip enrichment — stays, restaurants, weather & seasonality for ANY destination.

ONE `research()` web call per destination (the cost optimization), but the structured
extraction is SPLIT into four small parallel extractors — one per slice — instead of a single
monolithic output (2026-06-07). Same model, same notes, focused prompts: wall-clock for the
extraction drops to the slowest slice instead of the sum-shaped monolith. The seasonality
slice additionally resolves EARLY (`gather_seasonality`), so a season check stops paying for
stays/food/weather it doesn't need — those finish in the background and fill the same cache.

Four thin providers expose the slices behind the provider interfaces, so future paid sources
(Booking, Google Places, …) can replace any one of them with no planner change.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from agent.services.llm import build_model, research
from agent.tripos import intelligence_cache
from agent.tripos.models import (
    Accommodation,
    Destination,
    Restaurant,
    SeasonalityProfile,
    TripBrief,
    TripEnrichment,
    WeatherInsight,
)

_NEVER_INVENT = "Use ONLY real, verifiable places/facts from the notes — never invent one. "

_STAYS_PROMPT = _NEVER_INVENT + (
    "Extract places to STAY: 2–3 per tier (budget, mid, premium). Give area, kind "
    "(hostel/homestay/hotel/resort), a realistic price_per_night range, and a one-line `why`. "
    "tier must be exactly budget|mid|premium. Prices are estimates, not live quotes."
)
_RESTAURANTS_PROMPT = _NEVER_INVENT + (
    "Extract ~6 RESTAURANTS with VARIETY — include vegetarian-friendly, local/authentic, and "
    "family options; respect the traveler's food preference where possible. cuisine, "
    "price_band ($/$$/$$$), good_for, and a one-line why."
)
_WEATHER_PROMPT = _NEVER_INVENT + (
    "Extract the WEATHER picture: a season_label, a short summary, temp range if known, and "
    "practical advisories (e.g. 'Heavy monsoon rain Jun–Sep — favour indoor stops'). If the "
    "notes say nothing solid, return weather=null rather than guessing."
)
_SEASONALITY_PROMPT = _NEVER_INVENT + (
    "Extract SEASONALITY: ALL 12 months, each with a rating (excellent|good|acceptable|"
    "challenging|not_recommended), a short note giving the why (heat / monsoon / cyclones / "
    "crowds / prices), and lean_indoor=true ONLY when plans that month should favour indoor "
    "or sheltered stops (heavy rain, extreme heat — crowds alone don't set it). Also "
    "best_months (month numbers, the recommended window) and a one-line summary. Base every "
    "rating on the notes; if the notes say nothing about seasons, leave months EMPTY."
)


class _StaySlice(BaseModel):
    stays: list[Accommodation] = Field(default_factory=list)


class _RestaurantSlice(BaseModel):
    restaurants: list[Restaurant] = Field(default_factory=list)


class _WeatherSlice(BaseModel):
    weather: WeatherInsight | None = None


class _SeasonalitySlice(BaseModel):
    seasonality: SeasonalityProfile | None = None


_stays_agent = Agent(build_model("balanced"), output_type=_StaySlice, system_prompt=_STAYS_PROMPT)
_restaurants_agent = Agent(
    build_model("balanced"), output_type=_RestaurantSlice, system_prompt=_RESTAURANTS_PROMPT
)
_weather_agent = Agent(
    build_model("balanced"), output_type=_WeatherSlice, system_prompt=_WEATHER_PROMPT
)
_seasonality_agent = Agent(
    build_model("balanced"), output_type=_SeasonalitySlice, system_prompt=_SEASONALITY_PROMPT
)


# Slice wrappers as module functions so tests can monkeypatch each independently.
async def _extract_stays(notes: str, traveler: str) -> list[Accommodation]:
    return (await _stays_agent.run(f"{traveler}\n\nResearched notes:\n{notes}")).output.stays


async def _extract_restaurants(notes: str, traveler: str) -> list[Restaurant]:
    out = await _restaurants_agent.run(f"{traveler}\n\nResearched notes:\n{notes}")
    return out.output.restaurants


async def _extract_weather(notes: str) -> WeatherInsight | None:
    return (await _weather_agent.run(f"Researched notes:\n{notes}")).output.weather


async def _extract_seasonality(notes: str) -> SeasonalityProfile | None:
    out = await _seasonality_agent.run(f"Researched notes:\n{notes}")
    return out.output.seasonality


# Bump when the payload shape grows (v2 = seasonality added): a new key bypasses cached rows
# from before the change — otherwise they'd pin the missing field for the cache's max age.
# (The split extraction kept the SAME TripEnrichment shape, so v2 rows stay valid.)
_CACHE_KEY_VERSION = "v2"

# One retrieval per destination at a time: concurrent callers (e.g. a season check that warms
# the cache and a build that starts moments later) await the SAME task — never a double fetch.
# The first caller's brief colours the extraction slightly; followers get the identical result,
# exactly as a cache hit would.
_in_flight: dict[str, asyncio.Task[TripEnrichment]] = {}

# Early-resolution futures for the seasonality slice: a season check can have its answer the
# moment that ONE extraction finishes, while the other slices keep running in the background.
_season_ready: dict[str, asyncio.Future[SeasonalityProfile | None]] = {}


def _ensure_fetch(key: str, destination: Destination, brief: TripBrief) -> asyncio.Task:
    """The (coalesced) in-flight full fetch for a destination — started if not already running."""
    task = _in_flight.get(key)
    if task is None:
        task = asyncio.create_task(_fetch(key, destination, brief))
        _in_flight[key] = task
        task.add_done_callback(lambda _, k=key: _in_flight.pop(k, None))
    return task


async def gather(destination: Destination, brief: TripBrief) -> TripEnrichment:
    """Retrieve (and cache) stays + restaurants + weather + seasonality. One web fetch."""
    key = f"{destination.id}:{_CACHE_KEY_VERSION}"
    cached = await intelligence_cache.get(key)
    if cached is not None:
        return TripEnrichment.model_validate_json(cached)
    return await _ensure_fetch(key, destination, brief)


async def gather_seasonality(
    destination: Destination, brief: TripBrief
) -> SeasonalityProfile | None:
    """The seasonality slice as soon as IT is ready — without waiting for the full enrichment.

    Starts (or joins) the same full fetch the build uses, but returns the moment the
    seasonality extraction completes; stays/restaurants/weather keep running in the background
    and land in the same cache entry. A season check on a cold destination stops paying for
    work it doesn't need.
    """
    key = f"{destination.id}:{_CACHE_KEY_VERSION}"
    cached = await intelligence_cache.get(key)
    if cached is not None:
        return TripEnrichment.model_validate_json(cached).seasonality

    fut = _season_ready.get(key)
    if fut is None:
        fut = asyncio.get_running_loop().create_future()
        _season_ready[key] = fut
    task = _ensure_fetch(key, destination, brief)
    await asyncio.wait({fut, task}, return_when=asyncio.FIRST_COMPLETED)
    if fut.done() and not fut.cancelled():
        return fut.result()
    return (await task).seasonality  # full fetch won the race (or failed — propagate honestly)


async def _fetch(key: str, destination: Destination, brief: TripBrief) -> TripEnrichment:
    """The miss path: ONE research call, then four small slice extractions IN PARALLEL."""
    try:
        where = destination.name
        if destination.country:
            where = f"{destination.name}, {destination.country}"
        info = await research(
            f"For {where}: (1) places to STAY across budget, mid-range and premium tiers — name "
            f"real hotels/homestays/resorts, their area, and rough price per night; (2) notable "
            f"RESTAURANTS — vegetarian-friendly, local/authentic and family options, with cuisine "
            f"and rough price level; (3) the best SEASONS to visit and the WEATHER to expect, "
            f"with advisories; (4) a MONTH-BY-MONTH view of the whole year — for each month, how "
            f"suitable it is to visit (weather, rain/heat, crowds, prices) and which months are "
            f"best. Real, verifiable places only."
        )
        interests = ", ".join(s.value for s in brief.interests)
        traveler = (
            f"Traveler: group={brief.group_type.value}, interests={interests}, "
            f"food preference={brief.food_pref.value}, per-person budget=₹{brief.budget:.0f}."
        )

        async def _season_early() -> SeasonalityProfile | None:
            out = await _extract_seasonality(info.text)
            fut = _season_ready.get(key)
            if fut is not None and not fut.done():
                fut.set_result(out)  # a waiting season check gets its answer RIGHT NOW
            return out

        stays, restaurants, weather, seasonality = await asyncio.gather(
            _extract_stays(info.text, traveler),
            _extract_restaurants(info.text, traveler),
            _extract_weather(info.text),
            _season_early(),
        )
        # Construct with EVERY slice explicit — the silent-field-drop lesson (learnings.md).
        enriched = TripEnrichment(
            stays=stays, restaurants=restaurants, weather=weather, seasonality=seasonality
        )
        await intelligence_cache.put(key, enriched.model_dump_json())
        return enriched
    finally:
        fut = _season_ready.pop(key, None)
        if fut is not None and not fut.done():
            fut.cancel()  # fetch failed before the slice resolved — waiters fall back to task


_FOCUSED_PROMPT = _NEVER_INVENT + (
    "Convert the researched notes into structured trip enrichment. Fill ONLY the slices the "
    "notes actually cover (e.g. just stays, or just restaurants) and leave everything else "
    "EMPTY — never pad or guess. Prices are estimates, not live quotes."
)
_focused_extractor = Agent(
    build_model("balanced"), output_type=TripEnrichment, system_prompt=_FOCUSED_PROMPT
)


async def gather_focused(place: str, ask: str, cache_key: str) -> TripEnrichment:
    """A second, narrowly-scoped retrieval for a specific ask the generic enrichment was too
    thin for (e.g. "homestays" in a tiny village whose generic fetch found mostly hotels).

    Cached under its OWN key (e.g. "didupe:stays:homestay:v1") — NEVER the canonical
    "{slug}:v2" key — so a filtered niche fetch can't overwrite the per-destination enrichment
    that builds and season checks depend on. Callers gate this behind a thin-result check, so
    the common path stays one fetch. (Single combined extraction is fine here: the output is
    one slice's worth, so the monolith latency problem doesn't apply.)
    """
    cached = await intelligence_cache.get(cache_key)
    if cached is not None:
        return TripEnrichment.model_validate_json(cached)

    info = await research(
        f"For {place}: {ask}. Name real, verifiable places only — for each give the area, a "
        f"rough price range, and what makes it good."
    )
    result = await _focused_extractor.run(
        f"Researched notes:\n{info.text}\n\nProduce the structured enrichment from these notes "
        "only. Leave any slice the notes don't cover EMPTY — never pad or guess."
    )
    enriched = result.output
    await intelligence_cache.put(cache_key, enriched.model_dump_json())
    return enriched


class WebAccommodationProvider:
    name = "web"

    async def search(self, destination: Destination, brief: TripBrief) -> list[Accommodation]:
        return (await gather(destination, brief)).stays


class WebRestaurantProvider:
    name = "web"

    async def search(self, destination: Destination, brief: TripBrief) -> list[Restaurant]:
        return (await gather(destination, brief)).restaurants


class WebWeatherProvider:
    name = "web"

    async def insight(self, destination: Destination, brief: TripBrief) -> WeatherInsight | None:
        return (await gather(destination, brief)).weather


class WebSeasonalityProvider:
    name = "web"

    async def profile(
        self, destination: Destination, brief: TripBrief
    ) -> SeasonalityProfile | None:
        # The fast path: resolves the moment the seasonality extraction lands; the other
        # slices keep filling the shared cache in the background.
        return await gather_seasonality(destination, brief)
