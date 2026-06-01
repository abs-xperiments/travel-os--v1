"""Offline test: trip_planner assembles a complete TripPlan. No credentials needed.

uv run pytest scripts/tests/test_trip_planner.py
"""

from __future__ import annotations

import pytest

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


def test_plan_trip_assembles_a_complete_plan():
    plan = trip_planner.plan_trip(_priya_brief())
    assert plan.destination_id == "munnar"
    assert len(plan.itinerary.day_plans) == 5
    assert plan.attractions  # picked some stops
    assert plan.budget.low <= plan.budget.total <= plan.budget.high
    assert plan.feasibility.realistic is True
    # seniors promise holds end-to-end
    assert all(a.suitable_for_seniors for a in plan.attractions)


def test_unknown_destination_raises_clearly():
    brief = _priya_brief()
    brief.destination_id = "goa"
    with pytest.raises(ValueError, match="covers"):
        trip_planner.plan_trip(brief)


def test_missing_destination_raises():
    brief = _priya_brief()
    brief.destination_id = None
    with pytest.raises(ValueError, match="required"):
        trip_planner.plan_trip(brief)
