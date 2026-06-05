"""Core domain types shared across TripOS modules.

These Pydantic models are the contracts every module passes around. Keep them small —
add fields and new types *when* the module that needs them is built, not before.

Debugging tip: if a module receives bad data, validate it against these models first.
Pydantic's error tells you the exact field and why it failed (wrong type, out of range,
missing). Seed JSON that won't load is almost always a mismatch with `Attraction` or
`Destination` here.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

#: Month names indexed 1–12 (index 0 unused) — for presenting `travel_month` numbers.
MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


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


class Coordinates(BaseModel):
    """A geographic point — used to verify a place exists and to anchor weather/map lookups."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Destination(BaseModel):
    """A place you can take a trip to, plus its attractions.

    Comes from the curated catalog (seed JSON) OR from runtime web retrieval — the planner
    treats both identically. `country`/`coordinates` are optional: blank for the original
    India catalog, populated for retrieved (worldwide) destinations.
    """

    id: str
    name: str
    state: str
    region: str
    description: str
    bases: list[str] = Field(description="Towns/areas you'd stay in within this destination.")
    good_for: list[TravelStyle]
    nearest_railhead: str
    nearest_airport: str
    attractions: list[Attraction] = Field(default_factory=list)
    country: str | None = Field(
        default=None, description="Country (set for retrieved destinations)."
    )
    coordinates: Coordinates | None = Field(
        default=None, description="Lat/lon (set for retrieved destinations)."
    )


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
    """A trip's cost estimate. The PER-PERSON figure is primary; the group total is derived."""

    by_category: dict[str, float] = Field(description="Per-person cost by category (₹).")
    per_person_total: float = Field(description="Primary figure: estimated cost per traveler (₹).")
    per_person_low: float = Field(description="Lower end of the per-person range (₹).")
    per_person_high: float = Field(description="Upper end of the per-person range (₹).")
    travelers: int = Field(default=1, ge=1)
    group_total: float = Field(description="per_person_total × travelers (₹).")
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
    budget: float = Field(gt=0, description="PER-PERSON budget in ₹ (the primary planning figure).")
    group_type: GroupType
    interests: list[TravelStyle]
    pace: Pace = Pace.balanced
    food_pref: FoodPref = FoodPref.no_preference
    destination_id: str | None = None
    travelers: int | None = Field(
        default=None, ge=1, description="Traveler count if the user gave one; else inferred."
    )
    travel_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Month of travel (1–12) — drives all seasonality logic. None = flexible.",
    )
    # Exact dates are stored when the traveler gives them but never demanded — V1 plans by
    # month; these are the extension point for V2 accommodation booking (which needs dates).
    start_date: date | None = None
    end_date: date | None = None


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


class Accommodation(BaseModel):
    """A recommended place to stay (web-grounded estimate, not a live booking quote)."""

    name: str
    area: str = Field(description="Neighbourhood / base within the destination.")
    kind: str = Field(description="e.g. hostel, budget hotel, homestay, boutique, resort.")
    tier: str = Field(description="budget | mid | premium")
    price_per_night_low: float = Field(ge=0, description="Estimated room price/night (₹), low.")
    price_per_night_high: float = Field(ge=0, description="Estimated room price/night (₹), high.")
    rating: float | None = Field(default=None, description="0–5 if known.")
    why: str = Field(description="One-line reason this suits the traveler.")


class Restaurant(BaseModel):
    """A recommended place to eat (web-grounded estimate)."""

    name: str
    area: str
    cuisine: str
    price_band: str = Field(description="$ | $$ | $$$")
    good_for: str = Field(description="e.g. vegetarian-friendly, family, local/authentic.")
    why: str


class WeatherInsight(BaseModel):
    """What the weather/season means for the trip, with practical advisories."""

    summary: str
    season_label: str = Field(description="e.g. peak, shoulder, monsoon, winter.")
    advisories: list[str] = Field(default_factory=list)
    temp_low_c: float | None = None
    temp_high_c: float | None = None
    source: str = "Open-Meteo climate normals"


