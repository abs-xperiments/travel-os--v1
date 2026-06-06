"""Offline test: the planner agent's TOOLS (not the LLM). No credentials spent.

We test the plain tool functions directly. `build_trip` resolves a destination (which would
hit the network), so here we only cover the input-validation path that returns early BEFORE any
resolve — the happy path is covered live by the destination_intelligence integration test and
the streaming smoke.

    uv run pytest scripts/tests/test_tripos_planner_tools.py
"""

from __future__ import annotations

from datetime import date

from agent.agents.tripos_planner import (
    _PROMISE_RE,
    _parse_date,
    budget_compatibility,
    build_trip,
    check_travel_season,
    list_destinations,
    rank_circuits_by_budget,
    travel_context_now,
)


def test_promise_regex_triggers_on_build_promises_not_on_questions():
    # The dead-end guard fires only when the model PROMISED to build but didn't call a tool.
    assert _PROMISE_RE.search("Great! I'll put that together for you.")
    assert _PROMISE_RE.search("Let me build that plan now.")
    assert _PROMISE_RE.search("I'm going to prepare your itinerary.")
    # ...but NOT on legitimate clarifying questions or a plan it actually delivered.
    assert not _PROMISE_RE.search("Which city are you starting from?")
    assert not _PROMISE_RE.search("Want me to suggest a few options?")
    assert not _PROMISE_RE.search("Here's your 3-day plan, ready to go!")


def test_promise_regex_with_stay_promises_is_safe_by_design():
    # A stalled stays-promise also trips the guard — INTENTIONALLY. The forced nudge
    # (_FORCE_BUILD) is intent-aware: it tells the model to call the tool serving what it
    # promised (find_stays / find_restaurants / build_trip), so a homestay promise can never
    # force an unwanted full trip build.
    assert _PROMISE_RE.search("I'll pull together some homestay options for you.")
    # Delivered recommendations (no promise verbs) never trip it.
    assert not _PROMISE_RE.search("Here are a few homestays in Didupe you'll love.")


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


async def test_build_trip_rejects_impossible_month_without_network():
    # travel_month is validated on the brief (1-12) before any resolve — offline error path.
    out = await build_trip(
        destination="Munnar",
        start_city="Chennai",
        days=3,
        group_type="couple",
        interests=["nature"],
        budget=20000,
        travel_month=13,
    )
    assert "error" in out


async def test_check_travel_season_rejects_impossible_month_without_network():
    out = await check_travel_season(destination="Dubai", month=0)
    assert "error" in out


def test_circuits_rank_by_budget_fit_not_popularity():
    from agent.tripos.models import Circuit

    def _circuit(name: str, est: float | None) -> Circuit:
        return Circuit(
            name=name, legs=[], total_nights=5, style="s", est_per_person_budget=est, why="w"
        )

    circuits = [
        _circuit("Premium Kerala", 85000),
        _circuit("Classic Kerala", 28000),
        _circuit("Mystery", None),
        _circuit("Stretch Kerala", 38000),
    ]
    ranked = rank_circuits_by_budget(circuits, budget=30000)
    assert [(c.name, label) for c, label in ranked] == [
        ("Classic Kerala", "fits"),
        ("Stretch Kerala", "stretch"),
        ("Premium Kerala", "premium"),
        ("Mystery", "unknown"),
    ]


def test_budget_compatibility_thresholds():
    assert budget_compatibility(28000, 30000) == "fits"
    assert budget_compatibility(38000, 30000) == "stretch"  # within 1.4x
    assert budget_compatibility(85000, 30000) == "premium"
    assert budget_compatibility(None, 30000) == "unknown"


async def test_build_trip_rejects_unknown_popularity_pref_without_network():
    out = await build_trip(
        destination="Munnar",
        start_city="Chennai",
        days=3,
        group_type="couple",
        interests=["nature"],
        budget=20000,
        popularity_pref="super-hidden",  # not a valid value
    )
    assert "error" in out


def test_parse_date_accepts_iso_and_never_raises():
    # Dates are an optional nicety (stored for future booking) — junk must not break a build.
    assert _parse_date("2026-12-20") == date(2026, 12, 20)
    assert _parse_date("next friday") is None
    assert _parse_date(None) is None


def test_travel_context_now_carries_todays_date_but_no_season_verdict():
    # The Travel Context Engine: the model must know TODAY so "leaving today" / "next weekend" /
    # "this December" resolve without questions — but the date must never become a season verdict.
    from agent.tripos.models import MONTH_NAMES

    today = date.today()
    text = travel_context_now()
    assert f"{today:%A}" in text  # weekday
    assert MONTH_NAMES[today.month] in text  # month name
    assert str(today.year) in text
    # Relative-date resolution rules are spelled out for the model.
    assert "next weekend" in text
    assert "this December" in text.replace('"this December"', "this December")
    # The date informs WHEN, never HOW SUITABLE — suitability stays with check_travel_season.
    assert "season check" in text


def test_package_public_surface_is_stable():
    # The package split (2026-06-06) must keep every public symbol importable from the root —
    # tripos_web.py, main.py, and these tests all rely on it.
    import agent.agents.tripos_planner as planner

    for symbol in planner.__all__:
        assert hasattr(planner, symbol), f"missing re-export: {symbol}"
    # The two consumers outside tests use exactly these:
    assert callable(planner.stream_reply)  # tripos_web.py
    assert planner.planner_agent is not None  # main.py
