# `provider_interfaces` — the contracts that make TripOS provider-agnostic

## In one sentence
This module defines the **promises** ("give me destination knowledge for X") that the planner
relies on, so the planner never depends on *where* the data actually comes from.

## Why it exists
This is the single most important idea in the V2 architecture. We want TripOS to plan a trip
to **any** place on Earth without a hardcoded list of "supported destinations". To do that,
the planner must not call Wikipedia, or a web search, or Google directly — because then
swapping or adding a source would mean rewriting the planner. Instead the planner talks to an
**interface**: *"DestinationProvider, fetch me 'Tawang'."* Whoever can answer, answers.

## What's inside
- **`DestinationProvider`** — a `Protocol` (Python's lightweight "interface"): any class with a
  `name` and an `async fetch(query, brief) -> Destination | None` counts as one. No inheritance
  needed.
- **`slugify(name)`** — turns "Leh-Ladakh" into "leh-ladakh" so names map to stable ids.

More interfaces (`AccommodationProvider`, `RestaurantProvider`, `WeatherProvider`) will live
here in later phases — same idea.

## The golden rule
`fetch(...)` returning **None means "I don't have it"**, not "unsupported". The registry then
tries the next provider. A destination is only unplannable if *every* provider returns None
(i.e. it genuinely can't be identified). There is no "supported destinations" list anywhere.

## How to debug it
- This file has almost no logic — it's contracts + `slugify`. If a provider "isn't recognized"
  as a `DestinationProvider`, check it has both a `name` attribute and an `async fetch` method
  with the right shape.
- `uv run pytest scripts/tests/test_provider_registry.py` exercises `slugify` and the contract.
