"""Core domain types shared across TripOS modules.

These Pydantic models are the contracts every module passes around. Keep them small —
add fields and new types *when* the module that needs them is built, not before.

Debugging tip: if a module receives bad data, validate it against these models first.
Pydantic's error tells you the exact field and why it failed (wrong type, out of range,
missing). Seed JSON that won't load is almost always a mismatch with `Attraction` or
`Destination` here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TravelStyle(StrEnum):
    """The kinds of trip a traveler can want. Matches the options shown in the UI."""

    nature = "nature"
    adventure = "adventure"
    food = "food"
    relaxation = "relaxation"
    photography = "photography"
    road_trip = "road_trip"
    backpacking = "backpacking"
    luxury = "luxury"
    sightseeing = "sightseeing"


class Attraction(BaseModel):
    """One place to visit, with the facts the planner reasons about."""

    id: str
    name: str
    destination_id: str
    description: str
    duration_hours: float = Field(gt=0, description="Typical time spent here, in hours.")
    indoor: bool = Field(description="True if it's a rain-safe / indoor experience.")
    base: str = Field(description="Which town/cluster it belongs to (cuts backtracking).")
    suitable_for_seniors: bool
    child_friendly: bool
    photography_value: int = Field(ge=1, le=10)
    adventure_level: int = Field(ge=1, le=10)
    worth_visiting: int = Field(ge=1, le=10, description="Overall 'worth it' score, 1–10.")
    best_time: str = Field(description="When to go, e.g. 'early morning'.")


class Destination(BaseModel):
    """A place you can take a trip to, plus its attractions (loaded from seed JSON)."""

    id: str
    name: str
    state: str
    region: str
    description: str
    bases: list[str] = Field(description="Towns you'd stay in within this destination.")
    good_for: list[TravelStyle]
    nearest_railhead: str
    nearest_airport: str
    attractions: list[Attraction] = Field(default_factory=list)


class FeasibilityResult(BaseModel):
    """Whether a set of attractions realistically fits the available days, with the math."""

    realistic: bool
    required_hours: float = Field(description="Time the chosen stops need, incl. travel.")
    available_hours: float = Field(description="Usable sightseeing hours over the trip.")
    reasons: list[str] = Field(description="Plain-English explanation of the verdict.")
    suggestions: list[str] = Field(
        default_factory=list, description="How to fix it if it doesn't fit (drop stops / add days)."
    )


class BudgetBreakdown(BaseModel):
    """Per-category cost inputs in ₹. Composer modules fill this; the estimator totals it."""

    transport: float = Field(ge=0)
    accommodation: float = Field(ge=0)
    food: float = Field(ge=0)
    activities: float = Field(ge=0)
    misc: float = Field(default=0.0, ge=0)


class BudgetEstimate(BaseModel):
    """A trip's total cost as a single figure plus an honest likely range."""

    by_category: dict[str, float]
    total: float
    low: float = Field(description="Lower end of the likely range (₹).")
    high: float = Field(description="Upper end of the likely range (₹).")
    confidence: int = Field(ge=0, le=100, description="How tight the estimate is, 0–100.")
    notes: list[str] = Field(default_factory=list)


class GroupType(StrEnum):
    """Who's travelling — drives suitability (e.g. seniors need gentler stops)."""

    solo = "solo"
    couple = "couple"
    friends = "friends"
    family = "family"
    family_with_children = "family_with_children"
    family_with_seniors = "family_with_seniors"


class Pace(StrEnum):
    """How packed the days should feel."""

    relaxed = "relaxed"
    balanced = "balanced"
    packed = "packed"


class FoodPref(StrEnum):
    vegetarian = "vegetarian"
    non_vegetarian = "non_vegetarian"
    jain = "jain"
    vegan = "vegan"
    no_preference = "no_preference"


class TripBrief(BaseModel):
    """Everything the planner needs to know about what the traveler wants."""

    start_city: str
    days: int = Field(gt=0)
    budget: float = Field(gt=0)
    group_type: GroupType
    interests: list[TravelStyle]
    pace: Pace = Pace.balanced
    food_pref: FoodPref = FoodPref.no_preference
    destination_id: str | None = None


class DayPlan(BaseModel):
    """One day of the trip: its stops and any notes (arrival/departure, etc.)."""

    day: int
    title: str
    attractions: list[Attraction] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Itinerary(BaseModel):
    """A full day-by-day schedule for one destination."""

    destination_id: str
    days: int
    day_plans: list[DayPlan]


class TripPlan(BaseModel):
    """The complete proposal — the aggregate that ties every module's output together."""

    brief: TripBrief
    destination_id: str
    attractions: list[Attraction]
    itinerary: Itinerary
    budget: BudgetEstimate
    feasibility: FeasibilityResult
