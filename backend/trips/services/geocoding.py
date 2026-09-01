"""Nominatim-compatible geocoding with normalized application output."""

import time
from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings

from .errors import InvalidLocationError, LocationNotFoundError
from .http import fetch_json
from .validators import require_mapping, require_number, require_sequence


@dataclass(frozen=True)
class Location:
    input_text: str
    normalized_name: str
    latitude: float
    longitude: float
    city: str | None = None
    state: str | None = None
    country: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NominatimGeocoder:
    """Geocode one location at a time using Nominatim's public search API."""

    provider_name = "Geocoding provider"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        user_agent: str | None = None,
        timeout_seconds: float | None = None,
        min_interval_seconds: float | None = None,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ):
        self.base_url = base_url or settings.NOMINATIM_BASE_URL
        self.user_agent = user_agent or settings.NOMINATIM_USER_AGENT
        self.timeout_seconds = timeout_seconds or settings.EXTERNAL_PROVIDER_TIMEOUT_SECONDS
        self.min_interval_seconds = (
            settings.NOMINATIM_MIN_INTERVAL_SECONDS
            if min_interval_seconds is None
            else max(0.0, min_interval_seconds)
        )
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None

    def geocode(self, input_text: str, *, field: str | None = None) -> Location:
        query = " ".join(input_text.split()) if isinstance(input_text, str) else ""
        if not query:
            raise InvalidLocationError("Location is required.", field=field)

        payload = fetch_json(
            self.base_url,
            "/search",
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 1,
            },
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            provider_name=self.provider_name,
        )
        results = require_sequence(payload, "search result")
        if not results:
            raise LocationNotFoundError(f"No location was found for '{query}'.", field=field)

        result = require_mapping(results[0], "search result[0]")
        latitude = require_number(result.get("lat"), "search result[0].lat", minimum=-90)
        longitude = require_number(result.get("lon"), "search result[0].lon", minimum=-180)
        if latitude > 90 or longitude > 180:
            raise LocationNotFoundError(f"No valid coordinates were found for '{query}'.", field=field)

        address = require_mapping(result.get("address", {}), "search result[0].address")
        normalized_name = str(result.get("display_name") or query).strip()
        if not normalized_name:
            raise LocationNotFoundError(f"No normalized location was found for '{query}'.", field=field)

        return Location(
            input_text=query,
            normalized_name=normalized_name,
            latitude=round(latitude, 7),
            longitude=round(longitude, 7),
            city=self._first_text(address, "city", "town", "village", "municipality"),
            state=self._first_text(address, "state", "state_district"),
            country=self._first_text(address, "country"),
        )

    def geocode_many(self, queries: dict[str, str]) -> dict[str, Location]:
        locations: dict[str, Location] = {}
        for index, (field, query) in enumerate(queries.items()):
            if index:
                self._respect_rate_limit()
            locations[field] = self.geocode(query, field=field)
            self._last_request_at = self._monotonic()
        return locations

    def _respect_rate_limit(self) -> None:
        if self._last_request_at is None or self.min_interval_seconds <= 0:
            return
        elapsed = self._monotonic() - self._last_request_at
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)

    @staticmethod
    def _first_text(address: dict[str, Any] | Any, *keys: str) -> str | None:
        for key in keys:
            value = address.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
