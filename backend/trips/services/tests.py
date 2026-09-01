import json
import socket
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase

from .errors import (
    LocationNotFoundError,
    MalformedProviderResponseError,
    NoRouteFoundError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from .geocoding import Location, NominatimGeocoder
from .hos_engine import HOSScheduler
from .routing import METERS_PER_MILE, OSRMRouter
from .trip_planner import RoutePlanningService
from .test_hos_engine import START, synthetic_route


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def geocode_payload(display_name="Chicago, Illinois, United States"):
    return [
        {
            "lat": "41.8756",
            "lon": "-87.6244",
            "display_name": display_name,
            "address": {
                "city": "Chicago",
                "state": "Illinois",
                "country": "United States",
            },
        }
    ]


def location(role: str, latitude: float, longitude: float) -> Location:
    return Location(
        input_text=f"{role} input",
        normalized_name=f"{role.title()} normalized",
        latitude=latitude,
        longitude=longitude,
        city=role.title(),
        state="IL",
        country="United States",
    )


def routing_payload():
    return {
        "code": "Ok",
        "waypoints": [
            {"name": "Chicago", "location": [-87.6244, 41.8756]},
            {"name": "Dallas", "location": [-96.7970, 32.7767]},
            {"name": "Houston", "location": [-95.3698, 29.7604]},
        ],
        "routes": [
            {
                "distance": 2 * METERS_PER_MILE,
                "duration": 7200.4,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-87.6244, 41.8756],
                        [-96.7970, 32.7767],
                        [-95.3698, 29.7604],
                    ],
                },
                "legs": [
                    {
                        "distance": METERS_PER_MILE,
                        "duration": 3600.2,
                        "steps": [
                            {
                                "distance": 800,
                                "duration": 1200.1,
                                "name": "I-90",
                                "maneuver": {
                                    "type": "depart",
                                    "location": [-87.6244, 41.8756],
                                },
                            }
                        ],
                    },
                    {
                        "distance": METERS_PER_MILE,
                        "duration": 3600.2,
                        "steps": [
                            {
                                "distance": 2418.688,
                                "duration": 2400.3,
                                "name": "I-45",
                                "maneuver": {
                                    "type": "turn",
                                    "modifier": "right",
                                    "location": [-96.7970, 32.7767],
                                },
                            }
                        ],
                    },
                ],
            }
        ],
    }


class GeocodingServiceTests(SimpleTestCase):
    @patch("trips.services.http.urlopen")
    def test_successful_geocoding_normalizes_location(self, urlopen):
        urlopen.return_value = FakeResponse(geocode_payload())

        result = NominatimGeocoder(min_interval_seconds=0).geocode("  Chicago,  IL ", field="current_location")

        self.assertEqual(result.input_text, "Chicago, IL")
        self.assertEqual(result.normalized_name, "Chicago, Illinois, United States")
        self.assertEqual(result.city, "Chicago")
        self.assertEqual(result.latitude, 41.8756)
        request = urlopen.call_args.args[0]
        self.assertIn("format=jsonv2", request.full_url)
        self.assertEqual(request.headers["User-agent"], "HOSRoutePilot/0.1 (development)")

    @patch("trips.services.http.urlopen")
    def test_geocoding_no_result_is_location_not_found(self, urlopen):
        urlopen.return_value = FakeResponse([])

        with self.assertRaises(LocationNotFoundError):
            NominatimGeocoder(min_interval_seconds=0).geocode("Unknown place")

    @patch("trips.services.http.urlopen", side_effect=TimeoutError)
    def test_geocoding_timeout_is_normalized(self, urlopen):
        with self.assertRaises(ProviderTimeoutError):
            NominatimGeocoder(min_interval_seconds=0).geocode("Chicago")

    @patch("trips.services.http.urlopen", side_effect=URLError("offline"))
    def test_geocoding_provider_failure_is_normalized(self, urlopen):
        with self.assertRaises(ProviderUnavailableError):
            NominatimGeocoder(min_interval_seconds=0).geocode("Chicago")

    @patch("trips.services.http.urlopen")
    def test_malformed_geocoding_response_is_rejected(self, urlopen):
        urlopen.return_value = FakeResponse({"lat": "41.8"})

        with self.assertRaises(MalformedProviderResponseError):
            NominatimGeocoder(min_interval_seconds=0).geocode("Chicago")

    @patch("trips.services.http.urlopen")
    def test_geocoding_http_error_is_normalized(self, urlopen):
        urlopen.side_effect = HTTPError("https://example.test", 429, "rate limited", {}, None)

        with self.assertRaises(ProviderHTTPError):
            NominatimGeocoder(min_interval_seconds=0).geocode("Chicago")

    @patch("trips.services.http.urlopen")
    def test_identical_geocoding_data_is_deterministic(self, urlopen):
        urlopen.return_value = FakeResponse(geocode_payload())
        geocoder = NominatimGeocoder(min_interval_seconds=0)

        first = geocoder.geocode("Chicago")
        second = geocoder.geocode("Chicago")

        self.assertEqual(first.to_dict(), second.to_dict())


