/** Shows bounded, sanitized live-run activity in an accessible modal drawer. */

import {
  Activity,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  Play,
  Radio,
  X,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { humanize, meaningfulTrace } from "../lib/report";
import type { DemoStatusResponse } from "../types";
import { TraceEventRow } from "./TraceEventRow";

interface LiveTraceDrawerProps {
  open: boolean;
  status: DemoStatusResponse;
  onClose: () => void;
  onOpenResults: () => void;
  onStartRun: () => void;
}

/** Renders live job status, optional evidence writes, and per-household audit events. */
export function LiveTraceDrawer({
  open,
  status,
  onClose,
  onOpenResults,
  onStartRun,
}: LiveTraceDrawerProps) {
  const reduceMotion = useReducedMotion();
  const [showEvidenceEvents, setShowEvidenceEvents] = useState(false);
  const [follow, setFollow] = useState(true);
  const drawerRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  // Evidence writes are useful on demand but hidden initially to keep the audit readable.
  const events = useMemo(
    () => (showEvidenceEvents ? status.events : meaningfulTrace(status.events)),
    [showEvidenceEvents, status.events],
  );

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
              <span className="eyebrow">Agent activity</span>
              <h2 id="live-trace-title">Live audit trace</h2>
            </div>
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              aria-label="Close live audit trace"
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
            <span>{status.eventCount} recorded events</span>
          </div>

          <p className="live-trace-boundary">
            Shows sanitized questions, decisions, tool activity, evidence writes, and verification. Private model reasoning is not collected.
          </p>

          {status.jobId && (
            <details className="live-run-details">
              <summary>
                <ChevronDown size={12} aria-hidden="true" /> Run details
              </summary>
              <dl>
                <div><dt>Backend</dt><dd>{humanize(status.backend)}</dd></div>
                <div><dt>Model</dt><dd><code>{status.model || "—"}</code></dd></div>
                <div><dt>Households</dt><dd>{status.customers}</dd></div>
                <div><dt>Started</dt><dd>{formatTimestamp(status.startedAt)}</dd></div>
                <div><dt>Job</dt><dd><code>{status.jobId.slice(0, 8)}</code></dd></div>
              </dl>
              {status.command && <code>{status.command}</code>}
            </details>
          )}

          <div className="live-trace-controls">
            <label className="switch-label">
              <input
                type="checkbox"
                checked={showEvidenceEvents}
                onChange={(event) => setShowEvidenceEvents(event.target.checked)}
              />
              <span aria-hidden="true" />
              Evidence writes
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

          {(status.error || status.traceWarning) && (
            <div className="live-trace-error" role="alert">
              <CircleAlert size={16} />
              <span>{status.error || status.traceWarning}</span>
            </div>
          )}

          {status.droppedEventCount > 0 && (
            <div className="live-trace-error" role="status">
              <CircleAlert size={16} />
              <span>
                {status.droppedEventCount} earlier audit events were omitted from the bounded live window.
              </span>
            </div>
          )}

          <div
            className="live-trace-log"
            role="log"
            tabIndex={0}
            aria-label="Live audit event log"
            aria-live={status.status === "running" ? "polite" : "off"}
            aria-relevant="additions"
          >
            {events.map((event) => (
              <TraceEventRow event={event} showSource key={event.id} />
            ))}
            {events.length === 0 && status.status === "idle" && (
              <div className="live-trace-empty">
                <Activity size={20} />
                <strong>No run activity</strong>
                <span>Start a live Gemini run to populate this trace.</span>
              </div>
            )}
            {events.length === 0 && status.status === "running" && (
              <div className="live-trace-empty">
                <LoaderCircle className="spin" size={20} />
                <strong>Waiting for the first audit event</strong>
                <span>The CLI is preparing the run workspace.</span>
              </div>
            )}
            {status.status === "running" && events.length > 0 && (
              <div className="live-trace-waiting">
                <LoaderCircle className="spin" size={14} /> Waiting for the next event
              </div>
            )}
            <div ref={endRef} />
          </div>

          <footer className="live-trace-footer">
            {status.status === "completed" ? (
              <button type="button" onClick={onOpenResults}>
                <CircleCheck size={16} /> Open generated reports
              </button>
            ) : status.status === "running" ? (
              <span><LoaderCircle className="spin" size={14} /> Run in progress</span>
            ) : (
              <button type="button" onClick={onStartRun}>
                <Play size={15} /> {status.status === "failed" ? "Run live again" : "Start live run"}
              </button>
            )}
          </footer>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

/** Converts the machine live-run phase into its compact display label. */
function phaseLabel(status: DemoStatusResponse["status"]): string {
  if (status === "idle") return "Idle";
  return humanize(status);
}

/** Formats a live timestamp as local time and handles missing or invalid values. */
function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Unknown"
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
