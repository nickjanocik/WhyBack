/** Coordinates live analysis, decision activity, and verified report review. */

import {
  Activity,
  CircleCheck,
  CircleAlert,
  ChartNoAxesCombined,
  FileSearch,
  FlaskConical,
  House,
  LoaderCircle,
  Menu,
  Network,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  getDemoStatus,
  getInvestigation,
  getPopulation,
  getWorkspace,
  runDemo,
} from "./api";
import { AuditPanel } from "./components/AuditPanel";
import { CandidateRail } from "./components/CandidateRail";
import { EvidencePanel } from "./components/EvidencePanel";
import { ExecutiveHome } from "./components/ExecutiveHome";
import { FactorMap } from "./components/FactorMap";
import { LiveTraceDrawer } from "./components/LiveTraceDrawer";
import { OverviewPanel } from "./components/OverviewPanel";
import { PopulationExplorer } from "./components/PopulationExplorer";
import { RunCliDialog } from "./components/RunCliDialog";
import { productMessage } from "./lib/report";
import type {
  DemoCustomerLimits,
  DemoStatusResponse,
  DeclineThreshold,
  InvestigationResponse,
  LiveRunConfiguration,
  PopulationSummary,
  Workspace,
} from "./types";

type View = "home" | "population" | "factors" | "investigation" | "evidence" | "audit";

const views: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "home", label: "Home", icon: House },
  { id: "population", label: "Populations", icon: ChartNoAxesCombined },
  { id: "factors", label: "Factors", icon: Network },
  { id: "investigation", label: "Investigation", icon: FileSearch },
  { id: "evidence", label: "Evidence", icon: FlaskConical },
  { id: "audit", label: "Audit", icon: ShieldCheck },
];

const householdViews = new Set<View>(["investigation", "evidence", "audit"]);

