"""Integration test: the destination knowledge cache (needs DATABASE_URL).

Uses a throwaway row and deletes it afterward.

    uv run pytest -m integration scripts/tests/test_knowledge_cache.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import knowledge_cache
from agent.tripos.models import Destination, TravelStyle

pytestmark = pytest.mark.integration

_TEST_ID = "testcache_pondicherry_xyz"


def _sample() -> Destination:
    return Destination(
        id=_TEST_ID,
        name="Test City",
        state="Test State",
        region="Test Region",
        description="A throwaway destination for the cache test.",
        bases=["Test Town"],
        good_for=[TravelStyle.nature],
        nearest_railhead="Test Rail",
        nearest_airport="Test Air",
    )


async def test_cache_roundtrip_and_freshness():
    await knowledge_cache.init_db()
    try:
        await knowledge_cache.put(_sample())
        got = await knowledge_cache.get(_TEST_ID)
        assert got is not None
        assert got.name == "Test City"
        assert got.id == _TEST_ID
        # freshness: with a 0-day max age, an existing row is treated as stale
        assert await knowledge_cache.get(_TEST_ID, max_age_days=0) is None
    finally:
        await db.execute("DELETE FROM tripos_destination_cache WHERE id = $1", _TEST_ID)
