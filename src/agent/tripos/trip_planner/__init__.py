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
    Attraction,
    BudgetBreakdown,
    BudgetEstimate,
    Destination,
    GroupType,
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


def _rough_budget(brief: TripBrief, stops: list[Attraction]) -> BudgetEstimate:
    nights = max(brief.days - 1, 1)
    breakdown = BudgetBreakdown(  # all PER PERSON
        transport=_TRANSPORT_PER_PERSON + _LOCAL_TRANSPORT_PER_PERSON_PER_DAY * brief.days,
        accommodation=_STAY_PER_PERSON_PER_NIGHT * nights,
        food=_FOOD_PER_PERSON_PER_DAY * brief.days,
        activities=_ACTIVITY_PER_PERSON_PER_STOP * len(stops),
        misc=_MISC_PER_PERSON,
    )
    return budget_estimator.estimate_budget(
        breakdown, budget=brief.budget, travelers=traveler_count(brief)
    )


def plan_trip(brief: TripBrief, destination: Destination) -> TripPlan:
    """Build the full plan for a completed brief and an already-resolved destination.

    The destination is resolved upstream (catalog or web retrieval) and injected — there is no
    "unknown destination" case here; this module plans whatever it's given.
    """
    stops = attraction_selector.select_attractions(destination, brief)
    itinerary = itinerary_builder.build_itinerary(destination, stops, brief.days, brief.pace)
    budget = _rough_budget(brief, stops)
    feas = feasibility.check_feasibility(stops, brief.days)

    return TripPlan(
        brief=brief,
        destination_id=destination.id,
        attractions=stops,
        itinerary=itinerary,
        budget=budget,
        feasibility=feas,
    )
