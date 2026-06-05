"""Offline test: attraction_selector, in isolation. No credentials needed.

uv run pytest scripts/tests/test_attraction_selector.py
"""

from __future__ import annotations

from agent.tripos import attraction_selector
from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_feasibility_checker as feasibility
from agent.tripos.models import GroupType, Pace, TravelStyle, TripBrief


def _brief(days: int, group: GroupType = GroupType.family) -> TripBrief:
    return TripBrief(
        start_city="Chennai",
        days=days,
        budget=50000,
        group_type=group,
        interests=[TravelStyle.nature, TravelStyle.photography],
        pace=Pace.balanced,
        destination_id="munnar",
    )


def test_selection_is_a_feasible_subset_in_base_order():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    chosen = attraction_selector.select_attractions(munnar, _brief(days=5))
    catalog_ids = {a.id for a in munnar.attractions}
    assert chosen  # not empty
    assert all(a.id in catalog_ids for a in chosen)  # only real attractions
    assert feasibility.check_feasibility(chosen, 5).realistic  # fits the trip
    assert [a.base for a in chosen] == sorted(a.base for a in chosen)  # grouped by base


def test_more_days_allow_at_least_as_many_stops():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    short = attraction_selector.select_attractions(munnar, _brief(days=1))
    long = attraction_selector.select_attractions(munnar, _brief(days=5))
    assert len(long) >= len(short)


def test_prefer_indoor_biases_selection_toward_indoor_stops():
    # The season adaptation: in a wet/extreme-heat month, indoor stops should out-rank
    # comparable outdoor ones — a soft bias, so the result must still be feasible.
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    brief = _brief(days=2)  # a short trip forces real choices between stops
    normal = attraction_selector.select_attractions(munnar, brief)
    sheltered = attraction_selector.select_attractions(munnar, brief, prefer_indoor=True)
    indoor = lambda stops: sum(1 for a in stops if a.indoor)  # noqa: E731
    assert indoor(sheltered) >= indoor(normal)
    assert feasibility.check_feasibility(sheltered, 2).realistic


def test_seniors_selection_excludes_unsuitable_stops_and_stays_feasible():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    chosen = attraction_selector.select_attractions(
        munnar, _brief(days=4, group=GroupType.family_with_seniors)
    )
    assert feasibility.check_feasibility(chosen, 4).realistic
    # the core promise: never schedule a stop we've marked as not senior-suitable
    assert all(a.suitable_for_seniors for a in chosen)
    assert "munnar-eravikulam-np" not in {a.id for a in chosen}
