"""The planner agent's tools — the typed functions the LLM calls for anything concrete.

The LLM talks to the traveler; it never invents facts or does the planning maths itself.
Destinations, seasons, routes and full plans all come from these tools, backed by retrieval +
the tested planning modules.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import ValidationError

from agent.tripos import (
    circuit_discovery,
    circuit_planner,
    destination_intelligence,
    trip_intelligence,
    trip_planner,
)
from agent.tripos import destination_catalog as catalog
from agent.tripos.models import (
    MONTH_NAMES,
    GroupType,
    Pace,
    PopularityPref,
    TravelStyle,
    TripBrief,
)
from agent.tripos.provider_interfaces import slugify

from . import progress
from .compact import _compact_circuit, _compact_plan, _neutral_brief, _parse_date

# Checklist labels for the two halves of resolve_and_enrich (see _enrich_progress).
_PART_LABELS = {
    "destination": "Destination intelligence",
    "enrichment": "Stays, food & weather",
}


def _enrich_progress(part: str) -> None:
    """resolve_and_enrich's on_progress hook — ticks the matching checklist line."""
    label = _PART_LABELS.get(part)
    if label:
        progress.finish(label)


def list_destinations() -> list[dict]:
    """A few popular EXAMPLE destinations to suggest when a traveler doesn't know where to go.

    This is NOT the set of places TripOS can plan — it can plan anywhere via `build_trip`.
    These are just curated suggestions with rich detail.
    """
    return [
        {
            "id": d.id,
            "name": d.name,
            "state": d.state,
            "good_for": [s.value for s in d.good_for],
            "summary": d.description,
        }
        for d in catalog.list_destinations()
    ]


# Background prewarm tasks — held here so they aren't garbage-collected mid-flight.
_prewarm_tasks: set[asyncio.Task[None]] = set()


def _prewarm_destination(destination: str) -> None:
    """Fire-and-forget destination resolve, so the eventual build finds a warm cache.

    The season check runs BETWEEN gathering and building, while the traveler is still
    answering questions — dead time we can use. Its seasonality fetch already warms the
    enrichment cache; this warms the other half (destination knowledge). In-flight coalescing
    in destination_intelligence/web_intelligence guarantees a build that overlaps with this
    never pays for the same retrieval twice. Best-effort: failures are logged and ignored —
    the build simply retrieves fresh, exactly as before.
    """

    async def _run() -> None:
        try:
            await destination_intelligence.resolve(destination, _neutral_brief())
        except Exception:
            logger.debug("prewarm resolve failed for {!r} — build will retrieve fresh", destination)

    task = asyncio.create_task(_run())
    _prewarm_tasks.add(task)
    task.add_done_callback(_prewarm_tasks.discard)


async def check_travel_season(destination: str, month: int | None = None) -> dict:
    """How suitable a travel month is for a destination, plus the best months to go.

    Call this once you know the destination (or chosen region/route) AND when the traveler
    wants to go — BEFORE building the trip. month is 1–12; omit it when the traveler is
    flexible, to get the best window to recommend. Returns a suitability rating
    (excellent|good|acceptable|challenging|not_recommended) with the reason and best_months —
    or unknown=true when there's no reliable seasonal data (then plan WITHOUT any advisory).
    """
    if month is not None and not 1 <= month <= 12:
        return {"error": "month must be 1-12"}
    # Start warming destination knowledge NOW (concurrent with the season lookup below) — by
    # the time the traveler confirms and the build runs, retrieval is already done or underway.
    _prewarm_destination(destination)
    profile = await trip_intelligence.season_profile(destination, _neutral_brief())
    if profile is None or not profile.months:
        return {"destination": destination, "unknown": True}

    out: dict = {
        "destination": destination,
        "summary": profile.summary,
        "best_months": [MONTH_NAMES[m] for m in profile.best_months if 1 <= m <= 12],
    }
    if month is not None:
        assessment = profile.for_month(month)
        if assessment is None:
            out["unknown"] = True
        else:
            out["month"] = MONTH_NAMES[month]
            out["suitability"] = assessment.rating.value
            out["note"] = assessment.note
    return out


