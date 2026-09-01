"""OSRM-compatible routing and application-facing route normalization."""

from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings

from .errors import MalformedProviderResponseError, NoRouteFoundError
from .geocoding import Location
from .http import fetch_json
from .validators import parse_coordinate_pair, require_mapping, require_number, require_sequence

METERS_PER_MILE = 1609.344


@dataclass(frozen=True)
class RouteStep:
    sequence: int
    instruction: str
    road_name: str | None
    maneuver_type: str | None
    maneuver_modifier: str | None
    distance_miles: float
    duration_seconds: int
    cumulative_distance_miles: float
    location: dict[str, float] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Route:
    distance_miles: float
    estimated_driving_seconds: int
    estimated_driving_hours: float
    coordinates: list[list[float]]
    geometry: dict[str, Any]
    route_steps: list[RouteStep]
    legs: list[dict[str, Any]]
    waypoints: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "distance_miles": self.distance_miles,
            "estimated_driving_seconds": self.estimated_driving_seconds,
            "estimated_driving_hours": self.estimated_driving_hours,
            "coordinates": self.coordinates,
            "geometry": self.geometry,
            "route_steps": [step.to_dict() for step in self.route_steps],
            "legs": self.legs,
            "waypoints": self.waypoints,
        }


class OSRMRouter:
    """Request one ordered route and preserve its pickup waypoint."""

    provider_name = "Routing provider"

    def __init__(self, *, base_url: str | None = None, timeout_seconds: float | None = None):
        self.base_url = base_url or settings.OSRM_BASE_URL
        self.timeout_seconds = timeout_seconds or settings.EXTERNAL_PROVIDER_TIMEOUT_SECONDS

    def route(self, locations: dict[str, Location]) -> Route:
        ordered_roles = ("current", "pickup", "dropoff")
        if any(role not in locations for role in ordered_roles):
            raise MalformedProviderResponseError("A route requires current, pickup, and dropoff locations.")

        ordered_locations = [locations[role] for role in ordered_roles]
        coordinate_path = ";".join(
            f"{location.longitude:.7f},{location.latitude:.7f}" for location in ordered_locations
        )
        payload = fetch_json(
            self.base_url,
            f"/route/v1/driving/{coordinate_path}",
            params={
                "overview": "full",
                "geometries": "geojson",
                "steps": "true",
                "annotations": "distance,duration",
            },
            headers={"Accept": "application/json"},
            timeout_seconds=self.timeout_seconds,
            provider_name=self.provider_name,
        )
        return self._normalize(payload, ordered_locations, ordered_roles)

    def _normalize(
        self,
        payload: Any,
        locations: list[Location],
        roles: tuple[str, str, str],
    ) -> Route:
        response = require_mapping(payload, "routing response")
        code = response.get("code")
        if code == "NoRoute":
            raise NoRouteFoundError("The routing provider could not find a drivable route.")
        if code != "Ok":
            raise MalformedProviderResponseError("The routing provider returned an unsuccessful response.")

        routes = require_sequence(response.get("routes"), "routing response.routes")
        if not routes:
            raise MalformedProviderResponseError("The routing provider returned no route.")
        route_data = require_mapping(routes[0], "routing response.routes[0]")
        distance_meters = require_number(route_data.get("distance"), "route.distance", minimum=0)
        duration_seconds = round(require_number(route_data.get("duration"), "route.duration", minimum=0))
        geometry = require_mapping(route_data.get("geometry"), "route.geometry")
        if geometry.get("type") != "LineString":
            raise MalformedProviderResponseError("The routing provider returned unsupported geometry.")
        raw_coordinates = require_sequence(geometry.get("coordinates"), "route.geometry.coordinates")
        if len(raw_coordinates) < 2:
            raise MalformedProviderResponseError("The routing provider returned incomplete route geometry.")

        normalized_geometry_coordinates: list[list[float]] = []
        leaflet_coordinates: list[list[float]] = []
        for index, coordinate in enumerate(raw_coordinates):
            longitude, latitude = parse_coordinate_pair(coordinate, f"route.geometry.coordinates[{index}]")
            normalized_geometry_coordinates.append([round(longitude, 7), round(latitude, 7)])
            leaflet_coordinates.append([round(latitude, 7), round(longitude, 7)])

        legs = self._normalize_legs(route_data.get("legs"), locations)
        route_steps = self._normalize_steps(route_data.get("legs"))
        waypoints = self._normalize_waypoints(response.get("waypoints"), locations, roles)

        return Route(
            distance_miles=round(distance_meters / METERS_PER_MILE, 2),
            estimated_driving_seconds=duration_seconds,
            estimated_driving_hours=round(duration_seconds / 3600, 2),
            coordinates=leaflet_coordinates,
            geometry={"type": "LineString", "coordinates": normalized_geometry_coordinates},
            route_steps=route_steps,
            legs=legs,
            waypoints=waypoints,
        )

    def _normalize_legs(self, raw_legs: Any, locations: list[Location]) -> list[dict[str, Any]]:
        legs = require_sequence(raw_legs, "route.legs")
        if len(legs) != len(locations) - 1:
            raise MalformedProviderResponseError("The routing provider returned an unexpected leg count.")
        normalized: list[dict[str, Any]] = []
        for index, raw_leg in enumerate(legs):
            leg = require_mapping(raw_leg, f"route.legs[{index}]")
            distance_meters = require_number(leg.get("distance"), f"route.legs[{index}].distance", minimum=0)
            duration_seconds = round(
                require_number(leg.get("duration"), f"route.legs[{index}].duration", minimum=0)
            )
            normalized.append(
                {
                    "sequence": index,
                    "from": locations[index].to_dict(),
                    "to": locations[index + 1].to_dict(),
                    "distance_miles": round(distance_meters / METERS_PER_MILE, 2),
                    "duration_seconds": duration_seconds,
                }
            )
        return normalized

    def _normalize_steps(self, raw_legs: Any) -> list[RouteStep]:
        legs = require_sequence(raw_legs, "route.legs")
        steps: list[RouteStep] = []
        cumulative_miles = 0.0
        sequence = 0
        for leg_index, raw_leg in enumerate(legs):
            leg = require_mapping(raw_leg, f"route.legs[{leg_index}]")
            raw_steps = require_sequence(leg.get("steps", []), f"route.legs[{leg_index}].steps")
            for step_index, raw_step in enumerate(raw_steps):
                step = require_mapping(raw_step, f"route.legs[{leg_index}].steps[{step_index}]")
                distance_meters = require_number(
                    step.get("distance"),
                    f"route.legs[{leg_index}].steps[{step_index}].distance",
                    minimum=0,
                )
                duration_seconds = round(
                    require_number(
                        step.get("duration"),
                        f"route.legs[{leg_index}].steps[{step_index}].duration",
                        minimum=0,
                    )
                )
                maneuver = require_mapping(
                    step.get("maneuver", {}),
                    f"route.legs[{leg_index}].steps[{step_index}].maneuver",
                )
                raw_maneuver_location = maneuver.get("location")
                maneuver_location = None
                if raw_maneuver_location is not None:
                    longitude, latitude = parse_coordinate_pair(
                        raw_maneuver_location,
                        f"route.legs[{leg_index}].steps[{step_index}].maneuver.location",
                    )
                    maneuver_location = {"latitude": round(latitude, 7), "longitude": round(longitude, 7)}
                maneuver_type = self._optional_text(maneuver.get("type"))
                maneuver_modifier = self._optional_text(maneuver.get("modifier"))
                road_name = self._optional_text(step.get("name"))
                distance_miles = distance_meters / METERS_PER_MILE
                cumulative_miles += distance_miles
                steps.append(
                    RouteStep(
                        sequence=sequence,
                        instruction=self._instruction(maneuver_type, maneuver_modifier, road_name),
                        road_name=road_name,
                        maneuver_type=maneuver_type,
                        maneuver_modifier=maneuver_modifier,
                        distance_miles=round(distance_miles, 2),
                        duration_seconds=duration_seconds,
                        cumulative_distance_miles=round(cumulative_miles, 6),
                        location=maneuver_location,
                    )
                )
                sequence += 1
        return steps

    def _normalize_waypoints(
        self,
        raw_waypoints: Any,
        locations: list[Location],
        roles: tuple[str, str, str],
    ) -> list[dict[str, Any]]:
        waypoints = require_sequence(raw_waypoints, "routing response.waypoints")
        if len(waypoints) != len(locations):
            raise MalformedProviderResponseError("The routing provider returned an unexpected waypoint count.")
        normalized: list[dict[str, Any]] = []
        for index, (raw_waypoint, role, location) in enumerate(zip(waypoints, roles, locations, strict=True)):
            waypoint = require_mapping(raw_waypoint, f"routing response.waypoints[{index}]")
            snapped_longitude, snapped_latitude = parse_coordinate_pair(
                waypoint.get("location"),
                f"routing response.waypoints[{index}].location",
            )
            normalized.append(
                {
                    "sequence": index,
                    "role": role,
                    "input_text": location.input_text,
                    "normalized_name": location.normalized_name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "snapped_latitude": round(snapped_latitude, 7),
                    "snapped_longitude": round(snapped_longitude, 7),
                    "provider_name": self._optional_text(waypoint.get("name")),
                }
            )
        return normalized

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _instruction(
        maneuver_type: str | None,
        maneuver_modifier: str | None,
        road_name: str | None,
    ) -> str:
        if maneuver_type == "depart":
            return "Depart"
        if maneuver_type == "arrive":
            return "Arrive at destination"
        readable_type = (maneuver_type or "Continue").replace("_", " ").capitalize()
        readable_modifier = f" {maneuver_modifier}" if maneuver_modifier else ""
        road = f" onto {road_name}" if road_name else ""
        return f"{readable_type}{readable_modifier}{road}"
