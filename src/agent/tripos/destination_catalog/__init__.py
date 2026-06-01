"""destination_catalog — TripOS's source of truth for places and things to do.

Reads the curated seed data (versioned JSON in this folder's `data/`) and hands it back
as validated, typed `Destination` / `Attraction` objects. Every other module asks the
catalog for facts instead of trusting the LLM's memory — that's what keeps prices and
opening hours honest.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agent.tripos.models import Attraction, Destination

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def _load() -> dict[str, Destination]:
    """Load and validate every destination JSON file once, keyed by id (cached)."""
    destinations: dict[str, Destination] = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        dest = Destination.model_validate(json.loads(path.read_text(encoding="utf-8")))
        destinations[dest.id] = dest
    return destinations


def list_destinations() -> list[Destination]:
    """Every destination currently in the catalog (V1: the South Indian hill stations)."""
    return list(_load().values())


def get_destination(destination_id: str) -> Destination | None:
    """One destination by id, or None if it isn't in the catalog (i.e. out of V1 scope)."""
    return _load().get(destination_id)


def get_attractions(destination_id: str) -> list[Attraction]:
    """The attractions for a destination ([] if the destination isn't in the catalog)."""
    dest = _load().get(destination_id)
    return list(dest.attractions) if dest else []
