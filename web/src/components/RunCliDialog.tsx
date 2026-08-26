/** Collects the one runtime choice needed to start the real WhyBack CLI. */

import { Cpu, LoaderCircle, Play, Terminal, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type { DemoCustomerLimits, LiveRunConfiguration } from "../types";

interface RunCliDialogProps {
  open: boolean;
  running: boolean;
  error: string | null;
  customerLimits: DemoCustomerLimits;
  liveRun: LiveRunConfiguration;
  onClose: () => void;
  onRun: (customers: number) => Promise<void>;
}

const DEFAULT_CUSTOMERS = 5;

/** Renders a compact launch dialog; credentials remain entirely server-side. */
export function RunCliDialog({
  open,
  running,
  error,
  customerLimits,
  liveRun,
  onClose,
  onRun,
}: RunCliDialogProps) {
  const reduceMotion = useReducedMotion();
  const [customerInput, setCustomerInput] = useState(
    String(
      Math.min(
        customerLimits.maximum,
        Math.max(customerLimits.minimum, DEFAULT_CUSTOMERS),
      ),
    ),
  );
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  const runningRef = useRef(running);

  useEffect(() => {
    onCloseRef.current = onClose;
    runningRef.current = running;
  }, [onClose, running]);

  // Make the workspace inert, contain focus, and restore the launch control on close.
  useEffect(() => {
    if (!open) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const appContent = document.querySelector<HTMLElement>(".app-content");
    appContent?.setAttribute("inert", "");
    const focusFrame = window.requestAnimationFrame(() => dialogRef.current?.focus());

    /** Closes an idle dialog on Escape and wraps Tab focus inside the modal. */
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !runningRef.current) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0]!;
      const last = focusable.at(-1)!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialog || !dialog.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !dialog.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener("keydown", handleKey);
      appContent?.removeAttribute("inert");
      previousFocus?.focus();
    };
  }, [open]);

  const customers = Number(customerInput);
  const countIsValid =
    Number.isInteger(customers) &&
    customers >= customerLimits.minimum &&
    customers <= customerLimits.maximum;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="dialog-backdrop"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !running) onClose();
          }}
        >
          <motion.section
            ref={dialogRef}
            className="run-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="run-cli-title"
            tabIndex={-1}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.97, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 8 }}
            transition={{ type: "spring", stiffness: 360, damping: 30 }}
          >
            <button
              className="dialog-close"
              type="button"
              onClick={onClose}
              disabled={running}
              aria-label="Close CLI run dialog"
            >
              <X size={18} />
            </button>

            <div className="run-dialog__title">
              <span><Terminal size={18} /></span>
              <div>
                <span className="eyebrow">WhyBack CLI</span>
                <h2 id="run-cli-title">Start an investigation run</h2>
              </div>
            </div>

            <dl className="run-config-summary">
              <div><dt>Backend</dt><dd>Gemini API</dd></div>
              <div><dt>Model</dt><dd><code>{liveRun.model}</code></dd></div>
              <div><dt>Credential</dt><dd>Server environment</dd></div>
            </dl>

            <label className="customer-count-field">
              <span>Households</span>
              <input
                type="number"
                min={customerLimits.minimum}
                max={customerLimits.maximum}
                step={1}
                value={customerInput}
                disabled={running || !liveRun.ready}
                aria-describedby="customer-count-help"
                onChange={(event) => setCustomerInput(event.currentTarget.value)}
              />
            </label>
            <p id="customer-count-help" className="field-help">
              Enter {customerLimits.minimum}–{customerLimits.maximum}. The CLI selects the highest-ranked eligible households.
            </p>

            <p className="run-boundary">
              <Cpu size={15} />
              <span>
                This uses real provider quota. Python computes every metric; the run only recommends actions for human review and executes no outreach.
              </span>
            </p>

            {!liveRun.ready && (
              <div className="dialog-error" role="alert">
                {liveRun.blockedReason ?? "The CLI run is not ready on this bridge."}
              </div>
            )}
            {!countIsValid && (
              <div className="dialog-error" role="alert">
                Choose a whole number from {customerLimits.minimum} through {customerLimits.maximum}.
              </div>
            )}
            {error && <div className="dialog-error" role="alert">{error}</div>}

            <button
              className="run-submit"
              type="button"
              aria-busy={running}
              onClick={() => {
                if (liveRun.ready && countIsValid) void onRun(customers);
              }}
              disabled={running || !liveRun.ready || !countIsValid}
            >
              {running ? (
                <><LoaderCircle className="spin" size={18} /> Starting CLI…</>
              ) : (
                <><Play size={18} /> Run WhyBack CLI</>
              )}
            </button>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
