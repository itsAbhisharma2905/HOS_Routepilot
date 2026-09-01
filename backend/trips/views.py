import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TripPlanRequestSerializer
from .services.errors import ServiceError
from .services.trip_planner import RoutePlanningService

logger = logging.getLogger(__name__)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        return Response({"status": "ok", "service": "hos-routepilot-api"})


class PlanTripView(APIView):
    """Validate input, then return a normalized route and HOS schedule."""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = RoutePlanningService().plan(serializer.validated_data)
        except ServiceError as exc:
            error = {"code": exc.code, "message": exc.message}
            if exc.field:
                error["field"] = exc.field
            return Response({"error": error}, status=exc.http_status)
        except Exception:
            logger.exception("Unexpected error while planning route")
            return Response(
                {
                    "error": {
                        "code": "PLANNER_UNAVAILABLE",
                        "message": "The route planner is temporarily unavailable. Please try again.",
                    }
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result, status=status.HTTP_200_OK)
