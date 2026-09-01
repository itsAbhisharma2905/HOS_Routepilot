import { useEffect, useState, type CSSProperties } from "react";

import type { DailyLog, DailyLogSegment, DutyStatus } from "../types/trip";
import { eventLabel, formatDateTime, formatMiles, formatMinutes, locationLabel, statusLabel } from "../utils/format";

interface EldGraphProps {
  log: DailyLog;
}

const TICKS = Array.from({ length: 13 }, (_, index) => index * 120);
const STATUS_ROWS: Array<{ status: DutyStatus; label: string }> = [
  { status: "OFF_DUTY", label: "Off duty" },
  { status: "SLEEPER_BERTH", label: "Sleeper berth" },
  { status: "DRIVING", label: "Driving" },
  { status: "ON_DUTY_NOT_DRIVING", label: "On duty" },
];

function clockLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(remainingMinutes).padStart(2, "0")}`;
}

function minutesFromPeriod(periodStart: string, timestamp: string): number {
  const periodStartMs = Date.parse(periodStart);
  const timestampMs = Date.parse(timestamp);
  if (!Number.isFinite(periodStartMs) || !Number.isFinite(timestampMs)) return 0;
  return Math.max(0, Math.min(1440, (timestampMs - periodStartMs) / 60000));
}

function segmentStyle(log: DailyLog, segment: DailyLogSegment): CSSProperties {
  const start = minutesFromPeriod(log.period_start, segment.start);
  const end = minutesFromPeriod(log.period_start, segment.end);
  return {
    left: `${(start / 1440) * 100}%`,
    width: `${Math.max(0, ((end - start) / 1440) * 100)}%`,
  };
}

function segmentAriaLabel(log: DailyLog, segment: DailyLogSegment): string {
  const start = minutesFromPeriod(log.period_start, segment.start);
  const end = minutesFromPeriod(log.period_start, segment.end);
  return `${statusLabel(segment.status)}, ${segment.reason}, ${clockLabel(start)} to ${clockLabel(end)}, ${formatMinutes(segment.duration_minutes)}, ${locationLabel(segment.location)}`;
}

function SegmentButton({ log, segment, onSelect }: { log: DailyLog; segment: DailyLogSegment; onSelect: (segment: DailyLogSegment) => void }) {
  const width = ((minutesFromPeriod(log.period_start, segment.end) - minutesFromPeriod(log.period_start, segment.start)) / 1440) * 100;
  return (
    <button
      type="button"
      className={`eld-segment status-${segment.status.toLowerCase()}`}
      style={segmentStyle(log, segment)}
      title={segmentAriaLabel(log, segment)}
      aria-label={segmentAriaLabel(log, segment)}
      onClick={() => onSelect(segment)}
    >
      {width >= 7 && <span>{eventLabel(segment)}</span>}
    </button>
  );
}

function SegmentDetails({ log, segment }: { log: DailyLog; segment: DailyLogSegment }) {
  const start = minutesFromPeriod(log.period_start, segment.start);
  const end = minutesFromPeriod(log.period_start, segment.end);
  return (
    <div className="eld-selected-event" aria-live="polite">
      <div className="eld-selected-heading">
        <div>
          <span className="section-kicker">Selected log event</span>
          <h4>{eventLabel(segment)}</h4>
        </div>
        <span className={`eld-status-chip status-${segment.status.toLowerCase()}`}>{statusLabel(segment.status)}</span>
      </div>
      <dl className="eld-selected-grid">
        <div><dt>Time</dt><dd>{clockLabel(start)} to {clockLabel(end)}</dd></div>
        <div><dt>Duration</dt><dd>{formatMinutes(segment.duration_minutes)}</dd></div>
        <div><dt>Reason</dt><dd>{segment.reason}</dd></div>
        <div><dt>Location</dt><dd>{locationLabel(segment.location)}</dd></div>
        <div><dt>Route mileage</dt><dd>{segment.route_distance_start === segment.route_distance_end ? formatMiles(segment.route_distance_start) : `${formatMiles(segment.route_distance_start)} to ${formatMiles(segment.route_distance_end)}`}</dd></div>
        <div><dt>Timestamp</dt><dd>{formatDateTime(segment.start)} to {formatDateTime(segment.end)}</dd></div>
      </dl>
    </div>
  );
}

export function EldGraph({ log }: EldGraphProps) {
  const [selectedId, setSelectedId] = useState<string | null>(log.segments[0]?.id ?? null);
  const selectedSegment = log.segments.find((segment) => segment.id === selectedId) ?? null;

  useEffect(() => {
    setSelectedId(log.segments[0]?.id ?? null);
  }, [log.date, log.segments]);

  return (
    <div className="eld-graph-wrap">
      <div className="eld-chart-scroll" role="group" aria-label={`24-hour ELD graph for ${log.date}`}>
        <div className="eld-chart">
          <div className="eld-axis-spacer" aria-hidden="true" />
          <div className="eld-axis" aria-hidden="true">
            {TICKS.map((tick) => <span key={tick} style={{ left: `${(tick / 1440) * 100}%` }}>{clockLabel(tick)}</span>)}
          </div>
          <div className="eld-labels">
            {STATUS_ROWS.map((row) => <div className="eld-status-label" key={row.status}>{row.label}</div>)}
          </div>
          <div className="eld-rows">
            {STATUS_ROWS.map((row) => (
              <div className={`eld-row status-row-${row.status.toLowerCase()}`} key={row.status}>
                {log.segments.filter((segment) => segment.status === row.status).map((segment) => (
                  <SegmentButton key={segment.id} log={log} segment={segment} onSelect={(selected) => setSelectedId(selected.id)} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {selectedSegment && <SegmentDetails log={log} segment={selectedSegment} />}

      <details className="eld-event-details" open>
        <summary>Daily event details ({log.segments.length})</summary>
        <ol className="eld-event-list">
          {log.segments.map((segment) => (
            <li key={segment.id}>
              <button type="button" onClick={() => setSelectedId(segment.id)} aria-label={segmentAriaLabel(log, segment)}>
                <span className={`eld-list-status status-${segment.status.toLowerCase()}`} aria-hidden="true" />
                <span className="eld-list-copy">
                  <strong>{eventLabel(segment)}</strong>
                  <small>{clockLabel(minutesFromPeriod(log.period_start, segment.start))} to {clockLabel(minutesFromPeriod(log.period_start, segment.end))} | {formatMinutes(segment.duration_minutes)} | {locationLabel(segment.location)}</small>
                </span>
              </button>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
