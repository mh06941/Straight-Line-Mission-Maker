import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronDown,
  ChevronLeft,
  Compass,
  Crosshair,
  Flag,
  Globe2,
  HelpCircle,
  Info,
  Layers3,
  LoaderCircle,
  Map as MapIcon,
  MapPin,
  Mountain,
  MoveUpRight,
  Navigation2,
  Plus,
  Route as RouteIcon,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import MapView from "./components/Map";
import Search from "./components/Search";
import Statistics from "./components/Statistics";
import { GradeBadge, GradeScale } from "./components/Grading";
import { api } from "./lib/api";
import { downloadPreview } from "./lib/export";
import { messages as copy } from "./i18n/en";
import {
  coordinateLabel,
  distance,
  loadSaved,
  parseCoordinate,
  persistSaved,
  readShared,
  shareURL,
} from "./lib/mission";
import type {
  Analysis,
  Coordinate,
  DiscoveryJob,
  Layers,
  Obstacle,
  Parameters,
  PickMode,
  Place,
  Preview,
  SavedMission,
} from "./types";

type Section = "explore" | "plan" | "discover" | "saved";
const initial = readShared();
const initialLayers: Layers = {
  ideal: true,
  walking: true,
  mission: true,
  corridor: true,
  buildings: true,
  water: true,
  barriers: true,
  landuse: false,
  pedestrian: false,
};

function CoordinateField({
  label,
  point,
  target,
  picking,
  onPick,
  onChange,
}: {
  label: string;
  point: Coordinate | null;
  target: "start" | "end";
  picking: boolean;
  onPick: () => void;
  onChange: (c: Coordinate) => void;
}) {
  const [value, setValue] = useState(coordinateLabel(point));
  const [error, setError] = useState(false);
  useEffect(() => {
    setValue(coordinateLabel(point));
    setError(false);
  }, [point]);
  const commit = () => {
    if (!value.trim()) return;
    const c = parseCoordinate(value);
    setError(!c);
    if (c && coordinateLabel(c) !== coordinateLabel(point)) onChange(c);
  };
  return (
    <div className={`coordinate-field ${picking ? "selected" : ""}`}>
      <div className={`point-badge ${target}`}>
        {target === "start" ? "A" : "B"}
      </div>
      <label>
        <span>{label}</span>
        <input
          aria-label={`${label} coordinates`}
          value={value}
          placeholder="Select on map or enter lat, lon"
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }
          }}
          aria-invalid={error}
        />
      </label>
      <button
        className="icon-button"
        title={`Select ${target} on map`}
        aria-label={`Select ${target} on map`}
        aria-pressed={picking}
        onClick={onPick}
      >
        <Crosshair size={18} />
      </button>
      {error && (
        <small className="field-error">
          Use latitude, longitude (−90…90, −180…180).
        </small>
      )}
    </div>
  );
}

