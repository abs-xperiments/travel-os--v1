"""Web-grounded circuit discovery — multi-destination routes for a region + trip length.

Answers "I have N nights in Kerala — where should I go?" by retrieving real, commonly-travelled
routes (e.g. Kochi → Munnar → Thekkady → Alleppey) with an intelligent per-leg night
allocation (more nights where there's more to do, not an even split). One cached web call per
(region, nights). Behind the CircuitProvider interface, so a future routing/maps source can
replace it with no planner change.
"""

from __future__ import annotations

from pydantic_ai import Agent

from agent.services.llm import build_model, research
from agent.tripos import intelligence_cache
from agent.tripos.models import Circuit, CircuitOptions, TripBrief
from agent.tripos.provider_interfaces import slugify

_EXTRACTOR_PROMPT = """\
You convert researched notes into structured multi-destination travel circuits.
- Give 2–4 DISTINCT routes. Each circuit: a short name, the legs in travel order (destination +
  nights), total_nights (≈ the requested length), a style, a rough per-person budget, and why.
- Allocate nights by how much there is to do at each place — NOT evenly (e.g. 1 gateway night,
  2 at a hill station, 1 elsewhere). total_nights across legs should match the requested nights.
- Use REAL, well-known destinations and routes only — never invent a place."""

_extractor = Agent(
    build_model("balanced"), output_type=CircuitOptions, system_prompt=_EXTRACTOR_PROMPT
)


async def _gather(region: str, nights: int, brief: TripBrief) -> CircuitOptions:
    key = f"circuit:{slugify(region)}:{nights}"
    cached = await intelligence_cache.get(key)
    if cached is not None:
        return CircuitOptions.model_validate_json(cached)

    interests = ", ".join(s.value for s in brief.interests) or "general sightseeing"
    info = await research(
        f"Popular {nights}-night travel circuits/routes in {region} for a {brief.group_type.value} "
        f"trip with interests {interests}. Give 2-4 distinct multi-destination routes; for each, "
        f"the destinations in travel order with suggested nights per place (allocate by how much "
        f"there is to do, not evenly), the overall style, a rough per-person budget, and why it's "
        f"recommended. Real, well-known routes only."
    )
    result = await _extractor.run(
        f"Requested length: {nights} nights. Traveler: {brief.group_type.value}, "
        f"interests {interests}, per-person budget ~₹{brief.budget:.0f}.\n\n"
        f"Researched notes:\n{info.text}\n\nProduce the circuits."
    )
    await intelligence_cache.put(key, result.output.model_dump_json())
    return result.output


class WebCircuitProvider:
    name = "web"

    async def discover(self, region: str, nights: int, brief: TripBrief) -> list[Circuit]:
        return (await _gather(region, nights, brief)).circuits
