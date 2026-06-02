# `intelligence_cache` — remember a destination's stays/restaurants/weather

## In one sentence
A small database table that stores the retrieved **enrichment** (recommended stays,
restaurants, and weather notes) for a destination, so we look it up from the web once and
reuse it.

## Why it exists
Same reasoning as `knowledge_cache`, different payload. Fetching stays + restaurants + weather
is a web search plus an extraction — a few seconds and a little money. It changes slowly, so
we cache the whole bundle per destination (`tripos_intelligence_cache`, migration 003) and
reuse it for ~30 days.

## What it does
- `init_db()` — create the table on startup.
- `get(key, max_age_days=30)` — the cached JSON string if fresh, else `None`.
- `put(key, json)` — save/refresh under a key (we use the destination id).

## How to debug it
- **Stale recommendations:** delete the row to force a refetch:
  `DELETE FROM tripos_intelligence_cache WHERE key = '<slug>'`.
- **Nothing caches:** the migration runs on web startup; check logs for "applied migrations".
