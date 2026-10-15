import type { Coordinate, Parameters, SavedMission } from "../types";

export function parseCoordinate(text: string): Coordinate | null {
  const match = text
    .trim()
    .match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
  if (!match) return null;
  const lat = Number(match[1]),
    lon = Number(match[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
}

export function distance(meters: number, imperial = false) {
  if (imperial)
    return meters >= 1609.19
      ? `${(meters / 1609.344).toFixed(2)} mi`
      : `${Math.round(meters * 3.28084)} ft`;
  return Math.round(meters) >= 1000
    ? `${(meters / 1000).toFixed(2)} km`
    : `${Math.round(meters)} m`;
}

export function coordinateLabel(coord: Coordinate | null) {
  return coord ? `${coord.lat.toFixed(5)}, ${coord.lon.toFixed(5)}` : "";
}

export function shareURL(parameters: Parameters) {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("mission", JSON.stringify(parameters));
  return url.toString();
}

export function readShared(): Parameters | null {
  try {
    const value = new URLSearchParams(window.location.search).get("mission");
    if (!value || value.length > 2000) return null;
    const p = JSON.parse(value) as Parameters;
    const valid = (c: Coordinate) =>
      c &&
      Number.isFinite(c.lat) &&
      Number.isFinite(c.lon) &&
      Math.abs(c.lat) <= 90 &&
      Math.abs(c.lon) <= 180;
    if (!valid(p.start) || (p.end && !valid(p.end))) return null;
    if (
      !p.end &&
      !(Number.isFinite(p.bearing) && Number.isFinite(p.distance_m))
    )
      return null;
    if (!(p.max_deviation_m >= 1 && p.max_deviation_m <= 2000)) return null;
    return p;
  } catch {
    return null;
  }
}

const SAVED_KEY = "straightline.missions.v1";
export function loadSaved(): SavedMission[] {
  try {
    const list = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
    return Array.isArray(list)
      ? list
          .filter((m) => m && typeof m.name === "string" && m.parameters?.start)
          .slice(0, 50)
      : [];
  } catch {
    return [];
  }
}
export function persistSaved(missions: SavedMission[]) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(missions));
}
