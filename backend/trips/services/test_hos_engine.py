from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .errors import InvalidScheduleInputError
from .hos_engine import (
    DAILY_REST_MINUTES,
    DutyStatus,
    HOSPlanInput,
    HOSScheduler,
    TripEvent,
    split_event_at_midnight,
)
from .route_progress import RouteProgress
from .schedule_validator import validate_schedule


START = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def synthetic_route(
    distance_miles: float,
    duration_minutes: int,
    *,
    pickup_fraction: float = 0.5,
) -> dict:
    pickup_distance = round(distance_miles * pickup_fraction, 6)
    first_duration = round(duration_minutes * pickup_fraction)
    return {
        "distance_miles": distance_miles,
        "estimated_driving_seconds": duration_minutes * 60,
        "geometry": {
            "type": "LineString",
            "coordinates": [[-90.0, 40.0], [-95.0, 35.0], [-100.0, 30.0]],
        },
        "route_steps": [],
        "legs": [
            {
                "sequence": 0,
                "distance_miles": pickup_distance,
                "duration_seconds": first_duration * 60,
            },
            {
                "sequence": 1,
                "distance_miles": round(distance_miles - pickup_distance, 6),
                "duration_seconds": (duration_minutes - first_duration) * 60,
            },
        ],
        "waypoints": [],
    }


def plan_input(
    route: dict,
    *,
    cycle_used_hours: float = 0,
    start_timestamp: datetime = START,
) -> HOSPlanInput:
    return HOSPlanInput(
        current_location={"city": "Origin", "state": "IL"},
        pickup_location={"city": "Pickup", "state": "TX"},
        dropoff_location={"city": "Dropoff", "state": "TX"},
        cycle_used_hours=cycle_used_hours,
        route=route,
        start_timestamp=start_timestamp,
    )


def schedule_for(distance_miles: float, duration_minutes: int, **kwargs):
    return HOSScheduler().schedule(plan_input(synthetic_route(distance_miles, duration_minutes), **kwargs))


class RouteProgressTests(SimpleTestCase):
    def test_progress_uses_leg_specific_duration_and_answers_distance_questions(self):
        progress = RouteProgress(synthetic_route(1000, 1000))

        self.assertEqual(progress.waypoint_distances()["pickup"], 500)
        self.assertEqual(progress.driving_minutes_between(0, 500), 500)
        self.assertEqual(progress.distance_after(0, 250), 250)
        self.assertEqual(progress.distance_after(500, 250), 750)

    def test_progress_rejects_inconsistent_route_data(self):
        route = synthetic_route(1000, 1000)
        route["legs"][0]["distance_miles"] = 100

        with self.assertRaises(InvalidScheduleInputError):
            RouteProgress(route)

    def test_progress_rejects_distance_free_driving_time(self):
        route = {
            "distance_miles": 100,
            "estimated_driving_seconds": 180,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-90.0, 40.0], [-95.0, 35.0], [-100.0, 30.0]],
            },
            "route_steps": [],
            "legs": [
                {"sequence": 0, "distance_miles": 50, "duration_seconds": 60},
                {"sequence": 1, "distance_miles": 50.5, "duration_seconds": 60},
                {"sequence": 2, "distance_miles": 0, "duration_seconds": 60},
            ],
            "waypoints": [],
        }

        with self.assertRaises(InvalidScheduleInputError):
            RouteProgress(route)

    def test_positive_distance_legs_never_get_zero_normalized_minutes(self):
        route = {
            "distance_miles": 100,
            "estimated_driving_seconds": 180,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-90.0, 40.0], [-95.0, 35.0], [-100.0, 30.0]],
            },
            "route_steps": [],
            "legs": [
                {"sequence": 0, "distance_miles": 25, "duration_seconds": 45},
                {"sequence": 1, "distance_miles": 25, "duration_seconds": 45},
                {"sequence": 2, "distance_miles": 25, "duration_seconds": 45},
                {"sequence": 3, "distance_miles": 25, "duration_seconds": 45},
            ],
            "waypoints": [],
        }

        progress = RouteProgress(route)

        self.assertEqual([segment.duration_minutes for segment in progress.segments], [1, 1, 1, 1])
        self.assertEqual(progress.driving_minutes_between(0, 100), 4)
        self.assertEqual(progress.distance_after(0, 4), 100)

        schedule = HOSScheduler().schedule(plan_input(route))
        self.assertEqual(schedule.events[-1].reason, "Dropoff")
        self.assertEqual(schedule.events[-1].route_distance_end, 100)

    def test_normalization_preserves_floored_time_on_granular_routes(self):
        route = {
            "distance_miles": 100,
            "estimated_driving_seconds": 503,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-90.0, 40.0], [-95.0, 35.0], [-100.0, 30.0]],
            },
            "route_steps": [],
            "legs": [
                {"sequence": 0, "distance_miles": 40, "duration_seconds": 360},
                {"sequence": 1, "distance_miles": 30, "duration_seconds": 120},
                {"sequence": 2, "distance_miles": 20, "duration_seconds": 3},
                {"sequence": 3, "distance_miles": 10, "duration_seconds": 20},
            ],
            "waypoints": [],
        }

        progress = RouteProgress(route)

        self.assertEqual([segment.duration_minutes for segment in progress.segments], [6, 2, 1, 1])
        self.assertEqual(progress.total_driving_minutes, 10)
        self.assertEqual(progress.driving_minutes_between(0, 100), 10)
        self.assertEqual(progress.distance_after(0, 10), 100)

    def test_scheduler_keeps_sub_micro_mile_route_remainder_progressing(self):
        route = synthetic_route(100.0000012, 120)
        progress = RouteProgress(route)

        self.assertEqual(progress.distance_after(0, progress.total_driving_minutes), route["distance_miles"])
        schedule = HOSScheduler().schedule(plan_input(route))

        self.assertEqual(schedule.events[-1].reason, "Dropoff")
        self.assertAlmostEqual(schedule.final_state.route_distance_miles, route["distance_miles"], places=12)