class MonthRating(StrEnum):
    """How suitable a month is for visiting a destination (policy step 4's five levels)."""

    excellent = "excellent"
    good = "good"
    acceptable = "acceptable"
    challenging = "challenging"
    not_recommended = "not_recommended"


class MonthAssessment(BaseModel):
    """One month's travel suitability for a destination, with the reason."""

    month: int = Field(ge=1, le=12)
    rating: MonthRating
    note: str = Field(description="Short reason, e.g. 'peak monsoon — heavy daily rain'.")
    lean_indoor: bool = Field(
        default=False,
        description="True if plans this month should favour indoor/sheltered stops "
        "(heavy rain, extreme heat) — crowds alone don't set this.",
    )


class SeasonalityProfile(BaseModel):
    """A destination's year-round suitability — retrieved once, cached, answers any month.

    This is the ONLY legitimate source for season verdicts and best-window advice
    (never the model's memory — see failure_modes.md).
    """

    months: list[MonthAssessment] = Field(default_factory=list)
    best_months: list[int] = Field(
        default_factory=list, description="The recommended window, as month numbers."
    )
    summary: str = Field(default="", description="One line on the destination's seasons.")

    def for_month(self, month: int) -> MonthAssessment | None:
        """The assessment for a month, or None if the profile doesn't cover it."""
        return next((m for m in self.months if m.month == month), None)


class TripEnrichment(BaseModel):
    """Retrieved stays + restaurants + weather + seasonality (one cached retrieval)."""

    stays: list[Accommodation] = Field(default_factory=list)
    restaurants: list[Restaurant] = Field(default_factory=list)
    weather: WeatherInsight | None = None
    # Optional so enrichments cached before seasonality existed still validate.
    seasonality: SeasonalityProfile | None = None


class CircuitLeg(BaseModel):
    """One stop on a multi-destination circuit, with how many nights to spend there."""

    destination: str = Field(description="Destination name, e.g. 'Munnar'.")
    nights: int = Field(ge=0, description="Nights here — allocated by how much there is to do.")
    why: str = Field(description="One line on what this leg adds to the trip.")


class Circuit(BaseModel):
    """A recommended multi-destination route (e.g. Kochi → Munnar → Thekkady → Alleppey)."""

    name: str = Field(description="A short name, e.g. 'Classic Kerala'.")
    legs: list[CircuitLeg]
    total_nights: int = Field(ge=0)
    style: str = Field(description="e.g. first-timer, nature, relaxed, adventure.")
    est_per_person_budget: float | None = Field(default=None, description="Rough ₹ per person.")
    why: str = Field(description="Why this route is recommended for the traveler.")


class CircuitOptions(BaseModel):
    """A set of recommended circuits (the structured output of circuit discovery)."""

    circuits: list[Circuit] = Field(default_factory=list)


class CircuitStop(BaseModel):
    """One leg of a built circuit: a destination, its nights, day plans, and stays."""

    destination: str
    nights: int
    day_plans: list[DayPlan] = Field(default_factory=list)
    stays: list[Accommodation] = Field(default_factory=list)


class CircuitPlan(BaseModel):
    """A fully built multi-destination trip — the aggregate for a planned circuit."""

    name: str
    stops: list[CircuitStop]
    total_nights: int
    budget: BudgetEstimate
    feasibility: FeasibilityResult
    restaurants: list[Restaurant] = Field(default_factory=list)
    weather: WeatherInsight | None = None


class TripPlan(BaseModel):
    """The complete proposal — the aggregate that ties every module's output together."""

    brief: TripBrief
    destination_id: str
    attractions: list[Attraction]
    itinerary: Itinerary
    budget: BudgetEstimate
    feasibility: FeasibilityResult
    # Phase 2 enrichment (optional — attached after retrieval; absent on a bare plan).
    stays: list[Accommodation] = Field(default_factory=list)
    restaurants: list[Restaurant] = Field(default_factory=list)
    weather: WeatherInsight | None = None
