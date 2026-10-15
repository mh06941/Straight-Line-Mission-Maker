import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import { Compass, Layers3, LocateFixed, MousePointer2, X } from "lucide-react";
import type {
  Analysis,
  Coordinate,
  Layers,
  PickMode,
  Place,
  Preview,
} from "../types";

interface Props {
  start: Coordinate | null;
  end: Coordinate | null;
  preview: Preview | null;
  analysis: Analysis | null;
  pick: PickMode;
  setPoint: (point: Coordinate, target: "start" | "end") => void;
  place: Place | null;
  layers: Layers;
  setLayers: (layers: Layers) => void;
  area: [Coordinate, Coordinate] | null;
  setArea: (area: [Coordinate, Coordinate]) => void;
  onObstacle: (id: string) => void;
  focus: Coordinate | null;
}
const empty: FeatureCollection = { type: "FeatureCollection", features: [] };
const labels: Record<keyof Layers, string> = {
  ideal: "Ideal geodesic",
  walking: "Walking route",
  mission: "Mission route",
  corridor: "Deviation corridor",
  pedestrian: "Mapped paths",
  buildings: "Buildings",
  water: "Waterways",
  barriers: "Barriers & restrictions",
  landuse: "Land use",
};

export default function MapView(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const current = useRef(props);
  current.current = props;
  const markers = useRef<maplibregl.Marker[]>([]);
  const firstCorner = useRef<Coordinate | null>(null);
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [showLayers, setShowLayers] = useState(false);
  const [areaStarted, setAreaStarted] = useState(false);
  useEffect(() => {
    if (!container.current) return;
    let instance: maplibregl.Map;
    try {
      instance = new maplibregl.Map({
        container: container.current,
        center: [0, 24],
        zoom: 2.2,
        maxZoom: 19,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              maxzoom: 19,
              attribution:
                '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>',
            },
          },
          layers: [
            {
              id: "background",
              type: "background",
              paint: { "background-color": "#e7ede8" },
            },
            {
              id: "base",
              type: "raster",
              source: "osm",
              paint: { "raster-saturation": -0.55, "raster-opacity": 0.85 },
            },
          ],
        },
      });
    } catch {
      setMapError(true);
      return;
    }
    map.current = instance;
    instance.addControl(
      new maplibregl.NavigationControl({ showCompass: true }),
      "bottom-right",
    );
    instance.addControl(
      new maplibregl.ScaleControl({ unit: "metric" }),
      "bottom-left",
    );
    instance.on("error", (event) => {
      if (event.error?.message?.includes("WebGL")) setMapError(true);
      else if (
        (event as typeof event & { sourceId?: string }).sourceId === "osm"
      )
        setTileError(true);
      else console.warn("Map overlay error:", event.error?.message);
    });
    instance.on("movestart", () => setTileError(false));
    instance.on("click", (event) => {
      const p = current.current;
      const point = {
        lat: event.lngLat.lat,
        lon: ((((event.lngLat.lng + 180) % 360) + 360) % 360) - 180,
      };
      if (p.pick === "area") {
        if (!firstCorner.current) {
          firstCorner.current = point;
          setAreaStarted(true);
        } else {
          p.setArea([firstCorner.current, point]);
          firstCorner.current = null;
          setAreaStarted(false);
        }
      } else if (p.pick) p.setPoint(point, p.pick);
      else if (instance.getLayer("obstacle-points")) {
        const found = instance.queryRenderedFeatures(event.point, {
          layers: ["obstacle-points"],
        });
        if (found[0]?.properties?.id)
          p.onObstacle(String(found[0].properties.id));
      }
    });
    instance.on("load", () => {
      for (const id of [
        "features",
        "corridor",
        "ideal",
        "walking",
        "mission",
        "obstacles",
        "area",
        "snapping",
      ])
        instance.addSource(id, { type: "geojson", data: empty });
      instance.addLayer({
        id: "feature-fill",
        type: "fill",
        source: "features",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "fill-color": [
            "match",
            ["get", "kind"],
            "water",
            "#80b7d5",
            "building",
            "#bba99a",
            "restricted",
            "#dca895",
            "#9abb8f",
          ],
          "fill-opacity": 0.38,
        },
      });
      instance.addLayer({
        id: "feature-line",
        type: "line",
        source: "features",
        filter: ["==", ["geometry-type"], "LineString"],
        paint: {
          "line-color": [
            "match",
            ["get", "kind"],
            "water",
            "#5292b4",
            "barrier",
            "#b97142",
            "restricted",
            "#c36855",
            "#b6b9af",
          ],
          "line-width": 1.5,
        },
      });
      instance.addLayer({
        id: "corridor",
        type: "fill",
        source: "corridor",
        paint: { "fill-color": "#df9d55", "fill-opacity": 0.19 },
      });
      instance.addLayer({
        id: "area-fill",
        type: "fill",
        source: "area",
        paint: { "fill-color": "#387b6b", "fill-opacity": 0.12 },
      });
      instance.addLayer({
        id: "area-line",
        type: "line",
        source: "area",
        paint: {
          "line-color": "#387b6b",
          "line-width": 2,
          "line-dasharray": [3, 2],
        },
      });
      for (const [id, color, width, dash] of [
        ["walking", "#4975ce", 4, false],
        ["mission", "#208264", 5, false],
        ["ideal", "#d15a4e", 2.5, true],
      ] as const) {
        instance.addLayer({
          id: `${id}-halo`,
          type: "line",
          source: id,
          paint: {
            "line-color": "#ffffff",
            "line-width": width + 3,
            "line-opacity": 0.8,
          },
        });
        instance.addLayer({
          id,
          type: "line",
          source: id,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": color,
            "line-width": width,
            ...(dash ? { "line-dasharray": [3, 2] } : {}),
          },
        });
      }
      instance.addLayer({
        id: "snap-links",
        type: "line",
        source: "snapping",
        paint: {
          "line-color": "#74776d",
          "line-width": 2,
          "line-dasharray": [2, 2],
        },
      });
      instance.addLayer({
        id: "obstacle-points",
        type: "circle",
        source: "obstacles",
        paint: {
          "circle-color": "#b57435",
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
        },
      });
      setReady(true);
    });
    const resize = new ResizeObserver(() => instance.resize());
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !map.current) return;
    const instance = map.current;
    const set = (
      id: string,
      data: Geometry | FeatureCollection<Geometry, GeoJsonProperties> | null,
    ) =>
      (instance.getSource(id) as maplibregl.GeoJSONSource).setData(
        data || empty,
      );
    set("features", props.analysis?.features || empty);
    set("corridor", props.preview?.corridor || null);
    set("ideal", props.preview?.ideal || null);
    set("walking", props.analysis?.walking?.geometry || null);
    set("mission", props.analysis?.mission?.geometry || null);
    set("obstacles", {
      type: "FeatureCollection",
      features: (props.analysis?.obstacles || []).map((o) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: o.coordinate },
        properties: { id: o.id },
      })),
    });
    set("snapping", {
      type: "FeatureCollection",
      features: (["start", "end"] as const).flatMap((key) => {
        const snap = props.analysis?.snapping?.[key],
          endpoint = props.preview?.[key];
        return snap && endpoint && snap.distance_m > 1
          ? [
              {
                type: "Feature" as const,
                properties: {},
                geometry: {
                  type: "LineString" as const,
                  coordinates: [[endpoint.lon, endpoint.lat], snap.coordinate],
                },
              },
            ]
          : [];
      }),
    });
    for (const id of ["ideal", "walking", "mission", "corridor"] as const) {
      instance.setLayoutProperty(
        id,
        "visibility",
        props.layers[id] ? "visible" : "none",
      );
      if (id !== "corridor")
        instance.setLayoutProperty(
          `${id}-halo`,
          "visibility",
          props.layers[id] ? "visible" : "none",
        );
    }
    const featureKinds = [
      "buildings",
      "water",
      "barriers",
      "landuse",
      "pedestrian",
    ]
      .filter((k) => props.layers[k as keyof Layers])
      .flatMap((k) =>
        k === "buildings"
          ? ["building"]
          : k === "barriers"
            ? ["barrier", "restricted", "road", "railway"]
            : [k],
      );
    instance.setFilter("feature-fill", [
      "all",
      ["==", ["geometry-type"], "Polygon"],
      ["in", ["get", "kind"], ["literal", featureKinds]],
    ]);
    instance.setFilter("feature-line", [
      "all",
      ["==", ["geometry-type"], "LineString"],
      ["in", ["get", "kind"], ["literal", featureKinds]],
    ]);
  }, [ready, props.preview, props.analysis, props.layers]);

  useEffect(() => {
    if (!map.current || !ready) return;
    markers.current.forEach((m) => m.remove());
    markers.current = [];
    for (const [coord, target, label] of [
      [props.start, "start", "A"],
      [props.end || props.preview?.end, "end", "B"],
    ] as const) {
      if (!coord) continue;
      const el = document.createElement("button");
      el.className = `map-pin ${target}`;
      el.textContent = label;
      el.setAttribute("aria-label", `Drag ${target} point`);
      const marker = new maplibregl.Marker({ element: el, draggable: true })
        .setLngLat([coord.lon, coord.lat])
        .addTo(map.current);
      marker.on("dragend", () => {
        const p = marker.getLngLat();
        current.current.setPoint(
          { lat: p.lat, lon: ((((p.lng + 180) % 360) + 360) % 360) - 180 },
          target,
        );
      });
      markers.current.push(marker);
    }
  }, [ready, props.start, props.end, props.preview?.end]);

  useEffect(() => {
    if (props.place && map.current)
      map.current.flyTo({
        center: [props.place.lon, props.place.lat],
        zoom: 13,
        duration: 1000,
      });
  }, [props.place]);
  useEffect(() => {
    if (props.focus && map.current)
      map.current.flyTo({
        center: [props.focus.lon, props.focus.lat],
        zoom: Math.max(15, map.current.getZoom()),
      });
  }, [props.focus]);
  useEffect(() => {
    if (!props.preview || !ready || !map.current) return;
    const bounds = new maplibregl.LngLatBounds();
    props.preview.ideal.coordinates.forEach((p) => bounds.extend([p[0], p[1]]));
    map.current.fitBounds(bounds, { padding: 90, maxZoom: 16, duration: 700 });
    // Only refit when mission endpoints change, not on every corridor adjustment.
  }, [
    ready,
    props.preview?.start.lat,
    props.preview?.start.lon,
    props.preview?.end.lat,
    props.preview?.end.lon,
  ]);
  useEffect(() => {
    if (!map.current || !ready) return;
    if (!props.area) {
      (map.current.getSource("area") as maplibregl.GeoJSONSource).setData(
        empty,
      );
      return;
    }
    const [a, b] = props.area;
    const otherLon = a.lon + (((b.lon - a.lon + 540) % 360) - 180);
    (map.current.getSource("area") as maplibregl.GeoJSONSource).setData({
      type: "Polygon",
      coordinates: [
        [
          [a.lon, a.lat],
          [otherLon, a.lat],
          [otherLon, b.lat],
          [a.lon, b.lat],
          [a.lon, a.lat],
        ],
      ],
    });
  }, [props.area, ready]);
  useEffect(() => {
    if (props.pick !== "area") {
      firstCorner.current = null;
      setAreaStarted(false);
    }
  }, [props.pick]);

  return (
    <div className={`map-wrap ${props.pick ? "picking" : ""}`}>
      <div
        ref={container}
        className="map-canvas"
        data-testid="map"
        aria-label="Interactive world map"
      />
      <div className="map-topline">
        <span>
          <span className="live-dot" /> THE WORLD IS YOUR STARTING POINT
        </span>
        <span className="map-projection">WGS84 · Global coverage</span>
      </div>
      {mapError && (
        <div className="map-message error" role="alert">
          This browser could not initialize WebGL. Use a WebGL-enabled browser.
          Coordinate planning and exports remain available.
        </div>
      )}
      {tileError && !mapError && (
        <div className="tile-notice" role="status">
          Some base map tiles could not load. Check access to
          tile.openstreetmap.org.
        </div>
      )}
      {props.pick && (
        <div className="pick-hint">
          <MousePointer2 size={15} />{" "}
          {props.pick === "area"
            ? areaStarted
              ? "Click the opposite corner"
              : "Click the first corner of your search area"
            : `Click the map to place your ${props.pick === "start" ? "start" : "finish"}`}
        </div>
      )}
      <div className="map-tools">
        <button
          className={showLayers ? "map-tool active" : "map-tool"}
          onClick={() => setShowLayers(!showLayers)}
          aria-label="Map layers"
          aria-expanded={showLayers}
        >
          <Layers3 size={19} />
        </button>
        <button
          className="map-tool"
          aria-label="Return to world view"
          onClick={() => map.current?.flyTo({ center: [0, 24], zoom: 2.2 })}
        >
          <Compass size={19} />
        </button>
        <button
          className="map-tool"
          aria-label="Fit mission to map"
          disabled={!props.preview}
          onClick={() => {
            if (props.preview && map.current) {
              const b = new maplibregl.LngLatBounds();
              props.preview.ideal.coordinates.forEach((p) =>
                b.extend([p[0], p[1]]),
              );
              map.current.fitBounds(b, { padding: 80 });
            }
          }}
        >
          <LocateFixed size={19} />
        </button>
      </div>
      {showLayers && (
        <div className="layers-popover">
          <div className="popover-heading">
            Map layers
            <button
              className="icon-button"
              aria-label="Close map layers"
              onClick={() => setShowLayers(false)}
            >
              <X size={16} />
            </button>
          </div>
          {Object.entries(labels).map(([key, label]) => (
            <label className="layer-choice" key={key}>
              <input
                type="checkbox"
                checked={props.layers[key as keyof Layers]}
                onChange={(e) =>
                  props.setLayers({ ...props.layers, [key]: e.target.checked })
                }
              />
              <span className={`layer-dot ${key}`} />
              {label}
            </label>
          ))}
          <p>
            Feature layers appear after OSM analysis. Terrain and satellite
            layers are not configured.
          </p>
        </div>
      )}
      <div className="map-legend">
        <span>
          <i className="ideal" />
          Ideal line
        </span>
        <span>
          <i className="walking" />
          Walking
        </span>
        <span>
          <i className="mission" />
          Mission
        </span>
        <span className="legend-corridor">± corridor</span>
      </div>
    </div>
  );
}
