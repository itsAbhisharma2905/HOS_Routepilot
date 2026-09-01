"""Presentation-level daily ELD logs derived from the backend event timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Sequence

from .errors import DailyLogValidationError, InvalidScheduleInputError
from .hos_engine import DutyStatus, TripEvent, split_event_at_midnight

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class DailyLogSegment:
    """A single proportional segment on one calendar day's ELD graph."""

    id: str
    source_event_id: str | None
    start: datetime
    end: datetime
    status: DutyStatus
    reason: str
    location: dict[str, Any]
    route_distance_start: float
    route_distance_end: float
    presentation_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_minutes(self) -> int:
        return round((self.end - self.start).total_seconds() / 60)

    def to_dict(self) -> dict[str, Any]:
        duration_minutes = self.duration_minutes
        return {
            "id": self.id,
            "source_event_id": self.source_event_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "status": self.status.value,
            "reason": self.reason,
            "location": self.location,
            "duration": duration_minutes,
            "duration_minutes": duration_minutes,
            "duration_hours": round(duration_minutes / 60, 2),
            "distance_start": round(self.route_distance_start, 6),
            "distance_end": round(self.route_distance_end, 6),
            "route_distance_start": round(self.route_distance_start, 6),
            "route_distance_end": round(self.route_distance_end, 6),
            "presentation_only": self.presentation_only,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class DailyLogSummary:
    calendar_day_minutes: int
    driving_minutes: int
    on_duty_not_driving_minutes: int
    off_duty_minutes: int
    sleeper_berth_minutes: int
    off_duty_sleeper_minutes: int
    stop_count: int
    compliant: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "calendar_day_minutes": self.calendar_day_minutes,
            "driving_minutes": self.driving_minutes,
            "on_duty_not_driving_minutes": self.on_duty_not_driving_minutes,
            "off_duty_minutes": self.off_duty_minutes,
            "sleeper_berth_minutes": self.sleeper_berth_minutes,
            "off_duty_sleeper_minutes": self.off_duty_sleeper_minutes,
            "stop_count": self.stop_count,
            "compliant": self.compliant,
        }


@dataclass(frozen=True)
class DailyLogRemark:
    id: str
    text: str
    timestamp: datetime
    source_event_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "source_event_id": self.source_event_id,
        }


@dataclass(frozen=True)
class DailyLog:
    date: str
    period_start: datetime
    period_end: datetime
    events: tuple[DailyLogSegment, ...]
    segments: tuple[DailyLogSegment, ...]
    summary: DailyLogSummary
    remarks: tuple[DailyLogRemark, ...]

    def to_dict(self) -> dict[str, Any]:
        serialized_segments = [segment.to_dict() for segment in self.segments]
        return {
            "date": self.date,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "events": serialized_segments,
            "segments": serialized_segments,
            "summary": self.summary.to_dict(),
            "remarks": [remark.to_dict() for remark in self.remarks],
        }


def build_daily_logs(events: Sequence[TripEvent], *, compliant: bool) -> tuple[DailyLog, ...]:
    """Project a validated HOS timeline into complete 24-hour calendar logs.

    The only event splitting performed here delegates to the Phase 3 helper.
    Coverage outside the first and last scheduled events is explicit,
    presentation-only OFF_DUTY time so each rendered calendar day is complete.
    """

    source_events = tuple(events)
    if not source_events:
        return ()
    _validate_source_order(source_events)

    split_segments: list[DailyLogSegment] = []
    for source_event in source_events:
        for part in split_event_at_midnight(source_event):
            split_segments.append(_segment_from_event(part, source_event.id))

    first_start = source_events[0].start
    last_end = source_events[-1].end
    last_covered_date = (last_end - timedelta(microseconds=1)).date()
    segments_by_date: dict[date, list[DailyLogSegment]] = {}
    for segment in split_segments:
        segments_by_date.setdefault(segment.start.date(), []).append(segment)

    logs: list[DailyLog] = []
    current_date = first_start.date()
    while current_date <= last_covered_date:
        period_start = datetime.combine(current_date, time.min, tzinfo=first_start.tzinfo)
        period_end = period_start + timedelta(days=1)
        day_segments = list(segments_by_date.get(current_date, []))

        if current_date == first_start.date() and period_start < first_start:
            day_segments.insert(
                0,
                _coverage_segment(
                    period_start,
                    first_start,
                    route_distance=source_events[0].route_distance_start,
                ),
            )
        if current_date == last_covered_date and last_end < period_end:
            day_segments.append(
                _coverage_segment(
                    last_end,
                    period_end,
                    route_distance=source_events[-1].route_distance_end,
                ),
            )

        day_segments.sort(key=lambda segment: (segment.start, segment.end, segment.id))
        segment_tuple = tuple(day_segments)
        logs.append(
            DailyLog(
                date=current_date.isoformat(),
                period_start=period_start,
                period_end=period_end,
                events=segment_tuple,
                segments=segment_tuple,
                summary=_summarize(segment_tuple, compliant=compliant),
                remarks=_remarks(segment_tuple, source_events),
            ),
        )
        current_date += timedelta(days=1)

    validation = validate_daily_logs(logs, source_events)
    if not validation["valid"]:
        raise DailyLogValidationError(
            "The generated daily ELD logs failed integrity checks.",
        )
    return tuple(logs)


