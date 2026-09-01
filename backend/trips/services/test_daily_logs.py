from dataclasses import replace
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .daily_logs import build_daily_logs, validate_daily_logs
from .hos_engine import DutyStatus, TripEvent


UTC = timezone.utc
START = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


def make_event(
    event_id: str,
    start: datetime,
    duration_minutes: int,
    *,
    status: DutyStatus = DutyStatus.DRIVING,
    reason: str = "Driving",
    route_distance_start: float = 0.0,
    route_distance_end: float | None = None,
) -> TripEvent:
    if route_distance_end is None:
        route_distance_end = route_distance_start
    return TripEvent(
        id=event_id,
        start=start,
        end=start + timedelta(minutes=duration_minutes),
        status=status,
        reason=reason,
        location={
            "type": "route_position",
            "label": f"Route mile {route_distance_start:.1f}",
            "route_distance_miles": route_distance_start,
        },
        route_distance_start=route_distance_start,
        route_distance_end=route_distance_end,
    )


class DailyLogProjectionTests(SimpleTestCase):
    def test_one_day_trip_has_complete_log_and_presentation_coverage(self):
        events = (
            make_event("drive-1", START, 120, route_distance_start=0, route_distance_end=20),
            make_event("pickup", START + timedelta(minutes=120), 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Pickup", route_distance_start=20),
            make_event("drive-2", START + timedelta(minutes=180), 120, route_distance_start=20, route_distance_end=40),
            make_event("dropoff", START + timedelta(minutes=300), 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Dropoff", route_distance_start=40),
        )

        logs = build_daily_logs(events, compliant=True)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].summary.calendar_day_minutes, 1440)
        self.assertEqual(logs[0].summary.driving_minutes, 240)
        self.assertEqual(logs[0].summary.on_duty_not_driving_minutes, 120)
        self.assertEqual(logs[0].summary.stop_count, 2)
        self.assertTrue(logs[0].segments[0].presentation_only)
        self.assertTrue(logs[0].segments[-1].presentation_only)

    def test_multi_day_trip_generates_consecutive_complete_logs(self):
        events = (
            make_event("drive", START, 960, route_distance_start=0, route_distance_end=160),
            make_event("rest", START + timedelta(minutes=960), 600, status=DutyStatus.SLEEPER_BERTH, reason="Required 10-hour rest (daily reset)", route_distance_start=160),
            make_event("drive-2", START + timedelta(minutes=1560), 120, route_distance_start=160, route_distance_end=180),
            make_event("dropoff", START + timedelta(minutes=1680), 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Dropoff", route_distance_start=180),
        )

        logs = build_daily_logs(events, compliant=True)

        self.assertEqual([log.date for log in logs], ["2026-01-01", "2026-01-02"])
        self.assertTrue(all(log.summary.calendar_day_minutes == 1440 for log in logs))
        self.assertEqual(logs[1].summary.sleeper_berth_minutes, 600)

    def test_event_crossing_midnight_is_split_by_phase_three_helper(self):
        event = make_event("crossing", datetime(2026, 1, 1, 22, 0, tzinfo=UTC), 300, route_distance_start=10, route_distance_end=60)

        logs = build_daily_logs((event,), compliant=True)
        source_segments = [segment for log in logs for segment in log.segments if segment.source_event_id == "crossing"]

        self.assertEqual([segment.duration_minutes for segment in source_segments], [120, 180])
        self.assertEqual([segment.id for segment in source_segments], ["crossing-part-1", "crossing-part-2"])

    def test_event_ending_at_midnight_does_not_create_empty_next_day(self):
        event = make_event("ending", datetime(2026, 1, 1, 20, 0, tzinfo=UTC), 240)

        logs = build_daily_logs((event,), compliant=True)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].segments[-1].end, datetime(2026, 1, 2, 0, 0, tzinfo=UTC))

    def test_event_beginning_at_midnight_has_no_leading_coverage_segment(self):
        event = make_event("beginning", datetime(2026, 1, 2, 0, 0, tzinfo=UTC), 120)

        logs = build_daily_logs((event,), compliant=True)

        self.assertEqual(logs[0].segments[0].source_event_id, "beginning")
        self.assertEqual(logs[0].segments[0].start, logs[0].period_start)

    def test_break_crossing_midnight_preserves_both_parts(self):
        event = make_event(
            "break",
            datetime(2026, 1, 1, 23, 45, tzinfo=UTC),
            30,
            status=DutyStatus.OFF_DUTY,
            reason="Required 30-minute break",
        )

        logs = build_daily_logs((event,), compliant=True)
        source_segments = [segment for log in logs for segment in log.segments if segment.source_event_id == "break"]

        self.assertEqual([segment.duration_minutes for segment in source_segments], [15, 15])
        self.assertEqual(sum(segment.duration_minutes for segment in source_segments), event.duration_minutes)

    def test_rest_crossing_midnight_preserves_sleeper_status(self):
        event = make_event(
            "rest",
            datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
            600,
            status=DutyStatus.SLEEPER_BERTH,
            reason="Required 10-hour rest (daily reset)",
        )

        logs = build_daily_logs((event,), compliant=True)
        source_segments = [segment for log in logs for segment in log.segments if segment.source_event_id == "rest"]

        self.assertEqual([segment.duration_minutes for segment in source_segments], [240, 360])
        self.assertTrue(all(segment.status == DutyStatus.SLEEPER_BERTH for segment in source_segments))

    def test_fuel_event_is_counted_as_on_duty_stop_and_remark(self):
        event = make_event(
            "fuel",
            START,
            30,
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            reason="Fuel",
            route_distance_start=1000,
        )

        log = build_daily_logs((event,), compliant=True)[0]

        self.assertEqual(log.summary.on_duty_not_driving_minutes, 30)
        self.assertEqual(log.summary.stop_count, 1)
        self.assertIn("Fuel stop", [remark.text for remark in log.remarks])

    def test_pickup_is_exactly_one_hour_on_duty(self):
        event = make_event("pickup", START, 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Pickup")

        log = build_daily_logs((event,), compliant=True)[0]

        self.assertEqual(log.summary.on_duty_not_driving_minutes, 60)
        self.assertEqual(log.summary.stop_count, 1)
        self.assertIn("Pickup completed", [remark.text for remark in log.remarks])

    def test_dropoff_is_exactly_one_hour_on_duty(self):
        event = make_event("dropoff", START, 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Dropoff")

        log = build_daily_logs((event,), compliant=True)[0]

        self.assertEqual(log.summary.on_duty_not_driving_minutes, 60)
        self.assertEqual(log.summary.stop_count, 1)
        self.assertIn("Dropoff completed", [remark.text for remark in log.remarks])

    def test_34_hour_restart_is_split_over_all_calendar_days(self):
        event = make_event(
            "restart",
            datetime(2026, 1, 1, 22, 0, tzinfo=UTC),
            2040,
            status=DutyStatus.SLEEPER_BERTH,
            reason="34-hour cycle restart",
        )

        logs = build_daily_logs((event,), compliant=True)
        source_minutes = [
            sum(segment.duration_minutes for segment in log.segments if segment.source_event_id == "restart")
            for log in logs
        ]

        self.assertEqual([log.date for log in logs], ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(source_minutes, [120, 1440, 480])
        self.assertEqual(sum(source_minutes), 2040)
        self.assertIn("34-hour restart", [remark.text for log in logs for remark in log.remarks])

    def test_every_source_event_duration_is_preserved(self):
        first = make_event("first", datetime(2026, 1, 1, 23, 30, tzinfo=UTC), 90, route_distance_start=0, route_distance_end=10)
        second = make_event("second", first.end, 60, status=DutyStatus.ON_DUTY_NOT_DRIVING, reason="Fuel", route_distance_start=10)

        logs = build_daily_logs((first, second), compliant=True)

        for source_event in (first, second):
            represented = sum(
                segment.duration_minutes
                for log in logs
                for segment in log.segments
                if segment.source_event_id == source_event.id
            )
            self.assertEqual(represented, source_event.duration_minutes)

    def test_each_daily_log_totals_exactly_1440_minutes(self):
        event = make_event("long", START, 3000, route_distance_start=0, route_distance_end=300)

        logs = build_daily_logs((event,), compliant=True)

        self.assertGreater(len(logs), 2)
        self.assertTrue(all(sum(segment.duration_minutes for segment in log.segments) == 1440 for log in logs))

    def test_daily_log_validator_catches_overlapping_segments(self):
        event = make_event("event", START, 60)
        log = build_daily_logs((event,), compliant=True)[0]
        overlapping = replace(log.segments[1], start=log.segments[0].start)
        bad_segments = (log.segments[0], overlapping, *log.segments[2:])
        bad_log = replace(log, events=bad_segments, segments=bad_segments)

        validation = validate_daily_logs((bad_log,), (event,))

        self.assertFalse(validation["valid"])
        self.assertTrue(any("overlap" in error for error in validation["errors"]))

    def test_daily_log_validator_catches_missing_source_event(self):
        first = make_event("first", START, 60)
        second = make_event("second", START + timedelta(minutes=60), 60)
        logs = build_daily_logs((first,), compliant=True)

        validation = validate_daily_logs(logs, (first, second))

        self.assertFalse(validation["valid"])
        self.assertTrue(any("second" in error for error in validation["errors"]))

