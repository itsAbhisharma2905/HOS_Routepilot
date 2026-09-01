import type { TripSummary } from "../types/trip";
import { formatHours, formatMinutes, formatMiles, formatSeconds } from "../utils/format";

interface TripSummaryProps {
  summary: TripSummary;
}

interface SummaryMetric {
  label: string;
  value: string;
  emphasis?: boolean;
}

export function TripSummary({ summary }: TripSummaryProps) {
  const metrics: SummaryMetric[] = [
    { label: "Total miles", value: formatMiles(summary.total_route_miles), emphasis: true },
    { label: "Estimated drive", value: formatSeconds(summary.estimated_route_driving_seconds), emphasis: true },
    { label: "Scheduled duration", value: formatMinutes(summary.scheduled_total_duration_minutes), emphasis: true },
    { label: "Calendar days", value: `${summary.number_of_calendar_days} ${summary.number_of_calendar_days === 1 ? "day" : "days"}` },
    { label: "Driving hours", value: formatHours(summary.total_driving_hours) },
    { label: "On-duty, not driving", value: formatHours(summary.total_on_duty_not_driving_hours) },
    { label: "Required breaks", value: summary.number_of_breaks.toString() },
    { label: "Daily rest periods", value: summary.number_of_rest_periods.toString() },
    { label: "Fuel stops", value: summary.number_of_fuel_stops.toString() },
    { label: "Pickup duration", value: formatMinutes(summary.pickup_duration_minutes) },
    { label: "Dropoff duration", value: formatMinutes(summary.dropoff_duration_minutes) },
    { label: "Cycle used at start", value: formatHours(summary.initial_cycle_used_hours) },
    { label: "Cycle used at finish", value: formatHours(summary.final_cycle_usage_hours) },
    { label: "Cycle remaining", value: formatHours(summary.final_cycle_remaining_hours), emphasis: true },
  ];

  return (
    <section className="panel summary-panel" aria-labelledby="summary-title">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Plan summary</p>
          <h2 id="summary-title">The numbers that matter</h2>
        </div>
        <span className="backend-note">Backend calculated</span>
      </div>

      <div className="summary-grid">
        {metrics.map((metric) => (
          <div className={`summary-metric${metric.emphasis ? " emphasis" : ""}`} key={metric.label}>
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
          </div>
        ))}
      </div>

      <div className="summary-footer">
        <span>Planning window</span>
        <b>{summary.planning_start ? new Date(summary.planning_start).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Not available"} → {summary.planning_end ? new Date(summary.planning_end).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Not available"}</b>
      </div>
    </section>
  );
}
