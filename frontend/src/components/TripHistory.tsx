import { useEffect, useState } from "react";

import type { StoredTripHistoryItem } from "../services/tripHistory";
import { eventLabel, formatDateTime, formatMiles, formatMinutes, locationLabel, statusLabel } from "../utils/format";

interface TripHistoryProps {
  trips: StoredTripHistoryItem[];
  storageNotice: string;
  onViewTrip: (trip: StoredTripHistoryItem) => void;
  onDeleteTrip: (id: string) => void;
  onClearHistory: () => void;
  onPlanTrip: () => void;
}

type PendingAction =
  | { type: "trip"; id: string; label: string }
  | { type: "all" };

function complianceLabel(compliant: boolean): string {
  return compliant ? "Compliant" : "Violations returned";
}

export function TripHistory({
  trips,
  storageNotice,
  onViewTrip,
  onDeleteTrip,
  onClearHistory,
  onPlanTrip,
}: TripHistoryProps) {
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  useEffect(() => {
    if (!pendingAction) return undefined;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setPendingAction(null);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [pendingAction]);

  function confirmPendingAction() {
    if (!pendingAction) return;
    if (pendingAction.type === "all") {
      onClearHistory();
    } else {
      onDeleteTrip(pendingAction.id);
    }
    setPendingAction(null);
  }

  return (
    <section className="history-page" aria-labelledby="history-title">
      <div className="history-header">
        <div>
          <p className="eyebrow">Trip history</p>
          <h1 id="history-title">Plans worth revisiting.</h1>
          <p className="history-description">
            Reopen a validated route plan and its ELD logbook from this browser.
          </p>
        </div>
        <div className="history-header-actions">
          <span className="history-count" aria-label={`${trips.length} saved trips`}>
            {trips.length} {trips.length === 1 ? "saved trip" : "saved trips"}
          </span>
          {trips.length > 0 && (
            <button
              className="history-clear-button"
              type="button"
              onClick={() => setPendingAction({ type: "all" })}
            >
              Clear history
            </button>
          )}
        </div>
      </div>

      {storageNotice && <p className="history-storage-notice" role="status">{storageNotice}</p>}

      {trips.length === 0 ? (
        <div className="history-empty" role="status">
          <div className="history-empty-icon" aria-hidden="true">↗</div>
          <p className="section-kicker">Nothing saved yet</p>
          <h2>Your next plan will appear here.</h2>
          <p>Generate a compliant or valid trip plan to keep its route, stops, timeline, and daily logbook close at hand.</p>
          <button className="primary-button history-empty-button" type="button" onClick={onPlanTrip}>
            Plan a trip <span aria-hidden="true">→</span>
          </button>
        </div>
      ) : (
        <div className="history-grid">
          {trips.map((trip) => {
            const { locations, summary, compliance, events, stops } = trip.result;
            const routeLabel = [
              locationLabel(locations.current),
              locationLabel(locations.pickup),
              locationLabel(locations.dropoff),
            ].join(" → ");

            return (
              <article className="history-card" key={trip.id}>
                <div className="history-card-header">
                  <div>
                    <p className="section-kicker">Planned {formatDateTime(trip.saved_at)}</p>
                    <h2>{routeLabel}</h2>
                  </div>
                  <span className={`history-compliance ${compliance.compliant ? "is-compliant" : "has-violations"}`}>
                    <i aria-hidden="true" />
                    {complianceLabel(compliance.compliant)}
                  </span>
                </div>

                <dl className="history-location-list">
                  <div>
                    <dt>Origin</dt>
                    <dd>{locationLabel(locations.current)}</dd>
                  </div>
                  <div>
                    <dt>Pickup</dt>
                    <dd>{locationLabel(locations.pickup)}</dd>
                  </div>
                  <div>
                    <dt>Destination</dt>
                    <dd>{locationLabel(locations.dropoff)}</dd>
                  </div>
                </dl>

                <dl className="history-stats">
                  <div>
                    <dt>Total miles</dt>
                    <dd>{formatMiles(summary.total_route_miles)}</dd>
                  </div>
                  <div>
                    <dt>Events</dt>
                    <dd>{events.length}</dd>
                  </div>
                  <div>
                    <dt>Stops</dt>
                    <dd>{stops.length}</dd>
                  </div>
                  <div>
                    <dt>Trip duration</dt>
                    <dd>{formatMinutes(summary.scheduled_total_duration_minutes)}</dd>
                  </div>
                </dl>

                <div className="history-card-footer">
                  <p>{summary.planning_start ? `Schedule starts ${formatDateTime(summary.planning_start)}` : "Schedule start unavailable"}</p>
                  <p className="history-card-event-note">{events.length} timeline events · {stops.length} stops</p>
                </div>

                <div className="history-card-actions">
                  <button className="history-view-button" type="button" onClick={() => onViewTrip(trip)}>
                    View trip <span aria-hidden="true">→</span>
                  </button>
                  <button
                    className="history-delete-button"
                    type="button"
                    onClick={() => setPendingAction({ type: "trip", id: trip.id, label: routeLabel })}
                    aria-label={`Delete trip ${routeLabel}`}
                  >
                    Delete
                  </button>
                </div>

                <details className="history-card-details">
                  <summary>Plan details</summary>
                  <p>Driving {formatMinutes(summary.total_driving_hours * 60)} · {statusLabel("DRIVING")} time</p>
                  <p>{events.slice(0, 3).map((event) => `${formatDateTime(event.start)} ${eventLabel(event)}`).join(" · ")}</p>
                </details>
              </article>
            );
          })}
        </div>
      )}

      {pendingAction && (
        <div className="history-dialog-backdrop" role="presentation">
          <div
            className="history-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="history-confirm-title"
            aria-describedby="history-confirm-description"
          >
            <p className="section-kicker">Please confirm</p>
            <h2 id="history-confirm-title">
              {pendingAction.type === "all" ? "Clear all saved trips?" : "Delete this saved trip?"}
            </h2>
            <p id="history-confirm-description">
              {pendingAction.type === "all"
                ? "This removes every trip saved in this browser. This action cannot be undone."
                : `“${pendingAction.label}” will be removed from this browser. This action cannot be undone.`}
            </p>
            <div className="history-dialog-actions">
              <button className="history-cancel-button" type="button" autoFocus onClick={() => setPendingAction(null)}>
                Cancel
              </button>
              <button className="history-confirm-button" type="button" onClick={confirmPendingAction}>
                {pendingAction.type === "all" ? "Clear history" : "Delete trip"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
