"""Privacy-preserving, cached reverse geocoding for approximate locations."""

from __future__ import annotations

import logging
import re
import time
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

APPROXIMATE_LOCATION_LABEL = "Approximate current location"
GEOCODING_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
GEOCODING_CACHE_TTL_SECONDS = 86_400
GEOCODING_COMPONENT_PRIORITY = (
    "locality",
    "sublocality_level_1",
    "sublocality",
    "neighborhood",
    "administrative_area_level_2",
    "administrative_area_level_1",
    "country",
)
_geocoding_cache: dict[tuple[str, str], tuple[float, str | None]] = {}


def select_short_place_name(payload: dict) -> str | None:
    """Select the most useful locality from a Google geocoding response."""
    candidates: dict[str, str] = {}
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        for component in result.get("address_components", []):
            if not isinstance(component, dict):
                continue
            name = component.get("long_name")
            types = component.get("types", [])
            if isinstance(name, str) and name.strip() and isinstance(types, list):
                for component_type in types:
                    if component_type in GEOCODING_COMPONENT_PRIORITY and component_type not in candidates:
                        candidates[component_type] = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:160]
    for component_type in GEOCODING_COMPONENT_PRIORITY:
        if candidates.get(component_type):
            return candidates[component_type]
    return None


async def reverse_geocode_short_place_name(
    *, api_key: str, latitude: Decimal, longitude: Decimal
) -> str | None:
    """Return a cached locality label without exposing raw coordinates in logs."""
    cache_key = (f"{latitude:.3f}", f"{longitude:.3f}")
    cached = _geocoding_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < GEOCODING_CACHE_TTL_SECONDS:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
            response = await client.get(
                GEOCODING_ENDPOINT,
                params={"latlng": f"{latitude},{longitude}", "key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "OK":
                logger.info("Reverse geocoding returned status=%s", payload.get("status"))
                result = None
            else:
                result = select_short_place_name(payload)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Reverse geocoding failed: error=%s", exc.__class__.__name__)
        result = None
    _geocoding_cache[cache_key] = (now, result)
    return result
