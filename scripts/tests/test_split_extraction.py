"""Offline tests: the split (parallel, per-slice) enrichment extraction. No network.

Two contracts: (1) the field-drop lesson — every slice must survive into the cached
TripEnrichment (learnings.md 2026-06-06: a rebuilt struct silently dropped seasonality);
(2) the seasonality-fast path — a season check gets its answer the moment THAT slice is
extracted, while slower slices keep running in the background and still fill the cache.

    uv run pytest scripts/tests/test_split_extraction.py
"""

from __future__ import annotations

import asyncio

from agent.tripos.models import (
    Accommodation,
    Destination,
    FoodPref,
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
from agent.tripos.providers import web_intelligence as wi


def _brief() -> TripBrief:
    return TripBrief(
        start_city="Chennai",
        days=3,
        budget=30000,
        group_type=GroupType.couple,
        interests=[TravelStyle.nature],
        food_pref=FoodPref.no_preference,
    )


def _dest(name: str = "Didupe") -> Destination:
    return Destination(
        id=name.lower(),
        name=name,
        state="",
        region="",
        description="",
        bases=[],
        good_for=[],
        nearest_railhead="",
        nearest_airport="",
    )


_STAY = Accommodation(
    name="S",
    area="A",
    kind="homestay",
    tier="mid",
    price_per_night_low=1,
    price_per_night_high=2,
    why="w",
)
_REST = Restaurant(name="R", area="A", cuisine="C", price_band="$$", good_for="g", why="w")
_WX = WeatherInsight(summary="s", season_label="winter")
_SEASON = SeasonalityProfile(
    months=[MonthAssessment(month=1, rating=MonthRating.good, note="n")],
    best_months=[1],
    summary="s",
)


class _FakeResearch:
    text = "notes"


def _patch_slices(monkeypatch, *, season_delay: float = 0.0, stays_delay: float = 0.0):
    """Stub research + the four slice extractors with controllable delays."""
    cache: dict[str, str] = {}

    async def fake_research(query: str, **kw):
        return _FakeResearch()

    async def fake_stays(notes: str, traveler: str):
        await asyncio.sleep(stays_delay)
        return [_STAY]

    async def fake_restaurants(notes: str, traveler: str):
        return [_REST]

    async def fake_weather(notes: str):
        return _WX

    async def fake_seasonality(notes: str):
        await asyncio.sleep(season_delay)
        return _SEASON

    async def cache_get(key: str, max_age_days: int = 30):
        return cache.get(key)

    async def cache_put(key: str, data: str):
        cache[key] = data

    monkeypatch.setattr(wi, "research", fake_research)
    monkeypatch.setattr(wi, "_extract_stays", fake_stays)
    monkeypatch.setattr(wi, "_extract_restaurants", fake_restaurants)
    monkeypatch.setattr(wi, "_extract_weather", fake_weather)
    monkeypatch.setattr(wi, "_extract_seasonality", fake_seasonality)
    monkeypatch.setattr(wi.intelligence_cache, "get", cache_get)
    monkeypatch.setattr(wi.intelligence_cache, "put", cache_put)
    return cache


async def test_every_slice_survives_into_the_cached_enrichment(monkeypatch):
    # The field-drop lesson: the parallel rebuild must carry ALL four slices, and the cached
    # row must round-trip identically.
    cache = _patch_slices(monkeypatch)
    out = await wi.gather(_dest(), _brief())

    assert out.stays == [_STAY]
    assert out.restaurants == [_REST]
    assert out.weather == _WX
    assert out.seasonality == _SEASON

    cached = TripEnrichment.model_validate_json(cache["didupe:v2"])
    assert cached == out  # cache round-trips with every slice intact


async def test_seasonality_resolves_before_slow_slices_finish(monkeypatch):
    # The fast path: a season check must NOT wait for stays/restaurants/weather.
    _patch_slices(monkeypatch, stays_delay=0.2)

    t0 = asyncio.get_event_loop().time()
    season = await wi.gather_seasonality(_dest(), _brief())
    elapsed = asyncio.get_event_loop().time() - t0

    assert season == _SEASON
    assert elapsed < 0.15, "season check must not pay for the slow stays slice"

    # ...and the background fetch still completes and caches the FULL enrichment.
    task = wi._in_flight.get("didupe:v2")
    assert task is not None, "full fetch keeps running in the background"
    full = await task
    assert full.stays == [_STAY]


async def test_gather_seasonality_uses_cache_when_warm(monkeypatch):
    cache = _patch_slices(monkeypatch)
    await wi.gather(_dest(), _brief())  # warm the cache
    wi._in_flight.clear()

    calls = {"n": 0}

    async def counting_research(query: str, **kw):
        calls["n"] += 1
        return _FakeResearch()

    monkeypatch.setattr(wi, "research", counting_research)
    season = await wi.gather_seasonality(_dest(), _brief())
    assert season == _SEASON
    assert calls["n"] == 0  # pure cache hit, no new fetch
    assert cache  # (still cached)


async def test_concurrent_season_check_and_build_share_one_fetch(monkeypatch):
    # The real conversation shape: season check (fast path) and a build (full gather)
    # overlapping must still cost exactly ONE research call.
    _patch_slices(monkeypatch, stays_delay=0.05)
    calls = {"n": 0}

    async def counting_research(query: str, **kw):
        calls["n"] += 1
        return _FakeResearch()

    monkeypatch.setattr(wi, "research", counting_research)

    season, full = await asyncio.gather(
        wi.gather_seasonality(_dest(), _brief()),
        wi.gather(_dest(), _brief()),
    )
    assert season == _SEASON
    assert full.seasonality == _SEASON and full.stays == [_STAY]
    assert calls["n"] == 1  # coalesced — never a double fetch
