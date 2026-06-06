"""Offline tests: the FIND_STAYS / FIND_RESTAURANTS ranking + validation paths. No network.

The ranking helpers are pure functions over hand-built models; the tool validation paths
return an error BEFORE any enrichment call (same pattern as test_tripos_planner_tools.py).
Happy paths (live retrieval) are covered by the integration tests.

    uv run pytest scripts/tests/test_recommendations.py
"""

from __future__ import annotations

import pytest

from agent.agents.tripos_planner import find_restaurants, find_stays, suggest_destinations
from agent.agents.tripos_planner.recommend import _rank_restaurants, _rank_stays
from agent.tripos.models import Accommodation, FoodPref, Restaurant


def _stay(
    name: str,
    kind: str = "hotel",
    tier: str = "mid",
    low: float = 3000,
    high: float = 5000,
    rating: float | None = None,
    area: str = "Town centre",
) -> Accommodation:
    return Accommodation(
        name=name,
        area=area,
        kind=kind,
        tier=tier,
        price_per_night_low=low,
        price_per_night_high=high,
        rating=rating,
        why="w",
    )


def _spot(
    name: str,
    cuisine: str = "Indian",
    price_band: str = "$$",
    good_for: str = "local/authentic",
    area: str = "Town centre",
    why: str = "w",
) -> Restaurant:
    return Restaurant(
        name=name, area=area, cuisine=cuisine, price_band=price_band, good_for=good_for, why=why
    )


# ---------------------------------------------------------------- _rank_stays


def test_rank_stays_kind_filter_handles_plurals():
    # "homestays" (plural, capitalised) must match kind="homestay" — the plural lesson from
    # the avoid-filter bug ("no forts" missing "Amber Fort").
    stays = [_stay("Hilltop Hotel", kind="hotel"), _stay("Green Valley", kind="homestay")]
    ranked, note = _rank_stays(stays, kind="Homestays")
    assert ranked[0].name == "Green Valley"
    assert len(ranked) == 1  # kind filter narrows when matches exist
    assert note is None


def test_rank_stays_budget_fit_leads_and_rating_breaks_ties():
    stays = [
        _stay("Pricey Palace", low=12000, high=18000, rating=4.9),
        _stay("Fits A", low=3000, high=5000, rating=4.2),
        _stay("Fits B", low=2000, high=4000, rating=4.7),
    ]
    ranked, note = _rank_stays(stays, budget_per_night=6000)
    # Both fitting stays lead (best-rated first); the over-budget one trails — popularity or
    # rating never outranks affordability.
    assert [s.name for s in ranked] == ["Fits B", "Fits A", "Pricey Palace"]
    assert note is None


def test_rank_stays_nothing_fits_is_honest_not_empty():
    stays = [
        _stay("Mid", low=8000, high=11000),
        _stay("Cheapest", low=6000, high=7000),
    ]
    ranked, note = _rank_stays(stays, budget_per_night=5000)
    assert ranked, "never return empty when real options exist"
    assert ranked[0].name == "Cheapest"  # closest-priced first
    assert note is not None and "5,000" in note  # honest no-match note, never silence


def test_rank_stays_no_kind_match_keeps_pool_with_note():
    stays = [_stay("Hotel One", kind="hotel"), _stay("Hotel Two", kind="hotel")]
    ranked, note = _rank_stays(stays, kind="treehouse")
    assert len(ranked) == 2  # nothing silently dropped
    assert note is not None and "treehouse" in note


# ---------------------------------------------------------- _rank_restaurants


def test_rank_restaurants_cuisine_filter_with_honest_fallback():
    spots = [_spot("Fish Hut", cuisine="Seafood"), _spot("Dal House", cuisine="North Indian")]
    ranked, note = _rank_restaurants(spots, cuisine="seafood")
    assert [r.name for r in ranked] == ["Fish Hut"]
    assert note is None

    ranked, note = _rank_restaurants(spots, cuisine="sushi")
    assert len(ranked) == 2  # no match -> full pool kept, honestly flagged
    assert note is not None and "sushi" in note


def test_rank_restaurants_soft_preferences_reorder_never_drop():
    spots = [
        _spot("Steak Place", good_for="non-veg, groups", price_band="$$$"),
        _spot("Veg Sagar", good_for="vegetarian-friendly, family", price_band="$"),
    ]
    ranked, _ = _rank_restaurants(spots, food_pref=FoodPref.vegetarian)
    assert ranked[0].name == "Veg Sagar"
    assert len(ranked) == 2  # soft preference: reorder, never drop

    ranked, _ = _rank_restaurants(spots, price_band="$$$")
    assert ranked[0].name == "Steak Place"
    assert len(ranked) == 2


