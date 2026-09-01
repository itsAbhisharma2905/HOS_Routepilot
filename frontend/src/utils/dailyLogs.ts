import type { DailyLog, DailyLogSegment, TripEvent } from "../types/trip";

const MINUTES_PER_DAY = 1440;
const STATUS_KEYS = ["DRIVING", "ON_DUTY_NOT_DRIVING", "OFF_DUTY", "SLEEPER_BERTH"] as const;

function parsedMinutes(start: string, end: string): number | null {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null;
  const minutes = (endMs - startMs) / 60000;
  return Number.isInteger(minutes) ? minutes : null;
}

function statusDurations(segments: DailyLogSegment[]): Record<(typeof STATUS_KEYS)[number], number> {
  const totals: Record<(typeof STATUS_KEYS)[number], number> = {
    DRIVING: 0,
    ON_DUTY_NOT_DRIVING: 0,
    OFF_DUTY: 0,
    SLEEPER_BERTH: 0,
  };
  segments.forEach((segment) => {
    if (segment.status in totals) totals[segment.status as (typeof STATUS_KEYS)[number]] += segment.duration_minutes;
  });
  return totals;
}

export function validateDailyLogs(dailyLogs: DailyLog[], sourceEvents: TripEvent[]): string[] {
  const errors: string[] = [];
  const representedMinutes = new Map(sourceEvents.map((event) => [event.id, 0]));
  let previousPeriodStart: number | null = null;

  dailyLogs.forEach((log, logIndex) => {
    const periodStart = Date.parse(log.period_start);
    const periodEnd = Date.parse(log.period_end);
    const label = log.date || `day ${logIndex + 1}`;
    if (!Number.isFinite(periodStart) || !Number.isFinite(periodEnd)) {
      errors.push(`Daily log ${label} has invalid period timestamps.`);
      return;
    }
    if ((periodEnd - periodStart) / 60000 !== MINUTES_PER_DAY) errors.push(`Daily log ${label} does not cover 24 hours.`);
    const periodDate = new Date(periodStart);
    if (periodDate.getUTCHours() !== 0 || periodDate.getUTCMinutes() !== 0 || periodDate.getUTCSeconds() !== 0 || periodDate.getUTCMilliseconds() !== 0) {
      errors.push(`Daily log ${label} does not start at midnight.`);
    }
    if (periodDate.toISOString().slice(0, 10) !== log.date) errors.push(`Daily log ${label} has an inconsistent date.`);
    if (previousPeriodStart !== null && periodStart - previousPeriodStart !== 86400000) errors.push("Daily logs are not consecutive.");
    previousPeriodStart = periodStart;

    const eventIds = log.events.map((segment) => segment.id).join("|");
    const segmentIds = log.segments.map((segment) => segment.id).join("|");
    if (eventIds !== segmentIds) errors.push(`Daily log ${label} has inconsistent events and segments.`);

    let totalMinutes = 0;
    let previousEnd = periodStart;
    log.segments.forEach((segment) => {
      const segmentStart = Date.parse(segment.start);
      const segmentEnd = Date.parse(segment.end);
      const duration = parsedMinutes(segment.start, segment.end);
      if (!Number.isFinite(segmentStart) || !Number.isFinite(segmentEnd) || duration === null || duration <= 0) {
        errors.push(`Segment ${segment.id} has an invalid duration.`);
        return;
      }
      if (segment.duration_minutes !== duration) errors.push(`Segment ${segment.id} duration does not match its timestamps.`);
      if (segmentStart < periodStart || segmentEnd > periodEnd) errors.push(`Segment ${segment.id} is outside daily log ${label}.`);
      if (segmentStart < previousEnd) errors.push(`Segments in daily log ${label} overlap or are out of order.`);
      if (segmentStart > previousEnd) errors.push(`Daily log ${label} contains an unexplained gap.`);
      previousEnd = segmentEnd;
      totalMinutes += duration;
      if (segment.source_event_id !== null) {
        if (!representedMinutes.has(segment.source_event_id)) errors.push(`Segment ${segment.id} references an unknown source event.`);
        else representedMinutes.set(segment.source_event_id, (representedMinutes.get(segment.source_event_id) ?? 0) + duration);
      }
    });

    if (totalMinutes !== MINUTES_PER_DAY) errors.push(`Daily log ${label} totals ${totalMinutes} rather than 1440 minutes.`);
    if (previousEnd !== periodEnd) errors.push(`Daily log ${label} does not reach the end of its 24-hour period.`);
    const totals = statusDurations(log.segments);
    const summaryChecks: Array<[keyof DailyLog["summary"], number]> = [
      ["calendar_day_minutes", totalMinutes],
      ["driving_minutes", totals.DRIVING],
      ["on_duty_not_driving_minutes", totals.ON_DUTY_NOT_DRIVING],
      ["off_duty_minutes", totals.OFF_DUTY],
      ["sleeper_berth_minutes", totals.SLEEPER_BERTH],
      ["off_duty_sleeper_minutes", totals.OFF_DUTY + totals.SLEEPER_BERTH],
    ];
    summaryChecks.forEach(([field, expected]) => {
      if (log.summary[field] !== expected) errors.push(`Daily log ${label} summary field ${field} is inconsistent.`);
    });
    const expectedStops = log.segments.filter((segment) => segment.source_event_id !== null && segment.status !== "DRIVING").length;
    if (log.summary.stop_count !== expectedStops) errors.push(`Daily log ${label} stop count is inconsistent.`);
  });

  sourceEvents.forEach((event) => {
    if ((representedMinutes.get(event.id) ?? 0) !== event.duration_minutes) {
      errors.push(`Source event ${event.id} duration is not fully represented.`);
    }
  });
  if (sourceEvents.length > 0 && dailyLogs.length === 0) errors.push("Source events are not represented by daily logs.");
  return errors;
}
