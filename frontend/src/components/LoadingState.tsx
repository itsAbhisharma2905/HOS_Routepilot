export function LoadingState() {
  return (
    <div className="status-card loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>Building your plan</strong>
        <p>Geocoding locations, routing the trip, and checking HOS constraints…</p>
      </div>
    </div>
  );
}
