export function EmptyState() {
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <div className="empty-icon" aria-hidden="true">↗</div>
      <div>
        <p className="section-kicker">Ready when you are</p>
        <h2 id="empty-state-title">Your next route starts here</h2>
        <p>Enter trip details to generate a route, HOS schedule, stops, and compliance view.</p>
      </div>
      <div className="empty-checklist" aria-label="Plan contents">
        <span>01 <b>Route geometry</b></span>
        <span>02 <b>HOS timeline</b></span>
        <span>03 <b>Compliance check</b></span>
      </div>
    </section>
  );
}
