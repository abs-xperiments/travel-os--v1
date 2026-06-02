# `circuit_discovery` — "how many days? I'll tell you where to go"

## In one sentence
Given a region (like "Kerala" or "Rajasthan") and how many nights, it suggests a few
**multi-destination routes** — e.g. Kochi → Munnar → Thekkady → Alleppey — with how many
nights to spend at each stop and why.

## Why it exists
Most travelers don't know which places to combine ("I have 6 days in Kerala" — but is that
Munnar + Thekkady + Alleppey, or Munnar + Wayanad?). A great travel agent proposes the routes.
This module is that agent move: it turns a region + length into expert-style **circuits**,
*before* committing to a single destination.

## What it does
Calls the registered `circuit` provider (today: a cached web retrieval) and returns a list of
`Circuit`s. Each circuit has its legs in travel order, **nights allocated by how much there is
to do at each place** (not an even split), a style, a rough per-person budget, and a why.

It's **best-effort**: if retrieval fails it returns an empty list and the agent falls back to
asking for a destination directly.

## How it fits the flow
The agent calls `discover_circuits` when a traveler gives a region + days but no specific
place (or doesn't know where to go). It presents the routes; the traveler picks one, and the
existing `build_trip` plans a chosen destination from it (with Phase-2 stays/food/weather).
*(Auto-building the whole multi-leg circuit in one step is the next increment.)*

## How to debug it
- **No circuits:** check the provider is registered and the retrieval in `providers/circuits.py`;
  empty is the safe fallback.
- **Stale/odd routes:** clear the cache row (`tripos_intelligence_cache`, key
  `circuit:<region>:<nights>`).
- **Live test:** `uv run pytest -m integration scripts/tests/test_circuit_discovery.py`.
