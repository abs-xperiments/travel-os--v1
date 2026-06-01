"""providers — concrete data-source adapters that implement the provider_interfaces.

Each adapter wraps ONE source and returns our standardized types. They're registered in the
provider_registry at app startup; the planner only ever talks to the registry, never to an
adapter directly.

Phase 1 ships the catalog adapter (below) plus, in this package, a geocoding adapter and a
web-retrieval adapter (added alongside this file). Future paid sources (Google Places,
Booking.com, …) become new adapter classes here with no planner changes.

See README.md in this folder for a plain-English explanation.
"""

from __future__ import annotations

from agent.tripos import destination_catalog as catalog
from agent.tripos.models import Destination, TripBrief
from agent.tripos.provider_interfaces import slugify
from agent.tripos.provider_registry import ProviderRegistry


class CatalogDestinationProvider:
    """The hand-curated catalog as a fast-path provider — a CACHE, not a gatekeeper.

    A miss returns None (NOT "unsupported"); the registry then falls back to web retrieval.
    This gives instant, zero-cost answers for the curated places while everywhere else on
    Earth is handled by the retrieval provider.
    """

    name = "catalog"

    async def fetch(self, query: str, brief: TripBrief | None = None) -> Destination | None:
        dest = catalog.get_destination(slugify(query))
        if dest is not None:
            return dest
        wanted = query.strip().lower()
        return next((d for d in catalog.list_destinations() if d.name.lower() == wanted), None)


def register_defaults(reg: ProviderRegistry) -> None:
    """Register the Phase-1 providers (idempotent). Catalog is the fast path; web is the
    global fallback; Nominatim verifies existence. Premium adapters slot in here later."""
    if reg.get_all("destination"):  # already registered — do nothing
        return
    # imported here (not at module top) to keep the lightweight catalog adapter import cheap
    from agent.tripos.providers.destination_retrieval import WebDestinationProvider
    from agent.tripos.providers.geocoding import NominatimGeocoder

    reg.register("geocoding", NominatimGeocoder())
    reg.register("destination", CatalogDestinationProvider(), priority=10)
    reg.register("destination", WebDestinationProvider(), priority=1)
