"""trip_store — save and reopen trips (conversations) in Neon Postgres.

A "trip" is one saved conversation. We persist two things per trip:
  - `transcript`: a simple [{role, content}] list, for re-rendering the chat on reopen.
  - `agent_messages`: the pydantic-ai message history, serialized, so the AI can *continue*
    the conversation with full context (tool calls included) after a restart.

Keeping both is deliberate: the transcript is easy to display without parsing the model's
internal message format, and the agent_messages give the model everything it needs to carry on.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from agent.services import db

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class TranscriptEntry(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class StoredTrip(BaseModel):
    id: str
    title: str | None = None
    transcript: list[TranscriptEntry] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TripSummary(BaseModel):
    id: str
    title: str | None = None
    updated_at: datetime | None = None


async def init_db() -> list[str]:
    """Apply this module's migrations. Call once on web startup. Returns files applied."""
    return await db.apply_migrations(MIGRATIONS_DIR)


async def _exists(trip_id: str) -> bool:
    return await db.fetchrow("SELECT 1 FROM tripos_trips WHERE id = $1", trip_id) is not None


async def ensure_trip(trip_id: str | None) -> str:
    """Return a usable trip id: the given one if it exists, otherwise a fresh new trip."""
    if trip_id and await _exists(trip_id):
        return trip_id
    new_id = uuid4().hex
    await db.execute("INSERT INTO tripos_trips (id) VALUES ($1) ON CONFLICT DO NOTHING", new_id)
    return new_id


async def get_trip(trip_id: str) -> StoredTrip | None:
    """Load a trip (with its display transcript), or None if it doesn't exist."""
    row = await db.fetchrow(
        "SELECT id, title, transcript, created_at, updated_at FROM tripos_trips WHERE id = $1",
        trip_id,
    )
    if row is None:
        return None
    raw = row["transcript"]  # jsonb comes back as a JSON string from asyncpg
    entries = json.loads(raw) if isinstance(raw, str) else (raw or [])
    return StoredTrip(
        id=row["id"],
        title=row["title"],
        transcript=[TranscriptEntry(**e) for e in entries],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def load_agent_messages(trip_id: str) -> list[ModelMessage]:
    """Rehydrate the pydantic-ai history so the agent can continue the conversation."""
    row = await db.fetchrow("SELECT agent_messages FROM tripos_trips WHERE id = $1", trip_id)
    if row is None or row["agent_messages"] is None:
        return []
    return list(ModelMessagesTypeAdapter.validate_json(row["agent_messages"]))


def _title_from(message: str) -> str:
    """A short, human title from the first user message."""
    text = " ".join(message.split())
    return text[:60] + ("…" if len(text) > 60 else "")


async def append_turn(
    trip_id: str, user_message: str, reply: str, agent_messages_json: str
) -> None:
    """Append one user+assistant turn to a trip and store the updated agent history."""
    trip = await get_trip(trip_id)
    transcript = [e.model_dump() for e in trip.transcript] if trip else []
    transcript.append({"role": "user", "content": user_message})
    transcript.append({"role": "assistant", "content": reply})
    await db.execute(
        "UPDATE tripos_trips "
        "SET transcript = $2, agent_messages = $3, title = COALESCE(title, $4), updated_at = now() "
        "WHERE id = $1",
        trip_id,
        json.dumps(transcript),
        agent_messages_json,
        _title_from(user_message),
    )


async def list_recent(limit: int = 20) -> list[TripSummary]:
    """Most-recently-updated trips that actually have a conversation (skip empty ones)."""
    rows = await db.fetch(
        "SELECT id, title, updated_at FROM tripos_trips "
        "WHERE jsonb_array_length(transcript) > 0 "
        "ORDER BY updated_at DESC LIMIT $1",
        limit,
    )
    return [TripSummary(id=r["id"], title=r["title"], updated_at=r["updated_at"]) for r in rows]
