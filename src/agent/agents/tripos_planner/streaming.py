"""Streaming the planner's reply to the web UI, with progress statuses and the dead-end guard.

`stream_reply` is what `tripos_web.py` consumes: a stream of deltas (text chunks), transient
status notes while tools run, and a final `done` carrying the serialized history to persist.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from pydantic import BaseModel
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

from .agent import planner_agent


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

# Shown while check_travel_season runs — saying "building" there would be untrue.
_SEASON_STATUS = "Checking the season and weather for your dates…"

# Per-tool statuses for the intent-scoped tools — a stays search saying "Building your trip…"
# would be untrue (and confusing). Unknown tools fall back to the build status.
_STATUS_BY_TOOL = {
    "check_travel_season": _SEASON_STATUS,
    "find_stays": "Finding the best places to stay…",
    "find_restaurants": "Finding great places to eat…",
    "discover_circuits": "Mapping out route options…",
    "suggest_destinations": "Scouting destinations that fit…",
}

# Detects "I'll build it / put that together …" promises so we can force the work if the
# model stalled without calling a tool. Deliberately narrow so it won't match a question.
_PROMISE_RE = re.compile(
    r"\b(i'?ll|i will|let me|i'?m going to|give me a)\b[^.?!]*?"
    r"\b(put (it|that|this) together|prepare|build|create|generate|plan|pull together|work on)\b",
    re.IGNORECASE,
)

# Intent-aware: a stalled stays/restaurant promise must complete THAT promise, never force a
# full trip build the traveler didn't ask for.
_FORCE_BUILD = (
    "Proceed now: call the tool that serves what you just promised (build_trip for a full plan, "
    "find_stays for stays, find_restaurants for places to eat) using the details already "
    "gathered, and present the result. Do not ask anything else."
)


async def stream_reply(
    message: str, message_history: list[ModelMessage]
) -> AsyncIterator[StreamPiece]:
    """Stream the planner's reply — preamble, a progress status while tools run, then the plan.

    We use `agent.iter()` (not `run_stream()`): our agent calls `build_trip`, and `run_stream()`
    alone would only stream the first model turn, missing the plan written after the tool.

    Dead-end guard (Issue 1): if a turn ends having only PROMISED to build (no build_trip call),
    we automatically continue once with a forced nudge so the plan is produced in the same
    response — the user never has to send another message. EXCEPTION: if the turn asked the
    traveler a question, we do NOT force a build (they're still answering) — that would plan
    before the required info is in.
    """
    history = list(message_history)
    prompt = message

    for attempt in range(2):  # original turn + at most one forced continuation
        tool_called = False
        last_status: str | None = None
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
                            # Issue 2: show progress while a tool runs. The UI replaces the
                            # status line on each event, so we re-emit when it CHANGES — e.g.
                            # a season check followed by the build in the same turn.
                            if isinstance(part, ToolCallPart):
                                status = _STATUS_BY_TOOL.get(part.tool_name, _BUILD_STATUS)
                            else:
                                status = last_status or _BUILD_STATUS
                            if status != last_status:
                                last_status = status
                                yield StreamPiece(kind="status", text=status)

        result = run.result

        # Dead-end guard: promised to build but never called the tool -> force one continuation.
        # BUT never force a build on a turn that asked the traveler a question — that would
        # plan before they've answered. A question means we're still gathering, so we wait.
        full_text = "".join(text_parts)
        promised_without_asking = _PROMISE_RE.search(full_text) and "?" not in full_text
        if not tool_called and attempt == 0 and promised_without_asking:
            if result is not None:
                history = list(result.all_messages())
            prompt = _FORCE_BUILD
            continue

        if result is not None:
            yield StreamPiece(kind="done", messages_json=result.all_messages_json().decode())
        return
