"""Web-grounded destination discovery — "where should I go?" answered with real suggestions.

Answers constraint-shaped discovery asks ("5 days in December, beaches, ₹40k from Chennai")
by researching destinations that genuinely fit the month, budget, days and interests, then
extracting 3–5 structured ideas. One cached web call per distinct ask. Behind the
DestinationSuggestionProvider role in the registry, so a richer source can replace it later
with no planner change. (The 24-place curated catalog stays the fast path for full planning —
discovery deliberately searches the whole world.)
"""

from __future__ import annotations

from pydantic_ai import Agent

from agent.services.llm import build_model, research
from agent.tripos import intelligence_cache
from agent.tripos.models import MONTH_NAMES, DestinationIdea, DestinationIdeas
from agent.tripos.provider_interfaces import slugify

_EXTRACTOR_PROMPT = """\
You convert researched travel notes into structured destination suggestions.
- Give 3–5 DISTINCT destination ideas that genuinely fit the traveler's constraints (days,
  month/season, per-person budget, interests, region). Use REAL places only — never invent.
- For each: name, country, a one-line why tied to THEIR constraints, best_season (and how the
  asked month fits it), a rough est_per_person_budget (₹) for the asked trip length, good_for
  tags, and ONE honest tradeoff (crowds, travel time, monsoon risk, cost…).
- Budgets are rough estimates, never exact. If the notes don't support a destination for the
  asked month, leave it out rather than stretching the truth."""

_extractor = Agent(
    build_model("balanced"), output_type=DestinationIdeas, system_prompt=_EXTRACTOR_PROMPT
)


def _cache_key(
    days: int | None,
    month: int | None,
    budget: float | None,
    interests: list[str],
    region: str | None,
) -> str:
    """One cache row per distinct ask — constraints change the answer, so they key the cache."""
    parts = [
        "suggest",
        slugify(region) if region else "anywhere",
        str(days or 0),
        str(month or 0),
        str(int(budget or 0)),
        "-".join(sorted(i.lower() for i in interests)) or "any",
        "v1",
    ]
    return ":".join(parts)


async def _gather(
    days: int | None,
    month: int | None,
    budget: float | None,
    interests: list[str],
    region: str | None,
    start_city: str | None,
) -> DestinationIdeas:
    key = _cache_key(days, month, budget, interests, region)
    cached = await intelligence_cache.get(key)
    if cached is not None:
        return DestinationIdeas.model_validate_json(cached)

    asks: list[str] = []
    if days:
        asks.append(f"a {days}-day trip")
    if month:
        asks.append(f"travelling in {MONTH_NAMES[month]}")
    if budget:
        asks.append(f"around ₹{budget:,.0f} per person all-in")
    if interests:
        asks.append(f"interests: {', '.join(interests)}")
    if start_city:
        asks.append(f"starting from {start_city}")
    where = (
        f"in {region}" if region else "worldwide (lean towards destinations practical from India)"
    )
    info = await research(
        f"Best travel destinations {where} for {'; '.join(asks) or 'a leisure trip'}. "
        f"Suggest 3-5 distinct, real destinations that genuinely fit the month and budget; for "
        f"each give why it fits, its best season, a rough per-person trip cost, and one honest "
        f"drawback. Real places only."
    )
    result = await _extractor.run(
        f"Traveler constraints: {'; '.join(asks) or 'open'}.\n\n"
        f"Researched notes:\n{info.text}\n\nProduce the destination suggestions."
    )
    await intelligence_cache.put(key, result.output.model_dump_json())
    return result.output


class WebDestinationSuggester:
    name = "web"

    async def suggest(
        self,
        days: int | None,
        month: int | None,
        budget: float | None,
        interests: list[str],
        region: str | None,
        start_city: str | None,
    ) -> list[DestinationIdea]:
        return (await _gather(days, month, budget, interests, region, start_city)).ideas
