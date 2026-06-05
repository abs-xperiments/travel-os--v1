"""Offline test: the budget_estimator (ranges, confidence, budget-fit verdict). No credentials.

uv run pytest scripts/tests/test_budget_estimator.py
"""

from __future__ import annotations

from agent.tripos import budget_estimator
from agent.tripos.models import BudgetBreakdown, BudgetConfidence, BudgetFit


def _sample() -> BudgetBreakdown:
    # per-person category costs
    return BudgetBreakdown(
        transport=4500, accommodation=13400, food=4500, activities=6000, misc=2000
    )


def test_per_person_total_is_the_sum_and_range_brackets_it():
    est = budget_estimator.estimate_budget(_sample())
    assert est.per_person_total == 30400
    assert est.per_person_low < est.per_person_total < est.per_person_high
    assert est.travelers == 1
    assert est.group_total == 30400  # 1 traveler


def test_range_endpoints_are_rounded_never_falsely_precise():
    est = budget_estimator.estimate_budget(_sample())
    assert est.per_person_low % budget_estimator.ROUND_TO == 0
    assert est.per_person_high % budget_estimator.ROUND_TO == 0


def test_unknown_month_widens_the_range():
    known = budget_estimator.estimate_budget(_sample(), month_known=True)
    unknown = budget_estimator.estimate_budget(_sample(), month_known=False)
    assert (unknown.per_person_high - unknown.per_person_low) > (
        known.per_person_high - known.per_person_low
    )


def test_confidence_reflects_what_is_actually_known():
    # high: month + retrieved stay prices; medium: one of the two; low: neither.
    high = budget_estimator.estimate_budget(_sample(), month_known=True, stays_retrieved=True)
    assert high.confidence_level is BudgetConfidence.high
    med1 = budget_estimator.estimate_budget(_sample(), month_known=True)
    med2 = budget_estimator.estimate_budget(_sample(), stays_retrieved=True)
    assert med1.confidence_level is BudgetConfidence.medium
    assert med2.confidence_level is BudgetConfidence.medium
    low = budget_estimator.estimate_budget(_sample())
    assert low.confidence_level is BudgetConfidence.low
    for est in (high, med1, med2, low):
        assert est.confidence_reason  # the WHY is always stated


def test_fit_verdict_three_states():
    # total 30400: fits a 50k budget; slightly over a 28k one; not achievable on 15k.
    fits = budget_estimator.estimate_budget(_sample(), budget=50000)
    assert fits.fit is BudgetFit.fits and not fits.adjustments
    over = budget_estimator.estimate_budget(_sample(), budget=28000)
    assert over.fit is BudgetFit.slightly_over and over.adjustments
    nope = budget_estimator.estimate_budget(_sample(), budget=15000, month_known=True)
    assert nope.fit is BudgetFit.not_achievable
    assert any("budget" in a or "destination" in a for a in nope.adjustments)


def test_no_budget_means_no_verdict():
    est = budget_estimator.estimate_budget(_sample())
    assert est.fit is None and not est.adjustments


def test_extra_notes_surface_planner_decisions():
    est = budget_estimator.estimate_budget(
        _sample(), extra_notes=["Stays picked at the budget tier to fit your budget."]
    )
    assert any("budget tier" in n for n in est.notes)


def test_group_total_scales_with_travelers():
    est = budget_estimator.estimate_budget(_sample(), travelers=4)
    assert est.travelers == 4
    assert est.group_total == est.per_person_total * 4


def test_notes_state_figures_are_per_person():
    est = budget_estimator.estimate_budget(_sample())
    assert any("per person" in note.lower() for note in est.notes)


def test_zero_breakdown_is_safe():
    est = budget_estimator.estimate_budget(
        BudgetBreakdown(transport=0, accommodation=0, food=0, activities=0), travelers=3
    )
    assert est.per_person_total == 0
    assert est.per_person_low == 0 and est.per_person_high == 0
    assert est.group_total == 0
