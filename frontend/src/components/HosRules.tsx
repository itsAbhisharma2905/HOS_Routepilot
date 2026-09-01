interface HosRule {
  number: string;
  name: string;
  value: string;
  description: string;
  note: string;
}

const rules: HosRule[] = [
  {
    number: "01",
    name: "Rolling cycle",
    value: "70 hours / 8 days",
    description: "The property-carrying driver model tracks on-duty time against a 70-hour, 8-day rolling cycle.",
    note: "Driving and on-duty-not-driving consume the cycle; qualifying rest does not.",
  },
  {
    number: "02",
    name: "Driving limit",
    value: "11 hours",
    description: "Driving is limited to 11 hours within the applicable daily driving window.",
    note: "The backend scheduler stops driving before this allowance is exceeded.",
  },
  {
    number: "03",
    name: "On-duty window",
    value: "14 hours",
    description: "The daily on-duty window is 14 hours and includes driving and on-duty work such as pickup, dropoff, and fuel.",
    note: "A 30-minute break does not extend or reset this window.",
  },
  {
    number: "04",
    name: "Required break",
    value: "30 minutes after 8 hours driving",
    description: "A qualifying 30-minute interruption is scheduled after 8 cumulative driving hours require it.",
    note: "Break timing and completion are determined by the backend event timeline.",
  },
  {
    number: "05",
    name: "Required rest",
    value: "10 consecutive hours",
    description: "The backend uses a 10-hour qualifying rest period for the daily reset.",
    note: "The generated event is represented as SLEEPER_BERTH in the ELD view.",
  },
  {
    number: "06",
    name: "Cycle restart",
    value: "34 hours",
    description: "When cycle availability is exhausted, the scheduler inserts a 34-hour restart before continuing.",
    note: "The restart resets cycle availability and does not advance route distance.",
  },
  {
    number: "07",
    name: "Adverse conditions",
    value: "No exception applied",
    description: "Adverse-driving-condition exceptions are not represented in the current backend planning model.",
    note: "No adverse-condition or short-haul exception is configurable or assumed.",
  },
];

export function HosRules() {
  return (
    <section className="rules-page" aria-labelledby="rules-title">
      <div className="rules-header">
        <div>
          <p className="eyebrow">HOS rules &amp; settings</p>
          <h1 id="rules-title">Know the guardrails.</h1>
          <p className="rules-description">
            A plain-language view of the property-carrying driver assumptions used to produce each route plan.
          </p>
        </div>
        <span className="rules-read-only">Read only</span>
      </div>

      <div className="rules-authority-note" role="note">
        <div className="rules-authority-icon" aria-hidden="true">✓</div>
        <div>
          <strong>Backend-enforced rules — informational and not configurable.</strong>
          <p>RoutePilot displays the rules used by the backend scheduler and validator. This page does not change how a plan is calculated.</p>
        </div>
      </div>

      <div className="rules-grid">
        {rules.map((rule) => (
          <article className="rule-card" key={rule.number}>
            <div className="rule-card-topline">
              <span className="rule-number">{rule.number}</span>
              <span className="rule-source">Backend enforced</span>
            </div>
            <p className="section-kicker">{rule.name}</p>
            <h2>{rule.value}</h2>
            <p className="rule-description">{rule.description}</p>
            <p className="rule-note">{rule.note}</p>
          </article>
        ))}
      </div>

      <div className="rules-disclaimer">
        <strong>Planning model scope</strong>
        <p>This informational page describes the current assessment model, not a certified ELD or legal interpretation. Complete duty history, provider quality, and jurisdiction-specific review remain necessary for real operations.</p>
      </div>
    </section>
  );
}
