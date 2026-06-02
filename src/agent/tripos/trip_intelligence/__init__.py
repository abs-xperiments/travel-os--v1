"""trip_intelligence — enrich a destination with stays, restaurants, and weather.

The single entry the planner uses to add Phase-2 intelligence. It asks the registered
providers (accommodation / restaurant / weather) — which today are backed by one cached web
retrieval, tomorrow could be Booking/Google Places/Open-Meteo — and returns a `TripEnrichment`.
It never fails the trip: if enrichment can't be retrieved, it returns empty fields and the
plan is still produced.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from loguru import logger

from agent.tripos import intelligence_cache, providers
from agent.tripos.models import Destination, TripBrief, TripEnrichment
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
