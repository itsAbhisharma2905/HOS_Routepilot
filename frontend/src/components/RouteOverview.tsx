import type { Location, TripPlanResult } from "../types/trip";
import { formatMiles, formatSeconds, locationLabel } from "../utils/format";

interface RouteOverviewProps {
  result: TripPlanResult;
}

function waypointName(location: Location): string {
  return locationLabel(location);
}

export function RouteOverview({ result }: RouteOverviewProps) {
  const { locations, route } = result;
  const waypoints = [
    { role: "Current", location: locations.current, marker: "origin" },
    { role: "Pickup", location: locations.pickup, marker: "pickup" },
    { role: "Dropoff", location: locations.dropoff, marker: "dropoff" },
  ];

  return (
    <section className="panel route-overview" aria-labelledby="route-overview-title">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Route overview</p>
          <h2 id="route-overview-title">Your trip at a glance</h2>
        </div>
        <span className="data-source"><span className="source-dot" /> Live route data</span>
      </div>

      <div className="route-key-metrics">
        <div>
          <strong>{formatMiles(route.distance_miles)}</strong>
          <span>Total route distance</span>
        </div>
        <div>
          <strong>{formatSeconds(route.estimated_driving_seconds)}</strong>
          <span>Estimated drive time</span>
        </div>
        <div>
          <strong>{route.route_steps.length.toLocaleString()}</strong>
          <span>Turn-by-turn steps</span>
        </div>
      </div>

      <div className="route-stages" aria-label="Trip waypoints">
        {waypoints.map((waypoint, index) => (
          <div className="route-stage" key={waypoint.role}>
            <span className={`stage-marker ${waypoint.marker}`} aria-hidden="true">{index + 1}</span>
            <div>
              <span className="stage-role">{waypoint.role}</span>
              <strong>{waypointName(waypoint.location)}</strong>
              <small>{waypoint.location.normalized_name}</small>
            </div>
          </div>
        ))}
      </div>

      {route.legs.length > 0 && (
        <div className="route-legs">
          <div className="subheading"><span>Leg breakdown</span><span>{route.legs.length} legs</span></div>
          {route.legs.map((leg) => (
            <div className="route-leg" key={leg.sequence}>
              <span className="leg-index">0{leg.sequence + 1}</span>
              <span className="leg-route">{waypointName(leg.from)} <b>→</b> {waypointName(leg.to)}</span>
              <span className="leg-stat">{formatMiles(leg.distance_miles)} · {formatSeconds(leg.duration_seconds)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
