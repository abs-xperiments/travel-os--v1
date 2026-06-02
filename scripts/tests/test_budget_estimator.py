"""Offline test: the budget_estimator (per-person + group). No credentials needed.

    uv run pytest scripts/tests/test_budget_estimator.py
"""

from __future__ import annotations

from agent.tripos import budget_estimator
from agent.tripos.models import BudgetBreakdown


def _sample() -> BudgetBreakdown:
    # per-person category costs
    return BudgetBreakdown(
        transport=4500, accommodation=13400, food=4500, activities=6000, misc=2000
    )


def test_per_person_total_is_the_sum_and_range_brackets_it():
    est = budget_estimator.estimate_budget(_sample())
    assert est.per_person_total == 30400
    assert est.per_person_low < est.per_person_total < est.per_person_high
    assert 50 <= est.confidence <= 95
    assert est.travelers == 1
    assert est.group_total == 30400  # 1 traveler


def test_group_total_scales_with_travelers():
    est = budget_estimator.estimate_budget(_sample(), travelers=4)
    assert est.travelers == 4
    assert est.group_total == est.per_person_total * 4


def test_over_per_person_budget_is_flagged():
    est = budget_estimator.estimate_budget(_sample(), budget=28000)  # per person
    assert any("exceed" in note.lower() for note in est.notes)


def test_within_per_person_budget_is_reassured():
    est = budget_estimator.estimate_budget(_sample(), budget=50000)  # per person
    assert any("within" in note.lower() for note in est.notes)


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
    assert est.confidence == 95  # no spread => maximally confident
