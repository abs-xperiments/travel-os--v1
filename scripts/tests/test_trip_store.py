"""Integration test: trip_store persists, reopens, and lists trips (needs DATABASE_URL).

Uses a throwaway trip row and deletes it afterward.

    uv run pytest -m integration scripts/tests/test_trip_store.py
"""

from __future__ import annotations

import pytest

from agent.services import db
from agent.tripos import trip_store

pytestmark = pytest.mark.integration


async def test_create_append_reopen_and_list():
    await trip_store.init_db()
    trip_id = await trip_store.ensure_trip(None)
    try:
        # fresh trip: exists, empty transcript
        trip = await trip_store.get_trip(trip_id)
        assert trip is not None
        assert trip.transcript == []

        # save one turn (empty but valid serialized agent history)
        await trip_store.append_turn(trip_id, "Plan Goa for 3 days", "Here is your Goa plan…", "[]")

        reopened = await trip_store.get_trip(trip_id)
        assert reopened is not None
        assert reopened.title is not None and reopened.title.startswith("Plan Goa")
        assert len(reopened.transcript) == 2
        assert reopened.transcript[0].role == "user"
        assert reopened.transcript[1].role == "assistant"

        # the agent history round-trips (empty list here)
        assert await trip_store.load_agent_messages(trip_id) == []

        # shows up in the dashboard list
        assert trip_id in {t.id for t in await trip_store.list_recent()}
    finally:
        await db.execute("DELETE FROM tripos_trips WHERE id = $1", trip_id)
