import {
  Activity,
  CircleCheck,
  CircleAlert,
  FileSearch,
  FlaskConical,
  LoaderCircle,
  Menu,
  Play,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, getDemoStatus, getInvestigation, getWorkspace, runDemo } from "./api";
import { AuditPanel } from "./components/AuditPanel";
import { CandidateRail } from "./components/CandidateRail";
import { EvidencePanel } from "./components/EvidencePanel";
import { LiveTraceDrawer } from "./components/LiveTraceDrawer";
import { OverviewPanel } from "./components/OverviewPanel";
import { RunDemoDialog } from "./components/RunDemoDialog";
import type { DemoStatusResponse, InvestigationResponse, Workspace } from "./types";

type View = "overview" | "evidence" | "audit";

const views: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "overview", label: "Investigation", icon: FileSearch },
  { id: "evidence", label: "Evidence", icon: FlaskConical },
  { id: "audit", label: "Audit replay", icon: ShieldCheck },
];

const emptyLiveStatus: DemoStatusResponse = {
  jobId: null,
  status: "idle",
  customers: null,
  command: null,
  startedAt: null,
  completedAt: null,
  cursor: 0,
  eventCount: 0,
  droppedEventCount: 0,
  events: [],
  error: null,
  traceWarning: null,
  collectionId: null,
};

