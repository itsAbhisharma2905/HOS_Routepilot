"""Deterministic route-distance/time progression for the HOS engine."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import InvalidScheduleInputError

EPSILON = 1e-7


@dataclass(frozen=True)
class ProgressSegment:
    distance_start_miles: float
    distance_end_miles: float
    duration_minutes: int
    time_start_minutes: int
    time_end_minutes: int


class RouteProgress:
    """Map route mileage to the provider's estimated driving time.

    Leg distances and durations are preferred because they preserve the different
    current-to-pickup and pickup-to-dropoff portions. The input route duration is
    integerized once, using cumulative rounding, so scheduler arithmetic stays in
    minutes without repeatedly rounding each small route step.
    """

    def __init__(self, route: Mapping[str, Any]):
        if not isinstance(route, Mapping):
            raise InvalidScheduleInputError("A normalized route object is required.")
        self.route = dict(route)
        self.total_distance_miles = self._number(route.get("distance_miles"), "route.distance_miles", minimum=0)
        duration_seconds = self._number(
            route.get("estimated_driving_seconds"),
            "route.estimated_driving_seconds",
            minimum=0,
        )
        if duration_seconds <= 0:
            raise InvalidScheduleInputError("Route driving duration must be positive.")
        self.total_driving_seconds = round(duration_seconds)
        self.total_driving_minutes = math.ceil(duration_seconds / 60)
        self.segments = self._build_segments(duration_seconds)
        self._geometry = self._read_geometry(route)

    def distance_after(self, distance_start_miles: float, driving_minutes: int) -> float:
        """Return the route distance after an integer number of driving minutes."""

        self._validate_distance(distance_start_miles)
        if driving_minutes < 0:
            raise InvalidScheduleInputError("Driving minutes cannot be negative.")
        if driving_minutes == 0 or distance_start_miles >= self.total_distance_miles - EPSILON:
            return self.total_distance_miles if distance_start_miles >= self.total_distance_miles - EPSILON else distance_start_miles

        current_distance = distance_start_miles
        remaining_minutes = driving_minutes
        for segment in self.segments:
            if segment.distance_end_miles <= current_distance + EPSILON:
                continue
            segment_start = max(current_distance, segment.distance_start_miles)
            segment_distance = segment.distance_end_miles - segment_start
            if segment_distance <= EPSILON:
                continue
            if segment.duration_minutes <= 0:
                current_distance = segment.distance_end_miles
                continue
            segment_remaining_minutes = segment.duration_minutes
            if segment_start > segment.distance_start_miles:
                consumed_fraction = (segment_start - segment.distance_start_miles) / (
                    segment.distance_end_miles - segment.distance_start_miles
                )
                segment_remaining_minutes = max(0.0, segment.duration_minutes * (1 - consumed_fraction))
            if remaining_minutes >= segment_remaining_minutes - EPSILON:
                current_distance = segment.distance_end_miles
                remaining_minutes -= math.ceil(segment_remaining_minutes)
                if remaining_minutes <= 0:
                    break
            else:
                current_distance = segment_start + segment_distance * (remaining_minutes / segment_remaining_minutes)
                remaining_minutes = 0
                break
        return min(self.total_distance_miles, current_distance)

    def driving_minutes_between(self, distance_start_miles: float, distance_end_miles: float) -> int:
        """Return conservative integer minutes needed to reach a route distance."""

        self._validate_distance(distance_start_miles)
        self._validate_distance(distance_end_miles)
        if distance_end_miles < distance_start_miles - EPSILON:
            raise InvalidScheduleInputError("Route distance cannot move backwards.")
        if distance_end_miles <= distance_start_miles + EPSILON:
            return 0

        required_minutes = 0.0
        for segment in self.segments:
            if segment.distance_end_miles <= distance_start_miles + EPSILON:
                continue
            if segment.distance_start_miles >= distance_end_miles - EPSILON:
                break
            overlap_start = max(distance_start_miles, segment.distance_start_miles)
            overlap_end = min(distance_end_miles, segment.distance_end_miles)
            overlap_distance = overlap_end - overlap_start
            if overlap_distance <= EPSILON:
                continue
            segment_distance = segment.distance_end_miles - segment.distance_start_miles
            if segment.duration_minutes > 0 and segment_distance > EPSILON:
                required_minutes += segment.duration_minutes * (overlap_distance / segment_distance)
        return max(1, math.ceil(required_minutes - EPSILON))

    def waypoint_distances(self) -> dict[str, float]:
        """Return current, pickup, and dropoff mileage from ordered route legs."""

        legs = self.route.get("legs")
        if not isinstance(legs, list) or len(legs) < 2:
            raise InvalidScheduleInputError("A route must contain current-to-pickup and pickup-to-dropoff legs.")
        pickup_distance = self.segments[0].distance_end_miles
        return {
            "current": 0.0,
            "pickup": pickup_distance,
            "dropoff": self.total_distance_miles,
        }

    def location_at(self, distance_miles: float) -> dict[str, Any]:
        """Return a non-fabricated route-position location for a stop."""

        self._validate_distance(distance_miles)
        location: dict[str, Any] = {
            "type": "route_position",
            "label": f"Route mile {distance_miles:.1f}",
            "route_distance_miles": round(distance_miles, 2),
        }
        coordinate = self._coordinate_at(distance_miles)
        if coordinate:
            longitude, latitude = coordinate
            location.update({"latitude": round(latitude, 7), "longitude": round(longitude, 7)})
        return location

    def _build_segments(self, duration_seconds: float) -> list[ProgressSegment]:
        legs = self.route.get("legs")
        raw_segments: list[tuple[float, float]] = []
        if isinstance(legs, list) and legs:
            for index, leg in enumerate(legs):
                if not isinstance(leg, dict):
                    raise InvalidScheduleInputError(f"Route leg {index} is invalid.")
                raw_segments.append(
                    (
                        self._number(leg.get("distance_miles"), f"route.legs[{index}].distance_miles", minimum=0),
                        self._number(
                            leg.get("duration_seconds"),
                            f"route.legs[{index}].duration_seconds",
                            minimum=0,
                        ),
                    )
                )
                if raw_segments[-1][0] > EPSILON and raw_segments[-1][1] <= 0:
                    raise InvalidScheduleInputError(f"Route leg {index} has distance but no driving duration.")
                if raw_segments[-1][0] <= EPSILON and raw_segments[-1][1] > EPSILON:
                    raise InvalidScheduleInputError(f"Route leg {index} has driving duration but no route distance.")
        else:
            steps = self.route.get("route_steps")
            if isinstance(steps, list) and steps:
                for index, step in enumerate(steps):
                    if not isinstance(step, dict):
                        raise InvalidScheduleInputError(f"Route step {index} is invalid.")
                    raw_segments.append(
                        (
                            self._number(step.get("distance_miles"), f"route.route_steps[{index}].distance_miles", minimum=0),
                            self._number(
                                step.get("duration_seconds"),
                                f"route.route_steps[{index}].duration_seconds",
                                minimum=0,
                            ),
                        )
                    )
                    if raw_segments[-1][0] > EPSILON and raw_segments[-1][1] <= 0:
                        raise InvalidScheduleInputError(f"Route step {index} has distance but no driving duration.")
                    if raw_segments[-1][0] <= EPSILON and raw_segments[-1][1] > EPSILON:
                        raise InvalidScheduleInputError(f"Route step {index} has driving duration but no route distance.")
            else:
                raw_segments = [(self.total_distance_miles, duration_seconds)]

        distance_sum = sum(distance for distance, _ in raw_segments)
        duration_sum = sum(seconds for _, seconds in raw_segments)
        if abs(distance_sum - self.total_distance_miles) > max(0.1, self.total_distance_miles * 0.01):
            raise InvalidScheduleInputError("Route leg/step distances are inconsistent with total route distance.")
        if abs(duration_sum - duration_seconds) > max(60.0, duration_seconds * 0.01):
            raise InvalidScheduleInputError("Route leg/step durations are inconsistent with total route duration.")

        raw_seconds = [seconds for _, seconds in raw_segments]
        distance_scale = self.total_distance_miles / distance_sum if distance_sum > EPSILON else 1.0
        normalized_distances = [distance * distance_scale for distance, _ in raw_segments]
        minimum_durations = [1 if distance > EPSILON else 0 for distance in normalized_distances]
        # A positive-distance segment cannot be assigned zero integer minutes:
        # doing so would make a leg boundary unreachable after the scheduler
        # stops at that boundary. For unusually granular synthetic/provider
        # data, conservatively extend the normalized route time as needed.
        self.total_driving_minutes = max(self.total_driving_minutes, sum(minimum_durations))
        floored_minimum_total = sum(
            max(math.floor(seconds / 60), minimum)
            for seconds, minimum in zip(raw_seconds, minimum_durations, strict=True)
        )
        self.total_driving_minutes = max(self.total_driving_minutes, floored_minimum_total)
        integer_durations = self._integerize_durations(
            raw_seconds,
            self.total_driving_minutes,
            minimum_durations=minimum_durations,
        )
        segments: list[ProgressSegment] = []
        distance_cursor = 0.0
        time_cursor = 0
        for index, (normalized_distance, duration_minutes) in enumerate(zip(normalized_distances, integer_durations, strict=True)):
            if index == len(raw_segments) - 1:
                distance_end = self.total_distance_miles
            else:
                distance_end = min(self.total_distance_miles, distance_cursor + normalized_distance)
            segments.append(
                ProgressSegment(
                    distance_start_miles=distance_cursor,
                    distance_end_miles=distance_end,
                    duration_minutes=duration_minutes,
                    time_start_minutes=time_cursor,
                    time_end_minutes=time_cursor + duration_minutes,
                )
            )
            distance_cursor = distance_end
            time_cursor += duration_minutes
        if segments and time_cursor != self.total_driving_minutes:
            last = segments[-1]
            segments[-1] = ProgressSegment(
                last.distance_start_miles,
                last.distance_end_miles,
                last.duration_minutes + self.total_driving_minutes - time_cursor,
                last.time_start_minutes,
                last.time_end_minutes + self.total_driving_minutes - time_cursor,
            )
        return segments

    @staticmethod
    def _integerize_durations(
        raw_seconds: list[float],
        total_minutes: int,
        *,
        minimum_durations: list[int] | None = None,
    ) -> list[int]:
        floors = [math.floor(seconds / 60) for seconds in raw_seconds]
        minimum_durations = minimum_durations or [0] * len(raw_seconds)
        result = [max(floor, minimum) for floor, minimum in zip(floors, minimum_durations, strict=True)]
        remaining = total_minutes - sum(result)
        if remaining < 0 or remaining > len(floors):
            raise InvalidScheduleInputError("Route durations cannot be normalized to integer minutes.")
        fractions = sorted(
            range(len(raw_seconds)),
            key=lambda index: (raw_seconds[index] / 60 - floors[index], -index),
            reverse=True,
        )
        for index in fractions[:remaining]:
            result[index] += 1
        return result

    @staticmethod
    def _number(value: Any, context: str, *, minimum: float) -> float:
        if isinstance(value, bool):
            raise InvalidScheduleInputError(f"{context} must be numeric.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidScheduleInputError(f"{context} must be numeric.") from exc
        if not math.isfinite(number) or number < minimum:
            raise InvalidScheduleInputError(f"{context} is out of range.")
        return number

    def _validate_distance(self, distance_miles: float) -> None:
        if distance_miles < -EPSILON or distance_miles > self.total_distance_miles + EPSILON:
            raise InvalidScheduleInputError("Route distance is outside the normalized route.")

    @staticmethod
    def _read_geometry(route: dict[str, Any]) -> list[tuple[float, float]]:
        geometry = route.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(coordinates, list):
            coordinates = route.get("coordinates")
            if not isinstance(coordinates, list):
                return []
            try:
                return [(float(point[1]), float(point[0])) for point in coordinates if isinstance(point, list) and len(point) >= 2]
            except (TypeError, ValueError) as exc:
                raise InvalidScheduleInputError("Route geometry contains invalid coordinates.") from exc
        result: list[tuple[float, float]] = []
        try:
            for point in coordinates:
                if isinstance(point, list) and len(point) >= 2:
                    result.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError) as exc:
            raise InvalidScheduleInputError("Route geometry contains invalid coordinates.") from exc
        return result

    def _coordinate_at(self, distance_miles: float) -> tuple[float, float] | None:
        if not self._geometry:
            return None
        if len(self._geometry) == 1:
            return self._geometry[0]
        geometric_lengths = [self._haversine_miles(self._geometry[i], self._geometry[i + 1]) for i in range(len(self._geometry) - 1)]
        geometric_total = sum(geometric_lengths)
        if geometric_total <= EPSILON:
            return self._geometry[0]
        target = geometric_total * (distance_miles / max(self.total_distance_miles, EPSILON))
        traversed = 0.0
        for index, segment_length in enumerate(geometric_lengths):
            if traversed + segment_length >= target:
                fraction = 0.0 if segment_length <= EPSILON else (target - traversed) / segment_length
                start = self._geometry[index]
                end = self._geometry[index + 1]
                return (start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction)
            traversed += segment_length
        return self._geometry[-1]

    @staticmethod
    def _haversine_miles(first: tuple[float, float], second: tuple[float, float]) -> float:
        radius_miles = 3958.7613
        longitude_one, latitude_one = map(math.radians, first)
        longitude_two, latitude_two = map(math.radians, second)
        delta_latitude = latitude_two - latitude_one
        delta_longitude = longitude_two - longitude_one
        value = math.sin(delta_latitude / 2) ** 2 + math.cos(latitude_one) * math.cos(latitude_two) * math.sin(delta_longitude / 2) ** 2
        return radius_miles * 2 * math.asin(math.sqrt(value))
