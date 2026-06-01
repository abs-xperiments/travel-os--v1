"""Entry point — a simple console chat with the TripOS planner agent.

Run it:

    uv run agent

Type your trip request in plain English; type 'quit' to exit. This is the cheapest way
to exercise the agent end-to-end before there's a web UI. (Web version comes next.)
"""

import asyncio

from agent.agents.tripos_planner import planner_agent
from agent.logging_setup import setup_logging

GREETING = (
    "✈️  TripOS — your AI travel planner (destinations across India)\n"
    "Tell me about your trip, or say 'discover' if you don't know where to go.\n"
    "(type 'quit' to exit)\n"
)


async def _chat() -> None:
    print(GREETING)
    history: list = []
    while True:
        user_input = (await asyncio.to_thread(input, "You: ")).strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Safe travels! 👋")
            return
        result = await planner_agent.run(user_input, message_history=history)
        history = result.all_messages()
        print(f"\nTripOS: {result.output}\n")


def main() -> None:
    """Entry point for `uv run agent`."""
    setup_logging()
    try:
        asyncio.run(_chat())
    except (KeyboardInterrupt, EOFError):
        print("\nSafe travels! 👋")


if __name__ == "__main__":
    main()
