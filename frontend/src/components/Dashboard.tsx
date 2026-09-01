import type { StoredTripHistoryItem } from "../services/tripHistory";
import { formatDateTime, formatHours, formatMiles, formatMinutes, locationLabel } from "../utils/format";

interface DashboardProps {
  latestTrip: StoredTripHistoryItem | null;
  trips: StoredTripHistoryItem[];
  onNewTrip: () => void;
  onViewTrip: (trip: StoredTripHistoryItem) => void;
  onViewEldLogs: (trip: StoredTripHistoryItem) => void;
  onViewHistory: () => void;
  onViewRules: () => void;
}

function routeLabel(trip: StoredTripHistoryItem): string {
  const { locations } = trip.result;
  return [
    locationLabel(locations.current),
    locationLabel(locations.pickup),
    locationLabel(locations.dropoff),
  ].join(" → ");
}

function complianceLabel(compliant: boolean): string {
  return compliant ? "Compliant" : "Non-compliant";
}

export function Dashboard({
  latestTrip,
  trips,
  onNewTrip,
  onViewTrip,
  onViewEldLogs,
  onViewHistory,
  onViewRules,
}: DashboardProps) {
  const totalPlannedMiles = trips.reduce((total, trip) => total + trip.result.summary.total_route_miles, 0);
  const compliantTrips = trips.filter((trip) => trip.result.compliance.compliant).length;
  const nonCompliantTrips = trips.length - compliantTrips;

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Operations dashboard</p>
          <h1 id="dashboard-title">Stay ahead of every mile.</h1>
          <p className="dashboard-description">
            Your latest route plans, compliance signal, and daily logs in one calm operating view.
          </p>
        </div>
        <button className="dashboard-new-trip-button" type="button" onClick={onNewTrip}>
          New Trip <span aria-hidden="true">+</span>
        </button>
      </div>

      <div className="dashboard-kpi-grid" aria-label="Trip planning overview">
        <article className="dashboard-kpi dashboard-kpi-primary">
          <span>Saved plans</span>
          <strong>{trips.length}</strong>
          <small>Local trip history</small>
        </article>
        <article className="dashboard-kpi">
          <span>Total planned miles</span>
          <strong>{formatMiles(totalPlannedMiles)}</strong>
          <small>Across saved plans</small>
        </article>
        <article className="dashboard-kpi dashboard-kpi-success">
          <span>Compliant trips</span>
          <strong>{compliantTrips}</strong>
          <small>Backend result returned clear</small>
        </article>
        <article className="dashboard-kpi dashboard-kpi-warning">
          <span>Review required</span>
          <strong>{nonCompliantTrips}</strong>
          <small>Non-compliant saved plans</small>
        </article>
      </div>

      <section className="dashboard-latest" aria-labelledby="latest-trip-title">
        <div className="dashboard-section-heading">
          <div>
            <p className="section-kicker">Latest trip</p>
            <h2 id="latest-trip-title">Your most recent plan</h2>
          </div>
          <button className="dashboard-history-link" type="button" onClick={onViewHistory}>
            View all history <span aria-hidden="true">→</span>
          </button>
        </div>

        {latestTrip ? (
          <article className="dashboard-latest-card">
            <div className="dashboard-latest-heading">
              <div>
                <p className="dashboard-planned-time">Planned {formatDateTime(latestTrip.saved_at)}</p>
                <h3>{routeLabel(latestTrip)}</h3>
              </div>
              <span className={`dashboard-compliance ${latestTrip.result.compliance.compliant ? "is-compliant" : "has-violations"}`}>
                <i aria-hidden="true" /> {complianceLabel(latestTrip.result.compliance.compliant)}
              </span>
            </div>

            <dl className="dashboard-latest-stats">
              <div>
                <dt>Route</dt>
                <dd>{locationLabel(latestTrip.result.locations.current)} <span aria-hidden="true">→</span> {locationLabel(latestTrip.result.locations.dropoff)}</dd>
              </div>
              <div>
                <dt>Total miles</dt>
                <dd>{formatMiles(latestTrip.result.summary.total_route_miles)}</dd>
              </div>
              <div>
                <dt>Timeline</dt>
                <dd>{latestTrip.result.events.length} events · {latestTrip.result.stops.length} stops</dd>
              </div>
              <div>
                <dt>Scheduled duration</dt>
                <dd>{formatMinutes(latestTrip.result.summary.scheduled_total_duration_minutes)}</dd>
              </div>
            </dl>

            <div className="dashboard-latest-footer">
              <span>Cycle at finish: {formatHours(latestTrip.result.summary.final_cycle_usage_hours)}</span>
              <div className="dashboard-latest-actions">
                <button className="dashboard-secondary-button" type="button" onClick={() => onViewEldLogs(latestTrip)}>
                  Open ELD logs
                </button>
                <button className="dashboard-primary-button" type="button" onClick={() => onViewTrip(latestTrip)}>
                  View trip <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </article>
        ) : (
          <div className="dashboard-latest-empty" role="status">
            <div className="dashboard-empty-icon" aria-hidden="true">↗</div>
            <div>
              <h3>No saved plans yet.</h3>
              <p>Start a trip to see route details, compliance, stops, and ELD logs summarized here.</p>
            </div>
            <button className="dashboard-primary-button" type="button" onClick={onNewTrip}>
              Create your first trip <span aria-hidden="true">→</span>
            </button>
          </div>
        )}
      </section>

      <section className="dashboard-shortcuts" aria-labelledby="shortcuts-title">
        <div className="dashboard-section-heading">
          <div>
            <p className="section-kicker">Quick navigation</p>
            <h2 id="shortcuts-title">Pick up where you left off.</h2>
          </div>
        </div>
        <div className="dashboard-shortcut-grid">
          <button className="dashboard-shortcut" type="button" onClick={onViewHistory}>
            <span className="dashboard-shortcut-icon history-icon" aria-hidden="true">↺</span>
            <span className="dashboard-shortcut-copy"><strong>Trip History</strong><small>{trips.length ? `${trips.length} saved plan${trips.length === 1 ? "" : "s"} to review` : "No saved plans yet"}</small></span>
            <span className="dashboard-shortcut-arrow" aria-hidden="true">→</span>
          </button>
          <button className="dashboard-shortcut" type="button" onClick={() => latestTrip && onViewEldLogs(latestTrip)} disabled={!latestTrip}>
            <span className="dashboard-shortcut-icon eld-icon" aria-hidden="true">▤</span>
            <span className="dashboard-shortcut-copy"><strong>ELD Daily Logs</strong><small>{latestTrip ? "Open the latest 24-hour logbook" : "Create a trip to unlock logs"}</small></span>
            <span className="dashboard-shortcut-arrow" aria-hidden="true">→</span>
          </button>
          <button className="dashboard-shortcut" type="button" onClick={onViewRules}>
            <span className="dashboard-shortcut-icon rules-icon" aria-hidden="true">i</span>
            <span className="dashboard-shortcut-copy"><strong>HOS Rules</strong><small>Review the backend-enforced model</small></span>
            <span className="dashboard-shortcut-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>
    </section>
  );
}
