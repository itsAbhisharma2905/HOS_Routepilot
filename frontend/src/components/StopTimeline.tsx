import { useMemo, useState } from "react";

import type { TripEvent, TripPlanResult } from "../types/trip";
import { eventLabel, formatDateTime, formatMiles, formatMinutes, locationLabel, statusLabel } from "../utils/format";

interface StopTimelineProps {
  result: TripPlanResult;
}

type TimelineFilter = "all" | "driving" | "stops" | "rest";

const filters: Array<{ id: TimelineFilter; label: string }> = [
  { id: "all", label: "All events" },
  { id: "driving", label: "Driving" },
  { id: "stops", label: "Stops" },
  { id: "rest", label: "Rest" },
];

function matchesFilter(event: TripEvent, filter: TimelineFilter): boolean {
  if (filter === "all") return true;
  if (filter === "driving") return event.status === "DRIVING";
  if (filter === "rest") return event.status === "OFF_DUTY" || event.status === "SLEEPER_BERTH";
  return event.status !== "DRIVING";
}

function eventClass(event: TripEvent): string {
  if (event.status === "DRIVING") return "driving";
  if (event.reason === "Required 30-minute break") return "break";
  if (event.reason === "Required 10-hour rest (daily reset)") return "rest";
  if (event.reason === "34-hour cycle restart") return "restart";
  if (event.reason === "Fuel") return "fuel";
  if (event.reason === "Pickup") return "pickup";
  if (event.reason === "Dropoff") return "dropoff";
  return "activity";
}

function TimelineEvent({ event, index }: { event: TripEvent; index: number }) {
  const isDriving = event.status === "DRIVING";

  return (
    <li className={`timeline-item ${eventClass(event)}`}>
      <div className="timeline-marker" aria-hidden="true">{index + 1}</div>
      <article className="timeline-card">
        <div className="timeline-card-heading">
          <div>
            <span className="timeline-event-kind">{eventLabel(event)}</span>
            <h3>{event.reason}</h3>
          </div>
          <span className="timeline-status">{statusLabel(event.status)}</span>
        </div>
        <div className="timeline-main-line">
          <span>{formatDateTime(event.start)} <b aria-hidden="true">→</b> {formatDateTime(event.end)}</span>
          <strong>{formatMinutes(event.duration_minutes)}</strong>
        </div>
        <div className="timeline-meta">
          <span><i aria-hidden="true">⌖</i> {locationLabel(event.location)}</span>
          <span><i aria-hidden="true">↗</i> {isDriving ? `${formatMiles(event.route_distance_start)} → ${formatMiles(event.route_distance_end)}` : formatMiles(event.route_distance_start)}</span>
        </div>
      </article>
    </li>
  );
}

export function StopTimeline({ result }: StopTimelineProps) {
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const visibleEvents = useMemo(
    () => result.events.map((event, index) => ({ event, index })).filter(({ event }) => matchesFilter(event, filter)),
    [filter, result.events],
  );

  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <div className="panel-heading timeline-heading">
        <div>
          <p className="section-kicker">HOS timeline</p>
          <h2 id="timeline-title">Every event, in sequence</h2>
          <p className="panel-caption">Rendered directly from the backend event list. Display filters never change the plan.</p>
        </div>
        <span className="event-count">{result.events.length} events</span>
      </div>

      <div className="timeline-filters" role="group" aria-label="Filter timeline events">
        {filters.map((item) => (
          <button
            className={filter === item.id ? "active" : ""}
            type="button"
            key={item.id}
            aria-pressed={filter === item.id}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {visibleEvents.length > 0 ? (
        <ol className="timeline-list">
          {visibleEvents.map(({ event, index }) => (
            <TimelineEvent event={event} index={index} key={event.id} />
          ))}
        </ol>
      ) : (
        <p className="timeline-empty">No events match this filter.</p>
      )}
    </section>
  );
}
