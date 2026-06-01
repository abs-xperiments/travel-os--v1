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

from agent.tripos.models import Destination, TripBrief


@runtime_checkable
class DestinationProvider(Protocol):
    """Resolves a free-text destination name into a typed `Destination` (or None if it can't).

    Returning None is NOT "unsupported" — it just means this source didn't have it, so the
    registry tries the next provider. A destination is only truly unplannable if EVERY
    provider returns None.
    """

    name: str

    async def fetch(self, query: str, brief: TripBrief | None = None) -> Destination | None: ...


def slugify(name: str) -> str:
    """Turn a destination name into a stable id slug, e.g. 'Leh-Ladakh' -> 'leh-ladakh'."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return s.strip("-")
