"""Offline tests: the questionnaire bank + the request_trip_details tool. No network.

The contract under test: the model decides WHAT is missing, but deterministic code owns the
UI — unknown field names drop harmlessly, known fields are echoed (display-only), branching
children carry show_when, and the tool degrades to ask-in-text when no form channel exists.

    uv run pytest scripts/tests/test_questionnaire.py
"""

from __future__ import annotations

import asyncio
import json

from agent.agents.tripos_planner import progress
from agent.agents.tripos_planner import questionnaire as qn
from agent.agents.tripos_planner.pieces import StreamPiece


def test_build_spec_includes_only_missing_fields():
    spec = qn.build_spec(
        known={"destination": "Coorg", "duration": "4 days", "travelers": "2 people"},
        missing=["travel_when", "budget", "interests"],
    )
    assert [q["field"] for q in spec["questions"]] == ["travel_when", "budget", "interests"]
    assert spec["header"] == "Got it so far: Coorg · 4 days · 2 people"


def test_build_spec_drops_unknown_fields_silently():
    # A model typo must omit a question, never break the form (validation is load-bearing).
    spec = qn.build_spec(known={}, missing=["budget", "favourite_colour", "interests"])
    assert [q["field"] for q in spec["questions"]] == ["budget", "interests"]


def test_style_question_carries_branching_children():
    spec = qn.build_spec(known={}, missing=["style"])
    children = spec["questions"][0]["children"]
    by_field = {c["field"]: c for c in children}
    assert by_field["self_drive"]["show_when"] == ["Road trip"]
    assert by_field["max_driving_hours"]["show_when"] == ["Road trip"]
    assert by_field["resort_pref"]["show_when"] == ["Luxury"]
    assert by_field["hostel_ok"]["show_when"] == ["Budget travel"]


def test_known_style_pulls_branch_questions_top_level_without_reasking_style():
    # "We want a road trip to Coorg" — style is KNOWN, so its follow-ups are asked directly.
    spec = qn.build_spec(known={"style": "road trip"}, missing=["budget"], style="Road Trip")
    fields = [q["field"] for q in spec["questions"]]
    assert "style" not in fields
    assert fields == ["budget", "self_drive", "max_driving_hours"]
    assert all("show_when" not in q for q in spec["questions"])  # top-level, branch chosen


def test_budget_is_typed_input_with_preset_shortcuts():
    # User note (2026-06-07): budget must be TYPED; presets are only shortcuts.
    spec = qn.build_spec(known={}, missing=["budget"])
    q = spec["questions"][0]
    assert q["type"] == "budget"
    assert q["presets"]  # shortcuts exist…
    assert q["placeholder"]  # …but the typed input is primary


def test_interests_are_multi_select():
    # User note (2026-06-07): interests chosen by taps, multiple allowed.
    spec = qn.build_spec(known={}, missing=["interests"])
    assert spec["questions"][0]["type"] == "multi"
    assert spec["questions"][0]["allow_other"] is True


async def test_tool_falls_back_to_text_when_no_form_channel(monkeypatch):
    # CLI / plain agent runs: no reporter -> instruct the model to ask in text. Never raises.
    monkeypatch.setattr(qn, "_prewarm_destination", lambda d: None)
    out = await qn.request_trip_details(known={"destination": "Coorg"}, missing=["budget"])
    assert "Ask the missing details" in out


async def test_tool_emits_exactly_one_form_piece_and_prewarms(monkeypatch):
    prewarmed: list[str] = []
    monkeypatch.setattr(qn, "_prewarm_destination", prewarmed.append)

    queue: asyncio.Queue[StreamPiece] = asyncio.Queue()
    _, token = progress.activate(queue)
    try:
        out = await qn.request_trip_details(
            known={"destination": "Coorg", "duration": "4 days"},
            missing=["travel_when", "budget"],
        )
    finally:
        progress.deactivate(token)

    assert "questionnaire" in out.lower()
    assert "Do NOT ask any questions in text" in out
    assert prewarmed == ["Coorg"]  # retrieval starts while the traveler fills the form

    pieces = []
    while not queue.empty():
        pieces.append(queue.get_nowait())
    forms = [p for p in pieces if p.kind == "form"]
    assert len(forms) == 1
    spec = json.loads(forms[0].text)
    assert [q["field"] for q in spec["questions"]] == ["travel_when", "budget"]
    assert spec["header"].startswith("Got it so far: Coorg")


async def test_tool_with_no_valid_fields_tells_model_to_use_defaults(monkeypatch):
    monkeypatch.setattr(qn, "_prewarm_destination", lambda d: None)
    out = await qn.request_trip_details(known={}, missing=["not_a_field"])
    assert "defaults" in out.lower()


async def test_tool_skips_prewarm_without_destination(monkeypatch):
    prewarmed: list[str] = []
    monkeypatch.setattr(qn, "_prewarm_destination", prewarmed.append)
    await qn.request_trip_details(known={"duration": "4 days"}, missing=["budget"])
    assert prewarmed == []
