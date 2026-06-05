"""budget_estimator — turn PER-PERSON per-category costs into an honest, trustworthy estimate.

A pure, deterministic calculation (no AI, no network). Composer modules estimate per-person
category slices; this module sums them into a per-person RANGE (the primary, user-facing
figure — endpoints rounded so they never look falsely exact), derives a confidence level from
what's actually KNOWN (travel month? retrieved stay prices?), and gives a three-state verdict
against the traveler's budget (fits / slightly over / not achievable) with suggested levers.

The presentation contract (range + confidence + verdict) is permanent: future distance-aware
or live-priced composers improve the ACCURACY of the inputs, never the honesty of the format.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import math

from agent.tripos.models import BudgetBreakdown, BudgetConfidence, BudgetEstimate, BudgetFit

# How much each category typically swings, as a fraction. Accommodation moves most (season),
# misc is the least predictable. Kept here so the assumptions are easy to see and tweak.
CATEGORY_UNCERTAINTY: dict[str, float] = {
    "transport": 0.10,
    "accommodation": 0.20,
    "food": 0.15,
    "activities": 0.10,
    "misc": 0.25,
}

# With no travel month, seasonal pricing can swing widely — widen every category's band.
_UNKNOWN_MONTH_WIDENING = 1.5

# Range endpoints are rounded to this increment — "₹19,000–₹26,000", never "₹18,835–₹25,715".
ROUND_TO = 500

# Over this multiple of the budget (at the LOW end of the range), no realistic lever fixes it.
_NOT_ACHIEVABLE_FACTOR = 1.4

_SLIGHTLY_OVER_LEVERS = [
    "choose simpler stays",
    "trim a day off the trip",
    "drop a premium activity or two",
]
_NOT_ACHIEVABLE_LEVERS = [
    "raise the budget",
    "pick a closer or more affordable destination",
    "shorten the trip",
]


def _confidence(month_known: bool, stays_retrieved: bool) -> tuple[BudgetConfidence, str]:
    """Confidence reflects what we actually know — never the spread of our own guesses."""
    if month_known and stays_retrieved:
        return (
            BudgetConfidence.high,
            "Travel month known and stay prices retrieved for this destination; "
            "transport and food are typical-pattern estimates.",
        )
    if stays_retrieved:
        return (
            BudgetConfidence.medium,
            "Stay prices are retrieved, but without a travel month seasonal pricing "
            "can move the total.",
        )
    if month_known:
        return (
            BudgetConfidence.medium,
            "Travel month is known, but stay prices are typical averages, not retrieved rates.",
        )
    return (
        BudgetConfidence.low,
        "Travel month and destination-specific prices aren't known yet — "
        "seasonal pricing can swing widely.",
    )


def _fit(total: float, low: float, budget: float) -> tuple[BudgetFit, list[str]]:
    """Three-state verdict vs the budget, with the levers that match the situation."""
    if total <= budget:
        return BudgetFit.fits, []
    if low <= budget * _NOT_ACHIEVABLE_FACTOR:
        return BudgetFit.slightly_over, list(_SLIGHTLY_OVER_LEVERS)
    return BudgetFit.not_achievable, list(_NOT_ACHIEVABLE_LEVERS)


def estimate_budget(
    breakdown: BudgetBreakdown,
    budget: float | None = None,
    travelers: int = 1,
    *,
    month_known: bool = False,
    stays_retrieved: bool = False,
    extra_notes: list[str] | None = None,
) -> BudgetEstimate:
    """Total PER-PERSON categories into an honest range + confidence + budget-fit verdict.

    `breakdown` holds PER-PERSON category costs. `budget` is the traveler's PER-PERSON budget.
    `month_known` / `stays_retrieved` describe the real knowledge state and drive both the
    confidence level and (month unknown) a wider range. `extra_notes` lets the caller surface
    decisions it made (e.g. "stays picked at the budget tier to fit your budget").
    """
    by_category = breakdown.model_dump()
    per_person_total = sum(by_category.values())

    widen = 1.0 if month_known else _UNKNOWN_MONTH_WIDENING
    low = sum(
        amount * (1 - CATEGORY_UNCERTAINTY[name] * widen) for name, amount in by_category.items()
    )
    high = sum(
        amount * (1 + CATEGORY_UNCERTAINTY[name] * widen) for name, amount in by_category.items()
    )
    # Honest endpoints: floor the low, ceil the high — the range never narrows by rounding.
    low = math.floor(max(low, 0) / ROUND_TO) * ROUND_TO
    high = math.ceil(high / ROUND_TO) * ROUND_TO

    level, reason = _confidence(month_known, stays_retrieved)

    fit: BudgetFit | None = None
    adjustments: list[str] = []
    if budget is not None:
        fit, adjustments = _fit(per_person_total, low, budget)

    notes: list[str] = list(extra_notes or [])
    notes.append(
        "Figures are PER PERSON, based on "
        + ("retrieved stay prices" if stays_retrieved else "typical stay rates")
        + " and typical transport/food patterns; actual costs vary with dates, "
        "availability and seasonal demand."
    )

    return BudgetEstimate(
        by_category=by_category,
        per_person_total=round(per_person_total),
        per_person_low=low,
        per_person_high=high,
        travelers=travelers,
        group_total=round(per_person_total * travelers),
        confidence_level=level,
        confidence_reason=reason,
        fit=fit,
        adjustments=adjustments,
        notes=notes,
    )
