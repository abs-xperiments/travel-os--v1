"""Web destination retrieval adapter — plan ANY place on Earth.

This is what makes TripOS destination-agnostic. For a place not in the curated catalog it:
  1. VERIFIES it exists via the geocoding provider (real coordinates) — else returns None;
  2. gathers grounded facts via the web (`research()` = Perplexity Sonar, with citations);
  3. EXTRACTS a structured `Destination` (with attractions) from those facts using a model.

The result is the same `Destination` type the catalog yields, so every downstream engine
(attraction selection, feasibility, itinerary, budget) works unchanged.
"""

from __future__ import annotations

from pydantic_ai import Agent

from agent.services.llm import build_model, research
from agent.tripos.models import Destination, TripBrief
from agent.tripos.provider_interfaces import slugify
from agent.tripos.provider_registry import registry

_EXTRACTOR_PROMPT = """\
You convert researched travel notes into a structured Destination for a trip planner.
Rules:
- Use ONLY real, verifiable places named in the notes — never invent an attraction.
- Provide 10-12 attractions with a genuine MIX: the famous icons AND lesser-known local
  favourites / hidden gems, so the planner can serve both first-timers and "non-touristy"
  travelers. For each: a realistic duration_hours; indoor true/false; a `base`
  = the town/area/neighbourhood it sits in (group nearby ones under the same base so they can
  be clustered); honest suitable_for_seniors and child_friendly; photography_value,
  adventure_level and worth_visiting on 1-10; popularity on 1-10 (10 = world-famous icon,
  1 = local secret — score honestly; hidden gems can still have HIGH worth_visiting);
  best_time one of "early morning","morning","afternoon","evening".
- good_for: the travel styles this place genuinely suits (from the allowed set).
- state/region: the province/region and broader area; bases: realistic places to stay;
  nearest_railhead and nearest_airport as best known (use "Unknown" if truly unclear).
Be realistic and honest, not promotional. Durations/scores are typical estimates."""

# Sonnet — reliable structured extraction (the "balanced" cost/quality choice).
_extractor = Agent(
    build_model("balanced"), output_type=Destination, system_prompt=_EXTRACTOR_PROMPT
)


class WebDestinationProvider:
    """Builds a Destination for any verifiable place via geocoding + web research + extraction."""

    name = "web"

    async def fetch(self, query: str, brief: TripBrief | None = None) -> Destination | None:
        geocoder = registry.get("geocoding")
        place = await geocoder.geocode(query) if geocoder else None
        if place is None:
            return None  # can't verify it exists — the only legitimate "can't plan" case

        info = await research(
            f"Concise travel guide for {place.display_name}. List ~12 real attractions — BOTH "
            f"the famous must-sees AND lesser-known local favourites / hidden gems that "
            f"residents recommend (what each is, ideal hours to spend, indoor or outdoor, who "
            f"it suits, how touristy vs local it is), the best seasons to visit, how to get "
            f"around, the nearest airport and railway station, and notable local food. Real, "
            f"verifiable places only."
        )

        result = await _extractor.run(
            f"Destination: {place.display_name}\nCountry: {place.country}\n\n"
            f"Researched notes (ground your answer in these, do not invent places):\n"
            f"{info.text}\n\n"
            f"Build the structured Destination."
        )
        dest = result.output

        # Normalize: stable slug id, link attractions to it, trust geocoding for coords/country.
        slug = slugify(query)
        attractions = [a.model_copy(update={"destination_id": slug}) for a in dest.attractions]
        return dest.model_copy(
            update={
                "id": slug,
                "attractions": attractions,
                "coordinates": place.coordinates,
                "country": place.country or dest.country,
            }
        )