async def build_trip(
    destination: str,
    start_city: str,
    days: int,
    group_type: str,
    interests: list[str],
    budget: float,
    pace: str = "balanced",
    travelers: int | None = None,
    travel_month: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    popularity_pref: str = "balanced",
    avoid: list[str] | None = None,
    must_include: list[str] | None = None,
) -> dict:
    """Build a complete day-by-day plan + budget for a destination — ANY real place worldwide.

    Call this once you know the destination NAME and the traveler's days, group, interests and
    budget. It resolves the place (curated catalog or live web retrieval), then plans it —
    adapted to the travel month when one is known. Returns the plan, or an `error` string you
    should relay and then fix.

    - budget: the PER-PERSON budget in the local currency (per traveler, NOT the group total).
    - travelers: the number of travelers if known (used to compute the group total); if omitted
      it's inferred from the group_type.
    - travel_month: month of travel, 1–12 (e.g. July = 7). Omit only if the traveler is
      flexible and no window was agreed.
    - start_date / end_date: exact dates as YYYY-MM-DD, ONLY if the traveler gave them — they
      are kept with the trip; never ask for exact dates when a month is enough.

    Personalization (these CONSTRAIN the plan — pass them whenever the traveler expresses them):
    - popularity_pref: "offbeat" for non-touristy / hidden gems / local experiences;
      "iconic" for classic highlights / first-timer must-sees; "balanced" otherwise.
    - avoid: things to leave out entirely, e.g. ["temples", "malls"].
    - must_include: places they explicitly asked for, e.g. ["Taj Mahal"] — always honoured.

    Allowed values:
    - group_type: solo, couple, friends, family, family_with_children, family_with_seniors
    - interests: nature, adventure, food, relaxation, photography, road_trip, backpacking,
      luxury, sightseeing
    - pace: relaxed, balanced, packed
    """
    start = _parse_date(start_date)
    try:
        brief = TripBrief(
            start_city=start_city,
            days=days,
            budget=budget,
            group_type=GroupType(group_type),
            interests=[TravelStyle(i) for i in interests],
            pace=Pace(pace),
            destination_id=slugify(destination),
            travelers=travelers,
            travel_month=travel_month if travel_month else (start.month if start else None),
            start_date=start,
            end_date=_parse_date(end_date),
            popularity_pref=PopularityPref(popularity_pref),
            avoid=avoid or [],
            must_include=must_include or [],
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    # Resolve the destination AND fetch its stays/restaurants/weather CONCURRENTLY (≈2x faster
    # for an uncached place; identical results). Enrichment is best-effort. The two checklist
    # lines tick live (via _enrich_progress) as each half completes.
    progress.begin(_PART_LABELS["destination"])
    progress.begin(_PART_LABELS["enrichment"])
    resolved, enrichment = await trip_intelligence.resolve_and_enrich(
        destination, brief, on_progress=_enrich_progress
    )
    if resolved is None:
        return {
            "error": f"I couldn't find a place called {destination!r}. "
            "Could you check the spelling, or name a nearby well-known town?"
        }

    # The budget CONSTRAINS the plan: pick the stay tier it affords (fit-first; luxury is
    # never silently downgraded), and adapt to the travel month's season assessment (if any).
    progress.step("Choosing stays that fit your budget")
    choice = trip_planner.choose_stay(enrichment.stays, brief)
    season = (
        enrichment.seasonality.for_month(brief.travel_month)
        if enrichment.seasonality and brief.travel_month
        else None
    )
    progress.step("Selecting stops, days & budget")
    plan = trip_planner.plan_trip(
        brief,
        resolved,
        stay_per_person_per_night=choice.rate,
        season=season,
        stay_note=choice.note,
    )
    plan = plan.model_copy(
        update={
            "stays": enrichment.stays,
            "restaurants": enrichment.restaurants,
            "weather": enrichment.weather,
        }
    )
    out = _compact_plan(plan, resolved, enrichment.seasonality)
    out["recommended_stay_tier"] = choice.tier  # lead the stays section with this tier
    out["style_conflict"] = choice.style_conflict  # luxury asked but doesn't fit -> ASK
    progress.complete()
    return out


_COMPAT_ORDER = {"fits": 0, "stretch": 1, "premium": 2, "unknown": 3}


def budget_compatibility(est: float | None, budget: float) -> str:
    """How a route's rough cost relates to the traveler's budget (drives the ranking)."""
    if est is None or est <= 0:
        return "unknown"
    if est <= budget:
        return "fits"
    if est <= budget * 1.4:
        return "stretch"
    return "premium"


def rank_circuits_by_budget(circuits: list, budget: float) -> list[tuple]:
    """Best-budget-fit first (then cheapest) — popularity never outranks affordability."""
    labelled = [(c, budget_compatibility(c.est_per_person_budget, budget)) for c in circuits]
    return sorted(labelled, key=lambda cl: (_COMPAT_ORDER[cl[1]], cl[0].est_per_person_budget or 0))


async def discover_circuits(
    region: str,
    nights: int,
    group_type: str,
    interests: list[str],
    budget: float,
    travelers: int | None = None,
) -> dict:
    """Suggest multi-destination routes (circuits) for a REGION and trip length.

    Use this when the traveler gives a region + days but no single destination, or doesn't know
    where to go (e.g. "6 days in Kerala"). Returns 2–4 routes (stops in order + nights each +
    why), or an `error`. budget is PER-PERSON. After they pick, plan a chosen destination with
    `build_trip`.
    """
    try:
        brief = TripBrief(
            start_city="(unspecified)",
            days=max(nights, 1),
            budget=budget,
            group_type=GroupType(group_type),
            interests=[TravelStyle(i) for i in interests],
            pace=Pace.balanced,
            travelers=travelers,
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    circuits = await circuit_discovery.discover(region, nights, brief)
    if not circuits:
        return {
            "error": f"I couldn't find good multi-stop routes for {region!r}. "
            "Want to name a destination directly?"
        }
    ranked = rank_circuits_by_budget(circuits, brief.budget)
    return {
        "region": region,
        "nights": nights,
        # Already ranked best-budget-fit first — present them in THIS order.
        "circuits": [
            {
                "name": c.name,
                "route": [leg.destination for leg in c.legs],
                "nights_per_leg": [leg.nights for leg in c.legs],
                "total_nights": c.total_nights,
                "style": c.style,
                "est_per_person_budget": c.est_per_person_budget,
                "budget_compatibility": label,  # fits | stretch | premium | unknown
                "why": c.why,
            }
            for c, label in ranked
        ],
    }


async def build_circuit(
    name: str,
    destinations: list[str],
    nights: list[int],
    start_city: str,
    group_type: str,
    interests: list[str],
    budget: float,
    pace: str = "balanced",
    travelers: int | None = None,
    travel_month: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    popularity_pref: str = "balanced",
    avoid: list[str] | None = None,
    must_include: list[str] | None = None,
) -> dict:
    """Build a FULL multi-stop trip across several destinations (a chosen circuit) in one go.

    Call this after the traveler picks a route. `destinations` and `nights` are parallel lists
    in travel order (e.g. ["Kochi","Munnar","Thekkady"], [1,2,1]). Returns the stitched trip
    (a stay + day-by-day per leg, one combined per-person budget), or an `error`. budget is
    PER-PERSON. travel_month (1–12) adapts every leg to the season; start/end dates (YYYY-MM-DD)
    are kept only if the traveler gave them. (Takes a little longer — it plans each stop.)
    """
    if not destinations or len(destinations) != len(nights):
        return {"error": "Mismatched destinations and nights."}
    start = _parse_date(start_date)
    try:
        brief = TripBrief(
            start_city=start_city,
            days=max(sum(nights), 1),
            budget=budget,
            group_type=GroupType(group_type),
            interests=[TravelStyle(i) for i in interests],
            pace=Pace(pace),
            travelers=travelers,
            travel_month=travel_month if travel_month else (start.month if start else None),
            start_date=start,
            end_date=_parse_date(end_date),
            popularity_pref=PopularityPref(popularity_pref),
            avoid=avoid or [],
            must_include=must_include or [],
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    legs = list(zip(destinations, nights, strict=False))
    # One checklist line per leg — each ticks live as its (concurrent) planning completes.
    for dest in destinations:
        progress.begin(f"Planning {dest}")
    plan = await circuit_planner.plan_circuit(
        name or "Your circuit",
        legs,
        brief,
        on_leg_done=lambda dest: progress.finish(f"Planning {dest}"),
    )
    if plan is None:
        return {
            "error": "I couldn't build that route. Could you pick well-known towns, "
            "or name a single destination instead?"
        }
    progress.step("Stitching the legs into one trip")
    out = _compact_circuit(plan)
    progress.complete()
    return out
