"""Web-grounded trip enrichment — stays, restaurants, and weather for ANY destination.

One combined retrieval (a single `research()` web call + one extraction) produces all three,
cached per destination in `intelligence_cache`. Three thin providers expose the slices behind
the AccommodationProvider / RestaurantProvider / WeatherProvider interfaces, so future paid
sources (Booking, Google Places, …) can replace any one of them with no planner change.
The shared cache means calling all three costs ONE fetch, not three.
"""

from __future__ import annotations

from pydantic_ai import Agent

from agent.services.llm import build_model, research
from agent.tripos import intelligence_cache
from agent.tripos.models import (
    Accommodation,
    Destination,
    Restaurant,
    TripBrief,
    TripEnrichment,
    WeatherInsight,
)

_EXTRACTOR_PROMPT = """\
You convert researched travel notes into structured trip enrichment for a planner. Use ONLY
real, verifiable places from the notes — never invent one.
- stays: 2–3 per tier (budget, mid, premium). Give area, kind (hostel/homestay/hotel/resort),
  realistic price_per_night range, and a one-line `why`. tier must be exactly budget|mid|premium.
- restaurants: ~6 with VARIETY — include vegetarian-friendly, local/authentic, and family
  options; respect the traveler's food preference where possible. cuisine, price_band ($/$$/$$$),
  good_for, and a one-line why.
- weather: a season_label, a short summary, temp range if known, and practical advisories
  (e.g. "Heavy monsoon rain Jun–Sep — favour indoor stops").
Prices are estimates, not live quotes."""

_extractor = Agent(
    build_model("balanced"), output_type=TripEnrichment, system_prompt=_EXTRACTOR_PROMPT
)


async def gather(destination: Destination, brief: TripBrief) -> TripEnrichment:
    """Retrieve (and cache) stays + restaurants + weather for a destination. One web fetch."""
    cached = await intelligence_cache.get(destination.id)
    if cached is not None:
        return TripEnrichment.model_validate_json(cached)

    where = destination.name
    if destination.country:
        where = f"{destination.name}, {destination.country}"
    info = await research(
        f"For {where}: (1) places to STAY across budget, mid-range and premium tiers — name "
        f"real hotels/homestays/resorts, their area, and rough price per night; (2) notable "
        f"RESTAURANTS — vegetarian-friendly, local/authentic and family options, with cuisine "
        f"and rough price level; (3) the best SEASONS to visit and the WEATHER to expect, with "
        f"advisories. Real, verifiable places only."
    )
    interests = ", ".join(s.value for s in brief.interests)
    result = await _extractor.run(
        f"Traveler: group={brief.group_type.value}, interests={interests}, "
        f"food preference={brief.food_pref.value}, per-person budget=₹{brief.budget:.0f}.\n\n"
        f"Researched notes:\n{info.text}\n\nProduce the structured enrichment."
    )
    enriched = result.output
    await intelligence_cache.put(destination.id, enriched.model_dump_json())
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
