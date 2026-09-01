from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from .services.errors import ProviderTimeoutError


class ApiFoundationTests(APITestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "ok")

    @patch("trips.views.RoutePlanningService")
    def test_plan_endpoint_validates_input_and_reaches_routing_layer(self, planner_class):
        planner_class.return_value.plan.return_value = {
            "status": "route_ready",
            "route": {"distance_miles": 10},
        }
        response = self.client.post(
            "/api/trips/plan/",
            {
                "current_location": "  Chicago,   IL ",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "cycle_used_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "route_ready")
        planner_class.return_value.plan.assert_called_once_with(
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "cycle_used_hours": 24.0,
            }
        )

    def test_plan_endpoint_rejects_invalid_cycle_hours(self):
        response = self.client.post(
            "/api/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "cycle_used_hours": 71,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cycle_used_hours", response.json())

    def test_plan_endpoint_rejects_blank_location(self):
        response = self.client.post(
            "/api/trips/plan/",
            {
                "current_location": "   ",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "cycle_used_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_location", response.json())

    @patch("trips.views.RoutePlanningService")
    def test_plan_endpoint_returns_safe_provider_error(self, planner_class):
        planner_class.return_value.plan.side_effect = ProviderTimeoutError(
            "Geocoding provider did not respond in time."
        )
        response = self.client.post(
            "/api/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "cycle_used_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertEqual(response.json()["error"]["code"], "PROVIDER_TIMEOUT")
