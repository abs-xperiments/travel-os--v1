"""Offline test: itinerary_builder, in isolation. No credentials needed.

uv run pytest scripts/tests/test_itinerary_builder.py
"""

from __future__ import annotations

from agent.tripos import attraction_selector, itinerary_builder
from agent.tripos import destination_catalog as catalog
from agent.tripos.models import GroupType, Pace, TravelStyle, TripBrief


def _munnar_and_stops(days: int):
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    brief = TripBrief(
        start_city="Chennai",
        days=days,
        budget=50000,
        group_type=GroupType.family,
        interests=[TravelStyle.nature],
        pace=Pace.balanced,
        destination_id="munnar",
    )
    return munnar, attraction_selector.select_attractions(munnar, brief)


def test_five_day_plan_has_five_days_and_places_every_stop_once():
    munnar, stops = _munnar_and_stops(5)
    itin = itinerary_builder.build_itinerary(munnar, stops, days=5)
    assert len(itin.day_plans) == 5
    assert [d.day for d in itin.day_plans] == [1, 2, 3, 4, 5]
    placed = [a.id for d in itin.day_plans for a in d.attractions]
    assert sorted(placed) == sorted(a.id for a in stops)  # every stop once, none lost


def test_arrival_and_departure_days_are_labelled():
    munnar, stops = _munnar_and_stops(5)
    itin = itinerary_builder.build_itinerary(munnar, stops, days=5)
    assert itin.day_plans[0].title == "Arrival in Munnar"
    assert itin.day_plans[-1].title == "Departure from Munnar"


def test_single_day_trip_has_one_day():
    munnar, stops = _munnar_and_stops(1)
    itin = itinerary_builder.build_itinerary(munnar, stops, days=1)
    assert len(itin.day_plans) == 1
