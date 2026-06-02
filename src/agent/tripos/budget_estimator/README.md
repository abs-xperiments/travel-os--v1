# `budget_estimator` — the "what will this actually cost?" module

## In one sentence
This module takes the **per-person** cost of each part of a trip (travel, stay, food,
activities, extras) and turns it into one clear **per-person** estimate **plus an honest
range**, multiplies by the number of travelers for a **group total**, and warns you if the
per-person cost is heading over the per-person budget.

## Per-person is primary
TripOS thinks in **per-person budget** by default (it's how travelers compare trips). The
per-person figure is the headline; the group total is `per_person × travelers`. Inputs to this
module (the `BudgetBreakdown`) are per-person, and the budget it checks against is per-person.

## Why it exists
Two reasons. First, travelers hate surprises: a single guessed number ("₹32,000") pretends
to a precision nobody has. A *range* ("₹30,000–₹37,000") is honest. Second, in V1 we don't
do real bookings, so every price is an **estimate** — this module is where that honesty is
made visible. (Real, exact quotes come in V2 when drivers and hotels respond.)

## What it does, step by step
1. **Adds up the categories:** transport + accommodation + food + activities + misc = total.
2. **Builds a range:** each category swings by a different amount, so it widens each by a
   realistic percentage and adds them up to get a **low** and **high** figure. Accommodation
   swings most (prices jump in peak season); "misc" is the least predictable.
3. **Scores its confidence (0–100):** the tighter the range is relative to the total, the
   higher the confidence. A trip that's mostly volatile accommodation gets a lower score.
4. **Checks the budget (optional):** if you tell it the traveler's budget, it adds a plain
   note — either "comfortably within" or "heads up, this could exceed it".

## The knobs you can turn
At the top of `__init__.py`, `CATEGORY_UNCERTAINTY` lists how much each category can swing
(e.g. accommodation `0.20` = ±20%). If your estimates feel too tight or too loose, adjust
these percentages — that's the only place the range logic lives.

## How to debug it (if a number looks wrong)
- **The total is wrong:** the total is just the sum of what's passed in. Check the
  `BudgetBreakdown` the composer modules produced — the bug is almost always upstream, in
  what they estimated, not here.
- **The range feels too wide or too narrow:** that's the `CATEGORY_UNCERTAINTY` percentages.
- **Confidence seems off:** it's derived purely from how wide the range is versus the total;
  a very accommodation-heavy trip will (correctly) score lower.
- **Run it in isolation:** `uv run pytest scripts/tests/test_budget_estimator.py`.

## What it deliberately does NOT do
It doesn't *decide* the costs — it only totals and ranges the numbers other modules give it.
Keeping it a pure calculator makes it trivial to test and trust.
