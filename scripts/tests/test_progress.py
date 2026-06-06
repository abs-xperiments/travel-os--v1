"""Offline tests: the live progress checklist (Reporter) + the domain progress callbacks.

The honesty contract under test: a line is ✓ only when its work completed; helpers are safe
no-ops when no reporter is active (CLI, plain agent runs); the domain callbacks fire exactly
when each unit of work finishes.

    uv run pytest scripts/tests/test_progress.py
"""

from __future__ import annotations

import asyncio

from agent.agents.tripos_planner import progress
from agent.tripos import circuit_planner, trip_intelligence
from agent.tripos.models import (
    Destination,
    FoodPref,
    GroupType,
    TravelStyle,
    TripBrief,
    TripEnrichment,
)


def _drain(queue: asyncio.Queue[str]) -> list[str]:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


def _brief() -> TripBrief:
    return TripBrief(
        start_city="Chennai",
        days=3,
        budget=30000,
        group_type=GroupType.couple,
        interests=[TravelStyle.nature],
        food_pref=FoodPref.no_preference,
    )


def _dest(name: str) -> Destination:
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


# ------------------------------------------------------------------- Reporter


def test_reporter_renders_growing_checklist_with_title():
    queue: asyncio.Queue[str] = asyncio.Queue()
    reporter, token = progress.activate(queue)
    try:
        reporter.title = "Building your trip…"
        progress.begin("Destination intelligence")
        progress.begin("Stays, food & weather")
        progress.finish("Destination intelligence")
        progress.step("Selecting stops, days & budget")
        progress.complete()
    finally:
        progress.deactivate(token)

    blocks = _drain(queue)
    # Every emission is the FULL current checklist (the UI replaces wholesale).
    assert blocks[0] == "Building your trip…\n• Destination intelligence…"
    assert "✓ Destination intelligence" in blocks[2]
    assert "• Stays, food & weather…" in blocks[2]  # still pending at that point
    # The final block has everything ticked — nothing left "in progress".
    assert "•" not in blocks[-1]
    assert blocks[-1].count("✓") == 3


def test_step_completes_the_previous_step_only():
    queue: asyncio.Queue[str] = asyncio.Queue()
    reporter, token = progress.activate(queue)
    try:
        progress.begin("Parallel work")  # begun, NOT a step — step() must not touch it
        progress.step("Stage one")
        progress.step("Stage two")
    finally:
        progress.deactivate(token)

    last = _drain(queue)[-1]
    assert "• Parallel work…" in last  # untouched by step()
    assert "✓ Stage one" in last  # auto-completed by the next step
    assert "• Stage two…" in last  # the new current step


def test_helpers_are_noops_without_an_active_reporter():
    # CLI runs and plain agent.run() have no reporter — tool code must work unchanged.
    progress.begin("x")
    progress.finish("x")
    progress.step("y")
    progress.complete()  # nothing raised, nothing emitted anywhere


# ------------------------------------------------------- domain callbacks


async def test_resolve_and_enrich_reports_each_half(monkeypatch):
    parts: list[str] = []

    async def fake_resolve(query: str, brief: TripBrief | None = None):
        await asyncio.sleep(0.02)  # finish AFTER enrichment to prove per-half reporting
        return _dest(query)

    async def fake_enrich(destination: Destination, brief: TripBrief) -> TripEnrichment:
        return TripEnrichment()

    monkeypatch.setattr(trip_intelligence.destination_intelligence, "resolve", fake_resolve)
    monkeypatch.setattr(trip_intelligence, "enrich", fake_enrich)

    resolved, _ = await trip_intelligence.resolve_and_enrich(
        "Munnar", _brief(), on_progress=parts.append
    )
    assert resolved is not None
    assert parts == ["enrichment", "destination"]  # ticked in COMPLETION order, not call order


async def test_resolve_and_enrich_skips_destination_tick_on_failure(monkeypatch):
    parts: list[str] = []

    async def failed_resolve(query: str, brief: TripBrief | None = None):
        return None  # place not found — must NOT be reported as completed work

    async def fake_enrich(destination: Destination, brief: TripBrief) -> TripEnrichment:
        return TripEnrichment()

    monkeypatch.setattr(trip_intelligence.destination_intelligence, "resolve", failed_resolve)
    monkeypatch.setattr(trip_intelligence, "enrich", fake_enrich)

    resolved, _ = await trip_intelligence.resolve_and_enrich(
        "Atlantis", _brief(), on_progress=parts.append
    )
    assert resolved is None
    assert parts == ["enrichment"]  # no ✓ for work that didn't succeed


async def test_plan_circuit_reports_each_leg_as_it_completes(monkeypatch):
    done_legs: list[str] = []

    async def fake_build_leg(dest_name: str, nights: int, brief: TripBrief):
        await asyncio.sleep(0.03 if dest_name == "Munnar" else 0.01)
        return None  # leg "fails to resolve" — callback still fires (the WORK finished)

    monkeypatch.setattr(circuit_planner, "_build_leg", fake_build_leg)

    plan = await circuit_planner.plan_circuit(
        "Test", [("Munnar", 2), ("Wayanad", 1)], _brief(), on_leg_done=done_legs.append
    )
    assert plan is None  # no leg resolved -> no plan (existing behavior unchanged)
    assert done_legs == ["Wayanad", "Munnar"]  # completion order, concurrent legs
