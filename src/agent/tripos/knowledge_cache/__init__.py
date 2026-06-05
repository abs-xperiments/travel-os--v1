"""knowledge_cache — remember retrieved destinations in Neon so we don't re-fetch them.

Retrieving a destination from the web (Perplexity + extraction) costs money and takes a few
seconds. Stable travel facts barely change, so we cache the resulting `Destination` here and
reuse it until it goes stale (default ~60 days). The curated catalog is the *zero-cost* cache;
this is the cache for *everywhere else on Earth*.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from pathlib import Path

from agent.services import db
from agent.tripos.models import Destination

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DEFAULT_MAX_AGE_DAYS = 60

# Bump when the extraction payload grows (v2 = attraction popularity + icon/hidden-gem mix).
# The version lives in the ROW KEY only — destination.id stays clean — so pre-bump rows are
# simply bypassed and age out, instead of pinning the old shape for up to 60 days.
_SCHEMA_VERSION = "v2"


def _row_id(destination_id: str) -> str:
    return f"{destination_id}@{_SCHEMA_VERSION}"


async def init_db() -> list[str]:
    """Create the cache table on startup (runs migrations once). Returns files applied."""
    return await db.apply_migrations(MIGRATIONS_DIR)


async def get(destination_id: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> Destination | None:
    """Return a cached destination if present AND fresher than max_age_days, else None."""
    row = await db.fetchrow(
        "SELECT knowledge FROM tripos_destination_cache "
        "WHERE id = $1 AND fetched_at > now() - make_interval(days => $2::int)",
        _row_id(destination_id),
        max_age_days,
    )
    return Destination.model_validate_json(row["knowledge"]) if row else None


async def put(destination: Destination) -> None:
    """Store (or refresh) a retrieved destination, stamped with the current time."""
    await db.execute(
        "INSERT INTO tripos_destination_cache (id, name, knowledge, fetched_at) "
        "VALUES ($1, $2, $3, now()) "
        "ON CONFLICT (id) DO UPDATE SET "
        "name = EXCLUDED.name, knowledge = EXCLUDED.knowledge, fetched_at = now()",
        _row_id(destination.id),
        destination.name,
        destination.model_dump_json(),
    )
