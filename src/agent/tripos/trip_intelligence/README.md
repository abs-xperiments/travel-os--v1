# `trip_intelligence` — add stays, restaurants & weather to a plan

## In one sentence
Given a destination and the traveler's brief, it returns recommended **places to stay**,
**places to eat**, and a **weather/season note** — for anywhere in the world.

## Why it exists
A bare itinerary (just attractions + budget) isn't a full trip. A real travel consultant also
tells you where to sleep, where to eat, and what the weather will be like. This module adds
that layer — and, like everything in V2, it gets the data by **retrieval behind provider
interfaces**, never a hardcoded list.

## What it does
Calls the registered `accommodation`, `restaurant`, and `weather` providers and bundles their
results into a `TripEnrichment` (stays + restaurants + weather). Today all three are backed by
**one cached web retrieval** (a single search + extraction per destination, stored in
`intelligence_cache`), so asking for all three costs one fetch. Tomorrow, Booking / Google
Places / Open-Meteo can replace any one of them by registering under that role — no change here.

## Best-effort by design
It **never fails the trip**. If retrieval errors out, it returns an empty `TripEnrichment` and
the plan is still produced (just without the extras). Stays/restaurants/weather are always
*optional* on a `TripPlan`.

## Honesty
Prices and ratings are **web-grounded estimates, not live booking quotes** — surfaced as such.
Live inventory/booking is a future upgrade behind the same interfaces.

## How to debug it
- **No stays/restaurants showing:** check the web retrieval in
  `providers/web_intelligence.py` and that the providers are registered (web startup logs).
- **Stale or wrong recs:** clear the cache row (`tripos_intelligence_cache`, key = destination
  id) to force a refetch — see `intelligence_cache`.
- **Live test:** `uv run pytest -m integration scripts/tests/test_trip_intelligence.py`.
