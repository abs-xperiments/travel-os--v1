"""provider_registry — a swappable registry of data providers, keyed by role.

Adapters register at app startup with a role ("destination", and later "accommodation",
"restaurant", "weather", "geocoding") and a priority. Callers ask for a role and get the
providers in priority order — they never import a concrete provider class.

This is THE seam of the provider-agnostic design: adding Google Places or Booking.com later
is one `register()` line in startup + one new adapter file. No planner changes.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

from typing import Any


class ProviderRegistry:
    """Holds providers grouped by role, ordered by priority (highest first)."""

    def __init__(self) -> None:
        self._by_role: dict[str, list[tuple[int, Any]]] = {}

    def register(self, role: str, provider: Any, priority: int = 0) -> None:
        """Add a provider for a role. Higher priority is tried first (e.g. catalog=10, web=1)."""
        bucket = self._by_role.setdefault(role, [])
        bucket.append((priority, provider))
        bucket.sort(key=lambda pair: pair[0], reverse=True)

    def get(self, role: str) -> Any | None:
        """The highest-priority provider for a role, or None if none registered."""
        bucket = self._by_role.get(role)
        return bucket[0][1] if bucket else None

    def get_all(self, role: str) -> list[Any]:
        """All providers for a role, highest priority first (for fallback chains)."""
        return [provider for _, provider in self._by_role.get(role, [])]

    def clear(self) -> None:
        """Forget all providers (used in tests)."""
        self._by_role.clear()


# Module-level singleton — adapters register into this at startup; callers import and use it.
registry = ProviderRegistry()
