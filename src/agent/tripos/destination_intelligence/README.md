# `destination_intelligence` — "tell me about this place" for ANYWHERE

## In one sentence
Give it any destination name — "Munnar", "Tawang", "Kyoto", "a small town" — and it returns a
full, typed `Destination` (with attractions), fetching it from the web the first time and
remembering it after. This is what replaced the old "is it in our list?" gate.

## Why it exists
This module is the answer to the core requirement: **no hardcoded destination limit**. The
planner used to look a place up in 24 JSON files and refuse anything else. Now it asks
*"resolve this destination"* and gets an answer for anywhere a place can be verified to exist.

## What it does (in order)
1. **Fresh cache?** If we've retrieved this place recently (`knowledge_cache`), return it —
   instant and free.
2. **Providers by priority** (`provider_registry`):
   - the **catalog** provider (instant, the 24 curated India places),
   - then the **web** provider (geocode-verify → research → extract a `Destination`).
   The first one that answers wins; web results are saved to the cache for next time.
3. Returns **None only if no provider can identify the place at all** (a typo or invented
   name). That is the *only* "can't plan" case — and it's about existence, never a fixed list.

## The golden rule (again)
The catalog is a **cache/speed-up, not a gatekeeper**. Deleting it would only make TripOS
slower for those 24 places — it would still plan all of them (and everywhere else) via the web.

## How to debug it
- **A real place returns None:** geocoding (Nominatim) couldn't find it — try a fuller name
  ("Ziro, Arunachal Pradesh"); check `providers/geocoding.py` and that the network is up.
- **Wrong/thin attractions for a place:** that's the web provider's extraction —
  see `providers/destination_retrieval.py`; the underlying notes come from `research()`.
- **A stale result:** clear its cache row (see `knowledge_cache` README) to force a re-fetch.
- **Live test:** `uv run pytest -m integration scripts/tests/test_destination_intelligence.py`
  (hits the network + costs ~1 cent; resolves a non-catalog place, then cleans up).

## What it deliberately does NOT do
It only *resolves* a destination. Picking attractions, building days, budgets, stays — those
remain the existing engines' jobs; they just receive the resolved `Destination`.
