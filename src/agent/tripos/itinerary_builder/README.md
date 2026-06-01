# `itinerary_builder` — the "what do we do on each day?" module

## In one sentence
This module takes the chosen stops and spreads them across the trip's days into a realistic
day-by-day schedule.

## Why it exists
Knowing *which* places to visit isn't a plan yet — you need to know *when*. A good schedule
doesn't cram everything into day one, and it remembers that the day you arrive and the day
you leave are mostly travel. This module turns a list of stops into an actual Day 1 / Day 2
/ … plan a traveler can follow.

## What it does, step by step
1. **Works out each day's capacity.** A full day holds about 8 usable hours (it borrows that
   number from `trip_feasibility_checker`, so the whole app agrees). The **arrival** day and
   **departure** day are treated as half-days because of travel. A "packed" pace stretches
   each day a little; "relaxed" trims it.
2. **Fills days in order.** It walks the stops (already ordered by `attraction_selector`) and
   keeps adding them to the current day until it's full, then moves to the next day.
3. **Labels each day** ("Arrival in Munnar", "Exploring Munnar", "Departure from Munnar") and
   adds a friendly note on the arrival and departure days.
4. **Never silently drops a stop.** If something doesn't fit (rare, because stops were chosen
   to fit), it lands on the last day with a "schedule is tight" note instead of disappearing.

## How the pieces connect
It reuses `trip_feasibility_checker`'s hour assumptions (one source of truth for "how long is
a day") and consumes the ordered list from `attraction_selector`. Build order matters: those
existed first.

## How to debug it (if a schedule looks off)
- **A day looks too full or too empty:** check the `pace` passed in and the stops'
  `duration_hours` in the catalog. The capacity rule lives in `_day_capacity` — adjust the
  half-day assumption or pace factors there.
- **Arrival/departure days have too much:** confirm `days` is right; for a 1-day trip there's
  only a single half-day on purpose.
- **A stop you expected isn't anywhere:** that's an `attraction_selector` question (it chooses
  the stops) — this module only places whatever it's given.
- **Run it in isolation:** `uv run pytest scripts/tests/test_itinerary_builder.py`.

## What it deliberately does NOT do
It doesn't choose the stops, cost them, or check the weather. It only arranges a given list
into days — one job, easy to test.
