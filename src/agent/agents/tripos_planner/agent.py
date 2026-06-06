"""Builds the planner agent: model + rulebook + tools + the dynamic travel context.

This is the only place the LLM lives. Everything it can DO is a tool from `tools.py`;
everything it must FOLLOW is the rulebook in `prompt.py`.
"""

from __future__ import annotations

from pydantic_ai import Agent

from agent.services.llm import build_model

from . import recommend, tools
from .prompt import SYSTEM_PROMPT, travel_context_now

# balanced = Claude Sonnet (good at tool use); cheap enough for a chat. See services/llm.py.
planner_agent = Agent(build_model("balanced"), system_prompt=SYSTEM_PROMPT)

# Instructions (unlike the system prompt) are re-evaluated on every run and never replayed
# from history — exactly right for "what is today's date".
planner_agent.instructions(travel_context_now)

planner_agent.tool_plain(tools.list_destinations)
planner_agent.tool_plain(tools.check_travel_season)
planner_agent.tool_plain(tools.discover_circuits)
planner_agent.tool_plain(tools.build_trip)
planner_agent.tool_plain(tools.build_circuit)
# Intent-scoped tools (V2): standalone stay/restaurant/destination requests served directly —
# no trip-planning workflow.
planner_agent.tool_plain(recommend.find_stays)
planner_agent.tool_plain(recommend.find_restaurants)
planner_agent.tool_plain(recommend.suggest_destinations)
