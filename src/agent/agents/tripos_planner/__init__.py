"""The TripOS planner agent — the conversational AI travel consultant.

This package is the only place the LLM lives. It *talks* to the traveler (gathers what they
want, explains, modifies), but it never invents facts or does the planning maths itself: for
anything concrete it calls the tools in `tools.py`, backed by retrieval + the tested planning
modules.

Layout (split from one file on 2026-06-06 to stay under the 500-line cap; the public import
surface below is unchanged — `from agent.agents.tripos_planner import stream_reply` etc. all
keep working):

- `prompt.py`    — the system-prompt rulebook (from docs/policy.md) + the dynamic travel
                   context (today's date, re-evaluated every run)
- `tools.py`     — the trip-planning tool functions (season check, routes, builds)
- `recommend.py` — the intent-scoped tools: find_stays / find_restaurants / suggest_destinations
- `compact.py`   — token-light dict views of plans for the model to present
- `agent.py`     — builds `planner_agent` (model + prompt + tools + instructions)
- `streaming.py` — `stream_reply` for the web UI (deltas, statuses, dead-end guard)
"""

from .agent import planner_agent
from .compact import _parse_date
from .prompt import SYSTEM_PROMPT, travel_context_now
from .recommend import find_restaurants, find_stays, suggest_destinations
from .streaming import _PROMISE_RE, StreamPiece, stream_reply
from .tools import (
    budget_compatibility,
    build_circuit,
    build_trip,
    check_travel_season,
    discover_circuits,
    list_destinations,
    rank_circuits_by_budget,
)

__all__ = [
    "SYSTEM_PROMPT",
    "StreamPiece",
    "_PROMISE_RE",
    "_parse_date",
    "budget_compatibility",
    "build_circuit",
    "build_trip",
    "check_travel_season",
    "discover_circuits",
    "find_restaurants",
    "find_stays",
    "list_destinations",
    "planner_agent",
    "rank_circuits_by_budget",
    "stream_reply",
    "suggest_destinations",
    "travel_context_now",
]
