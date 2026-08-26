/** Coordinates CLI execution, live audit activity, and verified report review. */

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
  Terminal,
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
import { RunCliDialog } from "./components/RunCliDialog";
import type {
  DemoCustomerLimits,
  DemoStatusResponse,
  InvestigationResponse,
  LiveRunConfiguration,
  Workspace,
} from "./types";

type View = "overview" | "evidence" | "audit";

const views: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "overview", label: "Investigation", icon: FileSearch },
  { id: "evidence", label: "Evidence", icon: FlaskConical },
  { id: "audit", label: "Audit replay", icon: ShieldCheck },
];

const emptyLiveStatus: DemoStatusResponse = {
  jobId: null,
  status: "idle",
  backend: "gemini",
  model: "",
  customers: null,
  command: null,
  startedAt: null,
  completedAt: null,
  cursor: 0,
  eventCount: 0,
  eventCapacity: 0,
  droppedEventCount: 0,
  events: [],
  error: null,
  traceWarning: null,
  collectionId: null,
};

/** Reads the optional view query parameter while falling back to the investigation. */
function initialView(): View {
  const candidate = new URLSearchParams(window.location.search).get("view");
  return candidate === "evidence" || candidate === "audit" ? candidate : "overview";
}

/** Renders the complete WhyBack reviewer workspace and owns its application state. */
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
  const [runStarting, setRunStarting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<DemoStatusResponse>(emptyLiveStatus);
  const [liveOpen, setLiveOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [workspaceRefreshAttempt, setWorkspaceRefreshAttempt] = useState(0);
  const [reportRefreshFailed, setReportRefreshFailed] = useState(false);
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

  /** Selects the preferred verified CLI run and handles an honestly empty workspace. */
  const initializeWorkspace = useCallback((nextWorkspace: Workspace, preferredCollection?: string) => {
    setLoading(true);
    setWorkspace(nextWorkspace);
    const collection =
      nextWorkspace.collections.find((item) => item.id === preferredCollection) ??
      nextWorkspace.collections[0];
    if (!collection) {
      setCollectionId("");
      setHouseholdId("");
      setInvestigation(null);
      setError(null);
      setLoading(false);
      return;
    }
    setCollectionId(collection.id);
    setHouseholdId(collection.reports[0]?.householdId ?? "");
    setError(null);
  }, []);

  // Load the artifact catalog once and cancel the request if React unmounts the app.
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

  // Recover the bridge's latest in-memory job so a page refresh does not hide active work.
  useEffect(() => {
    const controller = new AbortController();
    getDemoStatus(null, 0, controller.signal)
      .then((status) => {
        if (activeJobRef.current && activeJobRef.current !== status.jobId) return;
        activeJobRef.current = status.jobId;
        liveCursorRef.current = status.cursor;
        if (status.status !== "running" && status.status !== "completed") {
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

  // Poll only the active job and merge cursor deltas without replaying older events.
  useEffect(() => {
    if (liveStatus.status !== "running" || !liveStatus.jobId) return;
    const controller = new AbortController();
    const jobId = liveStatus.jobId;
    let timer: number | undefined;

    /** Fetches the next live-status delta and schedules another bounded poll if needed. */
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

  // Refresh sealed artifacts after completion, retrying brief publication races a few times.
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
    let retryTimer: number | undefined;
    getWorkspace(controller.signal)
      .then((nextWorkspace) => {
        setWorkspaceRefreshAttempt(0);
        setReportRefreshFailed(false);
        initializeWorkspace(nextWorkspace, liveStatus.collectionId ?? undefined);
        setToast("CLI run verified. Reports refreshed.");
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setToast("CLI run finished, but the report list could not be refreshed.");
          if (workspaceRefreshAttempt < 3) {
            retryTimer = window.setTimeout(() => {
              refreshedJobRef.current = null;
              setWorkspaceRefreshAttempt((attempt) => attempt + 1);
            }, 500 * (workspaceRefreshAttempt + 1));
          } else {
            setReportRefreshFailed(true);
          }
        }
      });
    return () => {
      controller.abort();
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    };
  }, [
    initializeWorkspace,
    liveStatus.collectionId,
    liveStatus.jobId,
    liveStatus.status,
    workspaceRefreshAttempt,
  ]);

  // Load the selected household's report and trace whenever its artifact identity changes.
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

  // Remove transient completion notices after enough time for assistive technology to read them.
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4_500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  /** Switches collections and selects the first household in canonical report order. */
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

  /** Opens the evidence view with one cited ledger record selected. */
  function selectEvidence(evidenceId: string) {
    setSelectedEvidenceId(evidenceId);
    changeView("evidence");
  }

  /** Changes the visible panel and mirrors non-default views in the URL. */
  function changeView(nextView: View) {
    setView(nextView);
    const url = new URL(window.location.href);
    if (nextView === "overview") url.searchParams.delete("view");
    else url.searchParams.set("view", nextView);
    window.history.replaceState(null, "", url);
  }

  /** Starts a live batch and opens its audit drawer without waiting for completion. */
  async function handleRunCli(customers: number) {
    setRunStarting(true);
    setRunError(null);
    try {
      const status = await runDemo(customers);
      activeJobRef.current = status.jobId;
      liveCursorRef.current = status.cursor;
      refreshedJobRef.current = null;
      setWorkspaceRefreshAttempt(0);
      setReportRefreshFailed(false);
      setLiveStatus(status);
      setDialogOpen(false);
      setLiveOpen(true);
    } catch (caught) {
      setRunError(caught instanceof Error ? caught.message : "The WhyBack CLI could not start.");
    } finally {
      setRunStarting(false);
    }
  }

  /** Recovers a verified collection after automatic publication refresh is exhausted. */
  async function handleRefreshReports() {
    setLoading(true);
    try {
      const nextWorkspace = await getWorkspace();
      setWorkspaceRefreshAttempt(0);
      setReportRefreshFailed(false);
      initializeWorkspace(nextWorkspace, liveStatus.collectionId ?? undefined);
      setLiveOpen(false);
      setToast("Verified CLI reports reloaded.");
    } catch {
      setLoading(false);
      setReportRefreshFailed(true);
      setToast("The verified report list could not be reloaded. Try again.");
    }
  }

  const runRunning = liveStatus.status === "running";
  const runBusy = runStarting || runRunning;
  const customerLimits = workspace?.demoCustomerLimits;
  const liveRun = workspace?.liveRun;
  const hasReports = Boolean(selectedCollection && householdId);
  const priorRunCustomerCount =
    selectedCollection && selectedCollection.reportCount > 0
      ? selectedCollection.reportCount
      : liveStatus.customers;

  /** Opens the bounded launcher for a uniquely owned CLI run. */
  function openNewRun() {
    setRunError(null);
    setDialogOpen(true);
  }

  return (
    <div className="app-shell">
      <div className="app-content">
        <a className="skip-link" href="#main-investigation">Skip to investigation</a>
        <header className="app-header">
          {hasReports && (
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
          )}
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
              {runRunning ? <i aria-label="Run active" /> : liveStatus.eventCount > 0 ? <span className="live-toggle__count">{liveStatus.eventCount}</span> : null}
            </button>
            <button
              className="run-button"
              type="button"
              disabled={runBusy || !customerLimits || !liveRun}
              onClick={openNewRun}
              aria-label={runRunning ? "WhyBack CLI running" : "Start a new WhyBack CLI run"}
            >
              {runRunning ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}
              <span className="run-button__label">{runRunning ? "CLI running" : "New run"}</span>
            </button>
          </div>
        </header>

      <div className={`workspace-layout ${railOpen ? "workspace-layout--rail-open" : ""} ${hasReports ? "" : "workspace-layout--empty"}`}>
        {workspace && hasReports && (
          <CandidateRail
            collections={workspace.collections}
            collectionId={collectionId}
            householdId={householdId}
            onCollectionChange={changeCollection}
            onHouseholdChange={(value) => {
              // Closing the mobile rail returns focus to its trigger after selection.
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
          {hasReports && (
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
                <span>Household {householdId}</span>
              </div>
            </div>
          )}

          <div className="workspace-scroll">
            {workspace && workspace.collectionWarnings.length > 0 && (
              <div className="collection-warning" role="status">
                <CircleAlert size={16} />
                <span>{workspace.collectionWarnings.join(" ")}</span>
              </div>
            )}
            {loading && <LoadingState />}
            {!loading && error && <ErrorState message={error} onRetry={() => window.location.reload()} />}
            {!loading && !error && workspace && !hasReports && customerLimits && liveRun && (
              <EmptyWorkspace
                customerLimits={customerLimits}
                liveRun={liveRun}
                status={liveStatus}
                onOpenActivity={() => setLiveOpen(true)}
                onStart={openNewRun}
              />
            )}
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
          hasVisibleReport={hasReports}
          reportRefreshFailed={reportRefreshFailed}
          onClose={() => setLiveOpen(false)}
          onRefreshReports={() => void handleRefreshReports()}
          onStartRun={() => {
            setLiveOpen(false);
            openNewRun();
          }}
        />
      </div>

      {customerLimits && liveRun && (
        <RunCliDialog
          open={dialogOpen}
          running={runStarting}
          error={runError}
          customerLimits={customerLimits}
          liveRun={liveRun}
          initialCustomers={priorRunCustomerCount}
          onClose={() => !runStarting && setDialogOpen(false)}
          onRun={handleRunCli}
        />
      )}
      <AnimatePresence>{toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}><CircleCheck size={18} /><span>{toast}</span></motion.div>}</AnimatePresence>
    </div>
  );
}

/** Explains an empty operational workspace and offers the single useful next action. */
function EmptyWorkspace({
  customerLimits,
  liveRun,
  status,
  onOpenActivity,
  onStart,
}: {
  customerLimits: DemoCustomerLimits;
  liveRun: LiveRunConfiguration;
  status: DemoStatusResponse;
  onOpenActivity: () => void;
  onStart: () => void;
}) {
  const running = status.status === "running";
  return (
    <section className="empty-workspace" aria-labelledby="empty-workspace-title">
      <div className="empty-workspace__icon"><Terminal size={24} /></div>
      <span className="eyebrow">CLI workspace</span>
      <h1 id="empty-workspace-title">
        {running ? "Investigation in progress" : "No verified CLI runs yet"}
      </h1>
      <p>
        {running
          ? "The CLI is investigating households now. Reports appear here only after the run passes deterministic verification."
          : "Start the WhyBack CLI against official prepared data. This workspace intentionally excludes bundled examples and unverified output."}
      </p>

      <div className="empty-workspace__facts" aria-label="CLI configuration">
        <span><small>Backend</small>Gemini API</span>
        <span><small>Model</small><code>{liveRun.model}</code></span>
        <span><small>Batch range</small>{customerLimits.minimum}–{customerLimits.maximum} households</span>
      </div>

      {!liveRun.ready && !running && (
        <div className="empty-workspace__notice" role="status">
          <CircleAlert size={16} />
          <span>{liveRun.blockedReason ?? "The local CLI is not ready."}</span>
        </div>
      )}
      {status.status === "failed" && (
        <div className="empty-workspace__notice empty-workspace__notice--failed" role="alert">
          <CircleAlert size={16} />
          <span>
            <strong>The last CLI run was not published.</strong>{" "}
            {status.error ?? "It did not produce a verified report collection."}
          </span>
        </div>
      )}

      <button
        className="empty-workspace__action"
        type="button"
        onClick={running ? onOpenActivity : onStart}
      >
        {running ? <><Activity size={17} /> View CLI activity</> : <><Play size={17} /> Configure CLI run</>}
      </button>
    </section>
  );
}

/** Shows the shared accessible placeholder while a report request is pending. */
function LoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label="Loading investigation">
      <LoaderCircle className="spin" size={26} />
      <strong>Loading investigation…</strong>
    </div>
  );
}

/** Shows a terminal workspace-loading error with an explicit retry action. */
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-state" role="alert"><CircleAlert size={28} /><h1>Investigation unavailable</h1><p>{message}</p><button type="button" onClick={onRetry}><RefreshCw size={15} /> Try again</button></div>
  );
}

/** Merges cursor-based event deltas while keeping only the server's bounded capacity. */
function mergeLiveStatus(
  current: DemoStatusResponse,
  update: DemoStatusResponse,
): DemoStatusResponse {
  if (!current.jobId || current.jobId !== update.jobId) return update;
  const ids = new Set(current.events.map((event) => event.id));
  const events = [
    ...current.events,
    ...update.events.filter((event) => !ids.has(event.id)),
  ].slice(-Math.max(1, update.eventCapacity));
  return { ...update, events };
}
