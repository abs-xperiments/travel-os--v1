"""Offline test: trip_planner assembles a complete TripPlan from an injected Destination.

No credentials needed — the destination is taken from the catalog and passed in (the same way
destination_intelligence would inject a retrieved one).

    uv run pytest scripts/tests/test_trip_planner.py
"""

from __future__ import annotations

from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_planner
from agent.tripos.models import GroupType, Pace, TravelStyle, TripBrief


def _priya_brief() -> TripBrief:
    return TripBrief(
        start_city="Chennai",
        days=5,
        budget=50000,
        group_type=GroupType.family_with_seniors,
        interests=[TravelStyle.nature, TravelStyle.photography],
        pace=Pace.relaxed,
        destination_id="munnar",
    )


def test_plan_trip_assembles_a_complete_plan_from_injected_destination():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    plan = trip_planner.plan_trip(_priya_brief(), munnar)
    assert plan.destination_id == "munnar"
    assert len(plan.itinerary.day_plans) == 5
    assert plan.attractions  # picked some stops
    assert plan.budget.per_person_low <= plan.budget.per_person_total <= plan.budget.per_person_high
    assert plan.feasibility.realistic is True
    # per-person budget is primary; group total = per-person × travelers (seniors group ⇒ 4)
    assert plan.budget.travelers == 4
    assert plan.budget.group_total == plan.budget.per_person_total * 4
    # seniors promise holds end-to-end
    assert all(a.suitable_for_seniors for a in plan.attractions)


def test_plan_trip_plans_whatever_destination_it_is_given():
    # trip_planner has no concept of "supported" — any Destination is planned (here, a
    # different catalog entry, standing in for a web-retrieved one).
    goa = catalog.get_destination("goa")
    assert goa is not None
    plan = trip_planner.plan_trip(_priya_brief(), goa)
    assert plan.destination_id == "goa"
    assert plan.attractions
