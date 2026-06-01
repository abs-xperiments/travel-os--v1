"""Offline test: the planner agent's TOOLS (not the LLM). No credentials spent.

These are the plain functions the agent calls. We test them directly so we never pay for a
model call to check the wiring.

    uv run pytest scripts/tests/test_tripos_planner_tools.py
"""

from __future__ import annotations

from agent.agents.tripos_planner import build_plan, list_destinations


def test_list_destinations_includes_munnar():
    assert any(d["id"] == "munnar" for d in list_destinations())


def test_build_plan_happy_path():
    out = build_plan(
        destination_id="munnar",
        start_city="Chennai",
        days=5,
        group_type="family_with_seniors",
        interests=["nature", "photography"],
        budget=50000,
        pace="relaxed",
    )
    assert "error" not in out
    assert out["destination"] == "Munnar"
    assert len(out["itinerary"]) == 5
    assert out["budget"]["low"] <= out["budget"]["total"] <= out["budget"]["high"]


def test_build_plan_rejects_unknown_group_type():
    out = build_plan(
        destination_id="munnar",
        start_city="Chennai",
        days=3,
        group_type="aliens",
        interests=["nature"],
        budget=20000,
    )
    assert "error" in out


def test_build_plan_rejects_out_of_scope_destination():
    out = build_plan(
        destination_id="goa",
        start_city="Chennai",
        days=3,
        group_type="couple",
        interests=["nature"],
        budget=20000,
    )
    assert "error" in out
