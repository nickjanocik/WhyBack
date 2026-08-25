import { CheckCircle2, Command, LoaderCircle, Play, ShieldCheck, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

interface RunDemoDialogProps {
  open: boolean;
  running: boolean;
  error: string | null;
  onClose: () => void;
  onRun: (customers: number) => Promise<void>;
}

export function RunDemoDialog({ open, running, error, onClose, onRun }: RunDemoDialogProps) {
  const reduceMotion = useReducedMotion();
  const [customers, setCustomers] = useState(5);
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
            <div className="run-dialog__icon"><Play size={21} fill="currentColor" /></div>
            <span className="eyebrow">Credential-free workspace</span>
            <h2 id="run-demo-title">Run the WhyBack demo</h2>
            <p>
              Generate fresh, deterministic investigations through the real CLI and open the resulting artifacts here.
            </p>

            <fieldset disabled={running}>
              <legend>Households to investigate</legend>
              <div className="count-picker">
                {[1, 2, 3, 4, 5].map((count) => (
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

            <div className="command-preview">
              <Command size={16} />
              <code>uv run whyback demo --customers {customers} --backend scripted …</code>
            </div>

            <div className="safety-row">
              <ShieldCheck size={18} />
              <div><strong>Safe local control</strong><span>No model key, raw-data upload, outreach, or CRM mutation.</span></div>
            </div>

            {error && <div className="dialog-error" role="alert">{error}</div>}

            <button className="run-submit" type="button" onClick={() => void onRun(customers)} disabled={running}>
              {running ? <><LoaderCircle className="spin" size={18} /> Investigator running…</> : <><CheckCircle2 size={18} /> Generate investigations</>}
            </button>
            {running && <p className="running-note" role="status">The bounded Python pipeline is calculating and verifying evidence.</p>}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
