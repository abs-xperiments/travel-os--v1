"""trip_feasibility_checker — does this list of places actually fit the days?

A pure, deterministic reality-check (no AI, no network): it adds up how long the chosen
attractions take (plus travel between them) and compares that to the usable hours the
trip's days provide. If it doesn't fit, it says so and suggests concrete fixes.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import math

from agent.tripos.models import Attraction, FeasibilityResult

# Tunable assumptions — kept here, in one place, so they're easy to find and adjust.
HOURS_PER_FULL_DAY = 8.0  # realistic sightseeing hours in a full day (not 24!)
TRAVEL_BUFFER_HOURS_PER_STOP = 1.0  # avg local travel + setup time around each stop


def usable_hours(days: int) -> float:
    """Usable sightseeing hours for a trip of `days` days.

    Day 1 (arrival) and the last day (departure) are partial, so a 2-day trip gives
    roughly one full day of sightseeing. A 1-day trip gives half a day.
    """
    if days <= 0:
        return 0.0
    if days == 1:
        return HOURS_PER_FULL_DAY * 0.5
    return (days - 1) * HOURS_PER_FULL_DAY


def _required_hours(attractions: list[Attraction]) -> float:
    return sum(a.duration_hours for a in attractions) + TRAVEL_BUFFER_HOURS_PER_STOP * len(
        attractions
    )


def _drops_needed(attractions: list[Attraction], available: float) -> int:
    """How many of the lowest-value attractions to remove until the rest fit."""
    remaining = sorted(attractions, key=lambda a: a.worth_visiting)
    dropped = 0
    while remaining and _required_hours(remaining) > available:
        remaining.pop(0)
        dropped += 1
    return dropped


def check_feasibility(attractions: list[Attraction], days: int) -> FeasibilityResult:
    """Decide whether `attractions` realistically fit into `days`, with the math shown."""
    available = usable_hours(days)
    required = _required_hours(attractions)

    if not attractions:
        return FeasibilityResult(
            realistic=True,
            required_hours=0.0,
            available_hours=available,
            reasons=["No attractions chosen yet, so there's nothing that can't fit."],
        )

    realistic = required <= available
    reasons = [
        f"These {len(attractions)} stop(s) need about {required:.0f} hours "
        f"(time at each place plus travel between them).",
        f"{days} day(s) give about {available:.0f} usable sightseeing hours.",
    ]

    suggestions: list[str] = []
    if not realistic:
        excess = required - available
        days_to_add = math.ceil(excess / HOURS_PER_FULL_DAY)
        drops = _drops_needed(attractions, available)
        reasons.append(f"That's about {excess:.0f} hours more than the trip allows.")
        suggestions.append(f"Add about {days_to_add} more day(s), or")
        suggestions.append(f"drop about {drops} of the lower-priority stop(s).")

    return FeasibilityResult(
        realistic=realistic,
        required_hours=round(required, 1),
        available_hours=round(available, 1),
        reasons=reasons,
        suggestions=suggestions,
    )
