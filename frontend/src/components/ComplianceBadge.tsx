import type { Compliance, Violation } from "../types/trip";
import { formatDateTime, locationLabel } from "../utils/format";

interface ComplianceBadgeProps {
  compliance: Compliance;
}

function ViolationRow({ violation }: { violation: Violation }) {
  return (
    <article className="violation-row">
      <div className="violation-mark" aria-hidden="true">!</div>
      <div className="violation-copy">
        <strong>{violation.rule}</strong>
        <p>{violation.message}</p>
        <div className="violation-meta">
          {violation.timestamp && <span>{formatDateTime(violation.timestamp)}</span>}
          {violation.location && <span>{locationLabel(violation.location)}</span>}
        </div>
      </div>
    </article>
  );
}

export function ComplianceBadge({ compliance }: ComplianceBadgeProps) {
  return (
    <section className={`panel compliance-panel ${compliance.compliant ? "is-compliant" : "has-violations"}`} aria-labelledby="compliance-title" aria-live="polite">
      <div className="compliance-header">
        <div className="compliance-icon" aria-hidden="true">{compliance.compliant ? "✓" : "!"}</div>
        <div>
          <p className="section-kicker">Compliance check</p>
          <h2 id="compliance-title">{compliance.compliant ? "Plan is HOS compliant" : "Plan has HOS violations"}</h2>
          <p className="compliance-subtitle">
            {compliance.compliant
              ? "The returned event sequence stays within the configured planning rules."
              : `${compliance.violations.length} issue${compliance.violations.length === 1 ? "" : "s"} returned by the backend validator.`}
          </p>
        </div>
      </div>

      {compliance.compliant ? (
        <div className="compliance-clear"><span>✓</span> No violations returned for this plan</div>
      ) : (
        <div className="violations-list">
          {compliance.violations.map((violation, index) => (
            <ViolationRow key={`${violation.rule}-${violation.timestamp ?? index}`} violation={violation} />
          ))}
        </div>
      )}
    </section>
  );
}
