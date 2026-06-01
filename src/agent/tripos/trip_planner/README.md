# `trip_planner` — the "build the whole plan" module

## In one sentence
Give it a finished trip brief (where, how many days, who, budget, interests) and it returns
**one complete plan**: the chosen stops, a day-by-day schedule, a budget, and a feasibility
verdict — by calling all the other modules in the right order.

## Why it exists
The other modules each do one small job. Something has to be the **general contractor** that
calls them in sequence and hands back a single, complete result. That's this module. The AI
agent talks to the traveler and, once it knows what they want, calls `plan_trip(brief)` —
so the AI never has to do the planning maths itself (which it would get wrong).

## What it does, step by step
1. Receives an already-resolved `Destination` (from `destination_intelligence` — catalog OR
   web retrieval). It does not look anything up and never refuses: it plans whatever it's given.
2. Asks `attraction_selector` for the right stops in the right order.
3. Asks `itinerary_builder` to spread them across the days.
4. Estimates the cost via `budget_estimator`.
5. Runs `trip_feasibility_checker` for an overall realistic / not-realistic verdict.
6. Packs all of that into one `TripPlan` and returns it.

## ⚠️ About the budget numbers (important)
Right now the cost figures use **placeholder baselines** (e.g. ₹3,000/night, ₹1,200/day for
food) defined at the top of `__init__.py`. They make the budget *feel* real today, but they
are rough. They'll be replaced by proper `transport` / `accommodation` / `food` modules in a
later step. The numbers are clearly named and all in one place so they're easy to swap out.
(This is fine for V1 — every V1 price is an estimate anyway; real quotes come in V2.)

## How to debug it (if a plan looks wrong)
- **The plan is empty or missing obvious stops:** that's an `attraction_selector` question.
- **Days look unbalanced:** that's `itinerary_builder`.
- **The cost seems off:** check the placeholder baselines at the top of this file (until the
  composer modules replace them).
- **A place can't be planned at all:** that's decided upstream — `destination_intelligence`
  returns None only when a place can't be identified; the agent handles that. trip_planner
  itself always plans the destination it's handed.
- **Run it in isolation:** `uv run pytest scripts/tests/test_trip_planner.py` (no AI, no keys).

## What it deliberately does NOT do
It doesn't talk to the user, ask questions, or call the AI — that's the agent's job
(`agents/tripos_planner.py`). It only assembles a plan from a brief that's already complete.