def test_rank_restaurants_occasion_is_a_soft_signal():
    spots = [
        _spot("Canteen", good_for="quick lunch"),
        _spot("Rooftop", good_for="romantic dinner, couples"),
    ]
    ranked, _ = _rank_restaurants(spots, occasion="romantic dinner")
    assert ranked[0].name == "Rooftop"


# ------------------------------------------- tool validation paths (no network)


async def test_find_stays_rejects_bad_inputs_without_network():
    assert "error" in await find_stays("Didupe", group_type="aliens")
    assert "error" in await find_stays("Didupe", budget_per_night=-100)
    assert "error" in await find_stays("Didupe", total_budget=0)
    assert "error" in await find_stays("Didupe", nights=0)


async def test_find_restaurants_rejects_bad_inputs_without_network():
    assert "error" in await find_restaurants("Kochi", food_pref="carnivore")
    assert "error" in await find_restaurants("Kochi", price_band="$$$$")


async def test_suggest_destinations_rejects_bad_inputs_without_network():
    assert "error" in await suggest_destinations(month=13)
    assert "error" in await suggest_destinations(days=0)
    assert "error" in await suggest_destinations(budget=-5)
    assert "error" in await suggest_destinations(interests=["extreme-ironing"])


def test_destination_ideas_rank_by_budget_fit():
    # suggest_destinations reuses rank_circuits_by_budget (duck-typed on
    # est_per_person_budget) — best budget fit must lead, fame never outranks affordability.
    from agent.agents.tripos_planner import rank_circuits_by_budget
    from agent.tripos.models import DestinationIdea

    ideas = [
        DestinationIdea(name="Pricey Isles", why="w", est_per_person_budget=90000),
        DestinationIdea(name="Fits Beach", why="w", est_per_person_budget=35000),
        DestinationIdea(name="Stretch Hills", why="w", est_per_person_budget=50000),
    ]
    ranked = rank_circuits_by_budget(ideas, budget=40000)
    assert [(i.name, label) for i, label in ranked] == [
        ("Fits Beach", "fits"),
        ("Stretch Hills", "stretch"),
        ("Pricey Isles", "premium"),
    ]


# ------------------------------------------------- live happy paths (cost ~1¢)


@pytest.mark.integration
async def test_find_stays_live_and_shares_the_build_cache_key():
    """find_stays works end-to-end AND leaves the canonical enrichment cached under the SAME
    key a later build_trip uses — the 'stays question today makes tomorrow's plan faster'
    claim, proven."""
    from agent.services import db
    from agent.tripos import intelligence_cache, trip_intelligence

    await trip_intelligence.init_db()
    try:
        out = await find_stays("Munnar", budget_per_night=4000, group_type="couple")
        assert "error" not in out, out
        assert out["recommended"]["name"]
        low, high = out["recommended"]["price_per_night"]
        assert 0 <= low <= high
        assert isinstance(out["alternatives"], list)
        # The load-bearing cache alignment: the canonical per-destination key is now warm.
        assert await intelligence_cache.get("munnar:v2") is not None
    finally:
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key = $1", "munnar:v2")
        await db.execute(
            "DELETE FROM tripos_intelligence_cache WHERE key LIKE $1", "munnar:stays:%"
        )


@pytest.mark.integration
async def test_suggest_destinations_live_december_beaches():
    from agent.services import db
    from agent.tripos import trip_intelligence

    await trip_intelligence.init_db()
    try:
        out = await suggest_destinations(days=5, month=12, budget=40000, interests=["relaxation"])
        assert "error" not in out, out
        assert out["recommended"]["name"]
        assert out["recommended"]["why"]
        assert 2 <= 1 + len(out["alternatives"]) <= 5
    finally:
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key LIKE $1", "suggest:%")


@pytest.mark.integration
async def test_find_restaurants_live_kochi_seafood():
    from agent.services import db
    from agent.tripos import trip_intelligence

    await trip_intelligence.init_db()
    try:
        out = await find_restaurants("Kochi", cuisine="seafood")
        assert "error" not in out, out
        assert out["recommended"]["name"]
        assert out["recommended"]["cuisine"]
    finally:
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key = $1", "kochi:v2")
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key LIKE $1", "kochi:food:%")
