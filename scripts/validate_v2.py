"""Layer-3 scenario driver — run one docs/scenarios.md case LIVE through the real agent path.

Drives `stream_reply` (the exact pipeline the web chat uses: agent + tools + statuses +
dead-end guard) and prints statuses + the full reply, so the output can be compared against
the documented expectations. Costs real LLM/research calls — this is the release gate, not CI.

    uv run python scripts/validate_v2.py <scenario>
    uv run python scripts/validate_v2.py didupe

Multi-turn scenarios send the follow-up automatically with the carried history.
"""

from __future__ import annotations

import asyncio
import sys

from pydantic_ai.messages import ModelMessagesTypeAdapter

from agent.agents.tripos_planner import stream_reply
from agent.logging_setup import setup_logging
from agent.tripos import knowledge_cache, trip_intelligence, trip_store

SCENARIOS: dict[str, list[str]] = {
    # V2 intent scenarios (docs/scenarios.md "Intent-driven service")
    "didupe": ["Suggest homestays in Didupe under ₹10,000 per person."],
    "kochi": ["Best seafood restaurants in Kochi for a romantic dinner."],
    "december": [
        "Where should I go for 5 days in December? Beaches, ₹40,000 per person, "
        "starting from Chennai."
    ],
    "today": ["I'm leaving today for Kerala for 5 days."],
    # Regression sweep (existing behavior must be unchanged)
    "dubai": [
        "5 days in Dubai in July, from Mumbai, couple, ₹1,00,000 per person, sightseeing + food",
        "continue with July",
    ],
    "paris": [
        "4 days in Paris in May, non-touristy — hidden gems and local life. "
        "Couple, from Delhi, ₹1,50,000 per person, food + photography."
    ],
    "luxury": [
        "Plan 5 days in Goa in December from Mumbai, couple, ₹30,000 per person, "
        "luxury + relaxation."
    ],
}


async def run(name: str) -> None:
    await trip_store.init_db()
    await knowledge_cache.init_db()
    await trip_intelligence.init_db()

    history: list = []
    for i, message in enumerate(SCENARIOS[name], 1):
        print(f"\n{'=' * 70}\nTURN {i} — USER: {message}\n{'=' * 70}")
        parts: list[str] = []
        async for piece in stream_reply(message, history):
            if piece.kind == "status":
                block = piece.text.replace("\n", "\n         ")  # show the FULL checklist
                print(f"[status] {block}")
            elif piece.kind == "delta":
                parts.append(piece.text)
            else:
                history = list(ModelMessagesTypeAdapter.validate_json(piece.messages_json))
        print(f"\n--- REPLY ---\n{''.join(parts)}")


if __name__ == "__main__":
    setup_logging()
    scenario = sys.argv[1] if len(sys.argv) > 1 else ""
    if scenario not in SCENARIOS:
        print(f"usage: uv run python scripts/validate_v2.py [{'|'.join(SCENARIOS)}]")
        raise SystemExit(1)
    asyncio.run(run(scenario))
