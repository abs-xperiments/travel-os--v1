"""Offline test: the budget_estimator, in isolation. No credentials needed.

uv run pytest scripts/tests/test_budget_estimator.py
"""

from __future__ import annotations

from agent.tripos import budget_estimator
from agent.tripos.models import BudgetBreakdown


def _sample() -> BudgetBreakdown:
    return BudgetBreakdown(
        transport=4500, accommodation=13400, food=4500, activities=6000, misc=2000
    )


def test_total_is_the_sum_and_range_brackets_it():
    est = budget_estimator.estimate_budget(_sample())
    assert est.total == 30400
    assert est.low < est.total < est.high
    assert 50 <= est.confidence <= 95


def test_over_budget_is_flagged():
    est = budget_estimator.estimate_budget(_sample(), budget=28000)
    assert any("exceed" in note.lower() for note in est.notes)


def test_within_budget_is_reassured():
    est = budget_estimator.estimate_budget(_sample(), budget=50000)
    assert any("within" in note.lower() for note in est.notes)


def test_zero_budget_breakdown_is_safe():
    est = budget_estimator.estimate_budget(
        BudgetBreakdown(transport=0, accommodation=0, food=0, activities=0)
    )
    assert est.total == 0
    assert est.low == 0 and est.high == 0
    assert est.confidence == 95  # no spread => maximally confident
