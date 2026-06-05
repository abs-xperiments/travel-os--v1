"""trip_planner — run all the deterministic modules into one complete TripPlan.

This is the "general contractor": given a finished `TripBrief` AND a resolved `Destination`,
it picks attractions, builds the day-by-day, estimates the budget, and checks feasibility —
then returns one `TripPlan`. No AI and no network: the destination is RESOLVED upstream by
`destination_intelligence` (catalog or web retrieval) and INJECTED here, so this module has no
concept of "supported destinations" — it plans whatever Destination it's handed.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from agent.tripos import (
    attraction_selector,
    budget_estimator,
    itinerary_builder,
)
from agent.tripos import (
    trip_feasibility_checker as feasibility,
)
from agent.tripos.models import (
    MONTH_NAMES,
    Accommodation,
    Attraction,
    BudgetBreakdown,
    BudgetEstimate,
    Destination,
    GroupType,
    MonthAssessment,
    TripBrief,
    TripPlan,
)

# PLACEHOLDER *per-person* cost baselines (₹). Rough so the budget feels real today; the
# transport / accommodation / food composer modules will replace them. Per-person throughout
# (accommodation assumes ~2 travelers share a room, hence the lower nightly figure).
_TRANSPORT_PER_PERSON = 4500.0  # round trip from the start city (rough)
_LOCAL_TRANSPORT_PER_PERSON_PER_DAY = 500.0
_STAY_PER_PERSON_PER_NIGHT = 1800.0
_FOOD_PER_PERSON_PER_DAY = 1000.0
_ACTIVITY_PER_PERSON_PER_STOP = 400.0
_MISC_PER_PERSON = 1500.0
_INTER_CITY_PER_PERSON_PER_HOP = 1500.0  # travel between circuit legs (per person, rough)

# Default traveler count inferred from the group when the user didn't give an exact number.
_GROUP_DEFAULT_TRAVELERS: dict[GroupType, int] = {
    GroupType.solo: 1,
    GroupType.couple: 2,
    GroupType.friends: 3,
    GroupType.family: 4,
    GroupType.family_with_children: 4,
    GroupType.family_with_seniors: 4,
}


def traveler_count(brief: TripBrief) -> int:
    """How many travelers — the number the user gave, else inferred from the group type."""
    if brief.travelers and brief.travelers > 0:
        return brief.travelers
    return _GROUP_DEFAULT_TRAVELERS.get(brief.group_type, 2)


def per_person_nightly(stays: list[Accommodation]) -> float | None:
    """A per-person nightly rate from retrieved mid-tier stays (assume ~2 share a room).

    Returns None if there are no usable stays, so the budget falls back to the baseline.
    """
    mid = [s for s in stays if s.tier == "mid"] or stays
    if not mid:
        return None
    avg_room = sum((s.price_per_night_low + s.price_per_night_high) / 2 for s in mid) / len(mid)
    return round(avg_room / 2) if avg_room > 0 else None


def circuit_budget(
    brief: TripBrief,
    *,
    total_days: int,
    total_stops: int,
    accommodation_per_person: float,
    hops: int,
) -> BudgetEstimate:
    """Combined PER-PERSON budget for a multi-leg circuit (one transport base + inter-city hops)."""
    breakdown = BudgetBreakdown(
        transport=(
            _TRANSPORT_PER_PERSON
            + _INTER_CITY_PER_PERSON_PER_HOP * max(hops, 0)
            + _LOCAL_TRANSPORT_PER_PERSON_PER_DAY * total_days
        ),
        accommodation=accommodation_per_person,
        food=_FOOD_PER_PERSON_PER_DAY * total_days,
        activities=_ACTIVITY_PER_PERSON_PER_STOP * total_stops,
        misc=_MISC_PER_PERSON,
    )
    return budget_estimator.estimate_budget(
        breakdown, budget=brief.budget, travelers=traveler_count(brief)
    )


def _rough_budget(
    brief: TripBrief, stops: list[Attraction], stay_per_person_per_night: float | None = None
) -> BudgetEstimate:
    nights = max(brief.days - 1, 1)
    # Use a retrieved per-person nightly rate when available; else the placeholder baseline.
    stay = stay_per_person_per_night if stay_per_person_per_night else _STAY_PER_PERSON_PER_NIGHT
    breakdown = BudgetBreakdown(  # all PER PERSON
        transport=_TRANSPORT_PER_PERSON + _LOCAL_TRANSPORT_PER_PERSON_PER_DAY * brief.days,
        accommodation=stay * nights,
        food=_FOOD_PER_PERSON_PER_DAY * brief.days,
        activities=_ACTIVITY_PER_PERSON_PER_STOP * len(stops),
        misc=_MISC_PER_PERSON,
    )
    return budget_estimator.estimate_budget(
        breakdown, budget=brief.budget, travelers=traveler_count(brief)
    )


def plan_trip(
    brief: TripBrief,
    destination: Destination,
    stay_per_person_per_night: float | None = None,
    season: MonthAssessment | None = None,
) -> TripPlan:
    """Build the full plan for a completed brief and an already-resolved destination.

    The destination is resolved upstream (catalog or web retrieval) and injected — there is no
    "unknown destination" case here; this module plans whatever it's given. If a retrieved
    per-person nightly stay rate is supplied, it refines the accommodation budget. If a season
    assessment for the travel month is supplied, the plan adapts to it (indoor-leaning stop
    selection in wet/extreme-heat months, and a visible season note on day 1).
    """
    prefer_indoor = bool(season and season.lean_indoor)
    stops = attraction_selector.select_attractions(destination, brief, prefer_indoor=prefer_indoor)
    itinerary = itinerary_builder.build_itinerary(destination, stops, brief.days, brief.pace)
    budget = _rough_budget(brief, stops, stay_per_person_per_night)
    feas = feasibility.check_feasibility(stops, brief.days)

    # Make the adaptation visible on the itinerary itself (chat, print view, PDF alike).
    if season and brief.travel_month and itinerary.day_plans:
        note = f"Planned for {MONTH_NAMES[brief.travel_month]} travel — {season.note}"
        if prefer_indoor:
            note += " Favouring indoor/sheltered stops; keep outdoor time to mornings/evenings."
        itinerary.day_plans[0].notes.insert(0, note)

    return TripPlan(
        brief=brief,
        destination_id=destination.id,
        attractions=stops,
        itinerary=itinerary,
        budget=budget,
        feasibility=feas,
    )
