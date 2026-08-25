import {
  Activity,
  BookOpenText,
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
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getInvestigation, getWorkspace, runDemo } from "./api";
import { AuditPanel } from "./components/AuditPanel";
import { BrandMark } from "./components/BrandMark";
import { CandidateRail } from "./components/CandidateRail";
import { EvidencePanel } from "./components/EvidencePanel";
import { OverviewPanel } from "./components/OverviewPanel";
import { RunDemoDialog } from "./components/RunDemoDialog";
import type { InvestigationResponse, Workspace } from "./types";

type View = "overview" | "evidence" | "audit";

const views: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "overview", label: "Investigation", icon: FileSearch },
  { id: "evidence", label: "Evidence", icon: FlaskConical },
  { id: "audit", label: "Audit replay", icon: ShieldCheck },
];

function initialView(): View {
  const candidate = new URLSearchParams(window.location.search).get("view");
  return candidate === "evidence" || candidate === "audit" ? candidate : "overview";
}

export default function App() {
  const reduceMotion = useReducedMotion();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [collectionId, setCollectionId] = useState("");
  const [householdId, setHouseholdId] = useState("");
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [view, setView] = useState<View>(initialView);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLButtonElement>(null);

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
      setError("No WhyBack report artifacts are available. Run the scripted demo to create them.");
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
    setDemoRunning(true);
    setDemoError(null);
    try {
      const response = await runDemo(customers);
      initializeWorkspace(response.workspace, response.collectionId);
      setDialogOpen(false);
      changeView("overview");
      setToast(`${customers} fresh investigation${customers === 1 ? "" : "s"} generated by the WhyBack CLI.`);
    } catch (caught) {
      setDemoError(caught instanceof Error ? caught.message : "The scripted demo failed.");
    } finally {
      setDemoRunning(false);
    }
  }

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
        <BrandMark />
        <div className="header-divider" />
        <div className="product-title"><span>Investigator</span><small>Evidence review workspace</small></div>
        <div className="header-actions">
          <span className="local-status"><i /> Local artifacts</span>
          <span className="docs-link" aria-label="Report artifact schema version 2"><BookOpenText size={17} /><span>Artifact schema v2</span></span>
          <button className="run-button" type="button" onClick={() => { setDemoError(null); setDialogOpen(true); }}>
            <Play size={15} fill="currentColor" /> Run demo
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
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={`${investigation.report.run_id}-${view}`} exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}>
                  {view === "overview" && <OverviewPanel report={investigation.report} onEvidenceSelect={selectEvidence} />}
                  {view === "evidence" && <EvidencePanel report={investigation.report} selectedEvidenceId={selectedEvidenceId} onEvidenceSelect={setSelectedEvidenceId} />}
                  {view === "audit" && <AuditPanel collectionId={collectionId} report={investigation.report} trace={investigation.trace} />}
                </motion.div>
              </AnimatePresence>
            )}
          </div>
        </main>
      </div>
      </div>

      <RunDemoDialog open={dialogOpen} running={demoRunning} error={demoError} onClose={() => !demoRunning && setDialogOpen(false)} onRun={handleRunDemo} />
      <AnimatePresence>{toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}><ShieldCheck size={18} /><span>{toast}</span></motion.div>}</AnimatePresence>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label="Loading investigation">
      <LoaderCircle className="spin" size={26} />
      <strong>Opening the evidence ledger</strong>
      <span>Loading deterministic report and sanitized audit events…</span>
      <div className="skeleton skeleton--wide" /><div className="skeleton-grid"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-state" role="alert"><CircleAlert size={28} /><span className="eyebrow">Workspace unavailable</span><h1>We couldn’t open this investigation.</h1><p>{message}</p><button type="button" onClick={onRetry}><RefreshCw size={15} /> Try again</button></div>
  );
}
