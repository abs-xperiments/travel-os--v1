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
    try:
        stays = await acc.search(destination, brief) if acc else []
        restaurants = await res.search(destination, brief) if res else []
        weather = await wx.insight(destination, brief) if wx else None
        return TripEnrichment(stays=stays, restaurants=restaurants, weather=weather)
    except Exception:
        logger.exception("enrichment failed for {} — planning without it", destination.id)
        return TripEnrichment()


async def season_profile(destination_query: str, brief: TripBrief) -> SeasonalityProfile | None:
    """The year-round seasonality profile for a destination NAME — for advising before a build.

    Rides the same cached enrichment fetch the build uses, so checking the season early costs
    nothing extra overall: the first caller pays the one web fetch, the build then hits cache.
    Returns None when no solid seasonal data was retrieved (then: no advisory, never a bluff).
    """
    return (await enrich(_stub_for(destination_query), brief)).seasonality


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
    query: str, brief: TripBrief
) -> tuple[Destination | None, TripEnrichment]:
    """Resolve a destination AND fetch its enrichment CONCURRENTLY.

    Enrichment is keyed by the destination's slug and its research only needs the name, so it
    can run in parallel with resolve() instead of waiting for it — roughly halving the wait for
    an uncached destination, with identical results. (For a misspelled place, resolve returns
    None and the parallel enrichment is simply discarded.)
    """
    resolved, enrichment = await asyncio.gather(
        destination_intelligence.resolve(query, brief),
        enrich(_stub_for(query), brief),
    )
    return resolved, enrichment
