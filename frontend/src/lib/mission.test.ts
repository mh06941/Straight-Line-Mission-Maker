import { afterEach, describe, expect, it } from "vitest";
import {
  distance,
  loadSaved,
  parseCoordinate,
  persistSaved,
  readShared,
  shareURL,
} from "./mission";
import type { Parameters } from "../types";

const parameters: Parameters = {
  start: { lat: 85, lon: 179.9 },
  bearing: 90,
  distance_m: 2000,
  max_deviation_m: 50,
  strict: true,
};
afterEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("mission parameters and units", () => {
  it("accepts global coordinates and rejects ambiguous or invalid inputs", () => {
    expect(parseCoordinate(" -85, 179.9 ")).toEqual({ lat: -85, lon: 179.9 });
    expect(parseCoordinate("91, 20")).toBeNull();
    expect(parseCoordinate("20, 181")).toBeNull();
    expect(parseCoordinate("London")).toBeNull();
  });
  it("converts canonical metres to imperial display", () => {
    expect(distance(1609.344, true)).toBe("1.00 mi");
    expect(distance(25, true)).toBe("82 ft");
    expect(distance(2000)).toBe("2.00 km");
    expect(distance(999.999999)).toBe("1.00 km");
  });
  it("round trips share parameters without needing server state", () => {
    const url = shareURL(parameters);
    window.history.replaceState({}, "", new URL(url).search);
    expect(readShared()).toEqual(parameters);
  });
  it("rejects malformed shared missions", () => {
    window.history.replaceState({}, "", "?mission=%7Bbad");
    expect(readShared()).toBeNull();
  });
  it("stores mission parameters and tolerates corrupt browser data", () => {
    const record = {
      id: "1",
      name: "Polar walk",
      parameters,
      savedAt: new Date().toISOString(),
    };
    persistSaved([record]);
    expect(loadSaved()).toEqual([record]);
    localStorage.setItem("straightline.missions.v1", "{broken");
    expect(loadSaved()).toEqual([]);
  });
});