def validate_daily_logs(
    daily_logs: Sequence[DailyLog],
    source_events: Sequence[TripEvent],
) -> dict[str, Any]:
    """Validate daily-log coverage without evaluating HOS legality."""

    errors: list[str] = []
    source_events = tuple(source_events)
    source_by_id = {event.id: event for event in source_events}
    represented_minutes = {event.id: 0 for event in source_events}

    expected_date: date | None = None
    for log_index, log in enumerate(daily_logs):
        try:
            period_start = log.period_start
            period_end = log.period_end
            if period_start.tzinfo is None or period_end.tzinfo is None:
                errors.append(f"Daily log {log_index + 1} is not timezone-aware.")
            if period_end - period_start != timedelta(minutes=MINUTES_PER_DAY):
                errors.append(f"Daily log {log.date} does not cover exactly 24 hours.")
            if period_start.date().isoformat() != log.date or period_start.time() != time.min:
                errors.append(f"Daily log {log.date} does not start at calendar midnight.")
            if period_end.date() != period_start.date() + timedelta(days=1) or period_end.time() != time.min:
                errors.append(f"Daily log {log.date} does not end at the next calendar midnight.")
            if expected_date is not None and period_start.date() != expected_date:
                errors.append("Daily logs are not ordered by consecutive calendar dates.")
            expected_date = period_start.date() + timedelta(days=1)
        except (AttributeError, TypeError):
            errors.append(f"Daily log {log_index + 1} has invalid period timestamps.")
            continue

        if tuple(segment.id for segment in log.events) != tuple(segment.id for segment in log.segments):
            errors.append(f"Daily log {log.date} has inconsistent events and segments.")

        total_minutes = 0
        durations = {
            DutyStatus.DRIVING: 0,
            DutyStatus.ON_DUTY_NOT_DRIVING: 0,
            DutyStatus.OFF_DUTY: 0,
            DutyStatus.SLEEPER_BERTH: 0,
        }
        previous: DailyLogSegment | None = None
        previous_end = log.period_start
        for segment in log.segments:
            duration_minutes = _segment_duration(segment, errors, log.date)
            total_minutes += duration_minutes
            if segment.status in durations:
                durations[segment.status] += duration_minutes
            if segment.start < log.period_start or segment.end > log.period_end:
                errors.append(f"Segment {segment.id} is outside daily log {log.date}.")
            if previous is not None:
                if segment.start < previous.start:
                    errors.append(f"Segments in daily log {log.date} are not chronological.")
                if segment.start < previous.end:
                    errors.append(f"Segments in daily log {log.date} overlap.")
            if segment.start > previous_end:
                errors.append(f"Daily log {log.date} contains an unexplained gap.")
            previous = segment
            previous_end = segment.end
            if segment.source_event_id is not None:
                if segment.source_event_id not in source_by_id:
                    errors.append(f"Segment {segment.id} references an unknown source event.")
                else:
                    represented_minutes[segment.source_event_id] += duration_minutes

        if total_minutes != MINUTES_PER_DAY:
            errors.append(f"Daily log {log.date} totals {total_minutes} rather than 1440 minutes.")
        if previous_end != log.period_end:
            errors.append(f"Daily log {log.date} does not reach the end of its 24-hour period.")
        expected_summary = {
            "driving_minutes": durations[DutyStatus.DRIVING],
            "on_duty_not_driving_minutes": durations[DutyStatus.ON_DUTY_NOT_DRIVING],
            "off_duty_minutes": durations[DutyStatus.OFF_DUTY],
            "sleeper_berth_minutes": durations[DutyStatus.SLEEPER_BERTH],
            "off_duty_sleeper_minutes": durations[DutyStatus.OFF_DUTY] + durations[DutyStatus.SLEEPER_BERTH],
            "calendar_day_minutes": total_minutes,
        }
        for field_name, expected_value in expected_summary.items():
            if getattr(log.summary, field_name, None) != expected_value:
                errors.append(f"Daily log {log.date} summary field {field_name} is inconsistent.")
        if getattr(log.summary, "stop_count", None) != sum(
            1 for segment in log.segments if segment.source_event_id and segment.status != DutyStatus.DRIVING
        ):
            errors.append(f"Daily log {log.date} stop count is inconsistent.")

    if source_events:
        if not daily_logs:
            errors.append("Source events are not represented by any daily log.")
        for event in source_events:
            if represented_minutes[event.id] != event.duration_minutes:
                errors.append(
                    f"Source event {event.id} has {represented_minutes[event.id]} represented minutes; "
                    f"expected {event.duration_minutes}."
                )
    elif daily_logs:
        errors.append("Daily logs exist without source events.")

    return {"valid": not errors, "errors": errors}


