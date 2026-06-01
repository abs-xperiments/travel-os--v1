# `providers` — the actual data-source adapters

## In one sentence
The plug-in drivers: each class here knows how to talk to ONE source (the curated catalog, a
web search, a maps/geocoding service, …) and hand back TripOS's standardized types.

## Why it exists
The planner speaks the language of `provider_interfaces`. These adapters translate a real
source into that language. Keeping them in one folder, each tiny and single-source, is what
makes adding/removing/upgrading a source painless.

## What's inside (grows over Phase 1)
- **`CatalogDestinationProvider`** — the 24 curated India destinations as a fast, free,
  zero-latency provider. It's a **cache/optimization only**: a miss returns `None`, and the
  registry falls back to web retrieval. It is never a gatekeeper.
- *(added next in Phase 1)* a **geocoding adapter** (OpenStreetMap/Nominatim) to verify a
  place exists, and a **web-retrieval adapter** (Perplexity via `research()`) that builds a
  `Destination` for anywhere on Earth.
- *(future)* Google Places, Booking.com, etc. — new classes here, registered at startup.

## How adapters are wired up
They don't register themselves. The app's startup (web lifespan) registers them into the
`provider_registry` with priorities, so the catalog is tried first and web retrieval is the
fallback. Keeping registration in one place makes the provider lineup easy to see and change.

## How to debug it
- **A curated place isn't found:** check `slugify(name)` matches the JSON `id` in
  `destination_catalog/data/`.
- **A non-curated place returns None from the catalog adapter:** correct — that's the web
  retrieval adapter's job; check it's registered.
- `uv run pytest scripts/tests/test_provider_registry.py` covers the catalog adapter.
