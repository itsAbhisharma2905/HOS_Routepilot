import type { ApiErrorPayload, Compliance, DailyLog, DailyLogRemark, DailyLogSegment, DailyLogSummary, EventLocation, HOSState, Location, RouteResult, TripEvent, TripInput, TripPlanResult, TripSummary, Violation } from "../types/trip";
import { validateDailyLogs } from "../utils/dailyLogs";

function normalizeApiBaseUrl(value: string | undefined): string {
  const configuredValue = value?.trim().replace(/\/+$/, "") ?? "";
  if (!configuredValue) return import.meta.env.DEV ? "http://localhost:8000/api" : "";
  return configuredValue.toLowerCase().endsWith("/api") ? configuredValue : `${configuredValue}/api`;
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly field?: string;

  constructor(message: string, status: number, code?: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isCoordinate(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 && isNumber(value[0]) && isNumber(value[1]);
}

function isLocation(value: unknown): value is Location {
  return isRecord(value) &&
    typeof value.input_text === "string" &&
    typeof value.normalized_name === "string" &&
    isNumber(value.latitude) && value.latitude >= -90 && value.latitude <= 90 &&
    isNumber(value.longitude) && value.longitude >= -180 && value.longitude <= 180;
}

function isEventLocation(value: unknown): value is EventLocation {
  return isRecord(value) && (isLocation(value) || typeof value.type === "string" || typeof value.label === "string");
}

function isTripEvent(value: unknown): value is TripEvent {
  return isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.start === "string" &&
    typeof value.end === "string" &&
    ["OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY_NOT_DRIVING"].includes(String(value.status)) &&
    typeof value.reason === "string" &&
    isEventLocation(value.location) &&
    isNumber(value.duration) &&
    isNumber(value.duration_minutes) &&
    isNumber(value.duration_hours) &&
    isNumber(value.distance_start) &&
    isNumber(value.distance_end) &&
    isNumber(value.route_distance_start) &&
    isNumber(value.route_distance_end) &&
    isRecord(value.metadata);
}

function isGeometry(value: unknown): value is NonNullable<RouteResult["geometry"]> {
  return isRecord(value) && value.type === "LineString" && Array.isArray(value.coordinates) && value.coordinates.every(isCoordinate);
}

function isRoute(value: unknown): value is RouteResult {
  if (!isRecord(value) || !isNumber(value.distance_miles) || !isNumber(value.estimated_driving_seconds) || !isNumber(value.estimated_driving_hours)) return false;
  return Array.isArray(value.coordinates) && value.coordinates.every(isCoordinate) &&
    Array.isArray(value.route_steps) && Array.isArray(value.legs) && Array.isArray(value.waypoints) &&
    (value.geometry === null || isGeometry(value.geometry));
}

function isSummary(value: unknown): value is TripSummary {
  if (!isRecord(value)) return false;
  const numericFields = [
    "total_route_miles", "estimated_route_driving_seconds", "scheduled_total_duration_minutes",
    "scheduled_total_duration_hours", "total_driving_hours", "total_on_duty_not_driving_hours",
    "number_of_breaks", "number_of_rest_periods", "number_of_cycle_restarts", "number_of_fuel_stops",
    "pickup_duration_minutes", "dropoff_duration_minutes", "initial_cycle_used_hours",
    "final_cycle_usage_hours", "final_cycle_remaining_hours", "number_of_calendar_days",
  ];
  return numericFields.every((field) => isNumber(value[field]));
}

function isViolation(value: unknown): value is Violation {
  return isRecord(value) &&
    typeof value.rule === "string" &&
    typeof value.message === "string" &&
    (value.timestamp === null || typeof value.timestamp === "string") &&
    (value.location === null || isEventLocation(value.location));
}

function isCompliance(value: unknown): value is Compliance {
  return isRecord(value) && typeof value.compliant === "boolean" && Array.isArray(value.violations) && value.violations.every(isViolation);
}

function isHOSState(value: unknown): value is HOSState {
  if (!isRecord(value) || typeof value.current_timestamp !== "string" ||
    typeof value.pickup_completed !== "boolean" || typeof value.dropoff_completed !== "boolean") return false;
  return [
    "route_distance_miles", "cycle_used_minutes", "cycle_remaining_minutes",
    "driving_in_current_window_minutes", "elapsed_duty_window_minutes",
    "driving_since_break_minutes", "distance_since_fuel_miles",
  ].every((field) => isNumber(value[field]));
}

function isDailyLogSegment(value: unknown): value is DailyLogSegment {
  return isRecord(value) &&
    typeof value.id === "string" &&
    (value.source_event_id === null || typeof value.source_event_id === "string") &&
    typeof value.start === "string" &&
    typeof value.end === "string" &&
    ["OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY_NOT_DRIVING"].includes(String(value.status)) &&
    typeof value.reason === "string" &&
    isEventLocation(value.location) &&
    isNumber(value.duration) &&
    isNumber(value.duration_minutes) &&
    isNumber(value.duration_hours) &&
    isNumber(value.distance_start) &&
    isNumber(value.distance_end) &&
    isNumber(value.route_distance_start) &&
    isNumber(value.route_distance_end) &&
    typeof value.presentation_only === "boolean" &&
    isRecord(value.metadata);
}

function isDailyLogSummary(value: unknown): value is DailyLogSummary {
  if (!isRecord(value) || typeof value.compliant !== "boolean") return false;
  const numericFields = [
    "calendar_day_minutes", "driving_minutes", "on_duty_not_driving_minutes",
    "off_duty_minutes", "sleeper_berth_minutes", "off_duty_sleeper_minutes", "stop_count",
  ];
  return numericFields.every((field) => isNumber(value[field]));
}

function isDailyLogRemark(value: unknown): value is DailyLogRemark {
  return isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.text === "string" &&
    typeof value.timestamp === "string" &&
    (value.source_event_id === null || typeof value.source_event_id === "string");
}

function isDailyLog(value: unknown): value is DailyLog {
  return isRecord(value) &&
    typeof value.date === "string" &&
    typeof value.period_start === "string" &&
    typeof value.period_end === "string" &&
    Array.isArray(value.events) && value.events.every(isDailyLogSegment) &&
    Array.isArray(value.segments) && value.segments.every(isDailyLogSegment) &&
    isDailyLogSummary(value.summary) &&
    Array.isArray(value.remarks) && value.remarks.every(isDailyLogRemark);
}

export function isTripPlanResult(value: unknown): value is TripPlanResult {
  if (!isRecord(value)) return false;
  const locations = value.locations;
  const route = value.route;
  return (
    value.status === "planned" &&
    isRoute(route) &&
    isRecord(locations) &&
    isLocation(locations.current) &&
    isLocation(locations.pickup) &&
    isLocation(locations.dropoff) &&
    Array.isArray(value.events) && value.events.every(isTripEvent) &&
    Array.isArray(value.stops) && value.stops.every(isTripEvent) &&
    isSummary(value.summary) &&
    isCompliance(value.compliance) &&
    Array.isArray(value.violations) && value.violations.every(isViolation) &&
    Array.isArray(value.daily_logs) && value.daily_logs.every(isDailyLog) &&
    (value.state === undefined || isHOSState(value.state))
  );
}

export async function planTrip(input: TripInput): Promise<TripPlanResult> {
  if (!API_BASE_URL) {
    throw new ApiError("The planner API URL is not configured for this production build.", 0);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/trips/plan/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    if (import.meta.env.DEV) {
      console.error("[RoutePilot] Planner request failed", {
        status: 0,
        detail: "The planner API could not be reached.",
      });
    }
    throw new ApiError("The planner API could not be reached. Check that the backend is running.", 0);
  }

  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorPayload: ApiErrorPayload = isRecord(payload) ? payload : {};
    const fieldError = Object.values(errorPayload).find(
      (value) => Array.isArray(value) && typeof value[0] === "string",
    );
    const message =
      errorPayload.error?.message ??
      errorPayload.detail ??
      (Array.isArray(fieldError) ? String(fieldError[0]) : undefined) ??
      `The planner API returned HTTP ${response.status}${response.headers.get("content-type") ? ` (${response.headers.get("content-type")})` : ""}.`;
    if (import.meta.env.DEV) {
      console.error("[RoutePilot] Planner API error", {
        status: response.status,
        detail: message,
        code: errorPayload.error?.code,
        field: errorPayload.error?.field,
      });
    }
    throw new ApiError(message, response.status, errorPayload.error?.code, errorPayload.error?.field);
  }

  if (!isTripPlanResult(payload)) {
    if (import.meta.env.DEV) {
      console.error("[RoutePilot] Planner API returned an incomplete response", {
        status: response.status,
        detail: "The response did not match the planner contract.",
      });
    }
    throw new ApiError("The planner returned an incomplete response.", response.status);
  }

  const dailyLogErrors = validateDailyLogs(payload.daily_logs, payload.events);
  if (dailyLogErrors.length > 0) {
    if (import.meta.env.DEV) {
      console.error("[RoutePilot] Planner API returned invalid daily log data", {
        status: response.status,
        detail: dailyLogErrors[0],
      });
    }
    throw new ApiError(`The planner returned invalid daily log data: ${dailyLogErrors[0]}`, response.status);
  }

  return payload;
}
