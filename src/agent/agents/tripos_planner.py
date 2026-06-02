"""The TripOS planner agent — the conversational AI travel consultant.

This is the only place the LLM lives. It *talks* to the traveler (gathers what they want,
explains, modifies), but it never invents facts or does the planning maths itself: for
anything concrete it calls the deterministic tools below (`list_destinations`, `build_plan`),
which are backed by the curated catalog and the tested planning modules.

The system prompt is the plain-English rulebook from docs/policy.md, condensed.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
)

from agent.services.llm import build_model
from agent.tripos import (
    circuit_discovery,
    destination_intelligence,
    trip_intelligence,
    trip_planner,
)
from agent.tripos import destination_catalog as catalog
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
  destination (if they have one), start city, number of days, who's travelling (group) and
  how many travelers, the PER-PERSON budget (ALWAYS ask for budget per traveler, never total),
  interests, pace.
- You are NOT limited to a fixed list of places. To build a plan, call `build_trip` with the
  destination NAME (any place) plus the trip details. If the traveler doesn't know where to
  go, you may call `list_destinations` for a few popular EXAMPLE ideas to suggest — but those
  are only examples, not a limit; you can plan anywhere.
- If the traveler names a REGION or country + days but not a single place (e.g. "6 days in
  Kerala"), or isn't sure which places to combine, call `discover_circuits` and present 2–4
  routes (the stops in travel order with nights each, plus why). Let them pick one, then plan a
  chosen destination from it with `build_trip`. (Auto-building a whole multi-stop circuit is
  coming soon — for now plan their chosen base.)
- NEVER invent attractions, durations, or prices — always get them from `build_trip`.
- CRITICAL — act, don't stall. Each turn, do exactly ONE of: (a) ask ONE clarifying question
  if a REQUIRED detail is still missing (destination, start city, days, group, budget,
  interests); or (b) call `build_trip` and present the plan. The moment you have all required
  details, call `build_trip` in THIS turn. NEVER reply that you'll "put it together" / "build
  it now" / "prepare that" and then stop without calling `build_trip` — that strands the user.
- Present the plan clearly: the day-by-day; the budget as a PER-PERSON range, clearly LABELLED
  "per person" (e.g. "Estimated per-person budget: ₹X–₹Y") — it's an estimate, not a bookable
  price; when the traveler count is known, ALSO show the total group cost; and the feasibility
  verdict, with a one-line "why" for the destination. Per-person is always the primary figure.
- After the itinerary, add short sections using build_trip's data: "Where to stay" (a budget /
  mid / premium pick from `stays`, each with its nightly price range labelled an estimate),
  "Where to eat" (a few `restaurants`, matched to the food preference), and "Weather" (the
  `weather` season note + any advisories). A few lines each. These are web-grounded estimates,
  not live bookings — say so. If a section's data is empty, simply skip it.
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
        "currency": "INR",
        "per_person_budget": {  # PRIMARY figure — present this, labelled "per person"
            "estimate": plan.budget.per_person_total,
            "low": plan.budget.per_person_low,
            "high": plan.budget.per_person_high,
            "confidence": plan.budget.confidence,
        },
        "travelers": plan.budget.travelers,
        "group_total_estimate": plan.budget.group_total,  # per_person × travelers
        "budget_notes": plan.budget.notes,
        "itinerary": [
            {
                "day": d.day,
                "title": d.title,
                "stops": [a.name for a in d.attractions],
                "notes": d.notes,
            }
            for d in plan.itinerary.day_plans
        ],
        # Phase 2 enrichment (web-grounded estimates, not live bookings).
        "stays": [
            {
                "name": s.name,
                "area": s.area,
                "tier": s.tier,
                "kind": s.kind,
                "price_per_night": [s.price_per_night_low, s.price_per_night_high],
                "why": s.why,
            }
            for s in plan.stays[:6]
        ],
        "restaurants": [
            {
                "name": r.name,
                "area": r.area,
                "cuisine": r.cuisine,
                "price_band": r.price_band,
                "good_for": r.good_for,
            }
            for r in plan.restaurants[:6]
        ],
        "weather": (
            {
                "summary": plan.weather.summary,
                "season": plan.weather.season_label,
                "advisories": plan.weather.advisories,
                "temps_c": [plan.weather.temp_low_c, plan.weather.temp_high_c],
            }
            if plan.weather
            else None
        ),
    }


async def build_trip(
    destination: str,
    start_city: str,
    days: int,
    group_type: str,
    interests: list[str],
    budget: float,
    pace: str = "balanced",
    travelers: int | None = None,
) -> dict:
    """Build a complete day-by-day plan + budget for a destination — ANY real place worldwide.

    Call this once you know the destination NAME and the traveler's days, group, interests and
    budget. It resolves the place (curated catalog or live web retrieval), then plans it.
    Returns the plan, or an `error` string you should relay and then fix.

    - budget: the PER-PERSON budget in the local currency (per traveler, NOT the group total).
    - travelers: the number of travelers if known (used to compute the group total); if omitted
      it's inferred from the group_type.

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
            travelers=travelers,
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    resolved = await destination_intelligence.resolve(destination, brief)
    if resolved is None:
        return {
            "error": f"I couldn't find a place called {destination!r}. "
            "Could you check the spelling, or name a nearby well-known town?"
        }

    # Enrich with stays + restaurants + weather (best-effort), and use the retrieved nightly
    # rate to make the accommodation budget real.
    enrichment = await trip_intelligence.enrich(resolved, brief)
    stay_rate = trip_planner.per_person_nightly(enrichment.stays)
    plan = trip_planner.plan_trip(brief, resolved, stay_per_person_per_night=stay_rate)
    plan = plan.model_copy(
        update={
            "stays": enrichment.stays,
            "restaurants": enrichment.restaurants,
            "weather": enrichment.weather,
        }
    )
    return _compact_plan(plan, resolved)