const emptyLiveStatus: DemoStatusResponse = {
  jobId: null,
  status: "idle",
  backend: "gemini",
  model: "",
  customers: null,
  declineThreshold: null,
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

/** Reads the optional view query parameter while making Home the default. */
function initialView(): View {
  const candidate = new URLSearchParams(window.location.search).get("view");
  if (candidate === "overview" || candidate === "investigation") return "investigation";
  return candidate === "population" || candidate === "factors" || candidate === "evidence" || candidate === "audit"
    ? candidate
    : "home";
}

/** Renders the complete WhyBack reviewer workspace and owns its application state. */
export default function App() {
  const reduceMotion = useReducedMotion();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [collectionId, setCollectionId] = useState("");
  const [householdId, setHouseholdId] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [population, setPopulation] = useState<PopulationSummary | null>(null);
  const [populationLoading, setPopulationLoading] = useState(false);
  const [populationError, setPopulationError] = useState<string | null>(null);
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
  const investigationRequestEpochRef = useRef(0);
  const workspaceResetRef = useRef(false);

  const selectedCollection = useMemo(
    () => workspace?.collections.find((item) => item.id === collectionId),
    [collectionId, workspace],
  );
  const selectedGeneratedAt = selectedCollection?.reports.find(
    (item) => item.householdId === householdId,
  )?.generatedAt;

  /** Clears the visible run and invalidates any report request already in flight. */
  const clearActiveWorkspace = useCallback(() => {
    workspaceResetRef.current = true;
    investigationRequestEpochRef.current += 1;
    setWorkspace((current) =>
      current
        ? { ...current, collections: [], collectionWarnings: [] }
        : current,
    );
    setCollectionId("");
    setHouseholdId("");
    setInvestigation(null);
    setSelectedEvidenceId(null);
    setLoading(false);
    setError(null);
    setRailOpen(false);
    setToast(null);
    setPopulation(null);
    setPopulationError(null);
    setPopulationLoading(false);
    setView("home");
    const url = new URL(window.location.href);
    url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
  }, []);

  /** Selects the preferred verified analysis and handles an honestly empty workspace. */
  const initializeWorkspace = useCallback((nextWorkspace: Workspace, preferredCollection?: string) => {
    investigationRequestEpochRef.current += 1;
    setInvestigation(null);
    setSelectedEvidenceId(null);
    if (workspaceResetRef.current && !preferredCollection) {
      setWorkspace({ ...nextWorkspace, collections: [], collectionWarnings: [] });
      setCollectionId("");
      setHouseholdId("");
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(false);
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
    if (preferredCollection) workspaceResetRef.current = false;
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
          setError(caught instanceof Error ? productMessage(caught.message, "WhyBack is temporarily unavailable.") : "WhyBack is temporarily unavailable.");
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
        if (status.status !== "idle") clearActiveWorkspace();
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
              caught instanceof Error ? productMessage(caught.message, "Could not load live analysis status.") : "Could not load live analysis status.",
          }));
        }
      });
    return () => controller.abort();
  }, [clearActiveWorkspace]);

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
              "This analysis is no longer available. The analytics service may have restarted.",
            traceWarning: null,
          }));
          return;
        }
        setLiveStatus((current) => ({
          ...current,
          traceWarning:
            caught instanceof Error ? productMessage(caught.message, "Live progress could not be refreshed.") : "Live progress could not be refreshed.",
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
        const publishedCollectionId = requirePublishedCollection(
          nextWorkspace,
          liveStatus.collectionId,
        );
        setWorkspaceRefreshAttempt(0);
        setReportRefreshFailed(false);
        initializeWorkspace(nextWorkspace, publishedCollectionId);
        setToast("Analysis complete. Dashboard insights are ready.");
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name !== "AbortError") {
          setToast("Analysis complete, but the dashboard could not refresh yet.");
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

  // Load the aggregate population contract once per selected collection.
  useEffect(() => {
    if (!collectionId) return;
    const controller = new AbortController();
    setPopulationLoading(true);
    setPopulationError(null);
    setPopulation(null);
    getPopulation(collectionId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setPopulation(value);
        setPopulationLoading(false);
      })
      .catch((caught: unknown) => {
        if ((caught as { name?: string }).name === "AbortError") return;
        setPopulationError(
          caught instanceof Error ? productMessage(caught.message, "Could not load population context.") : "Could not load population context.",
        );
        setPopulationLoading(false);
      });
    return () => controller.abort();
  }, [collectionId]);

  // Load a report and trace only after entering a household-level view.
  useEffect(() => {
    if (!collectionId || !householdId || !householdViews.has(view)) return;
    const controller = new AbortController();
    const requestEpoch = ++investigationRequestEpochRef.current;
    setLoading(true);
    setError(null);
    getInvestigation(collectionId, householdId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted || investigationRequestEpochRef.current !== requestEpoch) {
          return;
        }
        setInvestigation(value);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted || investigationRequestEpochRef.current !== requestEpoch) {
          return;
        }
        if ((caught as { name?: string }).name !== "AbortError") {
          setError(caught instanceof Error ? productMessage(caught.message, "Could not load the investigation.") : "Could not load the investigation.");
          setLoading(false);
        }
      });
    return () => {
      controller.abort();
      if (investigationRequestEpochRef.current === requestEpoch) {
        investigationRequestEpochRef.current += 1;
      }
    };
  }, [collectionId, householdId, selectedGeneratedAt, view]);

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
    investigationRequestEpochRef.current += 1;
    setLoading(false);
    setError(null);
    setSelectedEvidenceId(null);
    setInvestigation(null);
    setCollectionId(next.id);
    setHouseholdId(next.reports[0]?.householdId ?? "");
    changeView("home");
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
    if (nextView === "home") url.searchParams.delete("view");
    else url.searchParams.set("view", nextView);
    window.history.replaceState(null, "", url);
  }

  /** Selects an investigated household and enters its report view. */
  function openHousehold(nextHouseholdId: string) {
    investigationRequestEpochRef.current += 1;
    setLoading(true);
    setError(null);
    setSelectedEvidenceId(null);
    setInvestigation(null);
    setHouseholdId(nextHouseholdId);
    setRailOpen(false);
    changeView("investigation");
  }

  /** Starts a live batch and opens its audit drawer without waiting for completion. */
  async function handleRunCli(
    customers: number,
    declineThreshold: DeclineThreshold,
  ) {
    setRunStarting(true);
    setRunError(null);
    try {
      const status = await runDemo(customers, declineThreshold);
      activeJobRef.current = status.jobId;
      liveCursorRef.current = status.cursor;
      refreshedJobRef.current = null;
      clearActiveWorkspace();
      setWorkspaceRefreshAttempt(0);
      setReportRefreshFailed(false);
      setLiveStatus(status);
      setDialogOpen(false);
      setLiveOpen(true);
    } catch (caught) {
      setRunError(caught instanceof Error ? productMessage(caught.message, "The analysis could not start.") : "The analysis could not start.");
    } finally {
      setRunStarting(false);
    }
  }

  /** Recovers a verified collection after automatic publication refresh is exhausted. */
  async function handleRefreshReports() {
    setLoading(true);
    try {
      const nextWorkspace = await getWorkspace();
      const publishedCollectionId = requirePublishedCollection(
        nextWorkspace,
        liveStatus.collectionId,
      );
      setWorkspaceRefreshAttempt(0);
      setReportRefreshFailed(false);
      initializeWorkspace(nextWorkspace, publishedCollectionId);
      setLiveOpen(false);
      setToast("Dashboard insights reloaded.");
    } catch {
      setLoading(false);
      setReportRefreshFailed(true);
      setToast("The published report list could not be reloaded. Try again.");
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

  /** Opens the bounded launcher for a new portfolio analysis. */
  function openNewRun() {
    setRunError(null);
    setDialogOpen(true);
  }

  return (
    <div className="app-shell">
      <div className="app-content">
        <a className="skip-link" href="#main-dashboard">Skip to dashboard</a>
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
          <div className="internal-brand">
            <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
            <span className="brand-copy"><strong>WhyBack</strong><small>Population Intelligence</small></span>
          </div>
          <div className="header-actions">
            <button
              className={`live-toggle ${liveOpen ? "active" : ""}`}
              type="button"
              onClick={() => setLiveOpen((value) => !value)}
              aria-label={`${liveOpen ? "Close" : "Open"} live analysis progress`}
              aria-expanded={liveOpen}
              aria-controls="live-trace-drawer"
            >
              <Activity size={15} />
              <span className="live-toggle__label">Live progress</span>
              {runRunning ? <i aria-label="Run active" /> : liveStatus.eventCount > 0 ? <span className="live-toggle__count">{liveStatus.eventCount}</span> : null}
            </button>
            <button
              className="run-button"
              type="button"
              disabled={runBusy || !customerLimits || !liveRun}
              onClick={openNewRun}
              aria-label={runRunning ? "Analysis in progress" : "Start a new analysis"}
            >
              {runRunning ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}
              <span className="run-button__label">{runRunning ? "Analyzing" : "New analysis"}</span>
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
              openHousehold(value);
              if (returnFocusToMenu) {
                window.requestAnimationFrame(() => mobileMenuRef.current?.focus());
              }
            }}
          />
        )}
        <main className="main-workspace" id="main-dashboard" tabIndex={-1}>
          {hasReports && (
            <div className="workspace-toolbar">
              <nav aria-label="Dashboard views">
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
                <span className="verified-context"><ShieldCheck size={12} /> Verified</span>
                <span>{selectedCollection?.title}</span>
                {householdViews.has(view) && <><i /><span>Household {householdId}</span></>}
              </div>
            </div>
          )}

          <div className="workspace-scroll">
            {workspace && workspace.collectionWarnings.length > 0 && (
              <div className="collection-warning" role="status">
                <CircleAlert size={16} />
                <span>{productMessage(workspace.collectionWarnings.join(" "), "Some analysis history is temporarily unavailable.")}</span>
              </div>
            )}
            {householdViews.has(view) && loading && <LoadingState />}
            {householdViews.has(view) && !loading && error && <ErrorState message={error} onRetry={() => window.location.reload()} />}
            {!loading && !error && workspace && !hasReports && customerLimits && liveRun && (
              <EmptyWorkspace
                customerLimits={customerLimits}
                liveRun={liveRun}
                status={liveStatus}
                onOpenActivity={() => setLiveOpen(true)}
                onStart={openNewRun}
              />
            )}
            {!householdViews.has(view) && populationLoading && <PopulationLoadingState />}
            {!householdViews.has(view) && !populationLoading && populationError && (
              <ErrorState message={populationError} onRetry={() => window.location.reload()} />
            )}
            {!householdViews.has(view) && !populationLoading && !populationError && population && (
              <motion.div
                className="view-stage"
                key={`${collectionId}-${view}`}
                initial={reduceMotion ? false : { opacity: 0, y: 8, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{ duration: reduceMotion ? 0 : 0.24, ease: "easeOut" }}
              >
                {view === "home" && <ExecutiveHome population={population} onNavigate={changeView} />}
                {view === "population" && <PopulationExplorer collectionId={collectionId} population={population} onOpenHousehold={openHousehold} />}
                {view === "factors" && <FactorMap population={population} onOpenHousehold={openHousehold} />}
              </motion.div>
            )}
            {householdViews.has(view) && !loading && !error && hasReports && investigation && (
              <motion.div
                className="view-stage"
                key={`${investigation.report.run_id}-${view}`}
                initial={reduceMotion ? false : { opacity: 0, y: 8, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{ duration: reduceMotion ? 0 : 0.24, ease: "easeOut" }}
              >
                {view === "investigation" && <OverviewPanel report={investigation.report} onEvidenceSelect={selectEvidence} />}
                {view === "evidence" && <EvidencePanel report={investigation.report} selectedEvidenceId={selectedEvidenceId} onEvidenceSelect={setSelectedEvidenceId} />}
                {view === "audit" && <AuditPanel collectionId={collectionId} report={investigation.report} trace={investigation.trace} />}
              </motion.div>
            )}
          </div>
        </main>
      </div>
        <LiveTraceDrawer
          open={liveOpen}
          status={liveStatus}
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
          initialDeclineThreshold={population?.detector_policy.decline_threshold}
          thresholdSensitivity={population?.threshold_sensitivity}
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
      <div className="empty-workspace__icon"><Sparkles size={24} /></div>
      <span className="eyebrow">Population intelligence</span>
      <h1 id="empty-workspace-title">
        {running ? "Portfolio analysis in progress" : "Ready for your first portfolio review"}
      </h1>
      <p>
        {running
          ? "WhyBack is comparing household behavior and verifying every result. Insights will appear here when the review is complete."
          : "Launch a verified analysis of official household data to surface population patterns, differentiated factors, and governed actions."}
      </p>

      <div className="empty-workspace__facts" aria-label="Analysis configuration">
        <span><small>Data</small>Official household records</span>
        <span><small>Method</small>Verified population analysis</span>
        <span><small>Review size</small>{customerLimits.minimum}–{customerLimits.maximum} households</span>
      </div>

      {!liveRun.ready && !running && (
        <div className="empty-workspace__notice" role="status">
          <CircleAlert size={16} />
          <span>{liveRun.blockedReason ? productMessage(liveRun.blockedReason, "Analysis is temporarily unavailable.") : "Analysis is temporarily unavailable. Check the secure model connection."}</span>
        </div>
      )}
      {status.status === "failed" && (
        <div className="empty-workspace__notice empty-workspace__notice--failed" role="alert">
          <CircleAlert size={16} />
          <span>
            <strong>The last analysis did not complete.</strong>{" "}
            {status.error ? productMessage(status.error, "No verified results were produced.") : "No verified results were produced."}
          </span>
        </div>
      )}

      <button
        className="empty-workspace__action"
        type="button"
        onClick={running ? onOpenActivity : onStart}
      >
        {running ? <><Activity size={17} /> View live progress</> : <><Play size={17} /> Start portfolio analysis</>}
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

/** Shows a distinct placeholder while aggregate collection data is loading. */
function PopulationLoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label="Loading population summary">
      <LoaderCircle className="spin" size={26} />
      <strong>Loading population summary…</strong>
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

/** Requires the just-finished run to exist before repopulating the cleared workspace. */
function requirePublishedCollection(
  workspace: Workspace,
  collectionId: string | null,
): string {
  if (!collectionId || !workspace.collections.some((item) => item.id === collectionId)) {
    throw new Error("The finished run is still being published.");
  }
  return collectionId;
}
