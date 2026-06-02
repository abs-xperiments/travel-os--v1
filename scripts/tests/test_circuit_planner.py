"""Integration test: circuit_planner builds a multi-leg trip (needs DATABASE_URL + network).

Uses two CATALOG destinations (free to resolve) to limit cost; enrichment still hits the web.
Cleans up its enrichment cache rows.

    uv run pytest -m integration scripts/tests/test_circuit_planner.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import circuit_planner, trip_intelligence
from agent.tripos.models import GroupType, TravelStyle, TripBrief

pytestmark = pytest.mark.integration


async def test_plan_circuit_stitches_legs_with_continuous_days():
    await trip_intelligence.init_db()
    brief = TripBrief(
        start_city="Chennai",
        days=3,
        budget=30000,
        group_type=GroupType.family,
        interests=[TravelStyle.nature],
        travelers=2,
    )
    try:
        plan = await circuit_planner.plan_circuit("Test", [("Munnar", 2), ("Wayanad", 1)], brief)
        assert plan is not None
        assert [s.destination for s in plan.stops] == ["Munnar", "Wayanad"]
        assert plan.total_nights == 3
        # day numbers run continuously 1..N across both legs
        days = [d.day for s in plan.stops for d in s.day_plans]
        assert days == list(range(1, len(days) + 1))
        # one combined per-person budget, scaled to the group
        assert plan.budget.per_person_total > 0
        assert plan.budget.group_total == plan.budget.per_person_total * 2
    finally:
        await db.execute(
            "DELETE FROM tripos_intelligence_cache WHERE key = ANY($1)", ["munnar", "wayanad"]
        )