async def discover_circuits(
    region: str,
    nights: int,
    group_type: str,
    interests: list[str],
    budget: float,
    travelers: int | None = None,
) -> dict:
    """Suggest multi-destination routes (circuits) for a REGION and trip length.

    Use this when the traveler gives a region + days but no single destination, or doesn't know
    where to go (e.g. "6 days in Kerala"). Returns 2–4 routes (stops in order + nights each +
    why), or an `error`. budget is PER-PERSON. After they pick, plan a chosen destination with
    `build_trip`.
    """
    try:
        brief = TripBrief(
            start_city="(unspecified)",
            days=max(nights, 1),
            budget=budget,
            group_type=GroupType(group_type),
            interests=[TravelStyle(i) for i in interests],
            pace=Pace.balanced,
            travelers=travelers,
        )
    except (ValueError, ValidationError) as exc:
        return {"error": f"Invalid input: {exc}"}

    circuits = await circuit_discovery.discover(region, nights, brief)
    if not circuits:
        return {
            "error": f"I couldn't find good multi-stop routes for {region!r}. "
            "Want to name a destination directly?"
        }
    return {
        "region": region,
        "nights": nights,
        "circuits": [
            {
                "name": c.name,
                "route": [leg.destination for leg in c.legs],
                "nights_per_leg": [leg.nights for leg in c.legs],
                "total_nights": c.total_nights,
                "style": c.style,
                "est_per_person_budget": c.est_per_person_budget,
                "why": c.why,
            }
            for c in circuits
        ],
    }


# balanced = Claude Sonnet (good at tool use); cheap enough for a chat. See services/llm.py.
planner_agent = Agent(build_model("balanced"), system_prompt=SYSTEM_PROMPT)
planner_agent.tool_plain(list_destinations)
planner_agent.tool_plain(discover_circuits)
planner_agent.tool_plain(build_trip)


class StreamPiece(BaseModel):
    """One item from stream_reply.

    kind="delta": a text chunk to render. kind="status": a transient progress note shown while
    a tool runs (Issue 2). kind="done": end of the reply, carrying the serialized history.
    """

    kind: str  # "delta" | "status" | "done"
    text: str = ""  # delta text, or the status message
    messages_json: str = ""  # full serialized history (when kind == "done"), for persistence


# Shown the moment build_trip starts, to fill the silent gap while retrieval/planning runs.
_BUILD_STATUS = (
    "Building your trip…\n"
    "• Retrieving destination intelligence\n"
    "• Selecting the best stops\n"
    "• Optimising the route & days\n"
    "• Estimating the budget"
)

# Detects "I'll build it / put that together …" promises so we can force the build if the
# model stalled without calling the tool. Deliberately narrow so it won't match a question.
_PROMISE_RE = re.compile(
    r"\b(i'?ll|i will|let me|i'?m going to|give me a)\b[^.?!]*?"
    r"\b(put (it|that|this) together|prepare|build|create|generate|plan|pull together|work on)\b",
    re.IGNORECASE,
)

_FORCE_BUILD = (
    "Proceed now: call build_trip with the details already gathered and present the full plan. "
    "Do not ask anything else."
)


async def stream_reply(
    message: str, message_history: list[ModelMessage]
) -> AsyncIterator[StreamPiece]:
    """Stream the planner's reply — preamble, a progress status while tools run, then the plan.

    We use `agent.iter()` (not `run_stream()`): our agent calls `build_trip`, and `run_stream()`
    alone would only stream the first model turn, missing the plan written after the tool.

    Dead-end guard (Issue 1): if a turn ends having only PROMISED to build (no build_trip call),
    we automatically continue once with a forced nudge so the plan is produced in the same
    response — the user never has to send another message.
    """
    history = list(message_history)
    prompt = message

    for attempt in range(2):  # original turn + at most one forced continuation
        tool_called = False
        status_sent = False
        text_parts: list[str] = []

        async with planner_agent.iter(prompt, message_history=history) as run:
            async for node in run:
                if not Agent.is_model_request_node(node):
                    continue
                async with node.stream(run.ctx) as model_stream:
                    async for event in model_stream:
                        part = getattr(event, "part", None)
                        delta = getattr(event, "delta", None)
                        if isinstance(event, PartStartEvent) and isinstance(part, TextPart):
                            if part.content:
                                text_parts.append(part.content)
                                yield StreamPiece(kind="delta", text=part.content)
                        elif isinstance(event, PartDeltaEvent) and isinstance(delta, TextPartDelta):
                            text_parts.append(delta.content_delta)
                            yield StreamPiece(kind="delta", text=delta.content_delta)
                        elif isinstance(part, ToolCallPart) or isinstance(delta, ToolCallPartDelta):
                            tool_called = True
                            if not status_sent:  # Issue 2: show progress while the tool runs
                                status_sent = True
                                yield StreamPiece(kind="status", text=_BUILD_STATUS)

        result = run.result

        # Dead-end guard: promised to build but never called the tool -> force one continuation.
        if not tool_called and attempt == 0 and _PROMISE_RE.search("".join(text_parts)):
            if result is not None:
                history = list(result.all_messages())
            prompt = _FORCE_BUILD
            continue

        if result is not None:
            yield StreamPiece(kind="done", messages_json=result.all_messages_json().decode())
        return
