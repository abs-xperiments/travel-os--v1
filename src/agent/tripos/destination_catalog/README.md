# `destination_catalog` — the trip facts library

## In one sentence
This module is TripOS's **fact library**: it holds the hand-checked information about each
destination (like Munnar) and the things to do there, and hands it to the rest of the app
in a clean, reliable form.

## Why it exists
An AI model, left to its own memory, will happily *invent* an attraction, a price, or an
opening time — confidently and wrongly. To stop that, TripOS keeps its own small,
**curated** set of facts that we control. Every other part of the app (the budget
calculator, the itinerary builder, the planner) asks **this** module for facts instead of
asking the AI. That single rule is what keeps the app trustworthy.

## What's inside this folder
- **`data/`** — the facts themselves, as plain JSON files, **one file per destination**
  (e.g. `munnar.json`). This is the part you'll edit most. It's stored as text in the
  repo so changes are easy to see, review, and undo.
- **`__init__.py`** — the code (Python keeps a folder's main code in a file called
  `__init__.py`). It reads the JSON, checks every field is valid, and offers four simple
  functions.

## What it does, step by step
1. On first use, it reads **every** `*.json` file in `data/`.
2. It **validates** each one against the rules in `../models.py` (e.g. "a duration must be
   a positive number", "a score must be 1–10"). A bad file fails loudly here, not later.
3. It keeps the result in memory (cached) so repeated lookups are instant.
4. It answers four questions for the rest of the app:
   - `list_destinations()` → all destinations we cover.
   - `get_destination("munnar")` → one destination (or `None` if we don't cover it).
   - `get_attractions("munnar")` → that destination's things to do.

## How to add or change a destination
Edit or add a JSON file in `data/`. Match the shape of `munnar.json` exactly. Every field
listed in `Destination` / `Attraction` in `../models.py` must be present and the right
type. That's the whole process — no code change needed.

## How to debug it (if something looks wrong)
- **A new/edited destination won't load, or you see a "validation error":** the JSON
  doesn't match the model. Run `uv run pytest scripts/tests/test_destination_catalog.py` —
  the error names the exact file and field (e.g. `duration_hours: must be > 0`). Fix that
  field. Common slips: a missing comma, a missing field, a string where a number belongs,
  or a `good_for` value that isn't one of the allowed travel styles.
- **Your edit to a JSON file doesn't show up:** results are cached for speed. The cache is
  per-run, so just re-run the app/test — no stale data survives a restart.
- **`get_destination("goa")` returns `None`:** that's correct — Goa isn't in V1. The app
  should tell the user honestly rather than make something up.
