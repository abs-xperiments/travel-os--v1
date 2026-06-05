# `budget_estimator` — the "what will this actually cost?" module

## In one sentence
This module takes the **per-person** cost of each part of a trip (travel, stay, food,
activities, extras) and turns it into an honest **per-person range** (rounded endpoints —
the primary, user-facing figure), a **confidence level** derived from what's actually known,
and a three-state **budget-fit verdict** (fits / slightly over / not achievable) with
suggested levers when over.

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
1. **Adds up the categories:** transport + accommodation + food + activities + misc = total
   (kept internal — the RANGE is what travelers see, never a falsely exact total).
2. **Builds a range:** each category swings by a different amount, so it widens each by a
   realistic percentage and adds them up to get a **low** and **high** figure. Accommodation
   swings most (prices jump in peak season); "misc" is the least predictable. With **no travel
   month**, every band widens further (seasonal pricing unknown). Endpoints are **rounded**
   (low floored, high ceiled, to ₹500) so "₹18,835" can never appear.
3. **Derives confidence from what's actually known** (never from the spread of its own
   guesses): travel month known **and** stay prices retrieved → high; one of the two →
   medium; neither → low. The reason is stated alongside, and shown to the traveler.
4. **Gives a budget-fit verdict (optional):** given the traveler's budget — `fits` (total
   within), `slightly_over` (over, but the usual levers fix it), or `not_achievable` (even
   the LOW end is >1.4× the budget), each with matching suggested adjustments. The agent
   turns a non-fitting verdict into an advisory *before* presenting the plan as final.

## The knobs you can turn
At the top of `__init__.py`, `CATEGORY_UNCERTAINTY` lists how much each category can swing
(e.g. accommodation `0.20` = ±20%). If your estimates feel too tight or too loose, adjust
these percentages — that's the only place the range logic lives.

## How to debug it (if a number looks wrong)
- **The total is wrong:** the total is just the sum of what's passed in. Check the
  `BudgetBreakdown` the composer modules produced — the bug is almost always upstream, in
  what they estimated, not here.
- **The range feels too wide or too narrow:** that's the `CATEGORY_UNCERTAINTY` percentages
  (and `_UNKNOWN_MONTH_WIDENING` when no month was given).
- **Confidence seems off:** it reflects the inputs' knowledge flags (`month_known`,
  `stays_retrieved`) — check what the caller passed, not the maths here.
- **Verdict seems harsh/lenient:** the thresholds live in `_fit()` (`_NOT_ACHIEVABLE_FACTOR`).
- **Run it in isolation:** `uv run pytest scripts/tests/test_budget_estimator.py`.

## What it deliberately does NOT do
It doesn't *decide* the costs — it only totals and ranges the numbers other modules give it.
Keeping it a pure calculator makes it trivial to test and trust.
