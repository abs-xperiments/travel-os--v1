"""itinerary_builder — lay chosen stops out into a realistic day-by-day schedule.

A deterministic packer (no AI, no network): it walks through the (already-ordered) stops
and fills each day up to that day's usable hours, treating arrival and departure days as
lighter. It reuses trip_feasibility_checker's hour assumptions so the whole app agrees on
what a "day" holds.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

from agent.tripos import trip_feasibility_checker as feasibility
from agent.tripos.models import Attraction, DayPlan, Destination, Itinerary, Pace

# Relaxed days do a little less; packed days a little more. Balanced = the default.
_PACE_FACTOR: dict[Pace, float] = {Pace.relaxed: 0.85, Pace.balanced: 1.0, Pace.packed: 1.2}


def _day_capacity(day: int, days: int, pace: Pace) -> float:
    """Usable hours for a given day. Arrival/departure days are half (travel eats time)."""
    hours = feasibility.HOURS_PER_FULL_DAY
    if days == 1 or day == 1 or day == days:
        hours *= 0.5
    return hours * _PACE_FACTOR[pace]


def _title(day: int, days: int, name: str) -> str:
    if day == 1:
        return f"Arrival in {name}"
    if day == days and days > 1:
        return f"Departure from {name}"
    return f"Exploring {name}"


def _notes(day: int, days: int) -> list[str]:
    if day == 1:
        return ["Arrival day — travel eats into it, so it's kept light."]
    if day == days and days > 1:
        return ["Departure day — enjoy a relaxed morning before heading back."]
    return []


def build_itinerary(
    destination: Destination,
    attractions: list[Attraction],
    days: int,
    pace: Pace = Pace.balanced,
) -> Itinerary:
    """Distribute `attractions` across `days`, respecting each day's usable hours."""
    remaining = list(attractions)
    day_plans: list[DayPlan] = []

    for day in range(1, days + 1):
        capacity = _day_capacity(day, days, pace)
        used = 0.0
        today: list[Attraction] = []
        while remaining:
            cost = remaining[0].duration_hours + feasibility.TRAVEL_BUFFER_HOURS_PER_STOP
            # Always allow the first stop of a day so nothing gets stranded; otherwise
            # stop once the day is full.
            if today and used + cost > capacity:
                break
            today.append(remaining.pop(0))
            used += cost
        day_plans.append(
            DayPlan(
                day=day,
                title=_title(day, days, destination.name),
                attractions=today,
                notes=_notes(day, days),
            )
        )

    # Safety net: if anything is left (shouldn't happen when stops were chosen feasibly),
    # put it on the last day and flag that the schedule is tight rather than dropping it.
    if remaining:
        day_plans[-1].attractions.extend(remaining)
        day_plans[-1].notes.append("Schedule is tight here — consider adding a day.")

    return Itinerary(destination_id=destination.id, days=days, day_plans=day_plans)
