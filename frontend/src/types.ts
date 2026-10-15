import type { FeatureCollection, LineString, Polygon } from "geojson";

export interface Coordinate {
  lat: number;
  lon: number;
}
export interface Parameters {
  start: Coordinate;
  end?: Coordinate | null;
  bearing?: number | null;
  distance_m?: number | null;
  max_deviation_m: number;
  strict: boolean;
}
export interface Preview {
  start: Coordinate;
  end: Coordinate;
  distance_m: number;
  initial_bearing: number;
  arrival_bearing: number;
  ideal: LineString;
  corridor: Polygon;
  max_deviation_m: number;
}
export interface Route {
  geometry: LineString;
  distance_m: number;
  extra_distance_m: number;
  max_deviation_m: number;
  average_deviation_m: number;
  within_percent: Record<string, number>;
  access: string;
  uncertain_distance_m: number;
  unverified_sections: number;
  corridor_compliant?: boolean;
  surfaces: string[];
}
export interface Obstacle {
  id: string;
  kind: string;
  name: string;
  position_m: number;
  crossing_extent_m: number;
  coordinate: [number, number];
  tags: Record<string, string>;
  confidence: string;
  crossing_infrastructure_nearby: boolean;
}
export interface Analysis extends Preview {
  id: string;
  created_at: string;
  parameters: Parameters;
  status: "mapped" | "uncertain" | "no_route" | "insufficient_data";
  message: string;
  walking: Route | null;
  mission: Route | null;
  minimum_corridor_m: number | null;
  warnings: string[];
  features: FeatureCollection;
  obstacles: Obstacle[];
  snapping?: {
    start: { distance_m: number; coordinate: [number, number] } | null;
    end: { distance_m: number; coordinate: [number, number] } | null;
  };
  terrain: { available: boolean; reason: string };
  data: {
    source: string;
    confidence: string;
    fetched_at: string | null;
    cached: boolean;
    network_edges?: number;
  };
  difficulty: { score: number; complete: boolean; explanation: string } | null;
}
export interface Place extends Coordinate {
  id: string;
  label: string;
}
export interface SavedMission {
  id: string;
  name: string;
  savedAt: string;
  parameters: Parameters;
}
export interface DiscoveryJob {
  id: string;
  status: "queued" | "running" | "complete" | "failed" | "cancelled";
  progress: number;
  evaluated: number;
  candidate_limit: number;
  results: Analysis[];
  message: string;
}
export type PickMode = "start" | "end" | "area" | null;
export type Layers = Record<
  | "ideal"
  | "walking"
  | "mission"
  | "corridor"
  | "buildings"
  | "water"
  | "barriers"
  | "landuse"
  | "pedestrian",
  boolean
>;
