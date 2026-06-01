# `trip_feasibility_checker` — the "is this trip even possible?" module

## In one sentence
This module is the **reality check**: given the places someone wants to visit and how
many days they have, it works out whether that's actually doable — and if not, by how much
and how to fix it.

## Why it exists
The single most useful thing an expert travel agent does is stop you from planning a trip
that can't happen — "you can't see 18 places in 2 days, that's not real." An AI left to
itself will cheerfully agree to anything. This module is the honest voice that does the
arithmetic, so TripOS never hands someone a fantasy schedule.

## What it does, step by step
1. **Adds up the time needed:** for every chosen attraction it counts the time spent there
   *plus* about an hour of local travel/getting-organised around each stop.
2. **Works out the time available:** a day isn't 24 hours of sightseeing — it assumes about
   **8 usable hours** per full day, and treats the arrival and departure days as half-days
   (because you're travelling). So 2 days ≈ one full sightseeing day; 5 days ≈ four.
3. **Compares the two** and returns a clear verdict (`realistic: true/false`) with the
   numbers spelled out in plain English.
4. **If it doesn't fit,** it suggests two concrete fixes: roughly how many more *days* would
   make it work, or roughly how many *low-priority stops* to drop (it drops the
   lowest-"worth visiting" ones first).

## The knobs you can turn
At the top of `__init__.py` are two clearly-named numbers:
- `HOURS_PER_FULL_DAY` (default **8**) — how many hours of real sightseeing fit in a day.
- `TRAVEL_BUFFER_HOURS_PER_STOP` (default **1**) — travel/setup time around each stop.

If trips feel too rushed or too empty, these are the dials to adjust. Nothing else needs to
change.

## How to debug it (if a verdict looks wrong)
- **It says something is unrealistic but you disagree:** read the `reasons` it returns —
  they show the exact "needs X hours vs Y available" maths. Usually the fix is one of the
  two knobs above, or an attraction's `duration_hours` in the catalog being off.
- **It calls an obviously packed plan realistic:** check the number of `days` passed in and
  the attractions' `duration_hours` in `destination_catalog/data/`. Garbage in, garbage out.
- **Run it in isolation:** `uv run pytest scripts/tests/test_trip_feasibility_checker.py`.
  The tests use real Munnar data, so they're a good template for trying your own cases.

## What it deliberately does NOT do
It doesn't know about opening hours, distances between towns, or weather — that's other
modules' jobs (`itinerary`, `weather`). It only answers the time-vs-days question, on
purpose, so it stays simple and easy to trust.
