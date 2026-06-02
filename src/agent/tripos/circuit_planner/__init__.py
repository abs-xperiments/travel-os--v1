"""circuit_planner — build a full multi-destination (multi-stay) trip, leg by leg.

Given a chosen circuit (destinations + nights each), it plans every leg with the existing
engines — resolve the destination, enrich it (stays/restaurants/weather), pick + schedule
attractions sized to that leg's nights — then stitches the legs into one continuous trip:
renumbered day-by-day, a different stay per leg, and ONE combined per-person budget (a single
base transport + inter-city hops). Reuses destination_intelligence, trip_intelligence and
trip_planner; adds no new planning maths beyond combining.

This is the heaviest operation (a resolve + enrich per leg), so callers run it behind the
streaming progress note. See README.md for a plain-English explanation.
"""

from __future__ import annotations

from agent.tripos import destination_intelligence, trip_intelligence, trip_planner
from agent.tripos.models import (
    CircuitPlan,
    CircuitStop,
    FeasibilityResult,
    Restaurant,
    TripBrief,
    WeatherInsight,
)

MAX_LEGS = 5  # safety cap on how many stops we'll build in one go


async def plan_circuit(
    name: str, legs: list[tuple[str, int]], brief: TripBrief
) -> CircuitPlan | None:
    """Build a CircuitPlan from (destination, nights) legs. Returns None if no leg resolves."""
    stops: list[CircuitStop] = []
    day = 0
    total_days = 0
    total_stops = 0
    accommodation_pp = 0.0
    restaurants: list[Restaurant] = []
    weather: WeatherInsight | None = None
    reasons: list[str] = []
    all_realistic = True

    for dest_name, nights in legs[:MAX_LEGS]:
        destination = await destination_intelligence.resolve(dest_name, brief)
        if destination is None:
            reasons.append(f"Couldn't place {dest_name}, so it was left out.")
            continue
        leg_days = max(nights, 1)
        leg_brief = brief.model_copy(update={"days": leg_days, "destination_id": destination.id})
        enrichment = await trip_intelligence.enrich(destination, leg_brief)
        stay_rate = trip_planner.per_person_nightly(enrichment.stays)
        leg_plan = trip_planner.plan_trip(
            leg_brief, destination, stay_per_person_per_night=stay_rate
        )

        renumbered = []
        for dp in leg_plan.itinerary.day_plans:
            day += 1
            renumbered.append(
                dp.model_copy(update={"day": day, "title": f"{destination.name}: {dp.title}"})
            )

        stops.append(
            CircuitStop(
                destination=destination.name,
                nights=nights,
                day_plans=renumbered,
                stays=enrichment.stays,
            )
        )
        total_days += leg_days
        total_stops += len(leg_plan.attractions)
        accommodation_pp += (stay_rate or trip_planner._STAY_PER_PERSON_PER_NIGHT) * max(nights, 1)
        restaurants.extend(enrichment.restaurants[:3])
        if weather is None:
            weather = enrichment.weather
        all_realistic = all_realistic and leg_plan.feasibility.realistic

    if not stops:
        return None

    budget = trip_planner.circuit_budget(
        brief,
        total_days=total_days,
        total_stops=total_stops,
        accommodation_per_person=accommodation_pp,
        hops=max(len(stops) - 1, 0),
    )
    feasibility = FeasibilityResult(
        realistic=all_realistic,
        required_hours=0.0,
        available_hours=0.0,
        reasons=reasons or ["Each stop's plan fits the nights spent there."],
        suggestions=[] if all_realistic else ["Consider an extra night on the busiest legs."],
    )
    return CircuitPlan(
        name=name,
        stops=stops,
        total_nights=sum(n for _, n in legs[:MAX_LEGS]),
        budget=budget,
        feasibility=feasibility,
        restaurants=restaurants[:8],
        weather=weather,
    )
