import {
  ArrowUpRight,
  BadgeCheck,
  Bot,
  Braces,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Database,
  FileJson,
  Fingerprint,
  Hammer,
  ListFilter,
  Route,
  ShieldCheck,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";

import { artifactUrl } from "../api";
import { compactId, eventLabel, humanize, meaningfulTrace } from "../lib/report";
import type { ReportData, TraceEvent } from "../types";

interface AuditPanelProps {
  collectionId: string;
  report: ReportData;
  trace: TraceEvent[];
}

export function AuditPanel({ collectionId, report, trace }: AuditPanelProps) {
  const reduceMotion = useReducedMotion();
  const [showEvidenceEvents, setShowEvidenceEvents] = useState(false);
  const events = useMemo(
    () => (showEvidenceEvents ? trace : meaningfulTrace(trace)),
    [showEvidenceEvents, trace],
  );
  const decisionCount = trace.filter((item) => item.event === "model_decision_received").length;
  const toolCount = trace.filter((item) => item.event === "tool_completed").length;
  const retryCount = trace.filter((item) => item.event === "tool_retried").length;

  return (
    <motion.div
      className="panel-stack"
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <section className="audit-hero">
        <div>
          <span className="eyebrow eyebrow--light">Replayable decision record</span>
          <h1>Proof, not promises.</h1>
          <p>
            Inspect the bounded decisions, deterministic calculations, and final verification behind this{" "}
            {report.action ? "recommendation" : "terminal investigation outcome"}.
          </p>
        </div>
        <ShieldCheck size={72} strokeWidth={1.1} aria-hidden="true" />
      </section>

      <section className="audit-stats" aria-label="Audit summary">
        <AuditStat icon={<Route size={18} />} label="Model decisions" value={decisionCount} />
        <AuditStat icon={<Hammer size={18} />} label="Tool completions" value={toolCount} />
        <AuditStat icon={<Braces size={18} />} label="Evidence records" value={report.evidence_ledger.length} />
        <AuditStat icon={<BadgeCheck size={18} />} label="Retries" value={retryCount} />
      </section>

      <div className="audit-layout">
        <section className="surface trace-surface">
          <div className="section-heading">
            <div><span className="eyebrow">Chronological replay</span><h2>{events.length} audit events</h2></div>
            <label className="switch-label">
              <input type="checkbox" checked={showEvidenceEvents} onChange={(event) => setShowEvidenceEvents(event.target.checked)} />
              <span aria-hidden="true" />
              Include evidence writes
            </label>
          </div>
          <div className="trace-list">
            {events.map((event, index) => <TraceRow event={event} key={`${event.timestamp}-${event.event}-${index}`} />)}
            {events.length === 0 && <p className="muted-copy">No trace JSONL is available for this artifact.</p>}
          </div>
        </section>

        <aside className="audit-aside">
          <section className="surface provenance-card">
            <span className="eyebrow">Run provenance</span>
            <h2>Artifact identity</h2>
            <ProvenanceRow icon={<Fingerprint size={15} />} label="Run ID" value={compactId(report.run_id, 8)} />
            <ProvenanceRow icon={<Database size={15} />} label="Dataset" value={humanize(report.provenance.dataset_kind)} />
            <ProvenanceRow icon={<Hammer size={15} />} label="Backend" value={humanize(report.provenance.backend)} />
            <ProvenanceRow icon={<Bot size={15} />} label="Model" value={report.provenance.model} />
            <ProvenanceRow icon={<FileJson size={15} />} label="Schema" value={`Report v${report.schema_version}`} />
            <ProvenanceRow icon={<Clock3 size={15} />} label="Generated" value={formatTimestamp(report.provenance.generated_at)} />
            <div className="hash-count"><CheckCircle2 size={17} /><div><strong>{Object.keys(report.provenance.source_hashes).length} source hashes</strong><small>Captured in immutable provenance</small></div></div>
          </section>

          <section className="surface original-links">
            <span className="eyebrow">Original renderers</span>
            <h2>Open source artifacts</h2>
            <a href={artifactUrl(collectionId, report.household_id, "report.html")} target="_blank" rel="noreferrer">Deterministic report <ArrowUpRight size={15} /></a>
            <a href={artifactUrl(collectionId, report.household_id, "trace.html")} target="_blank" rel="noreferrer">Replayable trace <ArrowUpRight size={15} /></a>
            <a href={artifactUrl(collectionId, report.household_id, "report.md")} target="_blank" rel="noreferrer">Markdown record <ArrowUpRight size={15} /></a>
          </section>
        </aside>
      </div>
    </motion.div>
  );
}

function AuditStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return <div>{icon}<span><strong>{value}</strong><small>{label}</small></span></div>;
}

function TraceRow({ event }: { event: TraceEvent }) {
  const details = Object.entries(event.details).filter(([, value]) => value !== null && value !== "");
  return (
    <article className={`trace-row trace-row--${traceCategory(event.event)}`}>
      <span className="trace-row__icon">{traceIcon(event.event)}</span>
      <div className="trace-row__body">
        <div><strong>{eventLabel(event.event)}</strong><time>{formatTime(event.timestamp)}</time></div>
        {details.length > 0 && (
          <div className="trace-details">
            {details.slice(0, 7).map(([key, value]) => (
              <span key={key}><small>{humanize(key)}</small>{formatDetail(value)}</span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function ProvenanceRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="provenance-row"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div>;
}

function traceCategory(event: string): string {
  if (event.includes("verification")) return "verify";
  if (event.includes("tool")) return "tool";
  if (event.includes("decision") || event === "finish_requested") return "decision";
  if (event.includes("failed") || event.includes("fallback")) return "warning";
  return "run";
}

function traceIcon(event: string) {
  const category = traceCategory(event);
  if (category === "verify") return <ShieldCheck size={15} />;
  if (category === "tool") return <Hammer size={15} />;
  if (category === "decision") return <Bot size={15} />;
  if (category === "warning") return <CircleAlert size={15} />;
  return <ListFilter size={15} />;
}

function formatDetail(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ") || "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(1);
  if (typeof value === "object") return "Structured detail";
  return String(value);
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Unknown" : date.toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}
