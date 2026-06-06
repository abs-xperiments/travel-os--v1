"""Offline regression test: enrich() must carry EVERY slice of the retrieved enrichment.

The bug this pins down: enrich() rebuilds TripEnrichment from the per-role providers, and
when the seasonality slice was added it was silently dropped there — no error, no log, the
agent just saw "no seasonal data" and every advisory turned into a no-op. We fake the one
web fetch (gather) and assert nothing is lost between retrieval and the planner.

    uv run pytest scripts/tests/test_trip_intelligence_offline.py
"""

from __future__ import annotations

import pytest

from agent.tripos import trip_intelligence
from agent.tripos.models import (
    Accommodation,
    Destination,
    GroupType,
    MonthAssessment,
    MonthRating,
    Restaurant,
    SeasonalityProfile,
    TravelStyle,
    TripBrief,
    TripEnrichment,
    WeatherInsight,
)
from agent.tripos.providers import web_intelligence

_FULL = TripEnrichment(
    stays=[
        Accommodation(
            name="Rove",
            area="Downtown",
            kind="hotel",
            tier="mid",
            price_per_night_low=9000,
            price_per_night_high=12000,
            why="central",
        )
    ],
    restaurants=[
        Restaurant(
            name="Al Fanar",
            area="Festival City",
            cuisine="Emirati",
            price_band="$$",
            good_for="couples",
            why="authentic",
        )
    ],
    weather=WeatherInsight(summary="Hot desert climate.", season_label="summer"),
    seasonality=SeasonalityProfile(
        months=[
            MonthAssessment(
                month=7,
                rating=MonthRating.not_recommended,
                note="extreme heat",
                lean_indoor=True,
            )
        ],
        best_months=[11, 12, 1],
        summary="Best Nov-Mar.",
    ),
)


def _dest() -> Destination:
    return Destination(
        id="faketown",
        name="Faketown",
        state="",
        region="",
        description="",
        bases=[],
        good_for=[],
        nearest_railhead="",
        nearest_airport="",
    )


def _brief() -> TripBrief:
    return TripBrief(
        start_city="Mumbai",
        days=5,
        budget=100000,
        group_type=GroupType.couple,
        interests=[TravelStyle.sightseeing],
    )


def _patch_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake BOTH web exits: the full gather AND the seasonality fast path (added 2026-06-07).

    Patching only `gather` silently let `season_profile` reach the live network through
    `gather_seasonality` — the same seam-drift this file exists to pin down. When a new
    retrieval exit is added, it must be faked here too.
    """

    async def fake_gather(destination: Destination, brief: TripBrief) -> TripEnrichment:
        return _FULL

    async def fake_gather_seasonality(
        destination: Destination, brief: TripBrief
    ) -> SeasonalityProfile | None:
        return _FULL.seasonality

    monkeypatch.setattr(web_intelligence, "gather", fake_gather)
    monkeypatch.setattr(web_intelligence, "gather_seasonality", fake_gather_seasonality)


async def test_enrich_carries_every_slice_through(monkeypatch: pytest.MonkeyPatch):
    _patch_fetches(monkeypatch)
    enr = await trip_intelligence.enrich(_dest(), _brief())
    assert enr.stays and enr.stays[0].name == "Rove"
    assert enr.restaurants and enr.restaurants[0].name == "Al Fanar"
    assert enr.weather is not None
    # THE regression: the seasonality slice must survive enrich(), verdict intact.
    assert enr.seasonality is not None
    july = enr.seasonality.for_month(7)
    assert july is not None and july.rating is MonthRating.not_recommended
    assert july.lean_indoor is True


async def test_season_profile_exposes_the_profile_by_name(monkeypatch: pytest.MonkeyPatch):
    _patch_fetches(monkeypatch)
    profile = await trip_intelligence.season_profile("Faketown", _brief())
    assert profile is not None and profile.best_months == [11, 12, 1]
