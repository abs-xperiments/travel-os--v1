"""Integration test: trip_intelligence enriches a destination (needs DATABASE_URL + network).

Costs ~1 cent (web research + extraction). Cleans up its cache row.

    uv run pytest -m integration scripts/tests/test_trip_intelligence.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_intelligence
from agent.tripos.models import GroupType, TravelStyle, TripBrief

pytestmark = pytest.mark.integration


async def test_enrich_returns_stays_and_restaurants():
    munnar = catalog.get_destination("munnar")
    assert munnar is not None
    brief = TripBrief(
        start_city="Chennai",
        days=3,
        budget=20000,
        group_type=GroupType.family,
        interests=[TravelStyle.nature],
        destination_id="munnar",
    )
    await trip_intelligence.init_db()
    try:
        enr = await trip_intelligence.enrich(munnar, brief)
        assert enr.stays, "expected some accommodation recommendations"
        assert all(s.tier in {"budget", "mid", "premium"} for s in enr.stays)
        assert all(s.price_per_night_high >= s.price_per_night_low for s in enr.stays)
        assert enr.restaurants, "expected some restaurant recommendations"
        assert enr.seasonality is not None and enr.seasonality.months, (
            "expected a year-round seasonality profile"
        )
    finally:
        await db.execute("DELETE FROM tripos_intelligence_cache WHERE key = $1", "munnar:v2")
