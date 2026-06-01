"""Offline test: the trip_feasibility_checker, in isolation. No credentials needed.

uv run pytest scripts/tests/test_trip_feasibility_checker.py
"""

from __future__ import annotations

from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_feasibility_checker as feasibility


def test_no_attractions_is_trivially_feasible():
    result = feasibility.check_feasibility([], days=3)
    assert result.realistic is True
    assert result.required_hours == 0.0


def test_a_couple_of_stops_over_three_days_fits():
    munnar = catalog.get_attractions("munnar")[:2]
    result = feasibility.check_feasibility(munnar, days=3)
    assert result.realistic is True
    assert result.required_hours <= result.available_hours


def test_everything_in_one_day_is_rejected_with_suggestions():
    all_munnar = catalog.get_attractions("munnar")  # 6 stops
    result = feasibility.check_feasibility(all_munnar, days=1)
    assert result.realistic is False
    assert result.required_hours > result.available_hours
    assert result.suggestions  # offers a way to fix it


def test_usable_hours_treats_travel_days_as_partial():
    assert feasibility.usable_hours(1) < feasibility.usable_hours(2)
    assert feasibility.usable_hours(2) == feasibility.HOURS_PER_FULL_DAY
