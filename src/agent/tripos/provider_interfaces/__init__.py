"""provider_interfaces — the contracts the planner depends on (never a concrete provider).

This is the heart of the provider-agnostic design. The planning engine asks for "destination
knowledge" (and later stays, restaurants, weather) through these Protocol interfaces and gets
back our OWN standardized types (`Destination`/`Attraction` from models.py). It never knows
whether the data came from the curated catalog, a Wikivoyage page, a web search, or a future
paid API like Google Places. Adding a new source = write a class with these methods and
register it — zero planner changes.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from agent.tripos.models import (
    Accommodation,
    Circuit,
    Destination,
    Restaurant,
    SeasonalityProfile,
    TripBrief,
    WeatherInsight,
)


@runtime_checkable
class DestinationProvider(Protocol):
    """Resolves a free-text destination name into a typed `Destination` (or None if it can't).

    Returning None is NOT "unsupported" — it just means this source didn't have it, so the
    registry tries the next provider. A destination is only truly unplannable if EVERY
    provider returns None.
    """

    name: str

    async def fetch(self, query: str, brief: TripBrief | None = None) -> Destination | None: ...


@runtime_checkable
class WeatherProvider(Protocol):
    """Returns a weather/season insight for a destination + trip (or None if unavailable)."""

    name: str

    async def insight(
        self, destination: Destination, brief: TripBrief
    ) -> WeatherInsight | None: ...


@runtime_checkable
class SeasonalityProvider(Protocol):
    """Returns a destination's year-round month-by-month suitability profile (or None).

    The ONLY legitimate source for season verdicts and best-window advice — the agent never
    answers those from model memory.
    """

    name: str

    async def profile(
        self, destination: Destination, brief: TripBrief
    ) -> SeasonalityProfile | None: ...


@runtime_checkable
class AccommodationProvider(Protocol):
    """Returns ranked, tiered accommodation recommendations for a destination + trip.

    Phase 2 ships a web-grounded implementation; future paid sources (Booking, Airbnb, …)
    implement this same interface and slot into the registry with no planner change.
    """

    name: str

    async def search(self, destination: Destination, brief: TripBrief) -> list[Accommodation]: ...


@runtime_checkable
class RestaurantProvider(Protocol):
    """Returns restaurant recommendations for a destination + trip (diet/budget-aware)."""

    name: str

    async def search(self, destination: Destination, brief: TripBrief) -> list[Restaurant]: ...


@runtime_checkable
class CircuitProvider(Protocol):
    """Recommends multi-destination circuits for a region + trip length (or None)."""

    name: str

    async def discover(self, region: str, nights: int, brief: TripBrief) -> list[Circuit]: ...


def slugify(name: str) -> str:
    """Turn a destination name into a stable id slug, e.g. 'Leh-Ladakh' -> 'leh-ladakh'."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return s.strip("-")
