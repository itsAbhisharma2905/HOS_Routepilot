import type { EventLocation, Location, TripEvent } from "../types/trip";

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

export function formatMiles(miles: number): string {
  return `${numberFormat.format(miles)} mi`;
}

export function formatMinutes(minutes: number): string {
  const rounded = Math.max(0, Math.round(minutes));
  const days = Math.floor(rounded / 1440);
  const hours = Math.floor((rounded % 1440) / 60);
  const remainingMinutes = rounded % 60;
  const parts: string[] = [];
  if (days) parts.push(`${days}d`);
  if (hours || days) parts.push(`${hours}h`);
  if (remainingMinutes || parts.length === 0) parts.push(`${remainingMinutes}m`);
  return parts.join(" ");
}

export function formatSeconds(seconds: number): string {
  return formatMinutes(Math.round(seconds / 60));
}

export function formatHours(hours: number): string {
  return `${numberFormat.format(hours)}h`;
}

export function formatDateTime(timestamp: string | null | undefined): string {
  if (!timestamp) return "Not available";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

export function formatTimeRange(event: Pick<TripEvent, "start" | "end">): string {
  return `${formatDateTime(event.start)} – ${formatDateTime(event.end)}`;
}

export function locationLabel(location: EventLocation | null | undefined): string {
  if (!location) return "Location unavailable";
  if (isGeocodedLocation(location)) {
    return [location.city, location.state].filter(Boolean).join(", ") || location.normalized_name;
  }
  return location.label ??
    (typeof location.route_distance_miles === "number"
      ? `Route mile ${location.route_distance_miles.toFixed(1)}`
      : "Route position");
}

export function isGeocodedLocation(location: EventLocation): location is Location {
  return "normalized_name" in location;
}

export function eventLabel(event: Pick<TripEvent, "reason">): string {
  if (event.reason === "Required 30-minute break") return "Required break";
  if (event.reason === "Required 10-hour rest (daily reset)") return "Daily rest";
  if (event.reason === "34-hour cycle restart") return "34-hour restart";
  return event.reason;
}

export function statusLabel(status: TripEvent["status"]): string {
  return status.replaceAll("_", " ");
}
