"""questionnaire — the deterministic question bank behind questionnaire-first planning.

Division of labour (the design's load-bearing idea): the AGENT analyzes the conversation and
decides what's already known vs genuinely missing — it owns inference. THIS module owns the
UI: a fixed bank of question specs keyed by canonical field name. The model can never invent
broken UI — `request_trip_details` validates every field name against the bank and silently
drops unknowns (a model typo just omits one question; the chat fallback still exists).

The assembled spec is pushed down the turn's stream channel (progress.show_form) for the
browser to render; in the CLI (no channel) the tool tells the model to ask in text instead.
Submitted answers come back as a normal chat message, so the conversation stays the single
source of truth — nothing here is ever parsed back into a TripBrief.
"""

from __future__ import annotations

from copy import deepcopy

from loguru import logger

from . import progress
from .tools import _prewarm_destination

# ---------------------------------------------------------------- question bank
#
# Spec shape the browser renders:
#   {"header": "Got it so far: …", "questions": [
#       {"field", "label", "type": single|multi|text|month|budget|number,
#        "options": [...], "allow_other": bool, "placeholder": str?, "presets": [...]?,
#        "children": [{…same shape…, "show_when": ["Option", …]}]}]}
#
# Tier 1 = essentials planning can't start without; Tier 2 = shape the trip; Tier 3 = only
# when the agent judges them contextually relevant (it simply includes them in `missing`).

_BANK: dict[str, dict] = {
    # ---- Tier 1 -------------------------------------------------------------
    "origin": {
        "field": "origin",
        "label": "Where are you starting from?",
        "type": "text",
        "placeholder": "e.g. Chennai",
    },
    "destination": {
        "field": "destination",
        "label": "Where would you like to go?",
        "type": "text",
        "placeholder": "A city, region, or country",
    },
    "travel_when": {
        "field": "travel_when",
        "label": "When are you travelling?",
        "type": "month",  # renderer: month picker + "Flexible" chip + optional exact dates
    },
    "duration": {
        "field": "duration",
        "label": "How many days?",
        "type": "number",
        "placeholder": "e.g. 4",
    },
    "group": {
        "field": "group",
        "label": "Who's travelling?",
        "type": "single",
        "options": ["Solo", "Couple", "Friends", "Family", "Family with kids", "With seniors"],
        "allow_other": False,
        "children": [
            {
                "field": "travelers",
                "label": "How many people?",
                "type": "number",
                "placeholder": "e.g. 4",
                # Solo=1 and Couple=2 are inferred — never ask the obvious.
                "show_when": ["Friends", "Family", "Family with kids", "With seniors"],
            }
        ],
    },
    "budget": {
        "field": "budget",
        "label": "Rough budget per person?",
        "type": "budget",  # typed ₹ input is primary; presets are just shortcuts
        "placeholder": "₹ per person",
        "presets": [15000, 30000, 50000, 100000],
    },
    # ---- Tier 2 -------------------------------------------------------------
    "interests": {
        "field": "interests",
        "label": "What do you enjoy?",
        "type": "multi",
        "options": [
            "Nature",
            "Adventure",
            "Food",
            "Relaxation",
            "Photography",
            "Sightseeing",
            "Hidden gems",
            "Luxury",
        ],
        "allow_other": True,
    },
    "style": {
        "field": "style",
        "label": "What kind of trip?",
        "type": "single",
        "options": ["Balanced", "Road trip", "Luxury", "Budget travel"],
        "allow_other": True,
        "children": [
            {
                "field": "self_drive",
                "label": "Driving yourselves?",
                "type": "single",
                "options": ["Self-drive", "Car with driver"],
                "show_when": ["Road trip"],
            },
            {
                "field": "max_driving_hours",
                "label": "Max driving hours per day?",
                "type": "number",
                "placeholder": "e.g. 4",
                "show_when": ["Road trip"],
            },
            {
                "field": "resort_pref",
                "label": "Stay style?",
                "type": "single",
                "options": ["Resort", "Boutique hotel", "Heritage stay"],
                "show_when": ["Luxury"],
            },
            {
                "field": "fine_dining",
                "label": "Fine dining a priority?",
                "type": "single",
                "options": ["Definitely", "Sometimes", "Not important"],
                "show_when": ["Luxury"],
            },
            {
                "field": "hostel_ok",
                "label": "Hostels okay?",
                "type": "single",
                "options": ["Yes", "No"],
                "show_when": ["Budget travel"],
            },
            {
                "field": "shared_transport_ok",
                "label": "Shared transport okay?",
                "type": "single",
                "options": ["Yes", "No"],
                "show_when": ["Budget travel"],
            },
        ],
    },
    "pace": {
        "field": "pace",
        "label": "What pace suits you?",
        "type": "single",
        # Each option carries its own one-line meaning — travelers shouldn't have to guess.
        "options": [
            "Relaxed — slow mornings, plenty of breathing room",
            "Balanced — full days without ever rushing",
            "Packed — see everything, rest when you're home",
        ],
        "allow_other": False,
    },
    "food_pref": {
        "field": "food_pref",
        "label": "Food preference?",
        "type": "single",
        "options": ["Vegetarian", "Non-vegetarian", "Jain", "Vegan", "No preference"],
        "allow_other": False,
    },
    "accommodation": {
        "field": "accommodation",
        "label": "Where do you like to stay?",
        "type": "single",
        "options": [
            "Homestay — local, homely, great value",
            "Budget hotel — clean and simple",
            "Comfort hotel — solid mid-range",
            "Resort — pool, views, amenities",
            "Boutique / heritage — character stays",
            "Hostel — cheapest, social",
        ],
        "allow_other": True,
    },
    "meals": {
        "field": "meals",
        "label": "How do you like to eat on a trip?",
        "type": "single",
        "options": [
            "Meals at the stay — easy and included",
            "Local eateries — eat where the locals do",
            "Mix of both",
            "A few special restaurants — worth the spend",
        ],
        "allow_other": True,
    },
    # ---- Tier 3 (the agent includes these only when contextually relevant) ---
    "accessibility": {
        "field": "accessibility",
        "label": "Any accessibility needs I should plan around?",
        "type": "text",
        "placeholder": "e.g. minimal stairs, gentle walks",
    },
    "pets": {
        "field": "pets",
        "label": "Travelling with a pet?",
        "type": "single",
        "options": ["Yes", "No"],
        "allow_other": False,
    },
    "remote_work": {
        "field": "remote_work",
        "label": "Need to work remotely during the trip?",
        "type": "single",
        "options": ["Yes — need good wifi", "No"],
        "allow_other": False,
    },
}

