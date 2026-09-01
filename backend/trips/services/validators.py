"""Defensive validators for untrusted provider payloads."""

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import MalformedProviderResponseError


def require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MalformedProviderResponseError(f"Provider response field '{context}' must be an object.")
    return value


def require_sequence(value: Any, context: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise MalformedProviderResponseError(f"Provider response field '{context}' must be an array.")
    return value


def require_number(value: Any, context: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise MalformedProviderResponseError(f"Provider response field '{context}' must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MalformedProviderResponseError(f"Provider response field '{context}' must be numeric.") from exc
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise MalformedProviderResponseError(f"Provider response field '{context}' is out of range.")
    return number


def parse_coordinate_pair(value: Any, context: str) -> tuple[float, float]:
    coordinates = require_sequence(value, context)
    if len(coordinates) < 2:
        raise MalformedProviderResponseError(f"Provider response field '{context}' needs two coordinates.")
    first = require_number(coordinates[0], f"{context}[0]")
    second = require_number(coordinates[1], f"{context}[1]")
    if not -180 <= first <= 180 or not -90 <= second <= 90:
        raise MalformedProviderResponseError(f"Provider response field '{context}' contains invalid coordinates.")
    return first, second


# Kept as a compatibility export for callers looking for the service-level
# validator module. The implementation remains separate from provider payload
# validation to keep the two concerns independently testable.
from .schedule_validator import ScheduleValidator, validate_schedule  # noqa: E402,F401
