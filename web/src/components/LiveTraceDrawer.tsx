/** Shows bounded, sanitized live-run activity in an accessible modal drawer. */

import {
  Activity,
  Check,
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  Play,
  Radio,
  RefreshCw,
  X,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { meaningfulTrace, productMessage } from "../lib/report";
import type { DemoStatusResponse, LiveTraceEvent } from "../types";
import { TraceEventRow } from "./TraceEventRow";

interface LiveTraceDrawerProps {
  open: boolean;
  status: DemoStatusResponse;
  reportRefreshFailed: boolean;
  onClose: () => void;
  onRefreshReports: () => void;
  onStartRun: () => void;
}

/** Renders live analysis status, optional evidence updates, and reviewable activity. */
export function LiveTraceDrawer({
  open,
  status,
  reportRefreshFailed,
  onClose,
  onRefreshReports,
  onStartRun,
}: LiveTraceDrawerProps) {
  const reduceMotion = useReducedMotion();
  const [showEvidenceEvents, setShowEvidenceEvents] = useState(false);
  const [follow, setFollow] = useState(true);
  const drawerRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  // Evidence updates are summarized on demand so the activity feed stays readable.
  const availableEvents = useMemo(
    () => compactLiveEvents(status.events, showEvidenceEvents),
    [showEvidenceEvents, status.events],
  );
  const events = availableEvents.slice(-160);
  const hiddenUpdateCount = availableEvents.length - events.length;

  // Keep the latest close callback available without rebuilding the focus-trap effect.
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // Make the workspace inert, contain keyboard focus, and restore the trigger on close.
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const backgroundElements = Array.from(
      document.querySelectorAll<HTMLElement>(
        ".skip-link, .app-header, .workspace-layout",
      ),
    ).map((element) => ({
      element,
      wasInert: element.hasAttribute("inert"),
    }));
    backgroundElements.forEach(({ element }) => element.setAttribute("inert", ""));
    const focusFrame = window.requestAnimationFrame(() => {
      closeRef.current?.focus();
    });

    /** Closes on Escape and wraps Tab focus within the modal drawer. */
    function handleKey(event: KeyboardEvent) {
      const drawer = drawerRef.current;
      if (!drawer || drawer.closest("[inert]")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        drawer.focus();
        return;
      }
      const first = focusable[0]!;
      const last = focusable.at(-1)!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === drawer || !drawer.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !drawer.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener("keydown", handleKey);
      backgroundElements.forEach(({ element, wasInert }) => {
        if (wasInert) element.setAttribute("inert", "");
        else element.removeAttribute("inert");
      });
      const fallback = document.querySelector<HTMLElement>(
        '[aria-controls="live-trace-drawer"]',
      );
      const restoreTarget = previousFocus?.isConnected ? previousFocus : fallback;
      if (restoreTarget && !restoreTarget.closest("[inert]")) restoreTarget.focus();
    };
  }, [open]);

  // Follow new events unless the reviewer has paused automatic scrolling.
  useEffect(() => {
    if (!open || !follow) return;
    endRef.current?.scrollIntoView({
      behavior: reduceMotion || status.status === "running" ? "auto" : "smooth",
    });
  }, [events.length, follow, open, reduceMotion, status.status]);

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          ref={drawerRef}
          id="live-trace-drawer"
          className="live-trace-drawer"
          role="dialog"
          aria-modal="true"
          aria-labelledby="live-trace-title"
          tabIndex={-1}
          initial={reduceMotion ? false : { opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 24 }}
          transition={{ duration: 0.18 }}
        >
          <header className="live-trace-header">
            <div>
              <span className="eyebrow">Analysis center</span>
              <h2 id="live-trace-title">Live progress</h2>
            </div>
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              aria-label="Close live analysis progress"
            >
              <X size={18} />
            </button>
          </header>

          <div className={`live-run-state live-run-state--${status.status}`} role="status">
            {status.status === "running" ? (
              <LoaderCircle className="spin" size={16} />
            ) : status.status === "completed" ? (
              <CircleCheck size={16} />
            ) : status.status === "failed" ? (
              <CircleAlert size={16} />
            ) : (
              <Radio size={16} />
            )}
            <strong>{phaseLabel(status.status)}</strong>
            <span>{status.eventCount.toLocaleString()} activity updates</span>
          </div>

          <AnalysisProgress status={status} reduced={Boolean(reduceMotion)} />

          <p className="live-trace-boundary">
            Reviewable questions, analytical checks, and verification steps appear here as they happen. Private model reasoning is never collected.
          </p>

          {status.jobId && (
            <section className="live-run-details" aria-label="Analysis details">
              <dl>
                <div><dt>Households</dt><dd>{status.customers}</dd></div>
                <div><dt>Started</dt><dd>{formatTimestamp(status.startedAt)}</dd></div>
                <div><dt>Sensitivity</dt><dd>{sensitivityLabel(status.declineThreshold)}</dd></div>
                <div><dt>Review mode</dt><dd>Population comparison</dd></div>
              </dl>
            </section>
          )}

          <div className="live-trace-controls">
            <label className="switch-label">
              <input
                type="checkbox"
                checked={showEvidenceEvents}
                onChange={(event) => setShowEvidenceEvents(event.target.checked)}
              />
              <span aria-hidden="true" />
              Evidence summaries
            </label>
            <label className="switch-label">
              <input
                type="checkbox"
                checked={follow}
                onChange={(event) => setFollow(event.target.checked)}
              />
              <span aria-hidden="true" />
              Follow latest
            </label>
          </div>

          {status.error && (
            <div className="live-trace-error" role="alert">
              <CircleAlert size={16} />
              <span>
                {status.status === "failed" && <strong>Analysis did not complete. </strong>}
                {productMessage(status.error, "The analysis could not be completed.")}
              </span>
            </div>
          )}

          {!status.error && status.traceWarning && (
            <div className="live-trace-notice" role="status">
              <RefreshCw className={status.status === "running" ? "spin" : ""} size={16} />
              <span>
                <strong>{status.status === "running" ? "Reconnecting live updates." : "Some live updates were unavailable."}</strong>{" "}
                {status.status === "running"
                  ? "The analysis is still running; progress will resume automatically."
                  : "Completed results and decision history remain authoritative."}
              </span>
            </div>
          )}

          {status.droppedEventCount > 0 && (
            <div className="live-trace-error" role="status">
              <CircleAlert size={16} />
              <span>
                {status.droppedEventCount} earlier updates were omitted from this live window. The completed decision history remains available.
              </span>
            </div>
          )}

          <div
            className="live-trace-log"
            role="log"
            tabIndex={0}
            aria-label="Live analysis activity"
            aria-live={status.status === "running" ? "polite" : "off"}
            aria-relevant="additions"
          >
            {hiddenUpdateCount > 0 && (
              <div className="live-window-note" role="status">
                Showing the latest {events.length} summarized updates · {hiddenUpdateCount} earlier updates remain in the completed decision history.
              </div>
            )}
            {events.map((event) => (
              <TraceEventRow event={event} showSource condensed key={event.id} />
            ))}
            {events.length === 0 && status.status === "idle" && (
              <div className="live-trace-empty">
                <Activity size={20} />
                <strong>No run activity</strong>
                <span>Start a new analysis to see verified progress here.</span>
              </div>
            )}
            {events.length === 0 && status.status === "running" && (
              <div className="live-trace-empty">
                <LoaderCircle className="spin" size={20} />
                <strong>Preparing the analysis</strong>
                <span>WhyBack is selecting the cohort and validating inputs.</span>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {status.status !== "running" && (
            <footer className="live-trace-footer">
              {status.status === "completed" && reportRefreshFailed ? (
                <button type="button" onClick={onRefreshReports}>
                  <CircleCheck size={15} /> Reload dashboard results
                </button>
              ) : (
                <button type="button" onClick={onStartRun}>
                  {status.status === "idle" ? <Play size={15} /> : <RefreshCw size={15} />}
                  {status.status === "idle" ? "Configure analysis" : "Start new analysis"}
                </button>
              )}
            </footer>
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

/** Collapses consecutive ledger writes into one readable evidence summary. */
function compactLiveEvents(
  events: LiveTraceEvent[],
  includeEvidence: boolean,
): LiveTraceEvent[] {
  if (!includeEvidence) return meaningfulTrace(events);
  const compacted: LiveTraceEvent[] = [];
  let evidenceBatchKey: string | null = null;
  for (const event of events) {
    if (event.event !== "evidence_added") {
      evidenceBatchKey = null;
      compacted.push(event);
      continue;
    }
    const source = String(event.details.source_tool ?? "analysis");
    const call = String(event.details.source_tool_call_id ?? source);
    const batchKey = `${event.householdId}:${call}`;
    const metric = String(event.details.metric ?? "observed signal");
    const limitations = Array.isArray(event.details.limitations)
      ? event.details.limitations.map(String).filter(Boolean)
      : [];
    const previous = compacted.at(-1);
    if (previous?.event === "evidence_batch" && evidenceBatchKey === batchKey) {
      const signals = Array.isArray(previous.details.signals)
        ? previous.details.signals.map(String)
        : [];
      compacted[compacted.length - 1] = {
        ...previous,
        id: event.id,
        cursor: event.cursor,
        timestamp: event.timestamp,
        details: {
          ...previous.details,
          evidence_count: Number(previous.details.evidence_count ?? 1) + 1,
          signals: [...new Set([...signals, metric])],
          scope_note: previous.details.scope_note ?? limitations[0],
        },
      };
      continue;
    }
    evidenceBatchKey = batchKey;
    compacted.push({
      ...event,
      event: "evidence_batch",
      details: {
        analytical_check: source,
        evidence_count: 1,
        signals: [metric],
        ...(limitations[0] ? { scope_note: limitations[0] } : {}),
      },
    });
  }
  return compacted;
}

/** Converts the machine live-run phase into its compact display label. */
function phaseLabel(status: DemoStatusResponse["status"]): string {
  if (status === "idle") return "Not started";
  if (status === "running") return "Analysis in progress";
  if (status === "completed") return "Analysis complete · insights ready";
  return "Analysis interrupted";
}

/** Names the cohort threshold without implying an action-evidence change. */
function sensitivityLabel(threshold: DemoStatusResponse["declineThreshold"]): string {
  if (threshold === 0.2) return "Broad · ≥20%";
  if (threshold === 0.4) return "Focused · ≥40%";
  return "Standard · ≥30%";
}

const analysisStages = [
  { label: "Select", events: ["run_started"] },
  { label: "Investigate", events: ["model_decision_requested", "model_decision_received", "tool_started", "tool_completed", "tool_partial", "tool_failed", "finish_requested"] },
  { label: "Verify", events: ["verification_started", "verification_passed"] },
  { label: "Ready", events: ["run_completed"] },
];

/** Shows the current analysis phase without exposing execution implementation. */
function AnalysisProgress({
  status,
  reduced,
}: {
  status: DemoStatusResponse;
  reduced: boolean;
}) {
  const eventNames = new Set(status.events.map((event) => event.event));
  const reached = analysisStages.map((stage, index) =>
    index === 0
      ? status.status !== "idle"
      : index === analysisStages.length - 1
        ? status.status === "completed"
        : stage.events.some((event) => eventNames.has(event)),
  );
  const latestReached = reached.reduce(
    (latest, value, index) => (value ? index : latest),
    0,
  );
  const activeIndex = status.status === "completed"
    ? analysisStages.length - 1
    : latestReached;

  return (
    <div className="analysis-progress" aria-label={`Analysis stage: ${analysisStages[activeIndex]?.label ?? "Select"}`}>
      <motion.span
        className="analysis-progress__line"
        aria-hidden="true"
        initial={reduced ? false : { scaleX: 0 }}
        animate={{ scaleX: status.status === "idle" ? 0 : activeIndex / (analysisStages.length - 1) }}
        transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 24 }}
      />
      <ol>
        {analysisStages.map((stage, index) => {
          const complete = index < activeIndex || status.status === "completed";
          const active = index === activeIndex && status.status !== "idle" && status.status !== "completed";
          return (
            <li className={complete ? "complete" : active ? "active" : ""} key={stage.label}>
              <span>{complete ? <Check size={11} /> : index + 1}</span>
              <small>{stage.label}</small>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Formats a live timestamp as local time and handles missing or invalid values. */
function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Unknown"
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
