"""Offline test: the planner agent's TOOLS (not the LLM). No credentials spent.

We test the plain tool functions directly. `build_trip` resolves a destination (which would
hit the network), so here we only cover the input-validation path that returns early BEFORE any
resolve — the happy path is covered live by the destination_intelligence integration test and
the streaming smoke.

    uv run pytest scripts/tests/test_tripos_planner_tools.py
"""

from __future__ import annotations

from agent.agents.tripos_planner import build_trip, list_destinations


def test_list_destinations_includes_munnar():
    # list_destinations is now just example suggestions, not a limit — still includes Munnar.
    assert any(d["id"] == "munnar" for d in list_destinations())


async def test_build_trip_rejects_unknown_group_type_without_network():
    # An invalid enum fails while building the brief — before any destination resolve — so this
    # returns an error with no network call.
    out = await build_trip(
        destination="Munnar",
        start_city="Chennai",
        days=3,
        group_type="aliens",
        interests=["nature"],
        budget=20000,
    )
    assert "error" in out
