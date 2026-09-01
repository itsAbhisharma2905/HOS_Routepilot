import { useState } from "react";

import { ComplianceBadge } from "./components/ComplianceBadge";
import { EldDailyLogs } from "./components/EldDailyLogs";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { RouteMap } from "./components/RouteMap";
import { RouteOverview } from "./components/RouteOverview";
import { StopDetails } from "./components/StopDetails";
import { StopTimeline } from "./components/StopTimeline";
import { TripForm } from "./components/TripForm";
import { TripSummary } from "./components/TripSummary";
import type { TripPlanResult } from "./types/trip";
import "./styles.css";

function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TripPlanResult | null>(null);

  function handleError(message: string) {
    setError(message);
    if (message) setResult(null);
  }

  function handleLoadingChange(nextLoading: boolean) {
    setLoading(nextLoading);
    if (nextLoading) setResult(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="RoutePilot home">
          <span className="brand-mark">R</span>
          <span>route<span>pilot</span></span>
        </a>
        <div className="topbar-meta">
          <span className="environment-pill"><i /> Planning workspace</span>
          <span className="phase-label">HOS route planning</span>
        </div>
      </header>

      <main className="content-width">
        <section className="hero-grid" aria-labelledby="page-title">
          <div className="hero-copy">
            <p className="eyebrow">HOS-aware trip planning</p>
            <h1 id="page-title">Make every mile <em>count.</em></h1>
            <p className="hero-description">
              Turn a route into a clear operating plan with live geometry, scheduled stops, and a backend-validated HOS timeline.
            </p>
            <div className="hero-proof" aria-label="RoutePilot capabilities">
              <span><b>01</b> Route intelligence</span>
              <span><b>02</b> HOS guardrails</span>
              <span><b>03</b> Review-ready output</span>
            </div>
          </div>

          <div className="planner-card">
            <TripForm
              isLoading={loading}
              onLoadingChange={handleLoadingChange}
              onError={handleError}
              onPlan={(nextResult) => {
                setResult(nextResult);
                setError("");
              }}
            />
            {loading && <LoadingState />}
            {error && <ErrorState message={error} />}
          </div>
        </section>

        {!result && !loading && !error && <EmptyState />}

        {result && (
          <div className="result-workspace">
            <div className="result-intro">
              <div>
                <p className="eyebrow">Plan output</p>
                <h2>Here is the road ahead.</h2>
              </div>
              <span className="result-status"><i /> Backend plan received</span>
            </div>

            <RouteOverview result={result} />
            <TripSummary summary={result.summary} />

            <section className="map-stops-grid" aria-label="Route map and scheduled stops">
              <div className="panel map-panel">
                <div className="panel-heading map-heading">
                  <div>
                    <p className="section-kicker">Live route</p>
                    <h2>Follow the planned journey</h2>
                  </div>
                  <span className="map-hint">Scroll to explore · Click a marker</span>
                </div>
                <RouteMap result={result} />
              </div>

              <section className="panel scheduled-stops" aria-labelledby="stops-title">
                <div className="panel-heading">
                  <div>
                    <p className="section-kicker">Operations</p>
                    <h2 id="stops-title">Scheduled stops</h2>
                  </div>
                  <span className="event-count">{result.stops.length} stops</span>
                </div>
                <div className="stops-list">
                  {result.stops.map((stop, index) => (
                    <div className="stop-list-item" key={stop.id}>
                      <span className="stop-number">{String(index + 1).padStart(2, "0")}</span>
                      <StopDetails stop={stop} compact />
                    </div>
                  ))}
                </div>
              </section>
            </section>

            <StopTimeline result={result} />
            <EldDailyLogs result={result} />
            <ComplianceBadge compliance={result.compliance} />
          </div>
        )}
      </main>

      <footer className="content-width">
        <span>RoutePilot · HOS planning workspace</span>
        <span>Backend source of truth · Phase 5 final frontend</span>
      </footer>
    </div>
  );
}

export default App;
