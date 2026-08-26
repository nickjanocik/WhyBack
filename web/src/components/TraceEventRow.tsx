/** Turns one sanitized audit event into a categorized, human-readable timeline row. */

import {
  Bot,
  CircleAlert,
  Hammer,
  ListFilter,
  ShieldCheck,
} from "lucide-react";

import { eventLabel, humanize } from "../lib/report";
import type { LiveTraceEvent, TraceEvent } from "../types";

/** Renders an audit event with its safe details and optional household source. */
export function TraceEventRow({
  event,
  showSource = false,
}: {
  event: TraceEvent | LiveTraceEvent;
  showSource?: boolean;
}) {
  const details = orderedDetails(event.details);
  const sourceLabel = "sourceLabel" in event ? event.sourceLabel : null;
  return (
    <article className={`trace-row trace-row--${traceCategory(event.event)}`}>
      <span className="trace-row__icon">{traceIcon(event.event)}</span>
      <div className="trace-row__body">
        <div>
          <strong>{eventLabel(event.event)}</strong>
          {showSource && sourceLabel && <span className="trace-source">{sourceLabel}</span>}
          <time>{formatTraceTime(event.timestamp)}</time>
        </div>
        {details.length > 0 && (
          <div className="trace-details">
            {details.slice(0, 7).map(([key, value]) => (
              <div
                className={`trace-detail ${narrativeDetailKeys.has(key) ? "trace-detail--narrative" : ""}`}
                key={key}
              >
                <small>{humanize(key)}</small>
                <span className="trace-detail__value">{formatTraceDetail(value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

/** Groups audit event names into the small visual categories used by the timeline. */
function traceCategory(event: string): string {
  if (
    event.includes("failed") ||
    event.includes("rejected") ||
    event.includes("retry") ||
    event.includes("partial")
  ) {
    return "warning";
  }
  if (event.includes("verification")) return "verify";
  if (event.includes("tool")) return "tool";
  if (event.includes("decision") || event === "finish_requested") return "decision";
  return "run";
}

const detailPriority = [
  "investigation_question",
  "decision_summary",
  "selected_tool",
  "tool_name",
  "status",
  "attempt",
  "latency_ms",
  "rows_examined",
  "evidence_count",
  "remaining_tool_budget",
  "remaining_turn_budget",
  "next_best_action_id",
  "resolved_confidence",
  "proposed_confidence",
  "confidence_cap_applied",
  "supporting_evidence_count",
  "counterevidence_count",
  "retryable",
  "failure_type",
  "message",
  "limitations",
  "human_review_required",
];
const narrativeDetailKeys = new Set([
  "investigation_question",
  "decision_summary",
]);
const detailPriorityByKey = new Map(
  detailPriority.map((key, index) => [key, index]),
);

/** Orders allow-listed details by reviewer importance and removes empty values. */
function orderedDetails(details: Record<string, unknown>) {
  return Object.entries(details)
    .filter(([, value]) => value !== null && value !== "")
    .sort(
      ([left], [right]) =>
        (detailPriorityByKey.get(left) ?? Number.MAX_SAFE_INTEGER) -
        (detailPriorityByKey.get(right) ?? Number.MAX_SAFE_INTEGER),
    );
}

/** Chooses the icon associated with an event's visual category. */
function traceIcon(event: string) {
  const category = traceCategory(event);
  if (category === "verify") return <ShieldCheck size={15} />;
  if (category === "tool") return <Hammer size={15} />;
  if (category === "decision") return <Bot size={15} />;
  if (category === "warning") return <CircleAlert size={15} />;
  return <ListFilter size={15} />;
}

/** Formats one already-sanitized trace value without exposing raw object content. */
function formatTraceDetail(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ") || "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "object") return "Structured detail";
  return String(value);
}

/** Formats an audit timestamp as local clock time with a safe fallback. */
function formatTraceTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? ""
    : date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
}
