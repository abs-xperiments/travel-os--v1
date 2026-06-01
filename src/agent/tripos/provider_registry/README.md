# `provider_registry` — the swap point for data sources

## In one sentence
A little phone book: data providers sign up under a role ("destination", "accommodation", …)
with a priority, and the planner looks up "who can give me a destination?" without knowing any
provider by name.

## Why it exists
It's what makes new data sources **plug-and-play**. The curated catalog, a web-search adapter,
and (one day) Google Places all register here. The planner asks the registry, not the
provider. So adding Booking.com later is literally:
```python
registry.register("accommodation", BookingComAdapter(), priority=20)
```
…and nothing in the planning code changes.

## What's inside
- **`ProviderRegistry`** with `register(role, provider, priority)`, `get(role)` (best one),
  `get_all(role)` (all, best-first — for "try the catalog, then fall back to web"), and
  `clear()` (tests).
- **`registry`** — a shared singleton everyone imports.

## How it's used
At app startup we register the providers (highest priority = tried first):
```python
registry.register("destination", CatalogDestinationProvider(), priority=10)  # fast cache
registry.register("destination", WebDestinationProvider(),     priority=1)   # global fallback
```
Then `destination_intelligence` does `for p in registry.get_all("destination"): ...` until one
returns a result.

## How to debug it
- **"No provider found":** nothing registered that role yet — check the startup registration
  ran (it happens in the web app's lifespan).
- **Wrong provider used:** check the `priority` numbers — higher wins.
- `uv run pytest scripts/tests/test_provider_registry.py` covers ordering and lookup.