function initialView(): View {
  const candidate = new URLSearchParams(window.location.search).get("view");
  return candidate === "evidence" || candidate === "audit" ? candidate : "overview";
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [collectionId, setCollectionId] = useState("");
  const [householdId, setHouseholdId] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [view, setView] = useState<View>(initialView);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [demoStarting, setDemoStarting] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<DemoStatusResponse>(emptyLiveStatus);
  const [liveOpen, setLiveOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLButtonElement>(null);
  const activeJobRef = useRef<string | null>(null);
  const liveCursorRef = useRef(0);
  const refreshedJobRef = useRef<string | null>(null);

  const selectedCollection = useMemo(
    () => workspace?.collections.find((item) => item.id === collectionId),
    [collectionId, workspace],
  );
  const selectedGeneratedAt = selectedCollection?.reports.find(
    (item) => item.householdId === householdId,
  )?.generatedAt;

  const initializeWorkspace = useCallback((nextWorkspace: Workspace, preferredCollection?: string) => {
    setLoading(true);
    setWorkspace(nextWorkspace);
    const collection =
      nextWorkspace.collections.find((item) => item.id === preferredCollection) ??
      nextWorkspace.collections.find((item) => item.id === "dashboard") ??
      nextWorkspace.collections.find((item) => item.id === "demo") ??
      nextWorkspace.collections[0];
    if (!collection) {
      setError("No WhyBack report artifacts are available. Run a scripted batch to create them.");
      setLoading(false);
      return;
    }
    setCollectionId(collection.id);
    setHouseholdId(collection.reports[0]?.householdId ?? "");
    setError(null);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getWorkspace(controller.signal)
      .then((value) => initializeWorkspace(value))
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setError(caught instanceof Error ? caught.message : "Could not reach the local WhyBack bridge.");
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [initializeWorkspace]);

  useEffect(() => {
    const controller = new AbortController();
    getDemoStatus(null, 0, controller.signal)
      .then((status) => {
        if (activeJobRef.current && activeJobRef.current !== status.jobId) return;
        activeJobRef.current = status.jobId;
        liveCursorRef.current = status.cursor;
        if (status.status !== "running") {
          refreshedJobRef.current = status.jobId;
        }
        setLiveStatus(status);
        if (status.status === "running") setLiveOpen(true);
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setLiveStatus((current) => ({
            ...current,
            traceWarning:
              caught instanceof Error ? caught.message : "Could not load live run status.",
          }));
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (liveStatus.status !== "running" || !liveStatus.jobId) return;
    const controller = new AbortController();
    const jobId = liveStatus.jobId;
    let timer: number | undefined;

    async function poll() {
      try {
        const status = await getDemoStatus(
          jobId,
          liveCursorRef.current,
          controller.signal,
        );
        liveCursorRef.current = status.cursor;
        setLiveStatus((current) => mergeLiveStatus(current, status));
        if (status.status === "running") {
          timer = window.setTimeout(() => void poll(), 400);
        }
      } catch (caught) {
        if ((caught as { name?: string }).name === "AbortError") return;
        if (caught instanceof ApiError && caught.status === 404) {
          activeJobRef.current = null;
          setLiveStatus((current) => ({
            ...current,
            status: "failed",
            completedAt: new Date().toISOString(),
            error:
              "This run is no longer available. The local dashboard bridge may have restarted.",
            traceWarning: null,
          }));
          return;
        }
        setLiveStatus((current) => ({
          ...current,
          traceWarning:
            caught instanceof Error ? caught.message : "Live trace polling failed.",
        }));
        timer = window.setTimeout(() => void poll(), 800);
      }
    }

    void poll();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [liveStatus.jobId, liveStatus.status]);

  useEffect(() => {
    if (
      liveStatus.status !== "completed" ||
      !liveStatus.jobId ||
      refreshedJobRef.current === liveStatus.jobId
    ) {
      return;
    }
    refreshedJobRef.current = liveStatus.jobId;
    const controller = new AbortController();
    getWorkspace(controller.signal)
      .then((nextWorkspace) => {
        initializeWorkspace(nextWorkspace, "dashboard");
        setToast(
          `${liveStatus.customers ?? 0} investigation${liveStatus.customers === 1 ? "" : "s"} completed.`,
        );
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setToast("Run completed, but the workspace refresh failed.");
        }
      });
    return () => controller.abort();
  }, [initializeWorkspace, liveStatus.customers, liveStatus.jobId, liveStatus.status]);

  useEffect(() => {
    if (!collectionId || !householdId) return;
    const controller = new AbortController();
    getInvestigation(collectionId, householdId, controller.signal)
      .then((value) => {
        setInvestigation(value);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setError(caught instanceof Error ? caught.message : "Could not load the investigation.");
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [collectionId, householdId, selectedGeneratedAt]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4_500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function changeCollection(nextId: string) {
    const next = workspace?.collections.find((item) => item.id === nextId);
    if (!next) return;
    setLoading(true);
    setError(null);
    setSelectedEvidenceId(null);
    setCollectionId(next.id);
    setHouseholdId(next.reports[0]?.householdId ?? "");
    changeView("overview");
  }

  function selectEvidence(evidenceId: string) {
    setSelectedEvidenceId(evidenceId);
    changeView("evidence");
  }

  function changeView(nextView: View) {
    setView(nextView);
    const url = new URL(window.location.href);
    if (nextView === "overview") url.searchParams.delete("view");
    else url.searchParams.set("view", nextView);
    window.history.replaceState(null, "", url);
  }

  async function handleRunDemo(customers: number) {
    setDemoStarting(true);
    setDemoError(null);
    try {
      const status = await runDemo(customers);
      activeJobRef.current = status.jobId;
      liveCursorRef.current = status.cursor;
      refreshedJobRef.current = null;
      setLiveStatus(status);
      setDialogOpen(false);
      setLiveOpen(true);
    } catch (caught) {
      setDemoError(caught instanceof Error ? caught.message : "The scripted run could not start.");
    } finally {
      setDemoStarting(false);
    }
  }

  const demoRunning = liveStatus.status === "running";
  const demoBusy = demoStarting || demoRunning;

  return (
    <div className="app-shell">
      <div className="app-content">
        <a className="skip-link" href="#main-investigation">Skip to investigation</a>
        <header className="app-header">
          <button
            ref={mobileMenuRef}
            className="mobile-menu"
            type="button"
            onClick={() => setRailOpen((value) => !value)}
            aria-label="Toggle investigations"
            aria-expanded={railOpen}
            aria-controls="candidate-rail"
          >
            {railOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="internal-brand"><strong>WhyBack</strong><span>Investigator</span></div>
          <div className="header-actions">
            <button
              className={`live-toggle ${liveOpen ? "active" : ""}`}
              type="button"
              onClick={() => setLiveOpen((value) => !value)}
              aria-label={`${liveOpen ? "Close" : "Open"} live audit trace`}
              aria-expanded={liveOpen}
              aria-controls="live-trace-drawer"
            >
              <Activity size={15} />
              <span className="live-toggle__label">Live activity</span>
              {demoRunning ? <i aria-label="Run active" /> : liveStatus.eventCount > 0 ? <span className="live-toggle__count">{liveStatus.eventCount}</span> : null}
            </button>
            <button
              className="run-button"
              type="button"
              disabled={demoBusy}
              onClick={() => { setDemoError(null); setDialogOpen(true); }}
              aria-label={demoRunning ? "Scripted batch running" : "Run scripted batch"}
            >
              {demoRunning ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}
              <span className="run-button__label">{demoRunning ? "Running" : "Run scripted batch"}</span>
            </button>
          </div>
        </header>

      <div className={`workspace-layout ${railOpen ? "workspace-layout--rail-open" : ""}`}>
        {workspace && workspace.collections.length > 0 && (
          <CandidateRail
            collections={workspace.collections}
            collectionId={collectionId}
            householdId={householdId}
            onCollectionChange={changeCollection}
            onHouseholdChange={(value) => {
              const returnFocusToMenu = railOpen;
              setLoading(true);
              setError(null);
              setSelectedEvidenceId(null);
              setHouseholdId(value);
              setRailOpen(false);
              if (returnFocusToMenu) {
                window.requestAnimationFrame(() => mobileMenuRef.current?.focus());
              }
            }}
          />
        )}
        <main className="main-workspace" id="main-investigation" tabIndex={-1}>
          <div className="workspace-toolbar">
            <nav aria-label="Investigation views">
              {views.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    type="button"
                    key={item.id}
                    className={view === item.id ? "active" : ""}
                    aria-current={view === item.id ? "page" : undefined}
                    onClick={() => changeView(item.id)}
                  >
                    <Icon size={15} /> {item.label}
                    {item.id === "evidence" && investigation && <span>{investigation.report.evidence_ledger.length}</span>}
                  </button>
                );
              })}
            </nav>
            <div className="toolbar-context">
              <span>{selectedCollection?.title}</span>
              <i />
              <span>Household {householdId || "—"}</span>
            </div>
          </div>

          <div className="workspace-scroll">
            {workspace && workspace.collectionWarnings.length > 0 && (
              <div className="collection-warning" role="status">
                <CircleAlert size={16} />
                <span>{workspace.collectionWarnings.join(" ")}</span>
              </div>
            )}
            {loading && <LoadingState />}
            {!loading && error && <ErrorState message={error} onRetry={() => window.location.reload()} />}
            {!loading && !error && investigation && (
              <div key={`${investigation.report.run_id}-${view}`}>
                {view === "overview" && <OverviewPanel report={investigation.report} onEvidenceSelect={selectEvidence} />}
                {view === "evidence" && <EvidencePanel report={investigation.report} selectedEvidenceId={selectedEvidenceId} onEvidenceSelect={setSelectedEvidenceId} />}
                {view === "audit" && <AuditPanel collectionId={collectionId} report={investigation.report} trace={investigation.trace} />}
              </div>
            )}
          </div>
        </main>
      </div>
        <LiveTraceDrawer
          open={liveOpen}
          status={liveStatus}
          onClose={() => setLiveOpen(false)}
          onOpenResults={() => {
            setLiveOpen(false);
            changeView("overview");
          }}
          onStartRun={() => {
            setLiveOpen(false);
            setDemoError(null);
            setDialogOpen(true);
          }}
        />
      </div>

      <RunDemoDialog open={dialogOpen} running={demoStarting} error={demoError} onClose={() => !demoStarting && setDialogOpen(false)} onRun={handleRunDemo} />
      <AnimatePresence>{toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}><CircleCheck size={18} /><span>{toast}</span></motion.div>}</AnimatePresence>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label="Loading investigation">
      <LoaderCircle className="spin" size={26} />
      <strong>Loading investigation…</strong>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-state" role="alert"><CircleAlert size={28} /><h1>Investigation unavailable</h1><p>{message}</p><button type="button" onClick={onRetry}><RefreshCw size={15} /> Try again</button></div>
  );
}

function mergeLiveStatus(
  current: DemoStatusResponse,
  update: DemoStatusResponse,
): DemoStatusResponse {
  if (!current.jobId || current.jobId !== update.jobId) return update;
  const ids = new Set(current.events.map((event) => event.id));
  const events = [
    ...current.events,
    ...update.events.filter((event) => !ids.has(event.id)),
  ].slice(-1_500);
  return { ...update, events };
}
