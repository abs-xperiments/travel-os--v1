"""Geocoding adapter — OpenStreetMap / Nominatim (free, no key).

Its job is VERIFICATION: does this place actually exist, and where is it? If Nominatim can
locate it, the destination is real and plannable; if not, it's the one legitimate case where
we can't plan (a typo or a made-up name). It also gives coordinates (for future weather/maps)
and the country.

Nominatim usage policy: <= 1 request/second and a descriptive User-Agent (set below). Results
are cached by the knowledge layer, so we hit it rarely.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from agent.tripos.models import Coordinates

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "TripOS/1.0 (AI travel planner; +https://tripos-web-production-4f1c.up.railway.app)"


class GeocodeResult(BaseModel):
    coordinates: Coordinates
    display_name: str
    country: str | None = None


class NominatimGeocoder:
    """Resolves a place name to coordinates + canonical name, or None if it doesn't exist."""

    name = "nominatim"

    async def geocode(self, query: str) -> GeocodeResult | None:
        params = {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    _NOMINATIM_URL, params=params, headers={"User-Agent": _USER_AGENT}
                )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        results = response.json()
        if not results:
            return None
        top = results[0]
        address = top.get("address") or {}
        return GeocodeResult(
            coordinates=Coordinates(lat=float(top["lat"]), lon=float(top["lon"])),
            display_name=top.get("display_name", query),
            country=address.get("country"),
        )
