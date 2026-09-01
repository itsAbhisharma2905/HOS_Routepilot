# HOS RoutePilot

Full-stack truck trip planner for the Spotter Full Stack Developer assessment.

## Current status

Phase 5 final implementation is now in place:

- Django + Django REST Framework backend
- React + TypeScript + Vite frontend
- environment-based configuration
- Nominatim-compatible location normalization
- OSRM-compatible combined current -> pickup -> dropoff routing
- normalized GeoJSON/Leaflet geometry, miles, seconds, legs, waypoints, and route steps
- pure deterministic HOS event scheduler
- independent schedule validation
- route-distance-aware pickup, dropoff, fuel, break, daily-rest, and cycle-restart events
- responsive React planning dashboard
- Leaflet route map using backend geometry with waypoint and HOS-stop markers
- backend-sourced summary, compliance, stop details, and chronological event timeline
- backend-derived ELD daily logs with midnight splitting, exact 24-hour coverage, daily summaries, remarks, and integrity validation
- time-proportional interactive ELD graph for all four backend duty statuses
- loading, empty, API-error, and malformed-response states

The plan endpoint returns the route, schedule, stops, summary, compliance result, and daily logs. ELD logs are a presentation of the backend schedule; they do not recalculate HOS compliance and do not claim regulatory certification.

## Repository layout

```text
backend/
  manage.py
  config/
  trips/
    services/
      geocoding.py
      http.py
      hos_engine.py
      route_progress.py
      routing.py
      schedule_validator.py
      daily_logs.py
      trip_planner.py
      validators.py
frontend/
  src/
    components/       # form, map, summary, stops, timeline, ELD, and state views
    services/         # centralized backend API client and response validation
    types/            # synchronized API/domain model
    utils/            # display-only formatting helpers
```

## Local setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` at the repository root before starting both services. The frontend uses `VITE_API_BASE_URL`; the backend reads the Django, provider, and CORS settings listed there.

## API

`GET /api/health/` returns a lightweight service health response.

`POST /api/trips/plan/` accepts:

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Houston, TX",
  "cycle_used_hours": 24
}
```

The response contains:

- `locations.current`, `locations.pickup`, and `locations.dropoff` with normalized names and coordinates
- `route.distance_miles` and `route.estimated_driving_seconds`
- `route.geometry` as GeoJSON `LineString` coordinates in `[longitude, latitude]` order
- `route.coordinates` as Leaflet-friendly `[latitude, longitude]` pairs
- ordered `route.route_steps` with generated maneuver instructions and cumulative distance
- normalized `route.legs` and snapped `route.waypoints`
- `events` as the single chronological source for future timeline and ELD consumers
- `stops` as the non-driving events: pickup, dropoff, fuel, break, rest, and restart
- `summary` with driving, duty, stop, duration, cycle, and calendar-day totals
- `compliance` and top-level `violations` from an independent validation pass
- `daily_logs` with complete calendar-day periods, split `segments`, daily summaries, and backend-derived remarks

The API validates the request before calling the service layer. Provider and planning errors are returned as JSON with stable codes such as `LOCATION_NOT_FOUND`, `PROVIDER_TIMEOUT`, `ROUTE_NOT_FOUND`, `INVALID_SCHEDULE_INPUT`, and `MALFORMED_PROVIDER_RESPONSE`.

## Frontend architecture

`App` owns the request lifecycle and passes one validated `TripPlanResult` to the presentation components. `TripForm` sends only user-entered values through `services/api.ts`; it does not contain route or HOS calculations. The API client validates the response shape before map, summary, timeline, or compliance components render it.

`RouteOverview` and `TripSummary` display backend route and summary values. `RouteMap` converts backend GeoJSON `[longitude, latitude]` coordinates to Leaflet positions, fits the map to the returned geometry, and renders current, pickup, dropoff, fuel, break, rest, and restart markers. `StopTimeline` preserves backend event order; its filters are display-only and never recompute the plan. `ComplianceBadge` reports the backend compliance result and violations without making a second client-side decision.

`daily_logs.py` delegates midnight splitting to the Phase 3 `split_event_at_midnight` helper. It creates one `DailyLog` per calendar day, adds explicit presentation-only off-duty coverage before the first and after the last scheduled event, derives daily status totals from the resulting segments, and validates source-duration preservation, chronology, coverage, and 1,440-minute totals. `EldDailyLogs` and `EldGraph` render this response directly. The graph maps minutes since local log midnight to percentage positions, while the accessible event list provides a text equivalent.

The frontend uses `leaflet`, `react-leaflet`, and `@types/leaflet`. Route geometry is passed to one polyline rather than rendered as one React node per point, which keeps large route responses manageable.

## Routing and HOS architecture

`RoutePlanningService` is the application boundary. It geocodes the three inputs in order, retrieves one ordered route containing current location, pickup, and dropoff, invokes the pure HOS scheduler, and validates the resulting event timeline. Django views do not contain provider calls, and the React app only calls the Django API.

Distance is converted from provider meters to application miles using `1609.344` meters per mile. `RouteProgress` consumes normalized leg distances and provider duration, allocating integer minutes with cumulative rounding while preserving at least one minute for every positive-distance leg. Small tolerated distance discrepancies are scaled monotonically; malformed distance/time segments are rejected. It answers both "how many minutes to reach this route mile?" and "where is the driver after this many driving minutes?" without replacing provider duration with a fixed speed.

`HOSScheduler` owns all event scheduling. At each driving iteration it uses the earliest of the remaining route time, 11-hour driving allowance, 14-hour window, 8-hour break allowance, and cycle allowance. It then schedules the required break, 10-hour rest, or 34-hour restart before continuing. Pickup and dropoff consume exactly 60 minutes of on-duty-not-driving time; fuel consumes 30 minutes.

`validate_schedule` is separate from the scheduler. It checks chronology, overlaps, positive durations, driving limits, window limits, break behavior, cycle usage, rest/restart durations, fuel intervals, pickup/dropoff durations, and route mileage monotonicity.

`daily_logs.py` is a presentation projection, not a second HOS engine. Its validator checks data integrity only; HOS legality and the compliance result remain owned by `HOSScheduler` and `validate_schedule`.

## HOS assumptions and limitations

The assessment model is a property-carrying driver with a 70-hour/8-day cycle, 11 driving hours, a 14-hour duty window, a required 30-minute interruption after 8 cumulative driving hours, 10 consecutive hours of qualifying rest, and a 34-hour restart when cycle availability is exhausted. No adverse-driving or short-haul exceptions are implemented.

`cycle_used_hours` is treated as initial rolling-cycle usage. Previous seven-day duty records are unavailable, so the application does not invent them. The daily window and driving counters begin fresh at the configured planning timestamp.

The default deterministic planning timestamp is `2026-01-01T08:00:00+00:00` and can be changed with `PLANNING_START_TIMESTAMP`. Fueling is modeled as 30 minutes (`FUEL_DURATION_MINUTES`); this is an application assumption because the assessment does not specify a fuel duration. Fuel is required before route mileage since the previous fuel event would exceed 1,000 miles.

This is an assessment model, not a certified electronic logging device or legal compliance system. Real operations require complete duty history, jurisdiction-specific review, provider-quality controls, and a qualified compliance interpretation.

## Routing provider considerations

Nominatim-compatible geocoding and OSRM-compatible routing are configured through environment variables. Public OpenStreetMap services have usage policies, shared capacity, and rate limits. Geocoding requests are serial with a default one-second interval between the three lookups. Production traffic should use a dedicated or hosted provider, durable caching, a contactable user-agent, and an HTTPS OSRM-compatible endpoint.

## Tests and build

```powershell
cd backend
python manage.py test

