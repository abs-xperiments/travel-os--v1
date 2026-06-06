"""destination_suggestion — "where should I go?" answered with ranked, real suggestions.

Recommends 3–5 destinations that fit the traveler's constraints (days, month, budget,
interests, region), so a traveler who doesn't know WHERE gets expert-style ideas before any
planning. Retrieval-backed (behind the destination_suggestion registry role), cached,
best-effort.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

from loguru import logger

from agent.tripos import providers
from agent.tripos.models import DestinationIdea
from agent.tripos.provider_registry import registry


async def suggest(
    days: int | None = None,
    month: int | None = None,
    budget: float | None = None,
    interests: list[str] | None = None,
    region: str | None = None,
    start_city: str | None = None,
) -> list[DestinationIdea]:
    """Suggest destinations for the given constraints. Best-effort: [] if retrieval fails."""
    providers.register_defaults(registry)
    provider = registry.get("destination_suggestion")
    if provider is None:
        return []
    try:
        return await provider.suggest(days, month, budget, interests or [], region, start_city)
    except Exception:
        logger.exception(
            "destination suggestion failed (days={} month={} region={})", days, month, region
        )
        return []
