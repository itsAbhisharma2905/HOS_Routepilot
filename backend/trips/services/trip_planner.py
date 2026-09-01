"""Application orchestration for routing, HOS scheduling, and validation."""

from datetime import datetime, timezone
from typing import Any, Protocol

from django.conf import settings

from .errors import InvalidScheduleInputError
from .daily_logs import build_daily_logs
from .geocoding import Location, NominatimGeocoder
from .hos_engine import HOSPlanInput, HOSScheduler, HOSSchedule
from .routing import OSRMRouter, Route
from .schedule_validator import validate_schedule


class Geocoder(Protocol):
    def geocode_many(self, queries: dict[str, str]) -> dict[str, Location]: ...


class Router(Protocol):
    def route(self, locations: dict[str, Location]) -> Route: ...


class Scheduler(Protocol):
    def schedule(self, plan_input: HOSPlanInput) -> HOSSchedule: ...


class RoutePlanningService:
    """Compose provider routing with the backend-owned HOS planning pipeline."""

    def __init__(
        self,
        *,
        geocoder: Geocoder | None = None,
        router: Router | None = None,
        scheduler: Scheduler | None = None,
    ):
        self.geocoder = geocoder or NominatimGeocoder()
        self.router = router or OSRMRouter()
        self.scheduler = scheduler or HOSScheduler()

    def plan_route(self, trip_input: dict[str, Any]) -> dict[str, Any]:
        locations = self.geocoder.geocode_many(
            {
                "current": trip_input["current_location"],
                "pickup": trip_input["pickup_location"],
                "dropoff": trip_input["dropoff_location"],
            }
        )
        route = self.router.route(locations)
        return {
            "status": "route_ready",
            "trip_input": trip_input,
            "locations": {role: location.to_dict() for role, location in locations.items()},
            "route": route.to_dict(),
        }

    def plan(
        self,
        trip_input: dict[str, Any],
        *,
        start_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Build route, schedule events, then independently validate the timeline."""

        route_plan = self.plan_route(trip_input)
        plan_input = HOSPlanInput(
            current_location=route_plan["locations"]["current"],
            pickup_location=route_plan["locations"]["pickup"],
            dropoff_location=route_plan["locations"]["dropoff"],
            cycle_used_hours=trip_input["cycle_used_hours"],
            route=route_plan["route"],
            start_timestamp=start_timestamp or self._configured_start_timestamp(),
        )
        schedule = self.scheduler.schedule(plan_input)
        compliance = validate_schedule(
            schedule.events,
            initial_cycle_used_hours=trip_input["cycle_used_hours"],
            route_total_distance_miles=schedule.route_total_distance_miles,
        )
        scheduled = schedule.to_dict()
        daily_logs = build_daily_logs(schedule.events, compliant=compliance["compliant"])
        summary = {**scheduled["summary"], "compliant": compliance["compliant"]}
        return {
            **route_plan,
            "status": "planned",
            "events": scheduled["events"],
            "stops": scheduled["stops"],
            "summary": summary,
            "compliance": compliance,
            "violations": compliance["violations"],
            "daily_logs": [daily_log.to_dict() for daily_log in daily_logs],
        }

    @staticmethod
    def _configured_start_timestamp() -> datetime:
        raw_value = settings.PLANNING_START_TIMESTAMP.replace("Z", "+00:00")
        try:
            timestamp = datetime.fromisoformat(raw_value)
        except ValueError as exc:
            raise InvalidScheduleInputError("PLANNING_START_TIMESTAMP must be a valid ISO-8601 timestamp.") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidScheduleInputError("PLANNING_START_TIMESTAMP must include a timezone offset.")
        return timestamp.astimezone(timezone.utc)
