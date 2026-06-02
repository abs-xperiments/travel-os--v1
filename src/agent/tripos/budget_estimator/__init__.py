"""budget_estimator — turn PER-PERSON per-category costs into a per-person estimate + group total.

A pure, deterministic calculation (no AI, no network). Composer modules estimate per-person
category slices; this module sums them into a PER-PERSON total (the primary figure), widens
each by how uncertain that category usually is for a range, scores confidence, multiplies by
the traveler count for a group total, and — if a per-person budget is given — says whether it fits.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from agent.tripos.models import BudgetBreakdown, BudgetEstimate

# How much each category typically swings, as a fraction. Accommodation moves most (season),
# misc is the least predictable. Kept here so the assumptions are easy to see and tweak.
CATEGORY_UNCERTAINTY: dict[str, float] = {
    "transport": 0.10,
    "accommodation": 0.20,
    "food": 0.15,
    "activities": 0.10,
    "misc": 0.25,
}


def estimate_budget(
    breakdown: BudgetBreakdown, budget: float | None = None, travelers: int = 1
) -> BudgetEstimate:
    """Total PER-PERSON categories into a per-person estimate (+ range) and a group total.

    `breakdown` holds PER-PERSON category costs. `budget`, if given, is the traveler's
    PER-PERSON budget. `travelers` scales the per-person total into the group total.
    """
    by_category = breakdown.model_dump()
    per_person_total = sum(by_category.values())

    low = sum(amount * (1 - CATEGORY_UNCERTAINTY[name]) for name, amount in by_category.items())
    high = sum(amount * (1 + CATEGORY_UNCERTAINTY[name]) for name, amount in by_category.items())

    # Tighter relative range => higher confidence. Clamped to a sensible 50–95.
    spread = (high - low) / per_person_total if per_person_total > 0 else 0.0
    confidence = max(50, min(95, round(95 - spread * 100)))

    notes: list[str] = [
        "Figures are PER PERSON. Accommodation varies most with season; misc is least predictable."
    ]
    if budget is not None:
        if high > budget:
            notes.append(
                f"Heads up: the per-person cost could exceed your ₹{budget:,.0f}/person budget "
                f"(up to ₹{high:,.0f}/person)."
            )
        elif per_person_total <= budget:
            notes.append(f"Comfortably within your ₹{budget:,.0f}/person budget.")

    return BudgetEstimate(
        by_category=by_category,
        per_person_total=round(per_person_total),
        per_person_low=round(low),
        per_person_high=round(high),
        travelers=travelers,
        group_total=round(per_person_total * travelers),
        confidence=confidence,
        notes=notes,
    )
