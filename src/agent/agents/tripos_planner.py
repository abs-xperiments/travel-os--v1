"""The TripOS planner agent — the conversational AI travel consultant.

This is the only place the LLM lives. It *talks* to the traveler (gathers what they want,
explains, modifies), but it never invents facts or does the planning maths itself: for
anything concrete it calls the deterministic tools below (`list_destinations`, `build_plan`),
which are backed by the curated catalog and the tested planning modules.

The system prompt is the plain-English rulebook from docs/policy.md, condensed.
"""

from __future__ import annotations

from pydantic import ValidationError
from pydantic_ai import Agent

from agent.services.llm import build_model
from agent.tripos import destination_catalog as catalog
from agent.tripos import trip_planner
from agent.tripos.models import GroupType, Pace, TravelStyle, TripBrief, TripPlan

SYSTEM_PROMPT = """\
You are TripOS, an expert, honest travel consultant for South Indian hill stations.
You feel like texting a sharp, friendly guide — warm, concise, never a form.

How you work:
- Greet, and offer two ways to start: "Discover My Trip" (they don't know where) or
  "Plan a Destination" (they do).
- Gather only what's missing, ONE question at a time (never a wall of questions):
  start city, number of days, who's travelling (group), budget, interests, pace.
- You ONLY cover the destinations returned by the `list_destinations` tool. If the user
  asks for somewhere else (e.g. Goa), say so honestly and offer the closest covered option.
  If they don't know where to go, use `list_destinations` and recommend 2–3 that fit their
  budget/days/interests, each with a one-line reason.
- When you know destination + days + group + interests + budget, call `build_plan` to build
  the actual day-by-day plan and budget. NEVER invent attractions, durations, or prices —
  always get them from the tools.
- Present the plan clearly: the day-by-day, the budget as a RANGE (it's an estimate, not a
  bookable price — real quotes come later), and the feasibility verdict. Give a one-line
  "why" for the destination.
- If `build_plan` returns `feasible: false`, tell the user plainly and pass on its fix
  suggestions. If it returns an `error`, relay it honestly and adjust.

Hard rules: never claim anything is booked (TripOS books nothing yet); label prices as
estimates; if unsure, say so. Keep replies short and skimmable."""


def list_destinations() -> list[dict]:
    """List the destinations TripOS can plan (its V1 scope).

    Use this for discovery, and to check a destination is supported before planning.
    """
    return [
        {
            "id": d.id,
            "name": d.name,
            "state": d.state,
            "good_for": [s.value for s in d.good_for],
            "summary": d.description,
        }
        for d in catalog.list_destinations()
    ]


def _compact_plan(plan: TripPlan) -> dict:
    """A small, token-light view of a TripPlan for the model to read and present."""
    destination = catalog.get_destination(plan.destination_id)
    return {
        "destination": destination.name if destination else plan.destination_id,
        "days": plan.itinerary.days,
        "feasible": plan.feasibility.realistic,
        "feasibility_reasons": plan.feasibility.reasons,
        "feasibility_suggestions": plan.feasibility.suggestions,
        "budget": {
            "total": plan.budget.total,
            "low": plan.budget.low,
            "high": plan.budget.high,
            "confidence": plan.budget.confidence,
            "notes": plan.budget.notes,
        },
        "itinerary": [
            {
                "day": d.day,
                "title": d.title,
                "stops": [a.name for a in d.attractions],
                "notes": d.notes,
            }
            for d in plan.itinerary.day_plans
        ],
    }


def build_plan(
    destination_id: str,
    start_city: str,
    days: int,
    group_type: str,
    interests: list[str],
    budget: float,
    pace: str = "balanced",
) -> dict:
    """Build a complete day-by-day plan + budget for ONE destination.

    Call this once you know the destination and the traveler's days, group, interests and
    budget. Returns the plan, or an `error` string you should relay and then fix.

    Allowed values:
    - group_type: solo, couple, friends, family, family_with_children, family_with_seniors
    - interests: nature, adventure, food, relaxation, photography, road_trip, backpacking,
      luxury, sightseeing
    - pace: relaxed, balanced, packed
    """
    try:
        brief = TripBrief(
            start_city=start_city,
            days=days,
            budget=budget,
            group_type=GroupType(group_type),
            interests=[TravelStyle(i) for i in interests],
            pace=Pace(pace),
            destination_id=destination_id,
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    try:
        plan = trip_planner.plan_trip(brief)
    except ValueError as exc:
        return {"error": str(exc)}

    return _compact_plan(plan)


# balanced = Claude Sonnet (good at tool use); cheap enough for a chat. See services/llm.py.
planner_agent = Agent(build_model("balanced"), system_prompt=SYSTEM_PROMPT)
planner_agent.tool_plain(list_destinations)
planner_agent.tool_plain(build_plan)
