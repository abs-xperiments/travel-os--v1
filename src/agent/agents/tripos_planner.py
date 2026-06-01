"""The TripOS planner agent — the conversational AI travel consultant.

This is the only place the LLM lives. It *talks* to the traveler (gathers what they want,
explains, modifies), but it never invents facts or does the planning maths itself: for
anything concrete it calls the deterministic tools below (`list_destinations`, `build_plan`),
which are backed by the curated catalog and the tested planning modules.

The system prompt is the plain-English rulebook from docs/policy.md, condensed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from agent.services.llm import build_model
from agent.tripos import destination_catalog as catalog
from agent.tripos import destination_intelligence, trip_planner
from agent.tripos.models import Destination, GroupType, Pace, TravelStyle, TripBrief, TripPlan
from agent.tripos.provider_interfaces import slugify

SYSTEM_PROMPT = """\
You are TripOS, an expert, honest travel consultant. You can plan a trip to ANY real
destination in the world — a city, town, village, national park, island, or region.
You feel like texting a sharp, friendly guide — warm, concise, never a form.

How you work:
- Greet, and offer two ways to start: "Discover My Trip" (they don't know where) or
  "Plan a Destination" (they do).
- Gather only what's missing, ONE question at a time (never a wall of questions):
  destination (if they have one), start city, number of days, who's travelling (group),
  budget, interests, pace.
- You are NOT limited to a fixed list of places. To build a plan, call `build_trip` with the
  destination NAME (any place) plus the trip details. If the traveler doesn't know where to
  go, you may call `list_destinations` for a few popular EXAMPLE ideas to suggest — but those
  are only examples, not a limit; you can plan anywhere.
- NEVER invent attractions, durations, or prices — always get them from `build_trip`.
- Present the plan clearly: the day-by-day, the budget as a RANGE (an estimate, not a
  bookable price — real quotes come later), and the feasibility verdict, with a one-line
  "why" for the destination.
- If `build_trip` returns `feasible: false`, say so plainly and pass on its fix suggestions.
- If `build_trip` returns an `error` that the place couldn't be found, the name was likely
  misspelled or too vague — ask the user to check the spelling or name a nearby well-known
  town. That is the ONLY case where a destination can't be planned.

Hard rules: never claim anything is booked (TripOS books nothing yet); label prices as
estimates; if unsure, say so. Keep replies short and skimmable."""


def list_destinations() -> list[dict]:
    """A few popular EXAMPLE destinations to suggest when a traveler doesn't know where to go.

    This is NOT the set of places TripOS can plan — it can plan anywhere via `build_trip`.
    These are just curated suggestions with rich detail.
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


def _compact_plan(plan: TripPlan, destination: Destination) -> dict:
    """A small, token-light view of a TripPlan for the model to read and present."""
    return {
        "destination": destination.name,
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


async def build_trip(
    destination: str,
    start_city: str,
    days: int,
    group_type: str,
    interests: list[str],
    budget: float,
    pace: str = "balanced",
) -> dict:
    """Build a complete day-by-day plan + budget for a destination — ANY real place worldwide.

    Call this once you know the destination NAME and the traveler's days, group, interests and
    budget. It resolves the place (curated catalog or live web retrieval), then plans it.
    Returns the plan, or an `error` string you should relay and then fix.

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
            destination_id=slugify(destination),
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    resolved = await destination_intelligence.resolve(destination, brief)
    if resolved is None:
        return {
            "error": f"I couldn't find a place called {destination!r}. "
            "Could you check the spelling, or name a nearby well-known town?"
        }

    plan = trip_planner.plan_trip(brief, resolved)
    return _compact_plan(plan, resolved)


# balanced = Claude Sonnet (good at tool use); cheap enough for a chat. See services/llm.py.
planner_agent = Agent(build_model("balanced"), system_prompt=SYSTEM_PROMPT)
planner_agent.tool_plain(list_destinations)
planner_agent.tool_plain(build_trip)


class StreamPiece(BaseModel):
    """One item from stream_reply: an incremental text delta, or the final 'done' marker."""

    kind: str  # "delta" | "done"
    text: str = ""  # the text delta (when kind == "delta")
    messages_json: str = ""  # full serialized history (when kind == "done"), for persistence


async def stream_reply(
    message: str, message_history: list[ModelMessage]
) -> AsyncIterator[StreamPiece]:
    """Stream the planner's reply token-by-token — the preamble AND the post-tool answer.

    We use `agent.iter()` (not `run_stream()`): our agent calls the `build_trip` tool, and
    `run_stream()` alone would only stream the first model turn (the preamble), missing the
    actual plan the model writes *after* the tool returns. iterating the run lets us stream
    text from every model step. Ends with one kind="done" piece carrying the serialized
    history, so the caller can persist the turn.
    """
    async with planner_agent.iter(message, message_history=message_history) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as model_stream:
                    async for event in model_stream:
                        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                            if event.part.content:
                                yield StreamPiece(kind="delta", text=event.part.content)
                        elif isinstance(event, PartDeltaEvent) and isinstance(
                            event.delta, TextPartDelta
                        ):
                            yield StreamPiece(kind="delta", text=event.delta.content_delta)
        result = run.result
        if result is not None:
            yield StreamPiece(kind="done", messages_json=result.all_messages_json().decode())
