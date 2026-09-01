"""Pure, deterministic HOS scheduling for the assessment's property-carrier model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from typing import Any, Mapping

from .errors import ImpossiblePlanningStateError, InvalidScheduleInputError
from .route_progress import EPSILON, RouteProgress

# All scheduling calculations use integer minutes. These are the only HOS rule
# values the scheduler uses, which keeps the rule set visible and testable.
DRIVING_LIMIT_MINUTES = 11 * 60
DUTY_WINDOW_MINUTES = 14 * 60
BREAK_AFTER_DRIVING_MINUTES = 8 * 60
BREAK_DURATION_MINUTES = 30
DAILY_REST_MINUTES = 600
CYCLE_LIMIT_HOURS = 70
CYCLE_LIMIT_MINUTES = CYCLE_LIMIT_HOURS * 60
RESTART_MINUTES = 34 * 60
PICKUP_MINUTES = 60
DROPOFF_MINUTES = 60
FUEL_INTERVAL_MILES = 1000.0
FUEL_DURATION_MINUTES = 30
MAX_SCHEDULER_ITERATIONS = 10000
DEFAULT_PLANNING_START_TIMESTAMP = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


class DutyStatus(str, Enum):
    OFF_DUTY = "OFF_DUTY"
    SLEEPER_BERTH = "SLEEPER_BERTH"
    DRIVING = "DRIVING"
    ON_DUTY_NOT_DRIVING = "ON_DUTY_NOT_DRIVING"


@dataclass(frozen=True)
class TripEvent:
    id: str
    start: datetime
    end: datetime
    status: DutyStatus
    reason: str
    location: dict[str, Any]
    route_distance_start: float
    route_distance_end: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_minutes(self) -> int:
        return round((self.end - self.start).total_seconds() / 60)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "status": self.status.value if isinstance(self.status, DutyStatus) else str(self.status),
            "reason": self.reason,
            "location": self.location,
            "duration": self.duration_minutes,
            "duration_minutes": self.duration_minutes,
            "duration_hours": round(self.duration_minutes / 60, 2),
            "distance_start": round(self.route_distance_start, 6),
            "distance_end": round(self.route_distance_end, 6),
            "route_distance_start": round(self.route_distance_start, 6),
            "route_distance_end": round(self.route_distance_end, 6),
            "metadata": self.metadata,
        }


@dataclass
class HOSState:
    current_timestamp: datetime
    route_distance_miles: float
    cycle_used_minutes: int
    driving_in_current_window_minutes: int = 0
    elapsed_duty_window_minutes: int = 0
    driving_since_break_minutes: int = 0
    distance_since_fuel_miles: float = 0.0
    pickup_completed: bool = False
    dropoff_completed: bool = False

    @property
    def cycle_remaining_minutes(self) -> int:
        return CYCLE_LIMIT_MINUTES - self.cycle_used_minutes

    @property
    def driving_remaining_minutes(self) -> int:
        return DRIVING_LIMIT_MINUTES - self.driving_in_current_window_minutes

    @property
    def duty_window_remaining_minutes(self) -> int:
        return DUTY_WINDOW_MINUTES - self.elapsed_duty_window_minutes

    @property
    def break_driving_remaining_minutes(self) -> int:
        return BREAK_AFTER_DRIVING_MINUTES - self.driving_since_break_minutes

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_timestamp": self.current_timestamp.isoformat(),
            "route_distance_miles": round(self.route_distance_miles, 6),
            "cycle_used_minutes": self.cycle_used_minutes,
            "cycle_remaining_minutes": self.cycle_remaining_minutes,
            "driving_in_current_window_minutes": self.driving_in_current_window_minutes,
            "elapsed_duty_window_minutes": self.elapsed_duty_window_minutes,
            "driving_since_break_minutes": self.driving_since_break_minutes,
            "distance_since_fuel_miles": round(self.distance_since_fuel_miles, 6),
            "pickup_completed": self.pickup_completed,
            "dropoff_completed": self.dropoff_completed,
        }


@dataclass(frozen=True)
class HOSPlanInput:
    current_location: Mapping[str, Any]
    pickup_location: Mapping[str, Any]
    dropoff_location: Mapping[str, Any]
    cycle_used_hours: float
    route: Mapping[str, Any]
    start_timestamp: datetime = DEFAULT_PLANNING_START_TIMESTAMP


@dataclass(frozen=True)
class HOSSchedule:
    events: tuple[TripEvent, ...]
    final_state: HOSState
    initial_cycle_used_minutes: int
    route_total_distance_miles: float
    estimated_route_driving_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "stops": [event.to_dict() for event in self.events if event.status != DutyStatus.DRIVING],
            "summary": self.summary(),
            "state": self.final_state.to_dict(),
        }

    def summary(self) -> dict[str, Any]:
        if not self.events:
            total_duration_minutes = 0
            first_start = self.final_state.current_timestamp
            last_end = first_start
        else:
            first_start = self.events[0].start
            last_end = self.events[-1].end
            total_duration_minutes = round((last_end - first_start).total_seconds() / 60)

        def minutes_for(status: DutyStatus) -> int:
            return sum(event.duration_minutes for event in self.events if event.status == status)

        driving_minutes = minutes_for(DutyStatus.DRIVING)
        on_duty_minutes = minutes_for(DutyStatus.ON_DUTY_NOT_DRIVING)
        breaks = [event for event in self.events if event.reason == "Required 30-minute break"]
        rests = [event for event in self.events if event.reason == "Required 10-hour rest (daily reset)"]
        restarts = [event for event in self.events if event.reason == "34-hour cycle restart"]
        fuel_stops = [event for event in self.events if event.reason == "Fuel"]
        pickup = [event for event in self.events if event.reason == "Pickup"]
        dropoff = [event for event in self.events if event.reason == "Dropoff"]
        number_of_days = (last_end.date() - first_start.date()).days + 1 if self.events else 0
        return {
            "total_route_miles": round(self.route_total_distance_miles, 2),
            "estimated_route_driving_seconds": self.estimated_route_driving_seconds,
            "scheduled_total_duration_minutes": total_duration_minutes,
            "scheduled_total_duration_hours": round(total_duration_minutes / 60, 2),
            "total_driving_hours": round(driving_minutes / 60, 2),
            "total_on_duty_not_driving_hours": round(on_duty_minutes / 60, 2),
            "number_of_breaks": len(breaks),
            "number_of_rest_periods": len(rests),
            "number_of_cycle_restarts": len(restarts),
            "number_of_fuel_stops": len(fuel_stops),
            "pickup_duration_minutes": sum(event.duration_minutes for event in pickup),
            "dropoff_duration_minutes": sum(event.duration_minutes for event in dropoff),
            "initial_cycle_used_hours": round(self.initial_cycle_used_minutes / 60, 2),
            "final_cycle_usage_hours": round(self.final_state.cycle_used_minutes / 60, 2),
            "final_cycle_remaining_hours": round(self.final_state.cycle_remaining_minutes / 60, 2),
            "number_of_calendar_days": number_of_days,
            "planning_start": first_start.isoformat() if self.events else None,
            "planning_end": last_end.isoformat() if self.events else None,
        }


class HOSScheduler:
    """Build an event timeline by applying the earliest HOS constraint."""

    def schedule(self, plan_input: HOSPlanInput | Mapping[str, Any]) -> HOSSchedule:
        if isinstance(plan_input, Mapping):
            locations = plan_input.get("locations")
            if not isinstance(locations, Mapping):
                locations = {}
            plan_input = HOSPlanInput(
                current_location=plan_input.get("current_location", locations.get("current", {})),
                pickup_location=plan_input.get("pickup_location", locations.get("pickup", {})),
                dropoff_location=plan_input.get("dropoff_location", locations.get("dropoff", {})),
                cycle_used_hours=plan_input.get("cycle_used_hours", 0),
                route=plan_input.get("route", {}),
                start_timestamp=plan_input.get("start_timestamp", DEFAULT_PLANNING_START_TIMESTAMP),
            )
        self._validate_plan_input(plan_input)
        progress = RouteProgress(dict(plan_input.route))
        waypoint_distances = progress.waypoint_distances()
        initial_cycle_used_minutes = self._hours_to_minutes(plan_input.cycle_used_hours)
        self._progress = progress
        self._waypoints = waypoint_distances
        self._locations = {
            "current": dict(plan_input.current_location),
            "pickup": dict(plan_input.pickup_location),
            "dropoff": dict(plan_input.dropoff_location),
        }
        self._state = HOSState(
            current_timestamp=self._normalize_timestamp(plan_input.start_timestamp),
            route_distance_miles=0.0,
            cycle_used_minutes=initial_cycle_used_minutes,
        )
        self._events: list[TripEvent] = []

        for _ in range(MAX_SCHEDULER_ITERATIONS):
            if self._state.dropoff_completed:
                break
            if not self._state.pickup_completed:
                if self._state.route_distance_miles < self._waypoints["pickup"] - EPSILON:
                    self._drive_toward(self._waypoints["pickup"])
                else:
                    self._schedule_activity(
                        duration_minutes=PICKUP_MINUTES,
                        reason="Pickup",
                        location=self._locations["pickup"],
                    )
                    self._state.pickup_completed = True
                continue

            if self._state.route_distance_miles < self._waypoints["dropoff"] - EPSILON:
                self._drive_toward(self._waypoints["dropoff"])
            else:
                self._schedule_activity(
                    duration_minutes=DROPOFF_MINUTES,
                    reason="Dropoff",
                    location=self._locations["dropoff"],
                )
                self._state.dropoff_completed = True
        else:
            raise ImpossiblePlanningStateError("The HOS scheduler could not reach the dropoff in a finite number of steps.")

        return HOSSchedule(
            events=tuple(self._events),
            final_state=self._state,
            initial_cycle_used_minutes=initial_cycle_used_minutes,
            route_total_distance_miles=progress.total_distance_miles,
            estimated_route_driving_seconds=progress.total_driving_seconds,
        )

    def _drive_toward(self, waypoint_distance: float) -> None:
        current_distance = self._state.route_distance_miles
        route_remaining = waypoint_distance - current_distance
        if route_remaining <= EPSILON:
            raise ImpossiblePlanningStateError("Driving was requested after the route waypoint was reached.")

        distance_until_fuel = FUEL_INTERVAL_MILES - self._state.distance_since_fuel_miles
        if distance_until_fuel <= EPSILON:
            self._schedule_fuel()
            return
        fuel_target = current_distance + distance_until_fuel
        target_distance = min(waypoint_distance, fuel_target)
        max_drive_minutes = self._max_drive_minutes()
        if max_drive_minutes <= 0:
            self._schedule_constraint_stop()
            return

        required_minutes = self._progress.driving_minutes_between(current_distance, target_distance)
        if required_minutes <= max_drive_minutes:
            drive_minutes = required_minutes
            end_distance = target_distance
        else:
            drive_minutes = max_drive_minutes
            end_distance = self._progress.distance_after(current_distance, drive_minutes)

        if end_distance <= current_distance + EPSILON or drive_minutes <= 0:
            raise ImpossiblePlanningStateError("Route progress did not advance during a driving segment.")
        self._schedule_driving(end_distance, drive_minutes)

    def _max_drive_minutes(self) -> int:
        return min(
            self._state.driving_remaining_minutes,
            self._state.duty_window_remaining_minutes,
            self._state.break_driving_remaining_minutes,
            self._state.cycle_remaining_minutes,
        )

    def _schedule_constraint_stop(self) -> None:
        if self._state.cycle_remaining_minutes <= 0:
            self._schedule_restart()
            return
        if self._state.driving_remaining_minutes <= 0 or self._state.duty_window_remaining_minutes <= 0:
            self._schedule_daily_rest()
            return
        if self._state.break_driving_remaining_minutes <= 0:
            if self._state.duty_window_remaining_minutes < BREAK_DURATION_MINUTES:
                self._schedule_daily_rest()
            else:
                self._schedule_break()
            return
        raise ImpossiblePlanningStateError("No applicable HOS constraint could explain the blocked driving state.")

    def _schedule_driving(self, end_distance: float, duration_minutes: int) -> None:
        start_distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.DRIVING,
            duration_minutes=duration_minutes,
            reason="Driving",
            location=self._progress.location_at(start_distance),
            route_distance_start=start_distance,
            route_distance_end=end_distance,
        )
        distance_driven = end_distance - start_distance
        # Keep full precision internally. Event serialization rounds for the
        # API, but rounding state here can leave a tiny remainder larger than
        # the completion epsilon and cause a non-advancing loop.
        self._state.route_distance_miles = end_distance
        self._state.driving_in_current_window_minutes += duration_minutes
        self._state.elapsed_duty_window_minutes += duration_minutes
        self._state.driving_since_break_minutes += duration_minutes
        self._state.cycle_used_minutes += duration_minutes
        self._state.distance_since_fuel_miles += distance_driven

    def _schedule_activity(self, *, duration_minutes: int, reason: str, location: dict[str, Any]) -> None:
        self._ensure_activity_capacity(duration_minutes)
        distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            duration_minutes=duration_minutes,
            reason=reason,
            location=location,
            route_distance_start=distance,
            route_distance_end=distance,
        )
        self._state.elapsed_duty_window_minutes += duration_minutes
        self._state.cycle_used_minutes += duration_minutes

    def _schedule_fuel(self) -> None:
        self._ensure_activity_capacity(FUEL_DURATION_MINUTES)
        distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            duration_minutes=FUEL_DURATION_MINUTES,
            reason="Fuel",
            location=self._progress.location_at(distance),
            route_distance_start=distance,
            route_distance_end=distance,
        )
        self._state.elapsed_duty_window_minutes += FUEL_DURATION_MINUTES
        self._state.cycle_used_minutes += FUEL_DURATION_MINUTES
        self._state.distance_since_fuel_miles = 0.0

    def _schedule_break(self) -> None:
        distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.OFF_DUTY,
            duration_minutes=BREAK_DURATION_MINUTES,
            reason="Required 30-minute break",
            location=self._progress.location_at(distance),
            route_distance_start=distance,
            route_distance_end=distance,
        )
        self._state.elapsed_duty_window_minutes += BREAK_DURATION_MINUTES
        self._state.driving_since_break_minutes = 0

    def _schedule_daily_rest(self) -> None:
        distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.SLEEPER_BERTH,
            duration_minutes=DAILY_REST_MINUTES,
            reason="Required 10-hour rest (daily reset)",
            location=self._progress.location_at(distance),
            route_distance_start=distance,
            route_distance_end=distance,
        )
        self._reset_daily_state()

    def _schedule_restart(self) -> None:
        distance = self._state.route_distance_miles
        self._add_event(
            status=DutyStatus.SLEEPER_BERTH,
            duration_minutes=RESTART_MINUTES,
            reason="34-hour cycle restart",
            location=self._progress.location_at(distance),
            route_distance_start=distance,
            route_distance_end=distance,
        )
        self._state.cycle_used_minutes = 0
        self._reset_daily_state()

    def _ensure_activity_capacity(self, duration_minutes: int) -> None:
        if duration_minutes <= 0:
            raise ImpossiblePlanningStateError("Non-driving activities must have positive duration.")
        if self._state.cycle_remaining_minutes < duration_minutes:
            self._schedule_restart()
        if self._state.duty_window_remaining_minutes < duration_minutes:
            self._schedule_daily_rest()

    def _reset_daily_state(self) -> None:
        self._state.driving_in_current_window_minutes = 0
        self._state.elapsed_duty_window_minutes = 0
        self._state.driving_since_break_minutes = 0

    def _add_event(
        self,
        *,
        status: DutyStatus,
        duration_minutes: int,
        reason: str,
        location: dict[str, Any],
        route_distance_start: float,
        route_distance_end: float,
    ) -> None:
        if duration_minutes <= 0:
            raise ImpossiblePlanningStateError("Generated events must have positive duration.")
        start = self._state.current_timestamp
        end = start + timedelta(minutes=duration_minutes)
        self._events.append(
            TripEvent(
                id=f"event-{len(self._events) + 1:04d}",
                start=start,
                end=end,
                status=status,
                reason=reason,
                location=dict(location),
                route_distance_start=round(route_distance_start, 6),
                route_distance_end=round(route_distance_end, 6),
            )
        )
        self._state.current_timestamp = end

    @staticmethod
    def _validate_plan_input(plan_input: HOSPlanInput) -> None:
        if not isinstance(plan_input, HOSPlanInput):
            raise InvalidScheduleInputError("HOS scheduler input must be a HOSPlanInput object.")
        if not isinstance(plan_input.start_timestamp, datetime):
            raise InvalidScheduleInputError("Planning start timestamp is required.")
        if not isinstance(plan_input.route, Mapping):
            raise InvalidScheduleInputError("A normalized route is required for HOS scheduling.")
        if not all(isinstance(location, Mapping) for location in (
            plan_input.current_location,
            plan_input.pickup_location,
            plan_input.dropoff_location,
        )):
            raise InvalidScheduleInputError("Current, pickup, and dropoff locations are required for HOS scheduling.")
        try:
            cycle_used_hours = float(plan_input.cycle_used_hours)
        except (TypeError, ValueError) as exc:
            raise InvalidScheduleInputError("cycle_used_hours must be numeric.") from exc
        if not math.isfinite(cycle_used_hours) or cycle_used_hours < 0 or cycle_used_hours > CYCLE_LIMIT_HOURS:
            raise InvalidScheduleInputError(f"cycle_used_hours must be between 0 and {CYCLE_LIMIT_HOURS}.")

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidScheduleInputError("Planning start timestamp must be timezone-aware.")
        if value.second or value.microsecond:
            raise InvalidScheduleInputError("Planning start timestamp must be aligned to a minute.")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _hours_to_minutes(hours: float) -> int:
        minutes = round(float(hours) * 60)
        if minutes < 0 or minutes > CYCLE_LIMIT_MINUTES:
            raise InvalidScheduleInputError(f"cycle_used_hours must be between 0 and {CYCLE_LIMIT_HOURS}.")
        return minutes


def split_event_at_midnight(event: TripEvent) -> list[TripEvent]:
    """Split a timezone-aware event at every calendar midnight."""

    if event.start.tzinfo is None or event.end.tzinfo is None:
        raise InvalidScheduleInputError("Events must use timezone-aware timestamps.")
    if event.end <= event.start:
        raise InvalidScheduleInputError("Cannot split an event without positive duration.")
    parts: list[TripEvent] = []
    cursor = event.start
    part_number = 1
    total_minutes = event.duration_minutes
    consumed_minutes = 0
    while cursor < event.end:
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=cursor.tzinfo,
        )
        end = min(event.end, next_midnight)
        part_start_distance = event.route_distance_start
        if total_minutes:
            part_start_distance += (event.route_distance_end - event.route_distance_start) * (consumed_minutes / total_minutes)
        part_minutes = round((end - cursor).total_seconds() / 60)
        consumed_minutes += part_minutes
        part_end_distance = event.route_distance_start
        if total_minutes:
            part_end_distance += (event.route_distance_end - event.route_distance_start) * (consumed_minutes / total_minutes)
        parts.append(
            TripEvent(
                id=f"{event.id}-part-{part_number}",
                start=cursor,
                end=end,
                status=event.status,
                reason=event.reason,
                location=dict(event.location),
                route_distance_start=round(part_start_distance, 6),
                route_distance_end=round(part_end_distance, 6),
                metadata={**event.metadata, "source_event_id": event.id, "midnight_segment": part_number},
            )
        )
        cursor = end
        part_number += 1
    return parts
