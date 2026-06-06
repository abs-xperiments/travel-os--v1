"""Streaming the planner's reply to the web UI, with live progress and the dead-end guard.

`stream_reply` is what `tripos_web.py` consumes: a stream of deltas (text chunks), transient
status notes while tools run, and a final `done` carrying the serialized history to persist.

Tool execution happens while we await the agent-run iterator's next node — so to show live
progress DURING a long tool run, the loop races that await against the turn's progress queue
(see `progress.py`) and yields each checklist update as a status piece the moment a stage
completes. Honest progress only: the checklist is written by the tools as work actually happens.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

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

from . import progress
from .agent import planner_agent
from .pieces import StreamPiece

# Single-line headers per tool — the live checklist (progress.py) provides the detail beneath.
_BUILD_STATUS = "Building your trip…"
_SEASON_STATUS = "Checking the season and weather for your dates…"

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
# full trip build the traveler didn't ask for — and a promised questionnaire must re-attempt
# the FORM, never a premature build.
_FORCE_BUILD = (
    "Proceed now: call the tool that serves what you just promised (request_trip_details to "
    "gather missing trip details, build_trip for a full plan, find_stays for stays, "
    "find_restaurants for places to eat) using the details already gathered, and present the "
    "result. Do not ask anything else."
)


async def stream_reply(
    message: str, message_history: list[ModelMessage]
) -> AsyncIterator[StreamPiece]:
    """Stream the planner's reply — preamble, live progress while tools run, then the plan.

    We use `agent.iter()` (not `run_stream()`): our agent calls `build_trip`, and `run_stream()`
    alone would only stream the first model turn, missing the plan written after the tool.

    Dead-end guard (Issue 1): if a turn ends having only PROMISED to build (no tool call),
    we automatically continue once with a forced nudge so the result is produced in the same
    response — the user never has to send another message. EXCEPTION: if the turn asked the
    traveler a question, we do NOT force (they're still answering) — that would plan
    before the required info is in.
    """
    history = list(message_history)
    prompt = message

    for attempt in range(2):  # original turn + at most one forced continuation
        tool_called = False
        last_status: str | None = None
        text_parts: list[str] = []

        # The turn's channel: tools report checklist stages AND questionnaire forms (via
        # progress.py helpers, inherited through the task context); the loop below relays
        # them while the node runs.
        queue: asyncio.Queue[StreamPiece] = asyncio.Queue()
        reporter, token = progress.activate(queue)

        try:
            async with planner_agent.iter(prompt, message_history=history) as run:
                run_iter = run.__aiter__()
                while True:
                    # Advancing the iterator is where tool execution happens and blocks — race
                    # it against the progress queue so checklist updates stream live.
                    node_task = asyncio.ensure_future(anext(run_iter))
                    try:
                        while not node_task.done():
                            get_task = asyncio.ensure_future(queue.get())
                            await asyncio.wait(
                                {node_task, get_task}, return_when=asyncio.FIRST_COMPLETED
                            )
                            if get_task.done() and not get_task.cancelled():
                                piece = get_task.result()
                                if piece.kind != "status":
                                    yield piece  # forms etc. always pass through
                                elif piece.text != last_status:
                                    last_status = piece.text
                                    yield piece
                            else:
                                get_task.cancel()
                    except BaseException:
                        node_task.cancel()  # never leave the run advancing unobserved
                        raise
                    try:
                        node = node_task.result()
                    except StopAsyncIteration:
                        break
                    # Relay anything that landed in the same instant the node completed.
                    while not queue.empty():
                        piece = queue.get_nowait()
                        if piece.kind != "status":
                            yield piece
                        elif piece.text != last_status:
                            last_status = piece.text
                            yield piece

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
                            elif isinstance(event, PartDeltaEvent) and isinstance(
                                delta, TextPartDelta
                            ):
                                text_parts.append(delta.content_delta)
                                yield StreamPiece(kind="delta", text=delta.content_delta)
                            elif isinstance(part, ToolCallPart) or isinstance(
                                delta, ToolCallPartDelta
                            ):
                                tool_called = True
                                # The header line for the tool about to run; the checklist the
                                # tool writes will then grow beneath it (reporter.title).
                                if isinstance(part, ToolCallPart):
                                    status = _STATUS_BY_TOOL.get(part.tool_name, _BUILD_STATUS)
                                    reporter.title = status
                                else:
                                    status = last_status or _BUILD_STATUS
                                if status != last_status:
                                    last_status = status
                                    yield StreamPiece(kind="status", text=status)
        finally:
            progress.deactivate(token)

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