class HOSSchedulerTests(SimpleTestCase):
    def test_short_trip_is_chronological_and_has_pickup_dropoff(self):
        schedule = schedule_for(300, 600)

        self.assertEqual(schedule.summary()["pickup_duration_minutes"], 60)
        self.assertEqual(schedule.summary()["dropoff_duration_minutes"], 60)
        self.assertEqual(schedule.summary()["number_of_calendar_days"], 1)
        self.assertTrue(any(event.reason == "Required 30-minute break" for event in schedule.events))
        self.assertTrue(all(event.end > event.start for event in schedule.events))
        self.assertTrue(all(first.end == second.start for first, second in zip(schedule.events, schedule.events[1:])))

    def test_more_than_eleven_driving_hours_requires_daily_rest(self):
        schedule = schedule_for(800, 720)

        self.assertTrue(any(event.reason == "Required 10-hour rest (daily reset)" for event in schedule.events))
        driving_since_rest = 0
        for event in schedule.events:
            if event.reason == "Required 10-hour rest (daily reset)":
                driving_since_rest = 0
            elif event.status == DutyStatus.DRIVING:
                driving_since_rest += event.duration_minutes
                self.assertLessEqual(driving_since_rest, 660)

    def test_fourteen_hour_window_is_reset_only_by_qualifying_rest(self):
        schedule = schedule_for(700, 780)

        self.assertTrue(any(event.reason == "Required 10-hour rest (daily reset)" for event in schedule.events))
        result = validate_schedule(
            schedule.events,
            initial_cycle_used_hours=0,
            route_total_distance_miles=700,
        )
        self.assertTrue(result["compliant"])

    def test_eight_hours_of_driving_inserts_visible_break(self):
        schedule = schedule_for(500, 540)
        breaks = [event for event in schedule.events if event.reason == "Required 30-minute break"]

        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0].status, DutyStatus.OFF_DUTY)
        self.assertEqual(breaks[0].duration_minutes, 30)

    def test_cycle_with_sufficient_remaining_hours_does_not_restart(self):
        schedule = schedule_for(300, 300, cycle_used_hours=60)

        self.assertEqual(schedule.summary()["number_of_cycle_restarts"], 0)
        self.assertLessEqual(schedule.final_state.cycle_used_minutes, 4200)

    def test_cycle_nearly_exhausted_restarts_before_activity_would_exceed_limit(self):
        schedule = schedule_for(20, 20, cycle_used_hours=69)

        self.assertTrue(any(event.reason == "34-hour cycle restart" for event in schedule.events))
        self.assertEqual(schedule.events[0].reason, "Driving")

    def test_exhausted_cycle_restarts_before_driving(self):
        schedule = schedule_for(100, 100, cycle_used_hours=70)

        self.assertEqual(schedule.events[0].reason, "34-hour cycle restart")
        self.assertEqual(schedule.events[0].duration_minutes, 2040)
        self.assertGreater(schedule.final_state.cycle_used_minutes, 0)

    def test_fuel_is_inserted_at_or_before_one_thousand_route_miles(self):
        schedule = schedule_for(1500, 900)
        fuels = [event for event in schedule.events if event.reason == "Fuel"]

        self.assertEqual(len(fuels), 1)
        self.assertLessEqual(fuels[0].route_distance_start, 1000)
        self.assertEqual(fuels[0].route_distance_start, fuels[0].route_distance_end)

    def test_pickup_and_dropoff_are_exactly_one_hour_on_duty(self):
        schedule = schedule_for(100, 120)
        pickup = next(event for event in schedule.events if event.reason == "Pickup")
        dropoff = next(event for event in schedule.events if event.reason == "Dropoff")

        self.assertEqual(pickup.status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(dropoff.status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(pickup.duration_minutes, 60)
        self.assertEqual(dropoff.duration_minutes, 60)

    def test_midnight_split_preserves_duration_and_status(self):
        event = TripEvent(
            id="event-1",
            start=datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc),
            end=datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
            status=DutyStatus.DRIVING,
            reason="Driving",
            location={"type": "route_position"},
            route_distance_start=10,
            route_distance_end=60,
        )

        parts = split_event_at_midnight(event)

        self.assertEqual([part.duration_minutes for part in parts], [120, 180])
        self.assertEqual(sum(part.duration_minutes for part in parts), event.duration_minutes)
        self.assertEqual([part.status for part in parts], [DutyStatus.DRIVING, DutyStatus.DRIVING])
        self.assertEqual(parts[0].end, parts[1].start)

    def test_schedule_is_deterministic_for_identical_inputs(self):
        first = [event.to_dict() for event in schedule_for(1200, 720).events]
        second = [event.to_dict() for event in schedule_for(1200, 720).events]

        self.assertEqual(first, second)

    def test_invalid_cycle_input_is_rejected(self):
        with self.assertRaises(InvalidScheduleInputError):
            schedule_for(100, 100, cycle_used_hours=70.1)

    def test_event_durations_sum_to_trip_elapsed_time(self):
        schedule = schedule_for(1000, 720)
        event_minutes = sum(event.duration_minutes for event in schedule.events)
        elapsed_minutes = round((schedule.events[-1].end - schedule.events[0].start).total_seconds() / 60)

        self.assertEqual(event_minutes, elapsed_minutes)


class ScheduleValidatorTests(SimpleTestCase):
    def test_validator_requires_timeline_to_cover_route(self):
        events = [
            TripEvent(
                id="pickup",
                start=START,
                end=START + timedelta(minutes=60),
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                reason="Pickup",
                location={},
                route_distance_start=0,
                route_distance_end=0,
            ),
            TripEvent(
                id="dropoff",
                start=START + timedelta(minutes=60),
                end=START + timedelta(minutes=120),
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                reason="Dropoff",
                location={},
                route_distance_start=0,
                route_distance_end=0,
            ),
        ]

        result = validate_schedule(
            events,
            initial_cycle_used_hours=0,
            route_total_distance_miles=100,
        )

        self.assertFalse(result["compliant"])
        self.assertIn("route completion", {violation["rule"] for violation in result["violations"]})

    def test_validator_catches_intentionally_invalid_timeline(self):
        first = TripEvent(
            id="event-1",
            start=START,
            end=START + timedelta(minutes=700),
            status=DutyStatus.DRIVING,
            reason="Driving",
            location={},
            route_distance_start=0,
            route_distance_end=500,
        )
        second = TripEvent(
            id="event-2",
            start=START + timedelta(minutes=690),
            end=START + timedelta(minutes=750),
            status=DutyStatus.DRIVING,
            reason="Driving",
            location={},
            route_distance_start=500,
            route_distance_end=550,
        )

        result = validate_schedule(
            [first, second],
            initial_cycle_used_hours=0,
            route_total_distance_miles=550,
        )
        rules = {violation["rule"] for violation in result["violations"]}

        self.assertFalse(result["compliant"])
        self.assertIn("overlapping events", rules)
        self.assertIn("11-hour driving limit", rules)
        self.assertIn("pickup duration", rules)
