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
