import type { DailyLog, TripPlanResult } from "../types/trip";
import { EldGraph } from "./EldGraph";
import { formatHours, formatDateTime } from "../utils/format";

interface EldDailyLogsProps {
  result: TripPlanResult;
}

function DailySummary({ log }: { log: DailyLog }) {
  const metrics = [
    ["Driving", formatHours(log.summary.driving_minutes / 60)],
    ["On duty", formatHours(log.summary.on_duty_not_driving_minutes / 60)],
    ["Off duty", formatHours(log.summary.off_duty_minutes / 60)],
    ["Sleeper berth", formatHours(log.summary.sleeper_berth_minutes / 60)],
    ["Stops", log.summary.stop_count.toString()],
  ];

  return (
    <section className="eld-day-summary" aria-labelledby={`summary-${log.date}`}>
      <div className="eld-subheading"><span id={`summary-${log.date}`}>Daily summary</span><span className="eld-compliance-state">{log.summary.compliant ? "Compliant" : "Violations returned"}</span></div>
      <div className="eld-summary-grid">
        {metrics.map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}
      </div>
      <p className="eld-total-note">Status totals: {formatHours(log.summary.off_duty_sleeper_minutes / 60)} off duty or sleeper berth across the complete 24-hour log.</p>
    </section>
  );
}

function DailyRemarks({ log }: { log: DailyLog }) {
  return (
    <section className="eld-remarks" aria-labelledby={`remarks-${log.date}`}>
      <div className="eld-subheading"><span id={`remarks-${log.date}`}>Remarks</span><span>{log.remarks.length}</span></div>
      {log.remarks.length > 0 ? (
        <ul>
          {log.remarks.map((remark) => <li key={remark.id}><time dateTime={remark.timestamp}>{formatDateTime(remark.timestamp)}</time><span>{remark.text}</span></li>)}
        </ul>
      ) : (
        <p className="eld-no-remarks">No stop remarks on this calendar day.</p>
      )}
    </section>
  );
}

function DailyLogCard({ log, index }: { log: DailyLog; index: number }) {
  return (
    <article className="eld-day-card" aria-labelledby={`eld-day-${log.date}`}>
      <div className="eld-day-heading">
        <div>
          <span className="section-kicker">Day {index + 1}</span>
          <h3 id={`eld-day-${log.date}`}>{log.date}</h3>
        </div>
        <span className="eld-period">24-hour period | {formatDateTime(log.period_start)} to {formatDateTime(log.period_end)}</span>
      </div>
      <EldGraph log={log} />
      <div className="eld-day-lower">
        <DailySummary log={log} />
        <DailyRemarks log={log} />
      </div>
    </article>
  );
}

export function EldDailyLogs({ result }: EldDailyLogsProps) {
  return (
    <section className="panel eld-panel" aria-labelledby="eld-title">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">ELD daily logs</p>
          <h2 id="eld-title">A complete 24-hour view</h2>
          <p className="panel-caption">A proportional representation of the validated backend event timeline. The log does not recalculate HOS compliance.</p>
        </div>
        <span className="event-count">{result.daily_logs.length} {result.daily_logs.length === 1 ? "day" : "days"}</span>
      </div>
      {result.daily_logs.length > 0 ? (
        <div className="eld-day-stack">
          {result.daily_logs.map((log, index) => <DailyLogCard key={log.date} log={log} index={index} />)}
        </div>
      ) : (
        <p className="eld-empty" role="alert">The backend returned no daily logs for this plan.</p>
      )}
    </section>
  );
}
