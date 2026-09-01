import { useState } from "react";

import { ComplianceBadge } from "./components/ComplianceBadge";
import { Dashboard } from "./components/Dashboard";
import { EldDailyLogs } from "./components/EldDailyLogs";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { HosRules } from "./components/HosRules";
import { LoadingState } from "./components/LoadingState";
import { RouteMap } from "./components/RouteMap";
import { RouteOverview } from "./components/RouteOverview";
import { StopDetails } from "./components/StopDetails";
import { StopTimeline } from "./components/StopTimeline";
import { TripHistory } from "./components/TripHistory";
import { TripForm } from "./components/TripForm";
import { TripSummary } from "./components/TripSummary";
import {
  addTripToHistory,
  clearTripHistory,
  deleteTripFromHistory,
  loadTripHistory,
  type StoredTripHistoryItem,
} from "./services/tripHistory";
import type { TripPlanResult } from "./types/trip";
import "./styles.css";

type AppView = "dashboard" | "planner" | "history" | "rules";

function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TripPlanResult | null>(null);
  const [tripFormKey, setTripFormKey] = useState(0);
  const [view, setView] = useState<AppView>("dashboard");
  const [history, setHistory] = useState<StoredTripHistoryItem[]>(() => loadTripHistory());
  const [historyNotice, setHistoryNotice] = useState("");

  function handleError(message: string) {
    setError(message);
    if (message) setResult(null);
  }

  function handleLoadingChange(nextLoading: boolean) {
    setLoading(nextLoading);
    if (nextLoading) setResult(null);
  }

  function handlePlan(nextResult: TripPlanResult) {
    setResult(nextResult);
    setError("");
    if (addTripToHistory(nextResult)) {
      setHistory(loadTripHistory());
      setHistoryNotice("");
    } else {
      setHistoryNotice("Trip planned, but it could not be saved to local history.");
    }
  }

  function handleViewTrip(trip: StoredTripHistoryItem) {
    setResult(trip.result);
    setError("");
    setHistoryNotice("");
    setView("planner");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleNewTrip() {
    setResult(null);
    setTripFormKey((current) => current + 1);
    setError("");
    setHistoryNotice("");
    setView("planner");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleViewLatestEldLogs(trip: StoredTripHistoryItem) {
    setResult(trip.result);
    setError("");
    setHistoryNotice("");
    setView("planner");
    window.setTimeout(() => {
      const target = document.getElementById("eld-daily-logs");
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      target.focus({ preventScroll: true });
    }, 0);
  }

  function handleDeleteTrip(id: string) {
    if (deleteTripFromHistory(id)) {
      setHistory(loadTripHistory());
      setHistoryNotice("");
    } else {
      setHistoryNotice("This trip could not be removed from local history.");
    }
  }

  function handleClearHistory() {
    if (clearTripHistory()) {
      setHistory([]);
      setHistoryNotice("");
    } else {
      setHistoryNotice("History could not be cleared.");
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="RoutePilot home">
          <span className="brand-mark">R</span>
          <span>route<span>pilot</span></span>
        </a>
        <nav className="primary-nav" aria-label="Primary navigation">
          <button
            className={view === "dashboard" ? "is-active" : ""}
            type="button"
            aria-current={view === "dashboard" ? "page" : undefined}
            onClick={() => setView("dashboard")}
          >
            Dashboard
          </button>
          <button className="nav-primary-action" type="button" onClick={handleNewTrip}>
            New Trip <span aria-hidden="true">+</span>
          </button>
          <button
            className={view === "history" ? "is-active" : ""}
            type="button"
            aria-current={view === "history" ? "page" : undefined}
            onClick={() => setView("history")}
          >
            Trip History <span className="primary-nav-count">{history.length}</span>
          </button>
          <button
            className={view === "rules" ? "is-active" : ""}
            type="button"
            aria-current={view === "rules" ? "page" : undefined}
            onClick={() => setView("rules")}
          >
            HOS Rules
          </button>
        </nav>
        <div className="topbar-meta">
          <span className="environment-pill"><i /> Planning workspace</span>
          <span className="phase-label">HOS route planning</span>
        </div>
      </header>

      <main className="content-width">
        {view === "dashboard" ? (
          <Dashboard
            latestTrip={history[0] ?? null}
            trips={history}
            onNewTrip={handleNewTrip}
            onViewTrip={handleViewTrip}
            onViewEldLogs={handleViewLatestEldLogs}
            onViewHistory={() => setView("history")}
            onViewRules={() => setView("rules")}
          />
        ) : view === "history" ? (
          <TripHistory
            trips={history}
            storageNotice={historyNotice}
            onViewTrip={handleViewTrip}
            onDeleteTrip={handleDeleteTrip}
            onClearHistory={handleClearHistory}
            onPlanTrip={() => {
              handleNewTrip();
            }}
          />
        ) : view === "rules" ? (
          <HosRules />
        ) : (
          <>
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
              key={tripFormKey}
              isLoading={loading}
              onLoadingChange={handleLoadingChange}
              onError={handleError}
              onPlan={handlePlan}
            />
            {loading && <LoadingState />}
            {error && <ErrorState message={error} />}
            {historyNotice && <p className="history-storage-notice" role="status">{historyNotice}</p>}
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
            <ComplianceBadge result={result} />
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
          </div>
        )}
          </>
        )}
      </main>

      <footer className="content-width">
        <span>RoutePilot · HOS planning workspace</span>
        <span>Backend source of truth · Phase 6.6 frontend</span>
      </footer>
    </div>
  );
}

export default App;
