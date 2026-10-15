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
  allow_unverified_crossings?: boolean;
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
  target_excess_m?: number;
  verification_sections?: VerificationSection[];
  surfaces: string[];
}
export interface VerificationSection {
  id: string;
  kind: "road_crossing" | "indoor_passage" | "open_space" | "access_unknown";
  name: string;
  reason: string;
  distance_m: number;
  geometry: LineString;
  coordinate: [number, number];
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
export interface GradeRule {
  tier: "diamond" | "platinum" | "gold" | "silver" | "bronze" | "out_of_grade";
  label: string;
  cutoff_m: number | null;
  inclusive: boolean;
  range: string;
}
export interface PlannedGrade extends GradeRule {
  max_deviation_m: number;
}
export interface GradingScale {
  rules: GradeRule[];
  note: string;
}
export interface Analysis extends Preview {
  id: string;
  created_at: string;
  parameters: Parameters;
  status:
    | "mapped"
    | "uncertain"
    | "outside_corridor"
    | "no_route"
    | "insufficient_data";
  message: string;
  walking: Route | null;
  mission: Route | null;
  planned_grade?: PlannedGrade | null;
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
