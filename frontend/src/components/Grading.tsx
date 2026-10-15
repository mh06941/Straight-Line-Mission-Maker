import { useQuery } from "@tanstack/react-query";
import { Award, ChevronDown } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import type { GradingScale, PlannedGrade } from "../types";

export function GradeBadge({ grade }: { grade: PlannedGrade }) {
  return (
    <span className={`grade-badge grade-${grade.tier}`}>
      <Award size={15} aria-hidden="true" />
      {grade.label}
    </span>
  );
}

export function GradeScale() {
  const scale = useQuery({
    queryKey: ["grading-scale"],
    queryFn: () => api<GradingScale>("/grading"),
    staleTime: Infinity,
    retry: false,
  });
  return (
    <section className="grade-scale" aria-label="Planned grading thresholds">
      <h3>Maximum deviation grades</h3>
      {scale.isPending && <p role="status">Loading grading thresholds…</p>}
      {scale.error && <p role="alert">{scale.error.message}</p>}
      {scale.data && (
        <>
          <dl>
            {scale.data.rules.map((rule) => (
              <div key={rule.tier}>
                <dt>{rule.label}</dt>
                <dd>{rule.range}</dd>
              </div>
            ))}
          </dl>
          <p>{scale.data.note}</p>
        </>
      )}
    </section>
  );
}

export function PlannedGradeCard({ grade }: { grade: PlannedGrade }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="planned-grade" aria-label="Planned mission grade">
      <div className="planned-grade-heading">
        <h3>Planned grade</h3>
        <GradeBadge grade={grade} />
      </div>
      <p>
        <strong>{grade.max_deviation_m.toFixed(2)} m</strong> maximum deviation
        <span className="grade-range">{grade.range}</span>
      </p>
      <p className="grade-note">
        Based on the route’s unrounded maximum, independent of your corridor
        setting. A planning estimate; a completed mission needs a recorded
        track.
      </p>
      <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
        <summary>
          View grading thresholds <ChevronDown size={14} />
        </summary>
        {expanded && <GradeScale />}
      </details>
    </section>
  );
}
