"""Offline test: provider interfaces, the registry, and the catalog adapter. No credentials.

uv run pytest scripts/tests/test_provider_registry.py
"""

from __future__ import annotations

from agent.tripos.provider_interfaces import DestinationProvider, slugify
from agent.tripos.provider_registry import ProviderRegistry
from agent.tripos.providers import CatalogDestinationProvider


def test_slugify():
    assert slugify("Leh-Ladakh") == "leh-ladakh"
    assert slugify("  Munnar ") == "munnar"
    assert slugify("Mount Abu") == "mount-abu"


def test_registry_priority_order_and_lookup():
    reg = ProviderRegistry()
    reg.register("destination", "low", priority=1)
    reg.register("destination", "high", priority=10)
    assert reg.get("destination") == "high"
    assert reg.get_all("destination") == ["high", "low"]  # highest first
    assert reg.get("missing") is None
    assert reg.get_all("missing") == []


async def test_catalog_provider_is_a_cache_not_a_gatekeeper():
    provider = CatalogDestinationProvider()
    # structurally satisfies the interface
    assert isinstance(provider, DestinationProvider)
    # a curated place resolves instantly
    munnar = await provider.fetch("Munnar")
    assert munnar is not None and munnar.id == "munnar"
    # a non-curated place returns None (NOT an error) — retrieval will handle it
    assert await provider.fetch("Pondicherry") is None
