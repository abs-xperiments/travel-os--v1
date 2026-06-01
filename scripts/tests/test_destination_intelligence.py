"""Integration test: destination_intelligence resolves ANY place (needs DATABASE_URL + network).

Costs ~1 cent (a web research + extraction) for the non-catalog case. Cleans up its cache row.

    uv run pytest -m integration scripts/tests/test_destination_intelligence.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import destination_intelligence as di

pytestmark = pytest.mark.integration


async def test_catalog_place_uses_fast_path():
    dest = await di.resolve("Munnar")
    assert dest is not None
    assert dest.id == "munnar"  # served from the curated catalog


async def test_noncatalog_place_is_retrieved_and_well_formed():
    dest = await di.resolve("Pondicherry")
    try:
        assert dest is not None  # NOT "unsupported" — retrieved from the web
        assert len(dest.attractions) >= 5
        assert all(a.destination_id == dest.id for a in dest.attractions)
        assert all(a.duration_hours > 0 for a in dest.attractions)
        assert dest.coordinates is not None  # geocoding verified it exists
    finally:
        if dest is not None:
            await db.execute("DELETE FROM tripos_destination_cache WHERE id = $1", dest.id)


async def test_unidentifiable_place_returns_none():
    assert await di.resolve("Zzxqwlkjhg Nowhereville 99999") is None
