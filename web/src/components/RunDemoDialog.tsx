import { LoaderCircle, Play, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type { DemoCustomerLimits, LiveRunConfiguration } from "../types";

interface RunDemoDialogProps {
  open: boolean;
  running: boolean;
  error: string | null;
  customerLimits: DemoCustomerLimits;
  liveRun: LiveRunConfiguration;
  onClose: () => void;
  onRun: (customers: number) => Promise<void>;
}

export function RunDemoDialog({
  open,
  running,
  error,
  customerLimits,
  liveRun,
  onClose,
  onRun,
}: RunDemoDialogProps) {
  const reduceMotion = useReducedMotion();
  const [customers, setCustomers] = useState(customerLimits.minimum);
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  const runningRef = useRef(running);

  useEffect(() => {
    onCloseRef.current = onClose;
    runningRef.current = running;
  }, [onClose, running]);

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const appContent = document.querySelector<HTMLElement>(".app-content");
    appContent?.setAttribute("inert", "");
    const focusFrame = window.requestAnimationFrame(() => dialogRef.current?.focus());

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
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0]!;
      const last = focusable.at(-1);
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialog || !dialog.contains(active))) {
        event.preventDefault();
        last?.focus();
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
            aria-labelledby="run-demo-title"
            tabIndex={-1}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 12 }}
            transition={{ type: "spring", stiffness: 360, damping: 30 }}
          >
            <button className="dialog-close" type="button" onClick={onClose} disabled={running} aria-label="Close">
              <X size={18} />
            </button>
            <span className="eyebrow">Live Gemini batch</span>
            <h2 id="run-demo-title">Run live Gemini investigations</h2>
            <p>
              Use {liveRun.model} through the Gemini API. The API key stays in local server-side processes and is never sent to the browser.
            </p>

            <fieldset disabled={running || !liveRun.ready}>
              <legend>
                Households to investigate ({customerLimits.minimum}–{customerLimits.maximum})
              </legend>
              <div className="count-picker">
                {batchSizeOptions(customerLimits).map((count) => (
                  <button
                    type="button"
                    className={count === customers ? "active" : ""}
                    aria-pressed={count === customers}
                    onClick={() => setCustomers(count)}
                    key={count}
                  >
                    {count}
                  </button>
                ))}
              </div>
            </fieldset>

            <p className="run-boundary">
              This makes real provider calls and may consume quota. Each household may use up to six live Gemini decisions. Deterministic Python tools calculate the evidence, and no outreach or customer action is executed.
            </p>

            {!liveRun.ready && (
              <div className="dialog-error" role="alert">
                {liveRun.blockedReason ?? "Live Gemini runs are not configured on this local bridge."}
              </div>
            )}
            {error && <div className="dialog-error" role="alert">{error}</div>}

            <button
              className="run-submit"
              type="button"
              aria-busy={running}
              onClick={() => { if (liveRun.ready) void onRun(customers); }}
              disabled={running || !liveRun.ready}
            >
              {running ? <><LoaderCircle className="spin" size={18} /> Starting live run…</> : <><Play size={18} /> Start live run</>}
            </button>
            {running && <p className="running-note" role="status">Starting the live Gemini process.</p>}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function batchSizeOptions({ minimum, maximum }: DemoCustomerLimits): number[] {
  const options = [];
  for (let count = minimum; count < maximum; count += 5) options.push(count);
  if (options.at(-1) !== maximum) options.push(maximum);
  return options;
}
