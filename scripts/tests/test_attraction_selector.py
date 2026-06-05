"""Offline test: attraction_selector, in isolation. No credentials needed.

uv run pytest scripts/tests/test_attraction_selector.py
"""

from __future__ import annotations

from agent.tripos import attraction_selector
from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_feasibility_checker as feasibility
from agent.tripos.models import (
    Attraction,
    Destination,
    GroupType,
    Pace,
    PopularityPref,
    TravelStyle,
    TripBrief,
)


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


def _spot(name: str, popularity: int | None, worth: int = 7, desc: str = "") -> Attraction:
    return Attraction(
        id=name.lower().replace(" ", "-"),
        name=name,
        destination_id="testville",
        description=desc or f"{name} in Testville",
        duration_hours=2.0,
        indoor=False,
        base="centre",
        suitable_for_seniors=True,
        child_friendly=True,
        photography_value=5,
        adventure_level=2,
        worth_visiting=worth,
        best_time="morning",
        popularity=popularity,
    )


def _testville(attractions: list[Attraction]) -> Destination:
    return Destination(
        id="testville",
        name="Testville",
        state="",
        region="",
        description="",
        bases=["centre"],
        good_for=[TravelStyle.sightseeing],
        nearest_railhead="",
        nearest_airport="",
        attractions=attractions,
    )


def _pref_brief(pref: PopularityPref = PopularityPref.balanced, **kw) -> TripBrief:
    return TripBrief(
        start_city="X",
        days=1,  # short trip -> real competition between stops
        budget=20000,
        group_type=GroupType.couple,
        interests=[TravelStyle.sightseeing],
        popularity_pref=pref,
        **kw,
    )


def test_offbeat_prefers_hidden_gems_iconic_prefers_icons():
    spots = [
        _spot("World Icon", popularity=10),
        _spot("Local Secret", popularity=2),
        _spot("Neighbourhood Market", popularity=3),
        _spot("Famous Fort", popularity=9),
    ]
    dest = _testville(spots)
    offbeat = attraction_selector.select_attractions(dest, _pref_brief(PopularityPref.offbeat))
    iconic = attraction_selector.select_attractions(dest, _pref_brief(PopularityPref.iconic))
    assert {a.name for a in offbeat} & {"Local Secret", "Neighbourhood Market"}
    assert "World Icon" not in {a.name for a in offbeat}
    assert "World Icon" in {a.name for a in iconic}


def test_offbeat_never_picks_mediocre_over_great_quality_floor():
    # A poor hidden stop must not beat an excellent moderately-known one.
    dest = _testville(
        [
            _spot("Mediocre Alley", popularity=1, worth=2),
            _spot("Great Garden", popularity=6, worth=10),
        ]
    )
    chosen = attraction_selector.select_attractions(dest, _pref_brief(PopularityPref.offbeat))
    assert chosen and chosen[0].name == "Great Garden"


def test_unknown_popularity_stays_neutral():
    # Curated data has popularity=None — preference must not invent a bias.
    dest = _testville([_spot("Mystery Spot", popularity=None, worth=9)])
    chosen = attraction_selector.select_attractions(dest, _pref_brief(PopularityPref.offbeat))
    assert [a.name for a in chosen] == ["Mystery Spot"]


def test_avoid_terms_hard_filter_by_name_and_description():
    dest = _testville(
        [
            _spot("Golden Temple", popularity=8),
            _spot("City Walk", popularity=4, desc="A stroll past the old temple quarter"),
            _spot("River Park", popularity=4),
        ]
    )
    chosen = attraction_selector.select_attractions(dest, _pref_brief(avoid=["temple"]))
    assert {a.name for a in chosen} == {"River Park"}


def test_avoid_handles_plural_terms():
    # Live-caught bug: the traveler says "no FORTS" (plural), attractions are named
    # "... Fort" (singular) — the filter must still catch them.
    dest = _testville([_spot("Amber Fort", popularity=9), _spot("River Park", popularity=4)])
    chosen = attraction_selector.select_attractions(dest, _pref_brief(avoid=["forts"]))
    assert {a.name for a in chosen} == {"River Park"}


def test_must_include_beats_avoid_and_popularity_bias():
    # "hidden gems, but include the World Icon" -> the icon is in, despite both filters.
    dest = _testville(
        [
            _spot("World Icon", popularity=10, desc="famous temple complex"),
            _spot("Local Secret", popularity=2),
        ]
    )
    brief = _pref_brief(PopularityPref.offbeat, avoid=["temple"], must_include=["World Icon"])
    chosen = attraction_selector.select_attractions(dest, brief)
    assert "World Icon" in {a.name for a in chosen}


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
