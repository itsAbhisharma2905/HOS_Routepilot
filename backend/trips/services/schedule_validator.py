"""Independent validation of a generated HOS event timeline."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .hos_engine import (
    BREAK_AFTER_DRIVING_MINUTES,
    BREAK_DURATION_MINUTES,
    CYCLE_LIMIT_HOURS,
    CYCLE_LIMIT_MINUTES,
    DAILY_REST_MINUTES,
    DRIVING_LIMIT_MINUTES,
    DROPOFF_MINUTES,
    DUTY_WINDOW_MINUTES,
    DutyStatus,
    FUEL_INTERVAL_MILES,
    PICKUP_MINUTES,
    RESTART_MINUTES,
    TripEvent,
)

EPSILON = 1e-6


def validate_schedule(
    events: Sequence[TripEvent],
    *,
    initial_cycle_used_hours: float,
    route_total_distance_miles: float | None = None,
) -> dict[str, Any]:
    """Return compliance data without trusting the scheduler that made events."""

    violations: list[dict[str, Any]] = []
    if route_total_distance_miles is None:
        route_total_distance_miles = max((event.route_distance_end for event in events), default=0.0)
    if not _valid_number(route_total_distance_miles, minimum=0):
        violations.append(_violation("route distance", "Route distance is invalid.", None))
        route_total_distance_miles = 0.0

    try:
        initial_cycle_minutes = round(float(initial_cycle_used_hours) * 60)
    except (TypeError, ValueError):
        initial_cycle_minutes = 0
        violations.append(_violation("70-hour rolling cycle", "Initial cycle usage is invalid.", None))
    if initial_cycle_minutes < 0 or initial_cycle_minutes > CYCLE_LIMIT_MINUTES:
        violations.append(_violation("70-hour rolling cycle", f"Initial cycle usage is outside 0-{CYCLE_LIMIT_HOURS} hours.", None))
        initial_cycle_minutes = max(0, min(CYCLE_LIMIT_MINUTES, initial_cycle_minutes))

    cycle_used_minutes = initial_cycle_minutes
    driving_minutes = 0
    window_elapsed_minutes = 0
    driving_since_break_minutes = 0
    last_fuel_distance = 0.0
    previous: TripEvent | None = None

    pickup_events: list[TripEvent] = []
    dropoff_events: list[TripEvent] = []
    for event in events:
        prior_event = previous
        duration_minutes = _duration_minutes(event, violations)
        status = _status(event, violations)

        if prior_event is not None:
            if event.start < prior_event.start:
                violations.append(_violation("chronological ordering", "Events are not ordered by start time.", event))
            if event.start < prior_event.end:
                violations.append(_violation("overlapping events", "Events overlap in time.", event))
            elif event.start > prior_event.end:
                violations.append(_violation("timeline continuity", "The timeline contains an unexplained gap.", event))

        if not _valid_number(event.route_distance_start, minimum=0) or not _valid_number(event.route_distance_end, minimum=0):
            violations.append(_violation("route distance monotonicity", "Event route distances are invalid.", event))
        else:
            if event.route_distance_start > route_total_distance_miles + EPSILON or event.route_distance_end > route_total_distance_miles + EPSILON:
                violations.append(_violation("route distance monotonicity", "Event route distance exceeds the route.", event))
            if event.route_distance_end < event.route_distance_start - EPSILON:
                violations.append(_violation("route distance monotonicity", "Route distance moves backwards.", event))
            if prior_event is not None and event.route_distance_start < prior_event.route_distance_end - EPSILON:
                violations.append(_violation("route distance monotonicity", "Event route position moves backwards.", event))

        previous = event

        if status == DutyStatus.DRIVING:
            driving_duration = max(duration_minutes, 0)
            driving_minutes += driving_duration
            driving_since_break_minutes += driving_duration
            window_elapsed_minutes += driving_duration
            if driving_minutes > DRIVING_LIMIT_MINUTES:
                violations.append(_violation("11-hour driving limit", "Driving exceeds the 11-hour allowance before a daily reset.", event))
            if driving_since_break_minutes > BREAK_AFTER_DRIVING_MINUTES:
                violations.append(_violation("30-minute break requirement", "Driving continues beyond 8 hours without a qualifying break.", event))
            if window_elapsed_minutes > DUTY_WINDOW_MINUTES:
                violations.append(_violation("14-hour driving window", "Duty activity exceeds the 14-hour window.", event))
        elif status in {DutyStatus.ON_DUTY_NOT_DRIVING}:
            window_elapsed_minutes += max(duration_minutes, 0)
            if window_elapsed_minutes > DUTY_WINDOW_MINUTES:
                violations.append(_violation("14-hour driving window", "On-duty activity exceeds the 14-hour window.", event))

        is_qualifying_rest = status in {DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH} and duration_minutes >= DAILY_REST_MINUTES
        is_cycle_restart = event.reason == "34-hour cycle restart"
        if is_cycle_restart:
            if duration_minutes != RESTART_MINUTES:
                violations.append(_violation("34-hour restart", "Cycle restart must be exactly 34 hours.", event))
            cycle_used_minutes = 0
            driving_minutes = 0
            window_elapsed_minutes = 0
            driving_since_break_minutes = 0
        elif is_qualifying_rest:
            if event.reason == "Required 10-hour rest (daily reset)" and duration_minutes != DAILY_REST_MINUTES:
                violations.append(_violation("required rest", "Daily reset rest must be exactly 10 hours.", event))
            driving_minutes = 0
            window_elapsed_minutes = 0
            driving_since_break_minutes = 0
        elif status in {DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH} and duration_minutes >= BREAK_DURATION_MINUTES:
            driving_since_break_minutes = 0
            window_elapsed_minutes += max(duration_minutes, 0)
            if window_elapsed_minutes > DUTY_WINDOW_MINUTES:
                violations.append(_violation("14-hour driving window", "A short off-duty event exceeds the 14-hour window.", event))

        if status in {DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING}:
            cycle_used_minutes += max(duration_minutes, 0)
            if cycle_used_minutes > CYCLE_LIMIT_MINUTES:
                violations.append(_violation("70-hour rolling cycle", "On-duty time exceeds the 70-hour cycle limit.", event))

        if event.reason == "Fuel":
            if event.route_distance_start - last_fuel_distance > FUEL_INTERVAL_MILES + EPSILON:
                violations.append(_violation("fuel interval", "Fueling occurs after more than 1,000 route miles.", event))
            last_fuel_distance = event.route_distance_end
        elif event.reason == "Pickup":
            pickup_events.append(event)
            if status != DutyStatus.ON_DUTY_NOT_DRIVING or duration_minutes != PICKUP_MINUTES:
                violations.append(_violation("pickup duration", "Pickup must be exactly 1 hour on duty not driving.", event))
        elif event.reason == "Dropoff":
            dropoff_events.append(event)
            if status != DutyStatus.ON_DUTY_NOT_DRIVING or duration_minutes != DROPOFF_MINUTES:
                violations.append(_violation("dropoff duration", "Dropoff must be exactly 1 hour on duty not driving.", event))

    if events and abs(events[0].route_distance_start) > EPSILON:
        violations.append(_violation("route completion", "The timeline must begin at route mile 0.", events[0]))
    if events and abs(events[-1].route_distance_end - route_total_distance_miles) > EPSILON:
        violations.append(_violation("route completion", "The timeline does not reach the end of the route.", events[-1]))
    if events and route_total_distance_miles - last_fuel_distance > FUEL_INTERVAL_MILES + EPSILON:
        violations.append(_violation("fuel interval", "The route ends more than 1,000 miles after the last fuel event.", events[-1]))
    if len(pickup_events) != 1:
        violations.append(_violation("pickup duration", "The timeline must contain exactly one pickup event.", events[0] if events else None))
    if len(dropoff_events) != 1:
        violations.append(_violation("dropoff duration", "The timeline must contain exactly one dropoff event.", events[-1] if events else None))

    return {"compliant": not violations, "violations": violations}


def _duration_minutes(event: TripEvent, violations: list[dict[str, Any]]) -> int:
    try:
        seconds = (event.end - event.start).total_seconds()
    except (AttributeError, TypeError):
        violations.append(_violation("positive duration", "Event timestamps are invalid.", event))
        return 0
    if seconds <= 0 or seconds % 60 != 0:
        violations.append(_violation("positive duration", "Every event must have a positive whole-minute duration.", event))
    return round(seconds / 60)


def _status(event: TripEvent, violations: list[dict[str, Any]]) -> DutyStatus | None:
    try:
        return event.status if isinstance(event.status, DutyStatus) else DutyStatus(event.status)
    except (TypeError, ValueError):
        violations.append(_violation("status", "Event has an unsupported duty status.", event))
        return None


def _valid_number(value: Any, *, minimum: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= minimum


def _violation(rule: str, message: str, event: TripEvent | None) -> dict[str, Any]:
    return {
        "rule": rule,
        "message": message,
        "timestamp": event.start.isoformat() if event is not None else None,
        "location": event.location if event is not None else None,
    }


class ScheduleValidator:
    """Object facade for callers that prefer an injectable validator service."""

    def validate(
        self,
        events: Sequence[TripEvent],
        *,
        initial_cycle_used_hours: float,
        route_total_distance_miles: float | None = None,
    ) -> dict[str, Any]:
        return validate_schedule(
            events,
            initial_cycle_used_hours=initial_cycle_used_hours,
            route_total_distance_miles=route_total_distance_miles,
        )
