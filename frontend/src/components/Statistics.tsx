import {
  ArrowDownToLine,
  Check,
  ChevronDown,
  ChevronRight,
  Info,
  Mountain,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import type { Analysis, Obstacle } from "../types";
import { distance } from "../lib/mission";
import { PlannedGradeCard } from "./Grading";

export default function Statistics({
  analysis,
  imperial,
  onObstacle,
}: {
  analysis: Analysis;
  imperial: boolean;
  onObstacle: (o: Obstacle) => void;
}) {
  const [tab, setTab] = useState<"overview" | "obstacles" | "data">("overview");
  const route = analysis.mission;
  const good = analysis.status === "mapped";
  return (
    <section className="analysis-results" aria-label="Mission analysis">
      <div className={`feasibility ${good ? "success" : ""}`} role="status">
        {good ? <ShieldCheck size={20} /> : <TriangleAlert size={20} />}
        <div>
          <strong>
            {good
              ? "A line worth exploring"
              : analysis.status === "uncertain"
                ? "A route with unknowns"
                : analysis.status === "no_route"
                  ? "No route within this corridor"
                  : "More data is needed"}
          </strong>
          <p>{analysis.message}</p>
        </div>
      </div>
      <div className="result-tabs" role="tablist" aria-label="Analysis details">
        {(["overview", "obstacles", "data"] as const).map((t) => (
          <button
            role="tab"
            id={`tab-${t}`}
            aria-controls="result-panel"
            aria-selected={tab === t}
            key={t}
            onClick={() => setTab(t)}
          >
            {t === "data"
              ? "Data & access"
              : t === "obstacles"
                ? `Obstacles ${analysis.obstacles.length}`
                : "Overview"}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="result-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "overview" && (
          <>
            <div className="route-comparison">
              {[
                {
                  name: "Ideal line",
                  className: "ideal",
                  value: analysis.distance_m,
                },
                {
                  name: "Walking route",
                  className: "walking",
                  value: analysis.walking?.distance_m,
                },
                {
                  name: "Mission route",
                  className: "mission",
                  value: route?.distance_m,
                },
              ].map((r) => (
                <div key={r.name}>
                  <span>
                    <i className={r.className} />
                    {r.name}
                  </span>
                  <strong>
                    {r.value !== undefined
                      ? distance(r.value, imperial)
                      : "Unavailable"}
                  </strong>
                </div>
              ))}
            </div>
            {route && analysis.planned_grade && (
              <PlannedGradeCard grade={analysis.planned_grade} />
            )}
            {!route && (
              <p className="inline-note">
                Planned grade unavailable until a mission route is found.
              </p>
            )}
            {route && (
              <>
                <div className="stat-grid">
                  <div>
                    <small>MAX. DEVIATION</small>
                    <strong>{distance(route.max_deviation_m, imperial)}</strong>
                    <span>
                      <Check size={12} /> Within ±
                      {distance(analysis.max_deviation_m, imperial)}
                    </span>
                  </div>
                  <div>
                    <small>AVG. DEVIATION</small>
                    <strong>
                      {distance(route.average_deviation_m, imperial)}
                    </strong>
                    <span>Weighted by distance</span>
                  </div>
                  <div>
                    <small>EXTRA DISTANCE</small>
                    <strong>
                      {distance(route.extra_distance_m, imperial)}
                    </strong>
                    <span>Relative to ideal line</span>
                  </div>
                  <div>
                    <small>ACCESS UNKNOWN</small>
                    <strong>
                      {distance(route.uncertain_distance_m, imperial)}
                    </strong>
                    <span>{route.unverified_sections} network sections</span>
                  </div>
                </div>
                <div className="section-heading">
                  <span>How close to the line?</span>
                  <Info size={14} />
                </div>
                <div className="deviation-bars">
                  {Object.entries(route.within_percent).map(
                    ([threshold, percent]) => (
                      <div key={threshold}>
                        <span>
                          Within {distance(Number(threshold), imperial)}
                        </span>
                        <div className="bar-track">
                          <div style={{ width: `${percent}%` }} />
                        </div>
                        <strong>{percent.toFixed(0)}%</strong>
                      </div>
                    ),
                  )}
                </div>
              </>
            )}
            {analysis.minimum_corridor_m !== null && !route && (
              <p className="inline-note">
                <ArrowDownToLine size={15} /> Smallest modelled corridor: ±
                {distance(analysis.minimum_corridor_m, imperial)}.
              </p>
            )}
            <div className="terrain-note">
              <Mountain size={23} />
              <div>
                <strong>Terrain is unknown</strong>
                <p>{analysis.terrain.reason}</p>
              </div>
            </div>
            {analysis.difficulty && (
              <details className="difficulty">
                <summary>
                  Partial planning difficulty{" "}
                  <strong>{analysis.difficulty.score}/10</strong>
                  <ChevronDown size={14} />
                </summary>
                <p>{analysis.difficulty.explanation}</p>
              </details>
            )}
          </>
        )}
        {tab === "obstacles" && (
          <div className="obstacle-list">
            <p className="muted small">
              Mapped intersections with the ideal line are potential obstacles.
              Nearby bridges or crossings do not prove passage.
            </p>
            {analysis.obstacles.length === 0 && (
              <p className="empty-note">
                No mapped intersections found. Unmapped obstacles may still
                exist.
              </p>
            )}
            {analysis.obstacles.map((o) => (
              <button key={o.id} onClick={() => onObstacle(o)}>
                <span className="obstacle-icon">
                  <TriangleAlert size={17} />
                </span>
                <span>
                  <strong>{o.name}</strong>
                  <small>
                    {distance(o.position_m, imperial)} from start · {o.kind}
                  </small>
                  {o.crossing_infrastructure_nearby && (
                    <small>Possible crossing infrastructure nearby</small>
                  )}
                </span>
                <ChevronRight size={16} />
              </button>
            ))}
          </div>
        )}
        {tab === "data" && (
          <div className="data-panel">
            <h3>Evidence, with its limits</h3>
            <dl>
              <div>
                <dt>Source</dt>
                <dd>{analysis.data.source}</dd>
              </div>
              <div>
                <dt>Coverage evidence</dt>
                <dd>{analysis.data.confidence}</dd>
              </div>
              <div>
                <dt>Retrieved</dt>
                <dd>
                  {analysis.data.fetched_at
                    ? new Date(analysis.data.fetched_at).toLocaleString()
                    : "Unavailable"}
                </dd>
              </div>
              <div>
                <dt>Cache</dt>
                <dd>
                  {analysis.data.cached
                    ? "Reused cached region"
                    : "Fresh request"}
                </dd>
              </div>
              <div>
                <dt>Modelled network</dt>
                <dd>{analysis.data.network_edges ?? 0} edges</dd>
              </div>
              <div>
                <dt>Numerical tolerance</dt>
                <dd>±0.5 m; geometry sampled at ≤5 m</dd>
              </div>
            </dl>
            {analysis.snapping && (
              <p className="inline-note">
                Unassessed endpoint gaps: start{" "}
                {distance(analysis.snapping.start?.distance_m ?? 0, imperial)},
                finish{" "}
                {distance(analysis.snapping.end?.distance_m ?? 0, imperial)}.
                Route statistics exclude these gaps.
              </p>
            )}
            {analysis.warnings.map((w) => (
              <p className="inline-note" key={w}>
                <Info size={14} />
                {w}
              </p>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
