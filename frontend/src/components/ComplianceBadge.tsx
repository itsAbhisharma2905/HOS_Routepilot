import type { TripEvent, TripPlanResult, Violation } from "../types/trip";
import { formatDateTime, formatHours, formatMinutes, locationLabel, statusLabel } from "../utils/format";

interface ComplianceBadgeProps {
  result: TripPlanResult;
}

interface ComplianceMetricProps {
  label: string;
  value: string;
  limit: string;
  detail: string;
}

// These labels mirror the fixed limits of the backend planning model. They
// are presentation context only and are never used to decide compliance.
const HOS_LIMITS = {
  drivingHours: 11,
  dutyWindowHours: 14,
  cycleHours: 70,
};

function ComplianceMetric({ label, value, limit, detail }: ComplianceMetricProps) {
  return (
    <div className="compliance-metric">
      <div className="compliance-metric-heading">
        <span>{label}</span>
        <b>{limit}</b>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function affectedEvent(violation: Violation, events: TripEvent[]): TripEvent | undefined {
  if (!violation.timestamp) return undefined;
  const timestamp = new Date(violation.timestamp).getTime();
  if (Number.isNaN(timestamp)) return undefined;
  return events.find((event) => {
    const start = new Date(event.start).getTime();
    const end = new Date(event.end).getTime();
    return timestamp >= start && timestamp <= end;
  });
}

function ViolationRow({ violation, events }: { violation: Violation; events: TripEvent[] }) {
  const event = affectedEvent(violation, events);

  return (
    <article className="violation-row">
      <div className="violation-mark" aria-hidden="true">!</div>
      <div className="violation-copy">
        <div className="violation-title-line">
          <strong>{violation.rule}</strong>
          <span className="violation-source">Backend validator</span>
        </div>
        <p>{violation.message}</p>
        <dl className="violation-details">
          <div>
            <dt>Affected time</dt>
            <dd>{violation.timestamp ? formatDateTime(violation.timestamp) : "Not supplied"}</dd>
          </div>
          <div>
            <dt>Affected event</dt>
            <dd>{event ? `${event.reason} · ${statusLabel(event.status)}` : "Not supplied"}</dd>
          </div>
          <div>
            <dt>Location</dt>
            <dd>{violation.location ? locationLabel(violation.location) : "Not supplied"}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}

export function ComplianceBadge({ result }: ComplianceBadgeProps) {
  const { compliance, summary, events } = result;
  const completedBreaks = events.filter((event) => event.reason === "Required 30-minute break").length;
  const completedRest = events.filter((event) => event.reason === "Required 10-hour rest (daily reset)").length;
  const currentDrivingMinutes = result.state?.driving_in_current_window_minutes;
  const currentWindowMinutes = result.state?.elapsed_duty_window_minutes;
  const currentCycleMinutes = result.state?.cycle_used_minutes;
  const statusLabelText = compliance.compliant ? "COMPLIANT" : "NON-COMPLIANT";

  return (
    <section className={`panel compliance-panel ${compliance.compliant ? "is-compliant" : "has-violations"}`} aria-labelledby="compliance-title" aria-live="polite">
      <div className="compliance-header">
        <div className="compliance-icon" aria-hidden="true">{compliance.compliant ? "✓" : "!"}</div>
        <div className="compliance-heading-copy">
          <p className="section-kicker">Compliance check · backend result</p>
          <div className="compliance-title-line">
            <h2 id="compliance-title">{statusLabelText}</h2>
            <span className="compliance-status-pill">{compliance.compliant ? "No violations" : `${compliance.violations.length} violation${compliance.violations.length === 1 ? "" : "s"}`}</span>
          </div>
          <p className="compliance-subtitle">
            {compliance.compliant
              ? "The backend validator returned a compliant plan. The event timeline below is the source used for this summary."
              : "The backend validator returned a non-compliant plan. Review each returned issue and its affected event below."}
          </p>
        </div>
      </div>

      <div className="compliance-result-banner" role="status">
        <strong>{statusLabelText}</strong>
        <span>{compliance.compliant ? "Ready for operational review" : "Operational review required before dispatch"}</span>
        <b>{compliance.violations.length} violation{compliance.violations.length === 1 ? "" : "s"} returned</b>
      </div>

      <div className="compliance-metric-grid" aria-label="Backend compliance summary">
        <ComplianceMetric
          label="Driving time"
          value={currentDrivingMinutes === undefined ? formatHours(summary.total_driving_hours) : formatMinutes(currentDrivingMinutes)}
          limit={`${HOS_LIMITS.drivingHours}h driving limit`}
          detail={currentDrivingMinutes === undefined ? "Backend total across driving windows" : `Current window · ${formatHours(summary.total_driving_hours)} trip total`}
        />
        <ComplianceMetric
          label="On-duty window"
          value={currentWindowMinutes === undefined ? formatHours(summary.total_driving_hours + summary.total_on_duty_not_driving_hours) : formatMinutes(currentWindowMinutes)}
          limit={`${HOS_LIMITS.dutyWindowHours}h window limit`}
          detail={currentWindowMinutes === undefined ? "Driving plus on-duty, across resets" : "Current window at finish · backend state"}
        />
        <ComplianceMetric
          label="Cycle usage"
          value={currentCycleMinutes === undefined ? formatHours(summary.final_cycle_usage_hours) : formatMinutes(currentCycleMinutes)}
          limit={`${HOS_LIMITS.cycleHours}h cycle limit`}
          detail={`Starts at ${formatHours(summary.initial_cycle_used_hours)} · backend state`}
        />
        <ComplianceMetric
          label="Breaks"
          value={`${summary.number_of_breaks} / ${completedBreaks}`}
          limit="Required / completed"
          detail="30-minute breaks from backend events"
        />
        <ComplianceMetric
          label="Rest periods"
          value={`${summary.number_of_rest_periods} / ${completedRest}`}
          limit="Required / completed"
          detail="10-hour resets from backend events"
        />
        <ComplianceMetric
          label="Fuel stops"
          value={summary.number_of_fuel_stops > 0 ? `${summary.number_of_fuel_stops}` : "None"}
          limit="When applicable"
          detail={summary.number_of_fuel_stops > 0 ? "Backend-generated route stops" : "No fuel stop returned by backend"}
        />
      </div>

      <p className="compliance-source-note">
        Values are displayed from the backend summary and event list. This presentation does not recalculate HOS rules.
      </p>

      {compliance.compliant ? (
        <div className="compliance-clear"><span aria-hidden="true">✓</span> 0 violations returned by the backend validator</div>
      ) : (
        <div className="violations-section" aria-labelledby="violations-title">
          <div className="violations-heading">
            <div>
              <p className="section-kicker">Returned issues</p>
              <h3 id="violations-title">Review before dispatch</h3>
            </div>
            <span>{compliance.violations.length} total</span>
          </div>
          <div className="violations-list">
            {compliance.violations.map((violation, index) => (
              <ViolationRow key={`${violation.rule}-${violation.timestamp ?? index}`} violation={violation} events={events} />
            ))}
          </div>
        </div>
      )}

      <div className="compliance-footnote">
        <span>Schedule duration: {formatMinutes(summary.scheduled_total_duration_minutes)}</span>
        <span>Backend source: {summary.planning_start ? formatDateTime(summary.planning_start) : "planning timestamp unavailable"}</span>
      </div>
    </section>
  );
}
