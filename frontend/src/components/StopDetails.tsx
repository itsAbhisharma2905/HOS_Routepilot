import type { TripEvent } from "../types/trip";
import { eventLabel, formatDateTime, formatMiles, formatMinutes, locationLabel, statusLabel } from "../utils/format";

interface StopDetailsProps {
  stop: TripEvent;
  compact?: boolean;
}

function eventClass(event: TripEvent): string {
  if (event.reason === "Fuel") return "fuel";
  if (event.reason === "Pickup") return "pickup";
  if (event.reason === "Dropoff") return "dropoff";
  if (event.reason === "Required 30-minute break") return "break";
  if (event.reason === "Required 10-hour rest (daily reset)") return "rest";
  if (event.reason === "34-hour cycle restart") return "restart";
  if (event.status === "DRIVING") return "driving";
  return "activity";
}

export function StopDetails({ stop, compact = false }: StopDetailsProps) {
  const sameRoutePosition = stop.route_distance_start === stop.route_distance_end;

  return (
    <div className={`stop-details${compact ? " compact" : ""}`}>
      <div className="stop-detail-heading">
        <span className={`event-pill ${eventClass(stop)}`}>{eventLabel(stop)}</span>
        <span className="event-status">{statusLabel(stop.status)}</span>
      </div>
      <dl className="stop-detail-list">
        <div><dt>Location</dt><dd>{locationLabel(stop.location)}</dd></div>
        <div><dt>Time</dt><dd>{formatDateTime(stop.start)} <span aria-hidden="true">→</span> {formatDateTime(stop.end)}</dd></div>
        <div><dt>Duration</dt><dd>{formatMinutes(stop.duration_minutes)}</dd></div>
        <div><dt>Reason</dt><dd>{stop.reason}</dd></div>
        <div><dt>Route mileage</dt><dd>{sameRoutePosition ? formatMiles(stop.route_distance_start) : `${formatMiles(stop.route_distance_start)} → ${formatMiles(stop.route_distance_end)}`}</dd></div>
      </dl>
    </div>
  );
}