export default function App() {
  const [section, setSection] = useState<Section>(initial ? "plan" : "explore");
  const [start, setStart] = useState<Coordinate | null>(initial?.start || null);
  const [end, setEnd] = useState<Coordinate | null>(initial?.end || null);
  const [method, setMethod] = useState<"points" | "bearing">(
    initial?.end || !initial ? "points" : "bearing",
  );
  const [bearing, setBearing] = useState(initial?.bearing ?? 90);
  const [length, setLength] = useState(initial?.distance_m ?? 2000);
  const [width, setWidth] = useState(initial?.max_deviation_m ?? 50);
  const [strict, setStrict] = useState(initial?.strict ?? true);
  const [imperial, setImperial] = useState(false);
  const [pick, setPick] = useState<PickMode>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [focus, setFocus] = useState<Coordinate | null>(null);
  const [layers, setLayers] = useState(initialLayers);
  const [collapsed, setCollapsed] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState(loadSaved);
  const [saveOpen, setSaveOpen] = useState(false);
  const [missionName, setMissionName] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [obstacle, setObstacle] = useState<Obstacle | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<
    "gpx" | "geojson" | "summary"
  >("gpx");
  const [exportRoute, setExportRoute] = useState<
    "ideal" | "walking" | "mission"
  >("ideal");
  const [area, setArea] = useState<[Coordinate, Coordinate] | null>(null);
  const [minDiscovery, setMinDiscovery] = useState(1000);
  const [maxDiscovery, setMaxDiscovery] = useState(3000);
  const [terrain, setTerrain] = useState("any");
  const [jobId, setJobId] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const params = useMemo<Parameters | null>(
    () =>
      start &&
      (method === "points" ? end : Number.isFinite(bearing) && length >= 10)
        ? {
            start,
            ...(method === "points"
              ? { end }
              : { bearing, distance_m: length }),
            max_deviation_m: width,
            strict,
          }
        : null,
    [start, end, method, bearing, length, width, strict],
  );
  const paramsKey = JSON.stringify(params);
  const currentKey = useRef(paramsKey);
  currentKey.current = paramsKey;
  const previewQuery = useQuery({
    queryKey: ["preview", params],
    queryFn: ({ signal }) => api<Preview>("/missions/preview", params, signal),
    enabled: !!params,
    staleTime: Infinity,
  });
  const preview = previewQuery.data || null;
  const analyseMutation = useMutation({
    mutationFn: ({
      parameters,
      signal,
    }: {
      parameters: Parameters;
      signal: AbortSignal;
    }) => api<Analysis>("/missions/analyse", parameters, signal),
  });
  const discoverMutation = useMutation({
    mutationFn: (body: unknown) => api<DiscoveryJob>("/discovery/start", body),
  });
  const job = useQuery({
    queryKey: ["discovery", jobId],
    queryFn: () => api<DiscoveryJob>(`/discovery/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) =>
      ["complete", "failed", "cancelled"].includes(q.state.data?.status || "")
        ? false
        : 1000,
  });
  const discoveryRunning =
    !!jobId &&
    !["complete", "failed", "cancelled"].includes(job.data?.status || "");

  function changed() {
    abort.current?.abort();
    setAnalysis(null);
    setError("");
    setExportRoute("ideal");
  }
  function setPoint(point: Coordinate, target: "start" | "end") {
    changed();
    setSection("plan");
    setCollapsed(false);
    if (target === "start") {
      setStart(point);
      setPick(method === "points" && !end ? "end" : null);
    } else {
      setEnd(point);
      setMethod("points");
      setPick(null);
    }
  }
  function applyParameters(p: Parameters) {
    changed();
    setStart(p.start);
    setEnd(p.end || null);
    setMethod(p.end ? "points" : "bearing");
    setBearing(p.bearing ?? 90);
    setLength(p.distance_m ?? 2000);
    setWidth(p.max_deviation_m);
    setStrict(p.strict);
    setSection("plan");
    setPick(null);
    setCollapsed(false);
  }
  async function runAnalysis() {
    if (!params) return;
    setError("");
    const key = paramsKey;
    abort.current = new AbortController();
    try {
      const result = await analyseMutation.mutateAsync({
        parameters: params,
        signal: abort.current.signal,
      });
      if (currentKey.current === key) setAnalysis(result);
    } catch (e) {
      if (
        e instanceof Error &&
        e.name !== "AbortError" &&
        currentKey.current === key
      )
        setError(e.message);
    }
  }
  function selectObstacle(o: Obstacle) {
    setObstacle(o);
    setFocus({ lon: o.coordinate[0], lat: o.coordinate[1] });
  }
  function saveMission() {
    if (!params) return;
    const next: SavedMission[] = [
      {
        id: crypto.randomUUID(),
        name: missionName.trim() || "Untitled mission",
        parameters: params,
        savedAt: new Date().toISOString(),
      },
      ...saved,
    ].slice(0, 50);
    try {
      persistSaved(next);
      setSaved(next);
      setSaveOpen(false);
      setNotice("Mission saved on this device.");
    } catch {
      setError(
        "Browser storage is unavailable or full. Export or share the mission instead.",
      );
      setSaveOpen(false);
    }
  }
  async function startDiscovery() {
    if (!area) return;
    const [a, b] = area;
    const delta = ((b.lon - a.lon + 540) % 360) - 180;
    const west = delta >= 0 ? a.lon : b.lon,
      east = delta >= 0 ? b.lon : a.lon;
    setError("");
    try {
      const next = await discoverMutation.mutateAsync({
        west,
        east,
        south: Math.min(a.lat, b.lat),
        north: Math.max(a.lat, b.lat),
        min_length_m: minDiscovery,
        max_length_m: maxDiscovery,
        max_deviation_m: width,
        strict,
        max_results: 5,
        terrain,
      });
      setJobId(next.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(id);
  }, [notice]);
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPick(null);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  useEffect(() => () => abort.current?.abort(), []);

  const corridorControls = (
    <>
      <div className="section-heading">
        <span>Deviation corridor</span>
        <span className="micro-label">EACH SIDE OF THE LINE</span>
      </div>
      <div className="corridor-options">
        {[10, 25, 50, 75, 100, 250].map((n) => (
          <button
            key={n}
            className={width === n ? "selected" : ""}
            onClick={() => {
              changed();
              setWidth(n);
            }}
          >
            {imperial ? `${Math.round(n * 3.28084)} ft` : `${n} m`}
          </button>
        ))}
      </div>
      <label className="custom-width">
        <span>Custom maximum</span>
        <input
          aria-label="Custom deviation in metres"
          type="number"
          min={1}
          max={2000}
          value={width}
          onChange={(e) => {
            changed();
            setWidth(Math.max(1, Math.min(2000, Number(e.target.value))));
          }}
        />
        <span>m</span>
      </label>
      <p className="field-hint">
        A {distance(width * 2, imperial)} wide corridor. Routes must stay within{" "}
        {distance(width, imperial)} on either side.
      </p>
    </>
  );
  const accessControl = (
    <label className="access-toggle">
      <span>
        <ShieldCheck size={18} />
        <span>
          <strong>Mapped paths only</strong>
          <small>
            {strict
              ? "Supporting pedestrian-access evidence required"
              : "Allow uncertain ways and public-space links"}
          </small>
        </span>
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={strict}
        onChange={(e) => {
          changed();
          setStrict(e.target.checked);
        }}
      />
      <span className="switch-track" />
    </label>
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="brand"
          onClick={() => {
            setSection("explore");
            setCollapsed(false);
          }}
          aria-label="StraightLine home"
        >
          <span className="brand-mark">
            <MoveUpRight size={25} />
          </span>
          <span>
            Straight<span className="brand-light">Line</span>
            <small>{copy.tagline}</small>
          </span>
        </button>
        <nav aria-label="Main navigation">
          {(
            [
              { key: "explore", name: "Explore", Icon: Globe2 },
              { key: "plan", name: "Plan a mission", Icon: RouteIcon },
              { key: "discover", name: "Discover", Icon: Sparkles },
              { key: "saved", name: "Saved", Icon: Bookmark },
            ] as const
          ).map(({ key, name, Icon }) => (
            <button
              key={key}
              className={section === key ? "nav-item active" : "nav-item"}
              onClick={() => {
                setSection(key);
                setCollapsed(false);
                setPick(null);
                setError("");
              }}
            >
              <Icon size={17} />
              <span>{name}</span>
              {key === "saved" && saved.length > 0 && (
                <small>{saved.length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="header-actions">
          <button
            className="unit-button"
            onClick={() => setImperial(!imperial)}
            aria-label={`Units: ${imperial ? "imperial" : "metric"}. Switch units.`}
          >
            {imperial ? "MI / FT" : "KM / M"}
            <ChevronDown size={12} />
          </button>
          <button
            className="help-button"
            aria-label="How it works"
            onClick={() => setHelpOpen(true)}
          >
            <HelpCircle size={18} />
            <span>How it works</span>
          </button>
        </div>
      </header>
      <div className="workspace">
        <aside
          className={`sidebar ${collapsed ? "collapsed" : ""}`}
          aria-label="Mission planning sidebar"
        >
          <button
            className="collapse-button"
            aria-label={
              collapsed ? "Open planning panel" : "Collapse planning panel"
            }
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <SlidersHorizontal size={18} />
            ) : (
              <ChevronLeft size={18} />
            )}
          </button>
          <div className="sidebar-inner">
            <div className="sidebar-scroll">
              {section === "explore" && (
                <>
                  <div className="eyebrow">
                    <span /> GO A LITTLE OFF SCRIPT
                  </div>
                  <h1>
                    {copy.title.split("\n").map((s, i) => (
                      <span key={s}>
                        {s}
                        {i === 0 && <br />}
                      </span>
                    ))}
                  </h1>
                  <p className="intro">{copy.intro}</p>
                  <div className="explore-art" aria-hidden="true">
                    <div className="contour c1" />
                    <div className="contour c2" />
                    <div className="contour c3" />
                    <div className="contour c4" />
                    <div className="art-line" />
                    <span className="art-a">A</span>
                    <span className="art-b">B</span>
                    <span className="art-label">
                      LESS DETOUR. MORE DISCOVERY.
                    </span>
                    <Mountain size={36} />
                  </div>
                  <button
                    className="primary-button"
                    onClick={() => {
                      setSection("plan");
                      setPick(start ? "end" : "start");
                    }}
                  >
                    Create your first line
                    <ArrowUpRight size={18} />
                  </button>
                  <div className="explore-features">
                    <div>
                      <Globe2 size={19} />
                      <span>
                        <strong>No borders to your curiosity</strong>
                        <p>Plan anywhere, with accurate WGS84 geodesics.</p>
                      </span>
                    </div>
                    <div>
                      <RouteIcon size={19} />
                      <span>
                        <strong>The straightest available way</strong>
                        <p>Compare walking and minimum-deviation routes.</p>
                      </span>
                    </div>
                    <div>
                      <ShieldCheck size={19} />
                      <span>
                        <strong>Know what’s known</strong>
                        <p>Real mapped features. Clearly stated uncertainty.</p>
                      </span>
                    </div>
                  </div>
                  <div className="try-place">
                    <small>A PLACE TO START</small>
                    <div>
                      {[
                        { name: "London", lat: 51.5074, lon: -0.1278 },
                        { name: "Chamonix", lat: 45.9237, lon: 6.8694 },
                        { name: "Kyoto", lat: 35.0116, lon: 135.7681 },
                      ].map((p) => (
                        <button
                          key={p.name}
                          onClick={() =>
                            setPlace({ ...p, id: p.name, label: p.name })
                          }
                        >
                          <MapPin size={12} />
                          {p.name}
                          <ArrowUpRight size={12} />
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {section === "plan" && (
                <>
                  <div className="panel-title">
                    <div>
                      <div className="eyebrow">YOUR NEXT ADVENTURE</div>
                      <h1>
                        Plan a mission<span className="title-dot">.</span>
                      </h1>
                    </div>
                    <button
                      className="icon-button"
                      aria-label="New mission"
                      onClick={() => {
                        changed();
                        setStart(null);
                        setEnd(null);
                        setPick("start");
                      }}
                    >
                      <Plus size={21} />
                    </button>
                  </div>
                  <p className="intro compact">
                    Two points. One line. A different way to explore.
                  </p>
                  <div
                    className="method-tabs"
                    role="tablist"
                    aria-label="Planning method"
                  >
                    <button
                      role="tab"
                      aria-selected={method === "points"}
                      onClick={() => {
                        changed();
                        setMethod("points");
                      }}
                    >
                      <MapPin size={15} /> Start & finish
                    </button>
                    <button
                      role="tab"
                      aria-selected={method === "bearing"}
                      onClick={() => {
                        changed();
                        setMethod("bearing");
                      }}
                    >
                      <Navigation2 size={15} /> Bearing & distance
                    </button>
                  </div>
                  <div className="points-stack">
                    <CoordinateField
                      label="Start point"
                      target="start"
                      point={start}
                      picking={pick === "start"}
                      onPick={() => setPick(pick === "start" ? null : "start")}
                      onChange={(c) => setPoint(c, "start")}
                    />
                    {method === "points" ? (
                      <CoordinateField
                        label="Finish point"
                        target="end"
                        point={end}
                        picking={pick === "end"}
                        onPick={() => setPick(pick === "end" ? null : "end")}
                        onChange={(c) => setPoint(c, "end")}
                      />
                    ) : (
                      <div className="bearing-fields">
                        <label>
                          Compass bearing
                          <div>
                            <input
                              aria-label="Compass bearing"
                              type="number"
                              min={0}
                              max={359.99}
                              value={bearing}
                              onChange={(e) => {
                                changed();
                                setBearing(Number(e.target.value));
                              }}
                            />
                            <span>°</span>
                          </div>
                        </label>
                        <label>
                          Mission distance
                          <div>
                            <input
                              aria-label="Mission distance"
                              type="number"
                              min={imperial ? 0.0063 : 0.01}
                              max={imperial ? 15.53 : 25}
                              step="0.1"
                              value={Number(
                                (length / (imperial ? 1609.344 : 1000)).toFixed(
                                  3,
                                ),
                              )}
                              onChange={(e) => {
                                changed();
                                setLength(
                                  Number(e.target.value) *
                                    (imperial ? 1609.344 : 1000),
                                );
                              }}
                            />
                            <span>{imperial ? "mi" : "km"}</span>
                          </div>
                        </label>
                      </div>
                    )}
                  </div>
                  <p className="field-hint">
                    <MapIcon size={12} /> Click the crosshair, then the map.
                    Drag markers to adjust.
                  </p>
                  {preview && (
                    <div className="preview-stats">
                      <span>
                        <small>IDEAL DISTANCE</small>
                        <strong>
                          {distance(preview.distance_m, imperial)}
                        </strong>
                      </span>
                      <span>
                        <small>INITIAL BEARING</small>
                        <strong>
                          {preview.initial_bearing.toFixed(1)}
                          <em>°</em>
                        </strong>
                      </span>
                      <span>
                        <small>ARRIVAL BEARING</small>
                        <strong>
                          {preview.arrival_bearing.toFixed(1)}
                          <em>°</em>
                        </strong>
                      </span>
                    </div>
                  )}
                  {previewQuery.error && (
                    <p className="error-note" role="alert">
                      {previewQuery.error.message}
                    </p>
                  )}
                  <div className="section-divider" />
                  {corridorControls}
                  <div className="section-divider" />
                  {accessControl}
                  <button
                    className="primary-button analyse-button"
                    disabled={!preview || analyseMutation.isPending}
                    onClick={runAnalysis}
                  >
                    {analyseMutation.isPending ? (
                      <>
                        <LoaderCircle size={18} className="spin" />
                        Reading the landscape…
                      </>
                    ) : (
                      <>
                        <RouteIcon size={18} />
                        Analyse mission
                        <ArrowRight size={18} />
                      </>
                    )}
                  </button>
                  {analyseMutation.isPending && (
                    <p className="field-hint">
                      Fetching a bounded OSM region. Public services may take a
                      minute.
                      <button
                        className="text-button"
                        onClick={() => abort.current?.abort()}
                      >
                        Cancel request
                      </button>
                    </p>
                  )}
                  {analysis && (
                    <Statistics
                      analysis={analysis}
                      imperial={imperial}
                      onObstacle={selectObstacle}
                    />
                  )}
                  {preview && (
                    <div className="mission-actions">
                      <div>
                        <button
                          onClick={() => {
                            setMissionName(
                              `Mission · ${distance(preview.distance_m, imperial)}`,
                            );
                            setSaveOpen(true);
                          }}
                        >
                          <Bookmark size={16} />
                          Save mission
                        </button>
                        <button onClick={() => setShareOpen(true)}>
                          <Share2 size={16} />
                          Share
                        </button>
                      </div>
                      <div className="export-row">
                        <select
                          aria-label="Export route"
                          value={exportRoute}
                          onChange={(e) =>
                            setExportRoute(e.target.value as typeof exportRoute)
                          }
                        >
                          <option value="ideal">Ideal line</option>
                          <option value="walking" disabled={!analysis?.walking}>
                            Walking route
                          </option>
                          <option value="mission" disabled={!analysis?.mission}>
                            Mission route
                          </option>
                        </select>
                        <select
                          aria-label="Export format"
                          value={exportFormat}
                          onChange={(e) =>
                            setExportFormat(
                              e.target.value as typeof exportFormat,
                            )
                          }
                        >
                          <option value="gpx">GPX</option>
                          <option value="geojson">GeoJSON</option>
                          <option value="summary">Summary</option>
                        </select>
                        <button
                          aria-label="Download mission"
                          onClick={() => {
                            if (analysis) {
                              const a = document.createElement("a");
                              a.href = `/api/export/${exportFormat}/${analysis.id}?route=${exportRoute}`;
                              a.download = "";
                              a.click();
                            } else downloadPreview(preview, exportFormat);
                          }}
                        >
                          <ArrowDownToLine size={17} />
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
              {section === "discover" && (
                <>
                  <div className="eyebrow">LET CURIOSITY LEAD</div>
                  <h1>
                    Discover a line<span className="title-dot">.</span>
                  </h1>
                  <p className="intro compact">
                    Find promising missions in a place you want to explore.
                  </p>
                  <button
                    className={`area-button ${pick === "area" ? "active" : ""}`}
                    onClick={() => setPick(pick === "area" ? null : "area")}
                  >
                    <Crosshair size={21} />
                    <span>
                      <strong>
                        {pick === "area"
                          ? "Choose two corners on the map"
                          : area
                            ? "Search area selected"
                            : "Draw your search area"}
                      </strong>
                      <small>
                        {area
                          ? `${coordinateLabel(area[0])} → ${coordinateLabel(area[1])}`
                          : "A rectangle up to 64 km²"}
                      </small>
                    </span>
                  </button>
                  <div className="bearing-fields discovery-fields">
                    <label>
                      Minimum length
                      <div>
                        <input
                          aria-label="Minimum discovery length in kilometres"
                          type="number"
                          min={0.1}
                          max={10}
                          step={0.1}
                          value={minDiscovery / 1000}
                          onChange={(e) =>
                            setMinDiscovery(Number(e.target.value) * 1000)
                          }
                        />
                        <span>km</span>
                      </div>
                    </label>
                    <label>
                      Maximum length
                      <div>
                        <input
                          aria-label="Maximum discovery length in kilometres"
                          type="number"
                          min={0.1}
                          max={10}
                          step={0.1}
                          value={maxDiscovery / 1000}
                          onChange={(e) =>
                            setMaxDiscovery(Number(e.target.value) * 1000)
                          }
                        />
                        <span>km</span>
                      </div>
                    </label>
                  </div>
                  <label className="terrain-select">
                    Surface preference
                    <select
                      value={terrain}
                      onChange={(e) => setTerrain(e.target.value)}
                    >
                      <option value="any">Any mapped surface</option>
                      <option value="paved">Mapped paved surfaces</option>
                      <option value="trail">Mapped trails & paths</option>
                    </select>
                  </label>
                  <div className="section-divider" />
                  {corridorControls}
                  <div className="section-divider" />
                  {accessControl}
                  <button
                    className="primary-button"
                    disabled={
                      !area || discoveryRunning || discoverMutation.isPending
                    }
                    onClick={startDiscovery}
                  >
                    <Sparkles size={18} />
                    Find promising missions
                    <ArrowRight size={18} />
                  </button>
                  <p className="field-hint">
                    Up to 24 candidate lines, ranked by access confidence,
                    maximum deviation and obstacles. Terrain elevation is not
                    assessed.
                  </p>
                  {job.data && (
                    <div className="discovery-progress" aria-live="polite">
                      <div>
                        <strong>
                          {job.data.status === "running"
                            ? "Exploring the possibilities…"
                            : `Search ${job.data.status}`}
                        </strong>
                        {discoveryRunning && (
                          <button
                            className="text-button"
                            onClick={async () => {
                              try {
                                await api(`/discovery/${jobId}/cancel`, {});
                                await job.refetch();
                              } catch (e) {
                                setError((e as Error).message);
                              }
                            }}
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                      <progress max={100} value={job.data.progress} />
                      <p>{job.data.message}</p>
                    </div>
                  )}
                  {job.error && (
                    <p role="alert" className="error-note">
                      {job.error.message}
                    </p>
                  )}
                  {job.data?.results.map((r, i) => (
                    <button
                      className="discovery-card"
                      key={r.id}
                      onClick={() => {
                        applyParameters(r.parameters);
                        setAnalysis(r);
                      }}
                    >
                      <span className="result-rank">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>
                          {distance(r.distance_m, imperial)} of possibility
                        </strong>
                        {r.planned_grade && (
                          <GradeBadge grade={r.planned_grade} />
                        )}
                        <small>
                          Max. deviation{" "}
                          {distance(r.mission!.max_deviation_m, imperial)} ·{" "}
                          {r.status === "mapped"
                            ? "Mapped pedestrian access"
                            : "Uncertain access"}
                        </small>
                      </span>
                      <ArrowUpRight size={17} />
                    </button>
                  ))}
                </>
              )}
              {section === "saved" && (
                <>
                  <div className="eyebrow">KEEP YOUR CURIOSITY</div>
                  <h1>
                    Your saved lines<span className="title-dot">.</span>
                  </h1>
                  <p className="intro compact">
                    Mission parameters stored on this device. Reanalyse to check
                    current mapping.
                  </p>
                  {saved.length === 0 ? (
                    <div className="saved-empty">
                      <Bookmark size={32} />
                      <h2>Your next adventure belongs here.</h2>
                      <p>
                        Create a mission and save it to return to your line
                        later.
                      </p>
                      <button
                        className="secondary-button"
                        onClick={() => setSection("plan")}
                      >
                        Plan a mission
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  ) : (
                    saved.map((m) => (
                      <div className="saved-card" key={m.id}>
                        <button onClick={() => applyParameters(m.parameters)}>
                          <span className="saved-icon">
                            <Bookmark size={19} />
                          </span>
                          <span>
                            <strong>{m.name}</strong>
                            <small>
                              {new Date(m.savedAt).toLocaleDateString()} · ±
                              {distance(m.parameters.max_deviation_m, imperial)}
                            </small>
                          </span>
                          <ArrowUpRight size={17} />
                        </button>
                        <button
                          className="icon-button delete-saved"
                          aria-label={`Delete ${m.name}`}
                          onClick={() => {
                            try {
                              const next = saved.filter((s) => s.id !== m.id);
                              persistSaved(next);
                              setSaved(next);
                            } catch {
                              setError("Could not update browser storage.");
                            }
                          }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    ))
                  )}
                </>
              )}
              {error && (
                <p role="alert" className="error-note">
                  {error}
                </p>
              )}
              <div className="sidebar-footnote">
                <Info size={14} />
                <span>
                  A plan is a starting point. Always check local access and
                  real-world conditions.
                </span>
              </div>
            </div>
            <div className="sidebar-footer">
              <span>
                <span className="live-dot" /> BUILT FOR THE WAYFARERS
              </span>
              <span>v0.1</span>
            </div>
          </div>
        </aside>
        <main className="map-main" aria-label="Map workspace">
          <Search onPlace={setPlace} />
          <MapView
            start={start}
            end={method === "points" ? end : null}
            preview={preview}
            analysis={analysis}
            pick={pick}
            setPoint={setPoint}
            place={place}
            layers={layers}
            setLayers={setLayers}
            area={area}
            setArea={(a) => {
              setArea(a);
              setPick(null);
            }}
            onObstacle={(id) => {
              const o = analysis?.obstacles.find((o) => o.id === id);
              if (o) selectObstacle(o);
            }}
            focus={focus}
          />
          {!start && section === "explore" && (
            <div className="map-welcome">
              <span>
                <Compass size={18} />
                ADVENTURE, IN ITS SIMPLEST FORM
              </span>
              <h2>
                What’s between
                <br />
                here and there?
              </h2>
              <p>Choose a place. Draw a line. Get curious.</p>
              <button
                onClick={() => {
                  setSection("plan");
                  setPick("start");
                }}
              >
                Start exploring
                <ArrowUpRight size={17} />
              </button>
            </div>
          )}
          <div className="map-bottom-note">
            <Flag size={13} /> Every line is a possibility. Every journey is
            your own.
          </div>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={17} />
          {notice}
        </div>
      )}
      <Dialog.Root open={saveOpen} onOpenChange={setSaveOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content">
            <Dialog.Title>Keep this line.</Dialog.Title>
            <Dialog.Description>
              Save its coordinates and settings in this browser. Geographic data
              will be checked again when you analyse it.
            </Dialog.Description>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveMission();
              }}
            >
              <label className="dialog-label">
                Mission name
                <input
                  autoFocus
                  value={missionName}
                  onChange={(e) => setMissionName(e.target.value)}
                  maxLength={100}
                  required
                />
              </label>
              <button className="primary-button" type="submit">
                <Bookmark size={17} />
                Save mission
              </button>
            </form>
            <Dialog.Close className="dialog-close" aria-label="Close">
              <X size={20} />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={shareOpen} onOpenChange={setShareOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content">
            <Dialog.Title>A line worth sharing.</Dialog.Title>
            <Dialog.Description>
              This link contains the mission coordinates and settings. OSM data
              may change, so analysis results can differ.
            </Dialog.Description>
            <input
              className="share-input"
              aria-label="Shareable mission URL"
              readOnly
              value={params ? shareURL(params) : ""}
              onFocus={(e) => e.target.select()}
            />
            <button
              className="primary-button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(shareURL(params!));
                  setNotice("Mission link copied.");
                  setShareOpen(false);
                } catch {
                  setNotice("Select and copy the link above.");
                }
              }}
            >
              <Share2 size={17} />
              Copy link
            </button>
            <Dialog.Close className="dialog-close" aria-label="Close">
              <X size={20} />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={helpOpen} onOpenChange={setHelpOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content help-dialog">
            <div className="eyebrow">A LITTLE FIELD GUIDE</div>
            <Dialog.Title>
              Follow the line.
              <br />
              Understand the landscape.
            </Dialog.Title>
            <Dialog.Description>
              StraightLine compares an ideal geodesic with routes through
              available OpenStreetMap pedestrian data.
            </Dialog.Description>
            <div className="help-steps">
              <div>
                <span>01</span>
                <section>
                  <h3>Choose your two points</h3>
                  <p>
                    Search any location or coordinates. Place start and finish
                    on the map, or use a bearing and distance. Local analysis
                    supports missions from 10 m to 25 km.
                  </p>
                </section>
              </div>
              <div>
                <span>02</span>
                <section>
                  <h3>Set your room to wander</h3>
                  <p>
                    A ±50 m corridor permits 50 m of deviation on either side.
                    The red line is a WGS84 geodesic; the blue route is shortest
                    by distance; the green route minimises its greatest
                    deviation before breaking ties by distance.
                  </p>
                </section>
              </div>
              <div>
                <span>03</span>
                <section>
                  <h3>Read the evidence</h3>
                  <p>
                    Strict mode requires supporting pedestrian-access tags.
                    Relaxed mode admits unknown ways and limited links inside
                    explicitly accessible open spaces, marked uncertain.
                    Endpoint gaps, missing fences and access changes require
                    checking on the ground.
                  </p>
                </section>
              </div>
            </div>
            <GradeScale />
            <div className="help-warning">
              <Layers3 size={19} />
              <p>
                Coverage is not completeness. No elevation provider is
                configured. Routes use a finite downloaded region and do not
                model every local restriction or turn relation. A result is a
                planning aid, never proof of safe or legal passage.
              </p>
            </div>
            <a
              className="text-link"
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
            >
              Geographic data © OpenStreetMap contributors
              <ArrowUpRight size={13} />
            </a>
            <Dialog.Close className="dialog-close" aria-label="Close">
              <X size={20} />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={!!obstacle}
        onOpenChange={(open) => {
          if (!open) setObstacle(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content">
            <Dialog.Title>{obstacle?.name}</Dialog.Title>
            <Dialog.Description>
              Mapped feature intersection with the ideal line. This does not
              establish an impassable obstruction.
            </Dialog.Description>
            {obstacle && (
              <div className="data-panel">
                <dl>
                  <div>
                    <dt>Along the line</dt>
                    <dd>{distance(obstacle.position_m, imperial)}</dd>
                  </div>
                  <div>
                    <dt>Intersection extent</dt>
                    <dd>{distance(obstacle.crossing_extent_m, imperial)}</dd>
                  </div>
                  {Object.entries(obstacle.tags).map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
                <p>
                  {obstacle.confidence}.{" "}
                  {obstacle.crossing_infrastructure_nearby
                    ? "Possible crossing infrastructure is mapped within 25 m; continuity and access are unverified."
                    : "No nearby crossing infrastructure identified by this model."}
                </p>
                <a
                  className="text-link"
                  href={`https://www.openstreetmap.org/${obstacle.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View OpenStreetMap feature
                  <ArrowUpRight size={13} />
                </a>
              </div>
            )}
            <Dialog.Close className="dialog-close" aria-label="Close">
              <X size={20} />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
