/** Presents sanitized provenance, replay events, and links to rendered audit artifacts. */

import {
  ArrowUpRight,
  Bot,
  CircleAlert,
  Clock3,
  Database,
  FileJson,
  Fingerprint,
  Hammer,
  Route,
} from "lucide-react";
import { useMemo, useState } from "react";

import { artifactUrl } from "../api";
import { compactId, humanize, meaningfulTrace } from "../lib/report";
import type { ReportData, TraceEvent } from "../types";
import { TraceEventRow } from "./TraceEventRow";

interface AuditPanelProps {
  collectionId: string;
  report: ReportData;
  trace: TraceEvent[];
}

/** Renders the read-only audit view for one completed or failed investigation. */
export function AuditPanel({ collectionId, report, trace }: AuditPanelProps) {
  const [showEvidenceEvents, setShowEvidenceEvents] = useState(false);
  // Hide low-level evidence-write noise until a reviewer explicitly requests it.
  const events = useMemo(
    () => (showEvidenceEvents ? trace : meaningfulTrace(trace)),
    [showEvidenceEvents, trace],
  );
  const decisionCount = trace.filter((item) =>
    ["model_decision_received", "model_decision_rejected"].includes(item.event),
  ).length;
  const toolCount = trace.filter((item) =>
    ["tool_completed", "tool_partial", "tool_failed"].includes(item.event),
  ).length;
  const retryCount = trace.filter((item) => item.event === "retry_scheduled").length;

  return (
    <div className="panel-stack">
      <div className="audit-layout">
        <section className="surface trace-surface">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Durable CLI trace</span>
              <h1>Recorded run events</h1>
              <p>{events.length} sanitized events for this household investigation.</p>
            </div>
            <label className="switch-label">
              <input type="checkbox" checked={showEvidenceEvents} onChange={(event) => setShowEvidenceEvents(event.target.checked)} />
              <span aria-hidden="true" />
              Include evidence writes
            </label>
          </div>
          <div className="audit-inline-stats" aria-label="Audit summary">
            <span><Route size={14} /> {decisionCount} decisions</span>
            <span><Hammer size={14} /> {toolCount} tool outcomes</span>
            <span><CircleAlert size={14} /> {retryCount} retries</span>
          </div>
          <div className="trace-list">
            {events.map((event, index) => <TraceEventRow event={event} key={`${event.timestamp}-${event.event}-${index}`} />)}
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
          </section>

          <section className="surface original-links">
            <span className="eyebrow">Artifact files</span>
            <h2>Generated views</h2>
            <a href={artifactUrl(collectionId, report.household_id, "report.html")} target="_blank" rel="noreferrer">Report HTML <ArrowUpRight size={15} /></a>
            <a href={artifactUrl(collectionId, report.household_id, "trace.html")} target="_blank" rel="noreferrer">Trace HTML <ArrowUpRight size={15} /></a>
          </section>
        </aside>
      </div>
    </div>
  );
}

/** Displays one immutable provenance field with its identifying icon. */
function ProvenanceRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="provenance-row"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div>;
}

/** Formats a machine timestamp for local display without changing its source value. */
function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Unknown" : date.toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}
