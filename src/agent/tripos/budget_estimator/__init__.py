"""budget_estimator — turn per-category costs into a total and an honest range.

A pure, deterministic calculation (no AI, no network). Composer modules (transport,
accommodation, food, activities) each estimate their slice; this module sums them, widens
each by how uncertain that category usually is, and reports a total, a likely range, a
confidence score, and — if a budget is given — whether the trip fits.

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


def estimate_budget(breakdown: BudgetBreakdown, budget: float | None = None) -> BudgetEstimate:
    """Total the categories, build a likely range, score confidence, and check the budget."""
    by_category = breakdown.model_dump()
    total = sum(by_category.values())

    low = sum(amount * (1 - CATEGORY_UNCERTAINTY[name]) for name, amount in by_category.items())
    high = sum(amount * (1 + CATEGORY_UNCERTAINTY[name]) for name, amount in by_category.items())

    # Tighter relative range => higher confidence. Clamped to a sensible 50–95.
    spread = (high - low) / total if total > 0 else 0.0
    confidence = max(50, min(95, round(95 - spread * 100)))

    notes: list[str] = [
        "Accommodation usually varies most with the season; misc is least predictable."
    ]
    if budget is not None:
        if high > budget:
            notes.append(
                f"Heads up: this could exceed your ₹{budget:,.0f} budget (up to ₹{high:,.0f})."
            )
        elif total <= budget:
            notes.append(f"Comfortably within your ₹{budget:,.0f} budget.")

    return BudgetEstimate(
        by_category=by_category,
        total=round(total),
        low=round(low),
        high=round(high),
        confidence=confidence,
        notes=notes,
    )
