"""circuit_discovery — "I have N days in <region>, where should I go?"

Recommends multi-destination circuits (routes) for a region and trip length, so a traveler who
doesn't know which places to combine gets expert-style suggestions before any single-destination
planning. Retrieval-backed (behind the CircuitProvider interface), cached, best-effort.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

from loguru import logger

from agent.tripos import providers
from agent.tripos.models import Circuit, TripBrief
from agent.tripos.provider_registry import registry


async def discover(region: str, nights: int, brief: TripBrief) -> list[Circuit]:
    """Recommend circuits for a region + length. Best-effort: returns [] if retrieval fails."""
    providers.register_defaults(registry)
    provider = registry.get("circuit")
    if provider is None:
        return []
    try:
        return await provider.discover(region, nights, brief)
    except Exception:
        logger.exception("circuit discovery failed for region={} nights={}", region, nights)
        return []
