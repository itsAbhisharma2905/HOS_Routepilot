export interface TripInput {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  cycle_used_hours: number;
}

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    field?: string;
  };
  detail?: string;
  [key: string]: unknown;
}

export interface Location {
  input_text: string;
  normalized_name: string;
  latitude: number;
  longitude: number;
  city: string | null;
  state: string | null;
  country: string | null;
}

export interface RoutePosition {
  type?: "route_position" | string;
  label?: string;
  route_distance_miles?: number;
  latitude?: number;
  longitude?: number;
  [key: string]: unknown;
}

export type EventLocation = Location | RoutePosition;

export type DutyStatus =
  | "OFF_DUTY"
  | "SLEEPER_BERTH"
  | "DRIVING"
  | "ON_DUTY_NOT_DRIVING";

export interface RouteStep {
  sequence: number;
  instruction: string;
  road_name: string | null;
  maneuver_type: string | null;
  maneuver_modifier: string | null;
  distance_miles: number;
  duration_seconds: number;
  cumulative_distance_miles: number;
  location: { latitude: number; longitude: number } | null;
}

export interface RouteLeg {
  sequence: number;
  from: Location;
  to: Location;
  distance_miles: number;
  duration_seconds: number;
}

export interface RouteWaypoint {
  sequence: number;
  role: "current" | "pickup" | "dropoff";
  input_text: string;
  normalized_name: string;
  latitude: number;
  longitude: number;
  snapped_latitude: number;
  snapped_longitude: number;
  provider_name: string | null;
}

export interface RouteResult {
  distance_miles: number;
  estimated_driving_seconds: number;
  estimated_driving_hours: number;
  coordinates: [number, number][];
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  } | null;
  route_steps: RouteStep[];
  legs: RouteLeg[];
  waypoints: RouteWaypoint[];
}

export interface TripEvent {
  id: string;
  start: string;
  end: string;
  status: DutyStatus;
  reason: string;
  location: EventLocation;
  duration: number;
  duration_minutes: number;
  duration_hours: number;
  distance_start: number;
  distance_end: number;
  route_distance_start: number;
  route_distance_end: number;
  metadata: Record<string, unknown>;
}

export type Stop = TripEvent;

export interface TripSummary {
  total_route_miles: number;
  estimated_route_driving_seconds: number;
  scheduled_total_duration_minutes: number;
  scheduled_total_duration_hours: number;
  total_driving_hours: number;
  total_on_duty_not_driving_hours: number;
  number_of_breaks: number;
  number_of_rest_periods: number;
  number_of_cycle_restarts: number;
  number_of_fuel_stops: number;
  pickup_duration_minutes: number;
  dropoff_duration_minutes: number;
  initial_cycle_used_hours: number;
  final_cycle_usage_hours: number;
  final_cycle_remaining_hours: number;
  number_of_calendar_days: number;
  planning_start: string | null;
  planning_end: string | null;
  compliant?: boolean;
}

export interface Violation {
  rule: string;
  message: string;
  timestamp: string | null;
  location: EventLocation | null;
}

export interface Compliance {
  compliant: boolean;
  violations: Violation[];
}

export interface DailyLogSegment {
  id: string;
  source_event_id: string | null;
  start: string;
  end: string;
  status: DutyStatus;
  reason: string;
  location: EventLocation;
  duration: number;
  duration_minutes: number;
  duration_hours: number;
  distance_start: number;
  distance_end: number;
  route_distance_start: number;
  route_distance_end: number;
  presentation_only: boolean;
  metadata: Record<string, unknown>;
}

export interface DailyLogSummary {
  calendar_day_minutes: number;
  driving_minutes: number;
  on_duty_not_driving_minutes: number;
  off_duty_minutes: number;
  sleeper_berth_minutes: number;
  off_duty_sleeper_minutes: number;
  stop_count: number;
  compliant: boolean;
}

export interface DailyLogRemark {
  id: string;
  text: string;
  timestamp: string;
  source_event_id: string | null;
}

export interface DailyLog {
  date: string;
  period_start: string;
  period_end: string;
  events: DailyLogSegment[];
  segments: DailyLogSegment[];
  summary: DailyLogSummary;
  remarks: DailyLogRemark[];
}

export interface HOSState {
  current_timestamp: string;
  route_distance_miles: number;
  cycle_used_minutes: number;
  cycle_remaining_minutes: number;
  driving_in_current_window_minutes: number;
  elapsed_duty_window_minutes: number;
  driving_since_break_minutes: number;
  distance_since_fuel_miles: number;
  pickup_completed: boolean;
  dropoff_completed: boolean;
}

export interface TripPlanResult {
  status: "planned";
  trip_input: TripInput;
  locations: {
    current: Location;
    pickup: Location;
    dropoff: Location;
  };
  route: RouteResult;
  events: TripEvent[];
  stops: Stop[];
  summary: TripSummary;
  compliance: Compliance;
  violations: Violation[];
  daily_logs: DailyLog[];
  state?: HOSState;
}
