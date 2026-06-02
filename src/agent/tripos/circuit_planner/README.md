# `circuit_planner` — build the whole multi-stop trip

## In one sentence
Give it a chosen route (e.g. Kochi 1 night → Munnar 2 → Thekkady 1 → Alleppey 1) and it
builds the entire trip: a stay for each leg, a continuous day-by-day across all of them, and
one combined per-person budget.

## Why it exists
`circuit_discovery` *suggests* routes; this module *builds* the one the traveler picks — the
final step that turns "Kochi → Munnar → Thekkady → Alleppey" into a real multi-stay itinerary.

## What it does (per leg, then stitched)
For each stop it reuses the existing engines: resolve the place
(`destination_intelligence`), get its stays/restaurants/weather (`trip_intelligence`), and
plan attractions + days sized to that leg's nights (`trip_planner`). Then it stitches:
- **continuous days** — day numbers run 1..N across all legs, each titled with its place;
- **a stay per leg** — different accommodation for each destination;
- **one combined per-person budget** — a single base transport + an inter-city hop per
  transition + each leg's accommodation/food/activities (via `trip_planner.circuit_budget`).

## Cost & latency (important)
This is the heaviest call: a resolve + an enrichment **per leg** (cached after the first time).
A fresh 3–4 leg circuit can take 20–40s and several web lookups. Callers run it behind the
streaming "Building your trip…" progress note. There's a `MAX_LEGS` safety cap.

## How to debug it
- **A leg is missing:** it couldn't be placed — its name is in the feasibility `reasons`; the
  rest of the trip still builds.
- **Budget looks off:** it's `trip_planner.circuit_budget` + the retrieved per-leg stay rates;
  all per-person, all estimates.
- **Live test:** `uv run pytest -m integration scripts/tests/test_circuit_planner.py` (uses a
  2-leg catalog route to limit cost).

## What it deliberately does NOT do (yet)
No deep geographic route re-ordering — it trusts the order of the chosen circuit (which the
discovery step already arranges sensibly). Real inter-city distances/times are a future upgrade.