# style values -> the child fields revealed (used when style is ALREADY known from chat,
# so the branch questions get asked top-level without re-asking style itself).
_STYLE_BRANCHES = {
    "road trip": ["self_drive", "max_driving_hours"],
    "luxury": ["resort_pref", "fine_dining"],
    "budget travel": ["hostel_ok", "shared_transport_ok"],
    "budget": ["hostel_ok", "shared_transport_ok"],
}


def build_spec(known: dict[str, str], missing: list[str], style: str | None = None) -> dict:
    """Assemble the questionnaire spec from validated `missing` fields.

    Unknown field names are dropped (debug-logged) — a model typo can never break the UI.
    `known` is display-only (echoed in the header for reassurance); it is never parsed back.
    When `style` is already known from chat, that branch's sub-questions are included
    top-level (the style question itself is not re-asked).
    """
    questions: list[dict] = []
    seen: set[str] = set()
    for field in missing:
        spec = _BANK.get(field)
        if spec is None:
            logger.debug("questionnaire: unknown field {!r} dropped", field)
            continue
        if field not in seen:
            seen.add(field)
            questions.append(deepcopy(spec))

    if style and "style" not in seen:
        style_children = {c["field"]: c for c in _BANK["style"].get("children", [])}
        for child_field in _STYLE_BRANCHES.get(style.strip().casefold(), []):
            if child_field not in seen:
                seen.add(child_field)
                child = deepcopy(style_children[child_field])
                child.pop("show_when", None)  # asked top-level; the branch is already chosen
                questions.append(child)

    header = ""
    if known:
        header = "Got it so far: " + " · ".join(str(v) for v in known.values() if v)
    return {"header": header, "questions": questions}


async def request_trip_details(
    known: dict[str, str], missing: list[str], style: str | None = None
) -> str:
    """Show the traveler ONE questionnaire collecting the trip details still missing.

    Call this when the intent is PLAN_TRIP and required details are missing — INSTEAD of
    asking questions in text. Put everything already known or inferable into `known`
    (short human-readable values, e.g. {"destination": "Coorg", "duration": "4 days",
    "travelers": "2 people"}) — it is echoed back to the traveler so they see you listened,
    and those fields are NEVER asked again. Put only the genuinely missing field names in
    `missing`, from: origin, destination, travel_when, duration, group, budget, interests,
    style, pace, food_pref, accommodation, meals, accessibility, pets, remote_work.
    Pass `style` when the trip style is already known (e.g. "road trip") so its follow-up
    questions are included without re-asking.

    Returns an instruction you MUST follow about what to say next.
    """
    spec = build_spec(known, missing, style)
    if not spec["questions"]:
        return (
            "Nothing valid was left to ask. Use sensible defaults for minor gaps, or ask "
            "ONE short question in text for anything truly essential."
        )

    # The destination is known by now in most flows — start retrieval while they fill the
    # form, so the eventual build finds warm caches. Best-effort, coalesced, never blocks.
    destination = known.get("destination") or known.get("region")
    if destination:
        _prewarm_destination(destination)

    if not progress.show_form(spec):
        # CLI / no UI channel: degrade to today's behavior.
        return (
            "No questionnaire UI is available here. Ask the missing details as ONE short, "
            "friendly bullet list in text instead."
        )

    asked = ", ".join(q["field"] for q in spec["questions"])
    return (
        f"A questionnaire is now on the traveler's screen collecting: {asked}. "
        "Write ONE short, warm sentence inviting them to fill it (e.g. 'A few quick taps "
        "and I'll build your trip!') and then STOP. Do NOT ask any questions in text."
    )
