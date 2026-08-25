import {
  AlertTriangle,
  ArrowDown,
  BadgeCheck,
  ChevronDown,
  CircleDot,
  Clock3,
  Filter,
  Search,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

import {
  compactId,
  evidenceDisplayValue,
  formatMetricValue,
  formatNumber,
  humanize,
} from "../lib/report";
import type { EvidenceRecord, EvidenceRole, ReportData } from "../types";

interface EvidencePanelProps {
  report: ReportData;
  selectedEvidenceId: string | null;
  onEvidenceSelect: (evidenceId: string | null) => void;
}

type RoleFilter = "all" | EvidenceRole;

export function EvidencePanel({
  report,
  selectedEvidenceId,
  onEvidenceSelect,
}: EvidencePanelProps) {
  const reduceMotion = useReducedMotion();
  const [role, setRole] = useState<RoleFilter>("all");
  const [tool, setTool] = useState("all");
  const [query, setQuery] = useState("");
  const [stepIds, setStepIds] = useState<string[] | null>(null);
  const [limit, setLimit] = useState(18);

  const tools = useMemo(
    () => [...new Set(report.evidence_ledger.map((item) => item.source_tool))].sort(),
    [report.evidence_ledger],
  );
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return report.evidence_ledger.filter((item) => {
      if (role !== "all" && item.role !== role) return false;
      if (tool !== "all" && item.source_tool !== tool) return false;
      if (stepIds && !stepIds.includes(item.evidence_id)) return false;
      return (
        !normalized ||
        item.metric.toLocaleLowerCase().includes(normalized) ||
        item.evidence_id.toLocaleLowerCase().includes(normalized) ||
        Object.values(item.dimensions).some((value) =>
          value.toLocaleLowerCase().includes(normalized),
        )
      );
    });
  }, [query, report.evidence_ledger, role, stepIds, tool]);

  useEffect(() => {
    if (!selectedEvidenceId) return;
    const focusFrame = requestAnimationFrame(() => {
      const row = document.getElementById(`evidence-${selectedEvidenceId}`);
      row?.querySelector<HTMLButtonElement>(".evidence-row__summary")?.focus({
        preventScroll: true,
      });
      row?.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "center",
      });
    });
    return () => cancelAnimationFrame(focusFrame);
  }, [filtered, reduceMotion, selectedEvidenceId]);

  const selectedIndex = selectedEvidenceId
    ? filtered.findIndex((item) => item.evidence_id === selectedEvidenceId)
    : -1;
  const visibleLimit = selectedIndex >= limit ? selectedIndex + 1 : limit;

  return (
    <motion.div
      className="panel-stack"
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <section className="surface path-surface">
        <div className="section-heading">
          <div><span className="eyebrow">Bounded reasoning path</span><h2>One analytical choice at a time</h2></div>
          <span className="context-chip">{report.investigation_path.length} of 5 tool executions</span>
        </div>
        <div className="investigation-path">
          {report.investigation_path.map((step, index) => (
            <button
              type="button"
              key={`${step.decision_number}-${step.tool_name}`}
              className={`path-step ${
                stepIds === step.evidence_ids ? "path-step--active" : ""
              } ${step.final_status !== "ok" ? "path-step--warning" : ""}`}
              aria-pressed={stepIds === step.evidence_ids}
              onClick={() => {
                setStepIds((current) => (current === step.evidence_ids ? null : step.evidence_ids));
                setLimit(18);
              }}
            >
              <span className="path-step__number">{String(index + 1).padStart(2, "0")}</span>
              <span className="path-step__line" aria-hidden="true" />
              <span className="path-step__icon">
                {step.final_status === "ok" ? <BadgeCheck size={16} /> : <AlertTriangle size={16} />}
              </span>
              <strong>{step.tool_label}</strong>
              <p>{step.investigation_question}</p>
              <span className="path-step__meta">
                <Clock3 size={12} /> {formatNumber(step.total_latency_ms, 1)}ms · {step.evidence_ids.length} records
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="surface ledger-surface">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Immutable evidence ledger</span>
            <h2>{filtered.length} grounded records</h2>
          </div>
          <div className="ledger-legend">
            <span><i className="role-dot role-dot--supporting" /> Supporting</span>
            <span><i className="role-dot role-dot--counterevidence" /> Counter</span>
            <span><i className="role-dot role-dot--context" /> Context</span>
          </div>
        </div>

        <div className="filter-bar">
          <label className="filter-search">
            <Search size={15} />
            <span className="sr-only">Search evidence</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search metric or ID" />
          </label>
          <div className="filter-select"><Filter size={14} /><select value={role} onChange={(event) => setRole(event.target.value as RoleFilter)} aria-label="Evidence role"><option value="all">All roles</option><option value="supporting">Supporting</option><option value="counterevidence">Counterevidence</option><option value="context">Context</option></select><ChevronDown size={13} /></div>
          <div className="filter-select"><select value={tool} onChange={(event) => setTool(event.target.value)} aria-label="Evidence source"><option value="all">All tools</option>{tools.map((item) => <option value={item} key={item}>{humanize(item)}</option>)}</select><ChevronDown size={13} /></div>
          {stepIds && <button type="button" className="clear-filter" onClick={() => setStepIds(null)}>Clear step filter</button>}
        </div>

        <div className="evidence-list">
          <AnimatePresence initial={false}>
            {filtered.slice(0, visibleLimit).map((record) => (
              <EvidenceRow
                key={record.evidence_id}
                record={record}
                expanded={selectedEvidenceId === record.evidence_id}
                onToggle={() =>
                  onEvidenceSelect(selectedEvidenceId === record.evidence_id ? null : record.evidence_id)
                }
              />
            ))}
          </AnimatePresence>
          {filtered.length === 0 && (
            <div className="ledger-empty"><CircleDot size={20} /><strong>No evidence matches these filters.</strong><p>Clear a filter to return to the full immutable ledger.</p></div>
          )}
        </div>
        {filtered.length > visibleLimit && (
          <button type="button" className="load-more" onClick={() => setLimit((value) => value + 18)}>
            Show 18 more <ArrowDown size={15} />
          </button>
        )}
      </section>
    </motion.div>
  );
}

function EvidenceRow({
  record,
  expanded,
  onToggle,
}: {
  record: EvidenceRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  const dimensions = Object.entries(record.dimensions);
  return (
    <motion.article
      layout
      id={`evidence-${record.evidence_id}`}
      className={`evidence-row evidence-row--${record.role} ${expanded ? "evidence-row--expanded" : ""}`}
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
    >
      <button type="button" className="evidence-row__summary" onClick={onToggle} aria-expanded={expanded}>
        <i className={`role-dot role-dot--${record.role}`} />
        <span className="evidence-name"><small>{humanize(record.source_tool)}</small><strong>{humanize(record.metric)}</strong></span>
        <span className="evidence-value">{evidenceDisplayValue(record)}</span>
        <span className="evidence-role">{humanize(record.role)}</span>
        <ChevronDown className="evidence-chevron" size={16} />
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="evidence-detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <div className="evidence-detail__grid">
              <div><small>Evidence ID</small><code>{compactId(record.evidence_id, 14)}</code></div>
              <div><small>Source status</small><strong>{humanize(record.source_status ?? "unknown")}</strong></div>
              {record.change !== null && <div><small>Absolute change</small><strong>{formatMetricValue(record.change, record.unit)}</strong></div>}
              {record.maximum_claim_type && <div><small>Maximum claim</small><strong>{humanize(record.maximum_claim_type)}</strong></div>}
            </div>
            {dimensions.length > 0 && <div className="dimension-list">{dimensions.map(([key, value]) => <span key={key}><small>{humanize(key)}</small>{value}</span>)}</div>}
            {record.limitations.map((limitation) => <p className="record-limitation" key={limitation}><AlertTriangle size={14} />{limitation}</p>)}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
