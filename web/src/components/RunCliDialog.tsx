/** Collects the one portfolio choice needed to start a new analysis. */

import { BrainCircuit, LoaderCircle, Play, ShieldCheck, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type {
  DeclineThreshold,
  DemoCustomerLimits,
  LiveRunConfiguration,
  PopulationSummary,
} from "../types";
import { formatNumber, productMessage } from "../lib/report";

interface RunCliDialogProps {
  open: boolean;
  running: boolean;
  error: string | null;
  customerLimits: DemoCustomerLimits;
  liveRun: LiveRunConfiguration;
  initialCustomers?: number | null;
  initialDeclineThreshold?: number | null;
  thresholdSensitivity?: PopulationSummary["threshold_sensitivity"];
  onClose: () => void;
  onRun: (
    customers: number,
    declineThreshold: DeclineThreshold,
  ) => Promise<void>;
}

const DEFAULT_CUSTOMERS = 5;
const DEFAULT_DECLINE_THRESHOLD: DeclineThreshold = 0.3;
const sensitivityOptions: ReadonlyArray<{
  label: string;
  threshold: DeclineThreshold;
  description: string;
}> = [
  {
    label: "Broad",
    threshold: 0.2,
    description: "More households can qualify",
  },
  {
    label: "Standard",
    threshold: 0.3,
    description: "Declared portfolio default",
  },
  {
    label: "Focused",
    threshold: 0.4,
    description: "Stronger decline signals",
  },
];

/** Mounts fresh launcher state whenever a new dialog session begins. */
export function RunCliDialog(props: RunCliDialogProps) {
  return (
    <AnimatePresence>
      {props.open && <RunCliDialogContent {...props} />}
    </AnimatePresence>
  );
}

/** Renders a compact, product-oriented analysis launcher. */
function RunCliDialogContent({
  running,
  error,
  customerLimits,
  liveRun,
  initialCustomers,
  initialDeclineThreshold,
  thresholdSensitivity,
  onClose,
  onRun,
}: RunCliDialogProps) {
  const reduceMotion = useReducedMotion();
  const [customerInput, setCustomerInput] = useState(() =>
    String(boundedInitialCustomers(customerLimits, initialCustomers)),
  );
  const [declineThreshold, setDeclineThreshold] = useState<DeclineThreshold>(
    () => declaredDeclineThreshold(initialDeclineThreshold),
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
  }, []);

  const customers = Number(customerInput);
  const countIsValid =
    Number.isInteger(customers) &&
    customers >= customerLimits.minimum &&
    customers <= customerLimits.maximum;

  return (
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
          aria-label="Close new analysis dialog"
        >
          <X size={18} />
        </button>

        <div className="run-dialog__title">
          <span><BrainCircuit size={18} /></span>
          <div>
            <span className="eyebrow">New analysis</span>
            <h2 id="run-cli-title">Review a household cohort</h2>
          </div>
        </div>

        <dl className="run-config-summary">
          <div><dt>Coverage</dt><dd>Official data</dd></div>
          <div><dt>Comparison</dt><dd>Nested cohorts</dd></div>
          <div><dt>Guardrail</dt><dd><ShieldCheck size={12} /> Human review</dd></div>
        </dl>

        <label className="customer-count-field">
          <span>Households to investigate</span>
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
          Choose {customerLimits.minimum}–{customerLimits.maximum}. WhyBack reviews the highest-ranked eligible households and keeps the broader population aggregated.
        </p>

        <fieldset
          className="review-sensitivity"
          aria-describedby="review-sensitivity-help"
          data-motion={reduceMotion ? "reduced" : "animated"}
          disabled={running || !liveRun.ready}
        >
          <legend>Review sensitivity</legend>
          <div className="review-sensitivity__choices">
            {sensitivityOptions.map((option) => {
              const selected = declineThreshold === option.threshold;
              const snapshot = thresholdSensitivity?.find(
                (item) => item.threshold === option.threshold,
              );
              const description =
                snapshot?.flagged_households !== null &&
                snapshot?.flagged_households !== undefined &&
                snapshot.eligible_households !== null
                  ? `${formatNumber(snapshot.flagged_households)} / ${formatNumber(snapshot.eligible_households)} flagged`
                  : option.description;
              return (
                <label
                  className={`sensitivity-choice ${selected ? "sensitivity-choice--selected" : ""}`}
                  key={option.threshold}
                >
                  <input
                    type="radio"
                    name="decline-threshold"
                    value={option.threshold}
                    checked={selected}
                    onChange={() => setDeclineThreshold(option.threshold)}
                  />
                  <span>
                    <strong>{option.label}</strong>
                    <small>≥ {Math.round(option.threshold * 100)}% decline score</small>
                  </span>
                  <small>{description}</small>
                  {selected && (
                    <motion.i
                      aria-hidden="true"
                      className="sensitivity-choice__indicator"
                      initial={reduceMotion ? false : { opacity: 0, scaleX: 0.35 }}
                      animate={{ opacity: 1, scaleX: 1 }}
                      transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
                    />
                  )}
                </label>
              );
            })}
          </div>
          <p id="review-sensitivity-help">
            Sets which eligible households enter the flagged cohort. Snapshot counts may
            change with new data. Recommendation evidence rules stay fixed at every
            setting; the score is not a churn probability.
          </p>
        </fieldset>

        <p className="run-boundary">
          <ShieldCheck size={15} />
          <span>
            Previous analyses remain available in history. Every metric is verified before display, recommendations require human review, and no outreach is executed automatically.
          </span>
        </p>

        {!liveRun.ready && (
          <div className="dialog-error" role="alert">
            {liveRun.blockedReason ? productMessage(liveRun.blockedReason, "Analysis is temporarily unavailable.") : "Analysis is temporarily unavailable. Check the secure model connection."}
          </div>
        )}
        {!countIsValid && (
          <div className="dialog-error" role="alert">
            Choose a whole number from {customerLimits.minimum} through {customerLimits.maximum}.
          </div>
        )}
        {error && <div className="dialog-error" role="alert">{productMessage(error, "The analysis could not start.")}</div>}

        <button
          className="run-submit"
          type="button"
          aria-busy={running}
          onClick={() => {
            if (liveRun.ready && countIsValid) {
              void onRun(customers, declineThreshold);
            }
          }}
          disabled={running || !liveRun.ready || !countIsValid}
        >
          {running ? (
            <><LoaderCircle className="spin" size={18} /> Starting analysis…</>
          ) : (
            <><Play size={18} /> Start analysis</>
          )}
        </button>
      </motion.section>
    </motion.div>
  );
}

/** Chooses a safe launcher default from the visible run or the product default. */
function boundedInitialCustomers(
  customerLimits: DemoCustomerLimits,
  requested: number | null | undefined,
): number {
  const candidate = Number.isInteger(requested) ? requested! : DEFAULT_CUSTOMERS;
  return Math.min(
    customerLimits.maximum,
    Math.max(customerLimits.minimum, candidate),
  );
}

/** Reuses a verified collection threshold only when it is a declared run choice. */
function declaredDeclineThreshold(
  requested: number | null | undefined,
): DeclineThreshold {
  return requested === 0.2 || requested === 0.3 || requested === 0.4
    ? requested
    : DEFAULT_DECLINE_THRESHOLD;
}
