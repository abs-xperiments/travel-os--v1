"""Offline test: the destination_catalog loads and validates seed data in isolation.

No credentials needed — this only reads local JSON.

    uv run pytest scripts/tests/test_destination_catalog.py
"""

from __future__ import annotations

from agent.tripos import destination_catalog as catalog
from agent.tripos.models import TravelStyle


def test_munnar_loads_with_core_fields():
    dest = catalog.get_destination("munnar")
    assert dest is not None
    assert dest.name == "Munnar"
    assert dest.state == "Kerala"
    assert TravelStyle.nature in dest.good_for


def test_munnar_has_attractions_all_well_formed():
    attractions = catalog.get_attractions("munnar")
    assert len(attractions) >= 5
    # every attraction points back at this destination and is sanely shaped
    assert all(a.destination_id == "munnar" for a in attractions)
    assert all(a.duration_hours > 0 for a in attractions)
    assert all(1 <= a.worth_visiting <= 10 for a in attractions)


def test_unknown_destination_is_none_not_an_error():
    assert catalog.get_destination("atlantis") is None
    assert catalog.get_attractions("atlantis") == []


def test_list_destinations_includes_munnar():
    ids = {d.id for d in catalog.list_destinations()}
    assert "munnar" in ids
