# `knowledge_cache` — remember retrieved destinations so we don't pay twice

## In one sentence
A database table that stores destinations we looked up from the web, so the second person to
plan a trip to (say) Pondicherry gets an instant, free answer instead of another web search.

## Why it exists
Looking a place up on the web (Perplexity + extracting structured facts) costs a little money
and takes a few seconds. Travel facts (top sights, typical durations, seasons) barely change
week to week. So we save the result and reuse it for a while. This is what keeps retrieval
**affordable and fast** at scale.

Two layers of caching, by the way: the **curated catalog** is the zero-cost cache for ~24
hand-checked places; **this** is the cache for everywhere else.

## What it does
- `init_db()` — creates the `tripos_destination_cache` table on startup (once).
- `get(id, max_age_days=60)` — returns the cached `Destination` **only if it's fresh enough**,
  else `None` (so the caller re-fetches).
- `put(destination)` — saves/refreshes a destination, time-stamped now.

## How the data is stored
One table, `tripos_destination_cache` (`migrations/002`): `id`, `name`, `knowledge` (a
serialized `Destination` with its attractions, as `jsonb`), and `fetched_at`. **Freshness** is
just "is `fetched_at` newer than N days ago?". Migrations are forward-only — add `003_*.sql`,
never edit `002`.

## How to debug it
- **Stale data showing:** lower `max_age_days`, or delete the row to force a re-fetch:
  `DELETE FROM tripos_destination_cache WHERE id = '<slug>'`.
- **Nothing caching / table errors:** the migration runs on web startup; check logs for
  "applied migrations". Run by hand:
  `uv run python -c "import asyncio; from agent.tripos import knowledge_cache; asyncio.run(knowledge_cache.init_db())"`.
- **Live test:** `uv run pytest -m integration scripts/tests/test_knowledge_cache.py` (needs
  `DATABASE_URL`; uses a throwaway row and cleans up).
