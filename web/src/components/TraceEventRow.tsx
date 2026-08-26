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
  condensed = false,
}: {
  event: TraceEvent | LiveTraceEvent;
  showSource?: boolean;
  condensed?: boolean;
}) {
  const details = orderedDetails(event.details, condensed);
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
                <small>{detailLabel(key)}</small>
                <span className="trace-detail__value">{formatTraceDetail(value, key)}</span>
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
  if (event.includes("evidence")) return "evidence";
  if (event.includes("tool")) return "tool";
  if (event.includes("decision") || event === "finish_requested") return "decision";
  return "run";
}

const detailPriority = [
  "investigation_question",
  "decision_summary",
  "analytical_check",
  "signals",
  "scope_note",
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
  "scope_note",
]);
const detailPriorityByKey = new Map(
  detailPriority.map((key, index) => [key, index]),
);
const condensedHiddenDetails = new Set([
  "allowed_tools",
  "evidence_id",
  "finish_available",
  "input_tokens",
  "model",
  "output_tokens",
  "prompt_version",
  "provider_call_id",
  "repair_attempted",
  "repair_available",
  "repair_requested",
  "source_tool",
  "source_tool_call_id",
  "tool_call_id",
  "unavailable_tools",
]);

/** Gives implementation-oriented activity fields product-friendly labels. */
function detailLabel(key: string): string {
  const labels: Record<string, string> = {
    selected_tool: "Analytical lens",
    tool_name: "Analytical check",
    latency_ms: "Elapsed milliseconds",
    remaining_tool_budget: "Checks remaining",
    remaining_turn_budget: "Review steps remaining",
    analytical_check: "Analytical check",
    signals: "Signals recorded",
    scope_note: "Scope note",
  };
  return labels[key] ?? humanize(key);
}

/** Orders allow-listed details by reviewer importance and removes empty values. */
function orderedDetails(details: Record<string, unknown>, condensed: boolean) {
  return Object.entries(details)
    .filter(([key, value]) => value !== null && value !== "" && (!condensed || !condensedHiddenDetails.has(key)))
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
function formatTraceDetail(value: unknown, key: string): string {
  if (Array.isArray(value)) {
    const values = value.map(String);
    return key === "signals"
      ? values.map(humanize).join(", ") || "None"
      : values.join(", ") || "None";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "object") return "Structured detail";
  const rendered = String(value);
  return key === "selected_tool" || key === "tool_name" || key === "analytical_check"
    ? humanize(rendered)
    : rendered;
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
