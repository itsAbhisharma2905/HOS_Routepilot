class ServiceError(Exception):
    """Safe, user-facing error raised by a routing or geocoding service."""

    code = "EXTERNAL_PROVIDER_ERROR"
    http_status = 502

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class InvalidLocationError(ServiceError):
    code = "INVALID_LOCATION"
    http_status = 400


class LocationNotFoundError(ServiceError):
    code = "LOCATION_NOT_FOUND"
    http_status = 404


class ProviderTimeoutError(ServiceError):
    code = "PROVIDER_TIMEOUT"
    http_status = 504


class ProviderHTTPError(ServiceError):
    code = "PROVIDER_HTTP_ERROR"
    http_status = 502


class ProviderUnavailableError(ServiceError):
    code = "PROVIDER_UNAVAILABLE"
    http_status = 503


class MalformedProviderResponseError(ServiceError):
    code = "MALFORMED_PROVIDER_RESPONSE"
    http_status = 502


class NoRouteFoundError(ServiceError):
    code = "ROUTE_NOT_FOUND"
    http_status = 422


class InvalidScheduleInputError(ServiceError):
    code = "INVALID_SCHEDULE_INPUT"
    http_status = 422


class ImpossiblePlanningStateError(ServiceError):
    code = "IMPOSSIBLE_PLANNING_STATE"
    http_status = 422


class DailyLogValidationError(ServiceError):
    code = "DAILY_LOG_GENERATION_FAILED"
    http_status = 503
