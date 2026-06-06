"""Offline tests: in-flight coalescing + the season-check prewarm. No network.

The speed mechanisms must never change WHAT is retrieved — only how often and how early:
- concurrent fetches for the same place share ONE retrieval task (coalescing);
- the season check warms the destination cache in the background (prewarm), and failures
  there are invisible (the build simply retrieves fresh).

    uv run pytest scripts/tests/test_speedups.py
"""

from __future__ import annotations

import asyncio

from agent.agents.tripos_planner import check_travel_season
from agent.agents.tripos_planner import tools as planner_tools
from agent.tripos import destination_intelligence
from agent.tripos.models import (
    Destination,
    FoodPref,
    GroupType,
    TravelStyle,
    TripBrief,
    TripEnrichment,
)
from agent.tripos.providers import web_intelligence


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


async def test_concurrent_gathers_share_one_fetch(monkeypatch):
    # Two simultaneous enrichment requests for the SAME destination must cost ONE retrieval.
    calls = 0

    async def fake_fetch(key: str, destination: Destination, brief: TripBrief) -> TripEnrichment:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)  # long enough that both callers overlap
        return TripEnrichment()

    async def no_cache(key: str, max_age_days: int = 30):
        return None

    monkeypatch.setattr(web_intelligence, "_fetch", fake_fetch)
    monkeypatch.setattr(web_intelligence.intelligence_cache, "get", no_cache)

    a, b = await asyncio.gather(
        web_intelligence.gather(_dest(), _brief()),
        web_intelligence.gather(_dest(), _brief()),
    )
    assert calls == 1, "coalescing must collapse concurrent fetches into one"
    assert a is b  # both callers got the same in-flight result


async def test_concurrent_resolves_share_one_retrieval(monkeypatch):
    calls = 0
    didupe = _dest()

    async def fake_uncached(query: str, brief: TripBrief | None) -> Destination | None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return didupe

    async def no_cache(slug: str, max_age_days: int = 60):
        return None

    monkeypatch.setattr(destination_intelligence, "_resolve_uncached", fake_uncached)
    monkeypatch.setattr(destination_intelligence.knowledge_cache, "get", no_cache)

    a, b = await asyncio.gather(
        destination_intelligence.resolve("Didupe", _brief()),
        destination_intelligence.resolve("Didupe", _brief()),
    )
    assert calls == 1
    assert a is didupe and b is didupe


async def test_sequential_gathers_after_completion_fetch_again(monkeypatch):
    # Coalescing is for IN-FLIGHT overlap only — once a task finishes, the cache (mocked away
    # here) is the dedupe layer, so a later miss fetches again rather than reusing a dead task.
    calls = 0

    async def fake_fetch(key: str, destination: Destination, brief: TripBrief) -> TripEnrichment:
        nonlocal calls
        calls += 1
        return TripEnrichment()

    async def no_cache(key: str, max_age_days: int = 30):
        return None

    monkeypatch.setattr(web_intelligence, "_fetch", fake_fetch)
    monkeypatch.setattr(web_intelligence.intelligence_cache, "get", no_cache)

    await web_intelligence.gather(_dest(), _brief())
    await web_intelligence.gather(_dest(), _brief())
    assert calls == 2  # the in-flight map must not leak completed tasks


async def test_season_check_prewarms_destination_resolve(monkeypatch):
    resolved: list[str] = []

    async def fake_resolve(query: str, brief: TripBrief | None = None) -> Destination | None:
        resolved.append(query)
        return _dest(query)

    async def fake_season(query: str, brief: TripBrief):
        return None  # "no seasonal data" path — returns unknown without network

    monkeypatch.setattr(planner_tools.destination_intelligence, "resolve", fake_resolve)
    monkeypatch.setattr(planner_tools.trip_intelligence, "season_profile", fake_season)

    out = await check_travel_season("Munnar", month=1)
    await asyncio.gather(*planner_tools._prewarm_tasks)  # let the background warm-up finish

    assert out["unknown"] is True  # season path unaffected
    assert resolved == ["Munnar"], "season check must warm the destination cache in background"


async def test_prewarm_failure_is_invisible(monkeypatch):
    async def exploding_resolve(query: str, brief: TripBrief | None = None):
        raise RuntimeError("network down")

    async def fake_season(query: str, brief: TripBrief):
        return None

    monkeypatch.setattr(planner_tools.destination_intelligence, "resolve", exploding_resolve)
    monkeypatch.setattr(planner_tools.trip_intelligence, "season_profile", fake_season)

    out = await check_travel_season("Munnar", month=1)
    await asyncio.gather(*planner_tools._prewarm_tasks)  # must not raise

    assert "error" not in out  # the traveler never sees a prewarm failure
