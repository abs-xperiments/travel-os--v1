"""Offline test: trip_planner assembles a complete TripPlan from an injected Destination.

No credentials needed — the destination is taken from the catalog and passed in (the same way
destination_intelligence would inject a retrieved one).

    uv run pytest scripts/tests/test_trip_planner.py
"""

from __future__ import annotations

from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_planner
from agent.tripos.models import (
    Accommodation,
    GroupType,
    MonthAssessment,
    MonthRating,
    Pace,
    TravelStyle,
    TripBrief,
)


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


def test_per_person_nightly_prefers_mid_tier_and_halves_room_price():
    stays = [
        Accommodation(
            name="A",
            area="x",
            kind="hotel",
            tier="mid",
            price_per_night_low=3000,
            price_per_night_high=5000,
            why="w",
        ),
        Accommodation(
            name="B",
            area="x",
            kind="resort",
            tier="premium",
            price_per_night_low=9000,
            price_per_night_high=11000,
            why="w",
        ),
    ]
    assert trip_planner.per_person_nightly(stays) == 2000  # mid avg room 4000, /2 occupancy
    assert trip_planner.per_person_nightly([]) is None


def test_season_assessment_adapts_the_plan_and_stamps_a_visible_note():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    brief = _priya_brief().model_copy(update={"travel_month": 7})
    monsoon = MonthAssessment(
        month=7, rating=MonthRating.challenging, note="Peak monsoon.", lean_indoor=True
    )
    plan = trip_planner.plan_trip(brief, munnar, season=monsoon)
    # The adaptation is visible on the itinerary itself (chat, print view, PDF alike).
    day1 = plan.itinerary.day_plans[0].notes
    assert any("July" in n and "Peak monsoon." in n for n in day1)
    assert any("indoor" in n for n in day1)
    # No month / no season -> no note is invented.
    bare = trip_planner.plan_trip(_priya_brief(), munnar)
    assert not any("Planned for" in n for n in bare.itinerary.day_plans[0].notes)


def test_retrieved_stay_rate_refines_the_accommodation_budget():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    base = trip_planner.plan_trip(_priya_brief(), munnar)
    cheaper = trip_planner.plan_trip(_priya_brief(), munnar, stay_per_person_per_night=500)
    assert cheaper.budget.per_person_total < base.budget.per_person_total
