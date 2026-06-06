"""Token-light views of plans for the model to read and present.

The planner's tools return these compact dicts (not raw Pydantic models) so the LLM gets
exactly what it needs to narrate a plan — ranges instead of exact figures, popularity for
honest storytelling — without burning tokens on internals it must never reveal.
"""

from __future__ import annotations

from datetime import date

from agent.tripos.models import (
    MONTH_NAMES,
    CircuitPlan,
    Destination,
    FoodPref,
    GroupType,
    PopularityPref,
    SeasonalityProfile,
    TravelStyle,
    TripBrief,
    TripPlan,
)


def _parse_date(value: str | None) -> date | None:
    """An ISO date if parseable, else None — dates are an optional nicety, never a blocker."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _neutral_brief() -> TripBrief:
    """A placeholder brief for the season check, which can run before gathering finishes.

    Enrichment is cached PER DESTINATION, so the brief only colours the first extraction
    slightly (stay/restaurant variety) — seasonality itself is traveler-independent.
    """
    return TripBrief(
        start_city="(unspecified)",
        days=5,
        budget=50000,
        group_type=GroupType.couple,
        interests=[TravelStyle.sightseeing],
        food_pref=FoodPref.no_preference,
    )


def _travel_context(plan: TripPlan, seasonality: SeasonalityProfile | None) -> dict | None:
    """The season block the model presents as the plan's 'Travel Context' note."""
    if not plan.brief.travel_month:
        return None
    assessment = seasonality.for_month(plan.brief.travel_month) if seasonality else None
    return {
        "month": MONTH_NAMES[plan.brief.travel_month],
        "suitability": assessment.rating.value if assessment else "unconfirmed",
        "note": assessment.note if assessment else "Seasonal conditions couldn't be confirmed.",
        "adapted_indoor_leaning": bool(assessment and assessment.lean_indoor),
        "best_months": [MONTH_NAMES[m] for m in seasonality.best_months if 1 <= m <= 12]
        if seasonality
        else [],
    }


def _compact_plan(
    plan: TripPlan, destination: Destination, seasonality: SeasonalityProfile | None = None
) -> dict:
    """A small, token-light view of a TripPlan for the model to read and present."""
    return {
        "destination": destination.name,
        # Present this FIRST as the "Travel Context" note (None = no month given).
        "travel_context": _travel_context(plan, seasonality),
        "days": plan.itinerary.days,
        "feasible": plan.feasibility.realistic,
        "feasibility_reasons": plan.feasibility.reasons,
        "feasibility_suggestions": plan.feasibility.suggestions,
        "currency": "INR",
        "per_person_budget": {  # PRIMARY figure — present the RANGE, labelled "per person"
            "range": [plan.budget.per_person_low, plan.budget.per_person_high],
            "fit": plan.budget.fit.value if plan.budget.fit else None,
            "confidence": plan.budget.confidence_level.value,
            "confidence_reason": plan.budget.confidence_reason,
            "adjustments": plan.budget.adjustments,
        },
        "travelers": plan.budget.travelers,
        "group_total_range": [  # per_person range × travelers — never an exact group figure
            plan.budget.per_person_low * plan.budget.travelers,
            plan.budget.per_person_high * plan.budget.travelers,
        ],
        "budget_notes": plan.budget.notes,
        "itinerary": [
            {
                "day": d.day,
                "title": d.title,
                # popularity lets the model narrate honestly ("a local favourite", "the icon")
                "stops": [{"name": a.name, "popularity": a.popularity} for a in d.attractions],
                "notes": d.notes,
            }
            for d in plan.itinerary.day_plans
        ],
        "personalization": (
            {
                "popularity_pref": plan.brief.popularity_pref.value,
                "avoid": plan.brief.avoid,
                "must_include": plan.brief.must_include,
                "stops_with_known_popularity": sum(
                    1 for a in plan.attractions if a.popularity is not None
                ),
                "total_stops": len(plan.attractions),
            }
            if (
                plan.brief.popularity_pref is not PopularityPref.balanced
                or plan.brief.avoid
                or plan.brief.must_include
            )
            else None
        ),
        # Phase 2 enrichment (web-grounded estimates, not live bookings).
        "stays": [
            {
                "name": s.name,
                "area": s.area,
                "tier": s.tier,
                "kind": s.kind,
                "price_per_night": [s.price_per_night_low, s.price_per_night_high],
                "why": s.why,
            }
            for s in plan.stays[:6]
        ],
        "restaurants": [
            {
                "name": r.name,
                "area": r.area,
                "cuisine": r.cuisine,
                "price_band": r.price_band,
                "good_for": r.good_for,
            }
            for r in plan.restaurants[:6]
        ],
        "weather": (
            {
                "summary": plan.weather.summary,
                "season": plan.weather.season_label,
                "advisories": plan.weather.advisories,
                "temps_c": [plan.weather.temp_low_c, plan.weather.temp_high_c],
            }
            if plan.weather
            else None
        ),
    }


def _compact_circuit(plan: CircuitPlan) -> dict:
    """A token-light view of a built circuit for the model to present, leg by leg."""
    return {
        "circuit": plan.name,
        "total_nights": plan.total_nights,
        "feasible": plan.feasibility.realistic,
        "feasibility_reasons": plan.feasibility.reasons,
        "currency": "INR",
        "per_person_budget": {  # PRIMARY — present the RANGE, labelled "per person"
            "range": [plan.budget.per_person_low, plan.budget.per_person_high],
            "fit": plan.budget.fit.value if plan.budget.fit else None,
            "confidence": plan.budget.confidence_level.value,
            "confidence_reason": plan.budget.confidence_reason,
            "adjustments": plan.budget.adjustments,
        },
        "travelers": plan.budget.travelers,
        "group_total_range": [
            plan.budget.per_person_low * plan.budget.travelers,
            plan.budget.per_person_high * plan.budget.travelers,
        ],
        "budget_notes": plan.budget.notes,
        "legs": [
            {
                "destination": s.destination,
                "nights": s.nights,
                "days": [
                    {"day": d.day, "title": d.title, "stops": [a.name for a in d.attractions]}
                    for d in s.day_plans
                ],
                "stays": [
                    {
                        "name": st.name,
                        "tier": st.tier,
                        "price_per_night": [st.price_per_night_low, st.price_per_night_high],
                    }
                    for st in s.stays[:4]
                ],
            }
            for s in plan.stops
        ],
        "restaurants": [
            {"name": r.name, "area": r.area, "cuisine": r.cuisine} for r in plan.restaurants[:6]
        ],
        "weather": (
            {
                "summary": plan.weather.summary,
                "season": plan.weather.season_label,
                "advisories": plan.weather.advisories,
            }
            if plan.weather
            else None
        ),
    }
