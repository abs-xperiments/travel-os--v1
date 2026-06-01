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
    TripBrief,
    TripPlan,
)

# PLACEHOLDER cost baselines (₹). These are rough so the budget feels real today; they will
# be replaced by the transport / accommodation / food composer modules in a later step.
# Kept here, clearly named, so they're trivial to find and swap out.
_TRANSPORT_TO_DESTINATION = 4500.0  # round trip from the start city (rough)
_LOCAL_TRANSPORT_PER_DAY = 1200.0
_STAY_PER_NIGHT = 3000.0
_FOOD_PER_DAY = 1200.0
_ACTIVITY_PER_STOP = 400.0
_MISC = 1500.0


def _rough_budget(brief: TripBrief, stops: list[Attraction]) -> BudgetEstimate:
    nights = max(brief.days - 1, 1)
    breakdown = BudgetBreakdown(
        transport=_TRANSPORT_TO_DESTINATION + _LOCAL_TRANSPORT_PER_DAY * brief.days,
        accommodation=_STAY_PER_NIGHT * nights,
        food=_FOOD_PER_DAY * brief.days,
        activities=_ACTIVITY_PER_STOP * len(stops),
        misc=_MISC,
    )
    return budget_estimator.estimate_budget(breakdown, budget=brief.budget)


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