class RoutingServiceTests(SimpleTestCase):
    @patch("trips.services.http.urlopen")
    def test_successful_routing_normalizes_geometry_distance_and_duration(self, urlopen):
        urlopen.return_value = FakeResponse(routing_payload())
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }

        result = OSRMRouter().route(locations)

        self.assertEqual(result.distance_miles, 2.0)
        self.assertEqual(result.estimated_driving_seconds, 7200)
        self.assertEqual(result.coordinates[0], [41.8756, -87.6244])
        self.assertEqual(result.geometry["coordinates"][0], [-87.6244, 41.8756])
        self.assertEqual(result.route_steps[0].instruction, "Depart")
        self.assertEqual(result.route_steps[1].cumulative_distance_miles, round(3218.688 / METERS_PER_MILE, 6))
        self.assertEqual([item["role"] for item in result.waypoints], ["current", "pickup", "dropoff"])
        request = urlopen.call_args.args[0]
        self.assertIn("/route/v1/driving/-87.6244000,41.8756000", request.full_url)

    @patch("trips.services.http.urlopen")
    def test_malformed_routing_response_is_rejected(self, urlopen):
        urlopen.return_value = FakeResponse({"code": "Ok", "routes": [{}]})
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }

        with self.assertRaises(MalformedProviderResponseError):
            OSRMRouter().route(locations)

    @patch("trips.services.http.urlopen")
    def test_routing_provider_failure_is_normalized(self, urlopen):
        urlopen.return_value = FakeResponse({"code": "NoRoute"})
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }

        with self.assertRaises(NoRouteFoundError):
            OSRMRouter().route(locations)

    @patch("trips.services.http.urlopen", side_effect=socket.timeout)
    def test_routing_timeout_is_normalized(self, urlopen):
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }

        with self.assertRaises(ProviderTimeoutError):
            OSRMRouter().route(locations)

    @patch("trips.services.http.urlopen")
    def test_identical_routing_data_is_deterministic(self, urlopen):
        urlopen.return_value = FakeResponse(routing_payload())
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }
        router = OSRMRouter()

        first = router.route(locations).to_dict()
        second = router.route(locations).to_dict()

        self.assertEqual(first, second)


class RoutePlanningServiceTests(SimpleTestCase):
    def test_route_planner_composes_geocoding_and_routing(self):
        geocoder = Mock()
        router = Mock()
        locations = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }
        geocoder.geocode_many.return_value = locations
        router.route.return_value = Mock(to_dict=lambda: {"distance_miles": 2.0})
        trip_input = {
            "current_location": "Chicago, IL",
            "pickup_location": "Dallas, TX",
            "dropoff_location": "Houston, TX",
            "cycle_used_hours": 24.0,
        }

        result = RoutePlanningService(geocoder=geocoder, router=router).plan_route(trip_input)

        geocoder.geocode_many.assert_called_once_with(
            {"current": "Chicago, IL", "pickup": "Dallas, TX", "dropoff": "Houston, TX"}
        )
        router.route.assert_called_once_with(locations)
        self.assertEqual(result["status"], "route_ready")

    def test_plan_integrates_hos_schedule_and_independent_compliance_result(self):
        geocoder = Mock()
        router = Mock()
        geocoder.geocode_many.return_value = {
            "current": location("current", 41.8756, -87.6244),
            "pickup": location("pickup", 32.7767, -96.7970),
            "dropoff": location("dropoff", 29.7604, -95.3698),
        }
        router.route.return_value = Mock(to_dict=lambda: synthetic_route(300, 300))
        trip_input = {
            "current_location": "Chicago, IL",
            "pickup_location": "Dallas, TX",
            "dropoff_location": "Houston, TX",
            "cycle_used_hours": 24.0,
        }

        result = RoutePlanningService(
            geocoder=geocoder,
            router=router,
            scheduler=HOSScheduler(),
        ).plan(trip_input, start_timestamp=START)

        self.assertEqual(result["status"], "planned")
        self.assertTrue(result["events"])
        self.assertIn("Pickup", [event["reason"] for event in result["events"]])
        self.assertIn("Dropoff", [event["reason"] for event in result["events"]])
        self.assertTrue(result["daily_logs"])
        self.assertTrue(all(log["summary"]["calendar_day_minutes"] == 1440 for log in result["daily_logs"]))
        self.assertTrue(result["compliance"]["compliant"])
