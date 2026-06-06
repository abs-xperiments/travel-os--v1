"""trip_intelligence — enrich a destination with stays, restaurants, and weather.

The single entry the planner uses to add Phase-2 intelligence. It asks the registered
providers (accommodation / restaurant / weather) — which today are backed by one cached web
retrieval, tomorrow could be Booking/Google Places/Open-Meteo — and returns a `TripEnrichment`.
It never fails the trip: if enrichment can't be retrieved, it returns empty fields and the
plan is still produced.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from loguru import logger

from agent.tripos import destination_intelligence, intelligence_cache, providers
from agent.tripos.models import Destination, SeasonalityProfile, TripBrief, TripEnrichment
from agent.tripos.provider_interfaces import slugify
from agent.tripos.provider_registry import registry


async def init_db() -> list[str]:
    """Create the enrichment cache table on startup."""
    return await intelligence_cache.init_db()


async def enrich(destination: Destination, brief: TripBrief) -> TripEnrichment:
    """Retrieve stays + restaurants + weather for a destination via the registered providers.

    Best-effort: on any failure it returns an empty TripEnrichment so the trip still plans.
    The providers share one cached web fetch, so this is a single retrieval per destination.
    """
    providers.register_defaults(registry)
    acc = registry.get("accommodation")
    res = registry.get("restaurant")
    wx = registry.get("weather")
    season = registry.get("seasonality")
    try:
        stays = await acc.search(destination, brief) if acc else []
        restaurants = await res.search(destination, brief) if res else []
        weather = await wx.insight(destination, brief) if wx else None
        seasonality = await season.profile(destination, brief) if season else None
        return TripEnrichment(
            stays=stays, restaurants=restaurants, weather=weather, seasonality=seasonality
        )
    except Exception:
        logger.exception("enrichment failed for {} — planning without it", destination.id)
        return TripEnrichment()


async def enrich_by_name(query: str, brief: TripBrief) -> TripEnrichment:
    """Enrichment (stays/restaurants/weather/seasonality) for a place NAME — no full resolve.

    The cheap path for standalone requests ("homestays in Didupe", "restaurants in Kochi"):
    enrichment only needs the name, and it rides the same per-destination cache the build uses
    (key = the name's slug) — so answering a stays question today makes a later full plan for
    the same place a cache HIT, not an extra fetch.
    """
    return await enrich(_stub_for(query), brief)


async def season_profile(destination_query: str, brief: TripBrief) -> SeasonalityProfile | None:
    """The year-round seasonality profile for a destination NAME — for advising before a build.

    Goes straight to the seasonality provider (NOT the full enrichment), which resolves the
    moment its slice of the shared fetch is extracted — the stays/restaurants/weather slices
    keep filling the same cache in the background, so the build that follows still hits cache.
    Returns None when no solid seasonal data was retrieved (then: no advisory, never a bluff).
    """
    providers.register_defaults(registry)
    season = registry.get("seasonality")
    if season is None:
        return None
    try:
        return await season.profile(_stub_for(destination_query), brief)
    except Exception:
        logger.exception("season profile failed for {!r} — advising without it", destination_query)
        return None


def _stub_for(query: str) -> Destination:
    """A minimal Destination carrying just the identity enrich needs (name + slug cache key),
    so enrichment can run BEFORE/while resolve() does its heavy retrieval."""
    return Destination(
        id=slugify(query),
        name=query,
        state="",
        region="",
        description="",
        bases=[],
        good_for=[],
        nearest_railhead="",
        nearest_airport="",
    )


async def resolve_and_enrich(
    query: str,
    brief: TripBrief,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[Destination | None, TripEnrichment]:
    """Resolve a destination AND fetch its enrichment CONCURRENTLY.

    Enrichment is keyed by the destination's slug and its research only needs the name, so it
    can run in parallel with resolve() instead of waiting for it — roughly halving the wait for
    an uncached destination, with identical results. (For a misspelled place, resolve returns
    None and the parallel enrichment is simply discarded.)

    on_progress, when given, is called with "destination" / "enrichment" as each half
    COMPLETES (resolve only on success) — so callers can show honest live progress.
    """

    async def _resolved() -> Destination | None:
        out = await destination_intelligence.resolve(query, brief)
        if on_progress is not None and out is not None:
            on_progress("destination")
        return out

    async def _enriched() -> TripEnrichment:
        out = await enrich(_stub_for(query), brief)
        if on_progress is not None:
            on_progress("enrichment")
        return out

    resolved, enrichment = await asyncio.gather(_resolved(), _enriched())
    return resolved, enrichment
