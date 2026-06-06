"""circuit_planner — build a full multi-destination (multi-stay) trip, leg by leg.

Given a chosen circuit (destinations + nights each), it plans every leg with the existing
engines — resolve the destination, enrich it (stays/restaurants/weather), pick + schedule
attractions sized to that leg's nights — then stitches the legs into one continuous trip:
renumbered day-by-day, a different stay per leg, and ONE combined per-person budget (a single
base transport + inter-city hops). Adds no new planning maths beyond combining.

The legs are planned CONCURRENTLY (each leg's resolve+enrich also overlap), so a multi-stop
circuit takes about as long as its slowest single leg rather than the sum. Runs behind the
streaming progress note. See README.md for a plain-English explanation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from agent.tripos import trip_intelligence, trip_planner
from agent.tripos.models import (
    CircuitPlan,
    CircuitStop,
    Destination,
    FeasibilityResult,
    Restaurant,
    TripBrief,
    TripEnrichment,
    TripPlan,
    WeatherInsight,
)

MAX_LEGS = 5  # safety cap on how many stops we'll build in one go

# What a successfully-built leg carries back from the concurrent fan-out.
_LegResult = tuple[Destination, int, TripPlan, TripEnrichment]


async def _build_leg(dest_name: str, nights: int, brief: TripBrief) -> _LegResult | None:
    """Resolve + enrich + plan one leg (all I/O for the leg). None if the place can't be found."""
    destination, enrichment = await trip_intelligence.resolve_and_enrich(dest_name, brief)
    if destination is None:
        return None
    leg_brief = brief.model_copy(update={"days": max(nights, 1), "destination_id": destination.id})
    # Stay tier is chosen against the WHOLE-trip budget (a leg doesn't get the full budget to
    # itself) — pass the original brief, not the leg slice, to the affordability math.
    choice = trip_planner.choose_stay(enrichment.stays, brief)
    # Each leg adapts to ITS OWN season for the travel month (profiles differ per destination).
    season = (
        enrichment.seasonality.for_month(brief.travel_month)
        if enrichment.seasonality and brief.travel_month
        else None
    )
    leg_plan = trip_planner.plan_trip(
        leg_brief, destination, stay_per_person_per_night=choice.rate, season=season
    )
    return destination, nights, leg_plan, enrichment


async def plan_circuit(
    name: str,
    legs: list[tuple[str, int]],
    brief: TripBrief,
    on_leg_done: Callable[[str], None] | None = None,
) -> CircuitPlan | None:
    """Build a CircuitPlan from (destination, nights) legs. Returns None if no leg resolves.

    on_leg_done, when given, is called with the leg's destination name as each concurrently-
    planned leg COMPLETES — so callers can show honest live progress per leg.
    """
    # Plan every leg CONCURRENTLY, then stitch the results back in travel order.
    chosen = legs[:MAX_LEGS]

    async def _leg(dest: str, nights: int) -> _LegResult | None:
        result = await _build_leg(dest, nights, brief)
        if on_leg_done is not None:
            on_leg_done(dest)
        return result

    results = await asyncio.gather(*(_leg(dest, nights) for dest, nights in chosen))

    stops: list[CircuitStop] = []
    day = 0
    total_days = 0
    total_stops = 0
    accommodation_pp = 0.0
    restaurants: list[Restaurant] = []
    weather: WeatherInsight | None = None
    reasons: list[str] = []
    all_realistic = True
    any_stays_retrieved = False
    stay_notes: list[str] = []

    for (dest_name, _), result in zip(chosen, results, strict=True):
        if result is None:
            reasons.append(f"Couldn't place {dest_name}, so it was left out.")
            continue
        destination, nights, leg_plan, enrichment = result
        choice = trip_planner.choose_stay(enrichment.stays, brief)
        stay_rate = choice.rate
        any_stays_retrieved = any_stays_retrieved or stay_rate is not None
        if choice.note and choice.note not in stay_notes:
            stay_notes.append(choice.note)

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
        total_days += max(nights, 1)
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
        stays_retrieved=any_stays_retrieved,
        extra_notes=stay_notes or None,
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
