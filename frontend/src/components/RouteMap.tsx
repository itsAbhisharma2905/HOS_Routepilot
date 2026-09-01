import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import type { EventLocation, TripEvent, TripPlanResult } from "../types/trip";
import { locationLabel } from "../utils/format";
import { StopDetails } from "./StopDetails";

interface RouteMapProps {
  result: TripPlanResult;
}

type MarkerKind = "origin" | "pickup" | "dropoff" | "fuel" | "break" | "rest" | "restart";
type MapPosition = [number, number];

interface MapMarker {
  id: string;
  kind: MarkerKind;
  label: string;
  position: MapPosition;
  event?: TripEvent;
  location: EventLocation;
}

const markerSymbols: Record<MarkerKind, string> = {
  origin: "O",
  pickup: "P",
  dropoff: "D",
  fuel: "F",
  break: "B",
  rest: "R",
  restart: "34",
};

function isPosition(value: unknown): value is MapPosition {
  return Array.isArray(value) && value.length >= 2 && value.every((part) => typeof part === "number" && Number.isFinite(part));
}

function eventPosition(location: EventLocation | null | undefined): MapPosition | null {
  if (!location) return null;
  if (typeof location.latitude !== "number" || typeof location.longitude !== "number") return null;
  if (!Number.isFinite(location.latitude) || !Number.isFinite(location.longitude)) return null;
  return [location.latitude, location.longitude];
}

function eventKind(event: TripEvent): MarkerKind | null {
  if (event.reason === "Fuel") return "fuel";
  if (event.reason === "Required 30-minute break") return "break";
  if (event.reason === "Required 10-hour rest (daily reset)") return "rest";
  if (event.reason === "34-hour cycle restart") return "restart";
  return null;
}

function createMarkerIcon(kind: MarkerKind): L.DivIcon {
  return L.divIcon({
    className: `route-marker route-marker-${kind}`,
    html: `<span>${markerSymbols[kind]}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -18],
  });
}

function FitRouteBounds({ positions }: { positions: MapPosition[] }) {
  const map = useMap();

  useEffect(() => {
    if (positions.length < 2) return;
    map.fitBounds(L.latLngBounds(positions), { padding: [28, 28], maxZoom: 11 });
  }, [map, positions]);

  return null;
}

function CurrentPopup({ marker }: { marker: MapMarker }) {
  const routeLabel = "type" in marker.location && marker.location.type === "route_position" ? marker.location.label : null;

  return (
    <div className="map-popup map-current-popup">
      <span className="map-popup-kicker">Current location</span>
      <strong>{locationLabel(marker.location)}</strong>
      <p>{routeLabel ?? "Trip starting point"}</p>
    </div>
  );
}

function markerPopup(marker: MapMarker) {
  if (marker.event) return <StopDetails stop={marker.event} compact />;
  return <CurrentPopup marker={marker} />;
}

export function RouteMap({ result }: RouteMapProps) {
  const positions = useMemo<MapPosition[]>(() => {
    const coordinates = result.route.geometry?.coordinates ?? [];
    return coordinates
      .filter((coordinate): coordinate is [number, number] => isPosition(coordinate))
      .map(([longitude, latitude]) => [latitude, longitude]);
  }, [result.route.geometry]);

  const markers = useMemo<MapMarker[]>(() => {
    const waypointMarkers: MapMarker[] = [];
    const waypointData: Array<{ kind: MarkerKind; label: string; location: EventLocation; event?: TripEvent }> = [
      { kind: "origin", label: "Current", location: result.locations.current },
      { kind: "pickup", label: "Pickup", location: result.locations.pickup, event: result.events.find((event) => event.reason === "Pickup") },
      { kind: "dropoff", label: "Dropoff", location: result.locations.dropoff, event: result.events.find((event) => event.reason === "Dropoff") },
    ];

    waypointData.forEach((item) => {
      const position = eventPosition(item.event?.location) ?? eventPosition(item.location);
      if (position) waypointMarkers.push({ ...item, id: item.kind, position });
    });

    result.stops.forEach((stop) => {
      const kind = eventKind(stop);
      if (!kind) return;
      const position = eventPosition(stop.location);
      if (position) waypointMarkers.push({ id: stop.id, kind, label: stop.reason, position, event: stop, location: stop.location });
    });

    return waypointMarkers;
  }, [result.events, result.locations, result.stops]);

  const icons = useMemo(() => {
    const kinds: MarkerKind[] = ["origin", "pickup", "dropoff", "fuel", "break", "rest", "restart"];
    return Object.fromEntries(kinds.map((kind) => [kind, createMarkerIcon(kind)])) as Record<MarkerKind, L.DivIcon>;
  }, []);

  if (positions.length < 2) {
    return (
      <div className="map-empty" role="status">
        <div className="map-empty-icon" aria-hidden="true">⌁</div>
        <strong>Route geometry unavailable</strong>
        <p>The backend returned no drawable route line for this plan.</p>
      </div>
    );
  }

  return (
    <div className="map-frame" aria-label="Interactive route map">
      <MapContainer className="route-map" center={positions[0]} zoom={6} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitRouteBounds positions={positions} />
        <Polyline positions={positions} pathOptions={{ color: "#1e6b5a", weight: 5, opacity: 0.9 }} />
        {markers.map((marker) => (
          <Marker key={marker.id} position={marker.position} icon={icons[marker.kind]}>
            <Popup>{markerPopup(marker)}</Popup>
          </Marker>
        ))}
      </MapContainer>
      <div className="map-legend" aria-label="Map marker legend">
        <span><i className="legend-line" /> Route</span>
        <span><i className="legend-dot origin" /> Current</span>
        <span><i className="legend-dot pickup" /> Pickup</span>
        <span><i className="legend-dot dropoff" /> Dropoff</span>
        <span><i className="legend-dot fuel" /> HOS stops</span>
      </div>
    </div>
  );
}
