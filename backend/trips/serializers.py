from rest_framework import serializers

from .services.hos_engine import CYCLE_LIMIT_HOURS


class TripPlanRequestSerializer(serializers.Serializer):
    """Validate the stable API input contract for trip planning."""

    current_location = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    pickup_location = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    dropoff_location = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    cycle_used_hours = serializers.FloatField(required=True, min_value=0, max_value=CYCLE_LIMIT_HOURS)

    def validate_current_location(self, value: str) -> str:
        return self._validate_location(value, "current_location")

    def validate_pickup_location(self, value: str) -> str:
        return self._validate_location(value, "pickup_location")

    def validate_dropoff_location(self, value: str) -> str:
        return self._validate_location(value, "dropoff_location")

    @staticmethod
    def _validate_location(value: str, field_name: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise serializers.ValidationError(f"{field_name.replace('_', ' ').capitalize()} is required.")
        return normalized