def _validate_source_order(events: Sequence[TripEvent]) -> None:
    previous: TripEvent | None = None
    for event in events:
        if event.start.tzinfo is None or event.end.tzinfo is None:
            raise InvalidScheduleInputError("Daily-log source events must be timezone-aware.")
        if event.end <= event.start:
            raise InvalidScheduleInputError("Daily-log source events must have positive duration.")
        if previous is not None and event.start != previous.end:
            raise DailyLogValidationError("The source event timeline contains a gap or overlap.")
        previous = event


def _segment_from_event(event: TripEvent, source_event_id: str) -> DailyLogSegment:
    return DailyLogSegment(
        id=event.id,
        source_event_id=source_event_id,
        start=event.start,
        end=event.end,
        status=event.status,
        reason=event.reason,
        location=dict(event.location),
        route_distance_start=event.route_distance_start,
        route_distance_end=event.route_distance_end,
        metadata=dict(event.metadata),
    )


def _coverage_segment(start: datetime, end: datetime, *, route_distance: float) -> DailyLogSegment:
    return DailyLogSegment(
        id=f"coverage-{start.date().isoformat()}-{start.strftime('%H%M')}",
        source_event_id=None,
        start=start,
        end=end,
        status=DutyStatus.OFF_DUTY,
        reason="Outside planned schedule",
        location={"type": "presentation", "label": "Outside planned schedule"},
        route_distance_start=route_distance,
        route_distance_end=route_distance,
        presentation_only=True,
        metadata={"presentation_only": True, "coverage": "outside_planned_schedule"},
    )


def _segment_duration(segment: DailyLogSegment, errors: list[str], log_date: str) -> int:
    try:
        seconds = (segment.end - segment.start).total_seconds()
    except (AttributeError, TypeError):
        errors.append(f"Segment {segment.id} in daily log {log_date} has invalid timestamps.")
        return 0
    if seconds <= 0 or seconds % 60 != 0:
        errors.append(f"Segment {segment.id} in daily log {log_date} has a non-positive or partial-minute duration.")
    return round(seconds / 60)


def _summarize(segments: Sequence[DailyLogSegment], *, compliant: bool) -> DailyLogSummary:
    minutes_by_status = {
        status: sum(segment.duration_minutes for segment in segments if segment.status == status)
        for status in DutyStatus
    }
    return DailyLogSummary(
        calendar_day_minutes=MINUTES_PER_DAY,
        driving_minutes=minutes_by_status[DutyStatus.DRIVING],
        on_duty_not_driving_minutes=minutes_by_status[DutyStatus.ON_DUTY_NOT_DRIVING],
        off_duty_minutes=minutes_by_status[DutyStatus.OFF_DUTY],
        sleeper_berth_minutes=minutes_by_status[DutyStatus.SLEEPER_BERTH],
        off_duty_sleeper_minutes=minutes_by_status[DutyStatus.OFF_DUTY] + minutes_by_status[DutyStatus.SLEEPER_BERTH],
        stop_count=sum(1 for segment in segments if segment.source_event_id and segment.status != DutyStatus.DRIVING),
        compliant=compliant,
    )


def _remarks(segments: Sequence[DailyLogSegment], source_events: Sequence[TripEvent]) -> tuple[DailyLogRemark, ...]:
    source_segments = [segment for segment in segments if segment.source_event_id is not None]
    if not source_segments:
        return ()
    remarks: list[DailyLogRemark] = []
    first_segment = source_segments[0]
    last_segment = source_segments[-1]
    if first_segment.start == source_events[0].start:
        remarks.append(DailyLogRemark("trip-start", "Trip start", first_segment.start, first_segment.source_event_id))
    for segment in source_segments:
        text = _remark_text(segment.reason)
        if text:
            remarks.append(DailyLogRemark(f"{segment.id}-remark", text, segment.start, segment.source_event_id))
    if last_segment.end == source_events[-1].end:
        remarks.append(DailyLogRemark("trip-complete", "Trip completed", last_segment.end, last_segment.source_event_id))
    return tuple(sorted(remarks, key=lambda remark: (remark.timestamp, remark.id)))


def _remark_text(reason: str) -> str | None:
    return {
        "Pickup": "Pickup completed",
        "Dropoff": "Dropoff completed",
        "Fuel": "Fuel stop",
        "Required 30-minute break": "Required 30-minute break",
        "Required 10-hour rest (daily reset)": "Daily rest",
        "34-hour cycle restart": "34-hour restart",
    }.get(reason)
