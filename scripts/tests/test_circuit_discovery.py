"""Integration test: circuit_discovery suggests routes for a region (needs DATABASE_URL + network).

Costs ~1 cent (web research + extraction). Cleans up its cache rows.

    uv run pytest -m integration scripts/tests/test_circuit_discovery.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import circuit_discovery, trip_intelligence
from agent.tripos.models import GroupType, TravelStyle, TripBrief

pytestmark = pytest.mark.integration


async def test_discover_returns_routes_for_a_region():
    await trip_intelligence.init_db()  # ensure the shared cache table exists
    brief = TripBrief(
        start_city="(unspecified)",
        days=6,
        budget=30000,
        group_type=GroupType.family,
        interests=[TravelStyle.nature],
        travelers=2,
    )
    try:
        circuits = await circuit_discovery.discover("Kerala", 6, brief)
        assert circuits, "expected at least one circuit"
        first = circuits[0]
        assert first.legs, "a circuit must have legs"
        assert all(leg.nights >= 0 for leg in first.legs)
        assert all(leg.destination for leg in first.legs)
    finally:
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key LIKE 'circuit:kerala:%'")
