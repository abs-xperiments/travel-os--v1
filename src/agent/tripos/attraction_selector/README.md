# `attraction_selector` — the "which places, and in what order?" module

## In one sentence
Given a destination and what the traveler wants, this module **picks the best stops that
actually fit the trip** and puts them in a sensible visiting order.

## Why it exists
A destination has many attractions; a real trip can only include some of them. A good
travel agent picks the ones that match *you* (your interests, who you're travelling with)
and quietly leaves out the rest — and never overstuffs the days. This module does exactly
that, as plain logic, so the choice is consistent and explainable.

## What it does, step by step
1. **Scores every attraction** for this traveler. The score starts from the attraction's
   "worth visiting" rating, then goes **up** for matches to their interests (e.g. a
   photo-friendly spot when they like photography, an outdoor spot when they like nature)
   for matches to their interests. Stops that don't suit the group are removed entirely
   first (see step 0).
0. **Removes unsuitable stops outright (a hard filter):** for a `family_with_seniors` trip,
   anything marked `suitable_for_seniors: false` is dropped; for `family_with_children`,
   anything not `child_friendly`. Comfort for seniors/children is a promise, so the score
   can never sneak an unsuitable stop back in.
   When the travel month calls for shelter (monsoon, extreme heat — the planner passes
   `prefer_indoor=True`), indoor stops get a **soft bonus**: they out-rank comparable outdoor
   ones, but a truly outstanding outdoor stop can still make the cut. It's a bias, not a ban.
2. **Sorts** attractions best-first.
3. **Adds them one by one** — but before adding each, it asks `trip_feasibility_checker`
   "does the trip still fit?" and stops adding once it's full. This is the key idea: it can
   never pick more than the days allow.
4. **Orders the chosen stops** by base/town first (so you finish one area before moving on),
   then early-morning-to-evening, then best-first — which cuts backtracking.

## How the pieces connect
This module *uses* two others: `destination_catalog` (for the attractions and their facts)
and `trip_feasibility_checker` (to know when the trip is full). It doesn't duplicate their
logic — it leans on them. That's why those were built first.

## How to debug it (if the picks look wrong)
- **A great stop was left out:** it was either filtered out as unsuitable for the group
  (e.g. `suitable_for_seniors: false` on a seniors trip), or it didn't fit once the days
  filled up. Check the attraction's suitability flags and `duration_hours` in the catalog.
- **Too few stops chosen:** the trip is short, or stops are long — that's the feasibility
  check doing its job. Increase `days` or check `duration_hours` in the catalog.
- **Order looks odd:** see `_ordering_key` and the `best_time` values in the catalog.
- **Run it in isolation:** `uv run pytest scripts/tests/test_attraction_selector.py`.

## What it deliberately does NOT do
It doesn't split stops across specific days (that's `itinerary_builder`) and it doesn't
*decide* what the season means — it only applies the `prefer_indoor` verdict handed to it
(the judgment comes from the retrieved seasonality profile, upstream). It answers "which
stops, what order".