cd ..\frontend
npm run build
```

The backend suite contains 55 tests, including 15 Phase 5 daily-log projection and integrity tests. The HOS and daily-log tests use synthetic route/event data and do not depend on live OSRM. Routing and geocoding tests mock all external HTTP requests. The frontend has no separate test runner; its TypeScript check is part of `npm run build`.

## Environment and deployment

Copy `.env.example` to `.env` for local development. The supported settings are:

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS` for backend runtime safety
- `CORS_ALLOWED_ORIGINS` for the deployed frontend origin
- `VITE_API_BASE_URL` for the frontend's deployed API base URL
- `NOMINATIM_BASE_URL`, `NOMINATIM_USER_AGENT`, and `NOMINATIM_MIN_INTERVAL_SECONDS` for geocoding
- `OSRM_BASE_URL` and `EXTERNAL_PROVIDER_TIMEOUT_SECONDS` for routing
- `PLANNING_START_TIMESTAMP` for deterministic planning output

For a deployment, build the frontend with the production `VITE_API_BASE_URL` and serve `frontend/dist` from a static host. Run the backend with `DJANGO_DEBUG=false`, a generated secret, explicit allowed hosts, explicit CORS origins, and a production WSGI/ASGI server using `config.wsgi:application` or `config.asgi:application`. Run migrations and `python manage.py collectstatic` during the backend release. Do not use Django `runserver` as the production process.

No deployment credentials or hosting target are configured in this workspace, so the application has not been deployed automatically. Actual hosting still requires provisioning the frontend/API origins, production provider endpoints, TLS, provider rate-limit capacity, and a production WSGI/ASGI server.

## Known limitations

- Daily logs represent the generated planning schedule and use explicit presentation-only off-duty coverage outside the scheduled trip. They are not certified driver logs.
- ELD export/PDF generation is not included because the core daily graph and integrity checks take priority.
- Public provider availability and coverage can vary. A provider timeout or malformed response is surfaced as a safe API error and no fake route is returned.
- The application is a planning/demo tool, not a certified legal ELD system. Real operations require complete duty history, jurisdiction-specific review, provider-quality controls, and qualified compliance interpretation.
