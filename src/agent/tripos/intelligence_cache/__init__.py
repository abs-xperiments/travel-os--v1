"""intelligence_cache — Neon cache for retrieved trip enrichment (stays/restaurants/weather).

Same idea as knowledge_cache, for a different payload: enrichment is expensive to retrieve
(a web search + extraction), so we store it per destination and reuse it until stale.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

from pathlib import Path

from agent.services import db

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DEFAULT_MAX_AGE_DAYS = 30


async def init_db() -> list[str]:
    """Create the cache table on startup (runs migrations once)."""
    return await db.apply_migrations(MIGRATIONS_DIR)


async def get(key: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> str | None:
    """Return the cached JSON string if present AND fresh, else None."""
    row = await db.fetchrow(
        "SELECT data FROM tripos_intelligence_cache "
        "WHERE key = $1 AND fetched_at > now() - make_interval(days => $2::int)",
        key,
        max_age_days,
    )
    if row is None:
        return None
    data = row["data"]
    return data if isinstance(data, str) else None


async def put(key: str, data_json: str) -> None:
    """Store (or refresh) a JSON payload under a key, stamped now."""
    await db.execute(
        "INSERT INTO tripos_intelligence_cache (key, data, fetched_at) "
        "VALUES ($1, $2, now()) "
        "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, fetched_at = now()",
        key,
        data_json,
    )
