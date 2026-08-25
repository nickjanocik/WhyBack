import { AlertTriangle, Check, ChevronDown, Database, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { formatPercent } from "../lib/report";
import type { ArtifactCollection, ReportSummary } from "../types";

interface CandidateRailProps {
  collections: ArtifactCollection[];
  collectionId: string;
  householdId: string;
  onCollectionChange: (collectionId: string) => void;
  onHouseholdChange: (householdId: string) => void;
}

export function CandidateRail({
  collections,
  collectionId,
  householdId,
  onCollectionChange,
  onHouseholdChange,
}: CandidateRailProps) {
  const [query, setQuery] = useState("");
  const collection = collections.find((item) => item.id === collectionId);
  const reports = useMemo(() => {
    if (!collection) return [];
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return collection.reports;
    return collection.reports.filter(
      (item) =>
        item.householdId.toLocaleLowerCase().includes(normalized) ||
        (item.actionId ?? "").toLocaleLowerCase().includes(normalized),
    );
  }, [collection, query]);

  return (
    <aside className="candidate-rail" id="candidate-rail">
      <div className="collection-picker">
        <label htmlFor="collection">Artifact collection</label>
        <div className="select-wrap">
          <Database size={15} aria-hidden="true" />
          <select
            id="collection"
            value={collectionId}
            onChange={(event) => onCollectionChange(event.target.value)}
          >
            {collections.map((item) => (
              <option value={item.id} key={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <ChevronDown size={14} aria-hidden="true" />
        </div>
        <p>{collection?.description}</p>
      </div>

      <div className="rail-heading">
        <div>
          <span className="eyebrow">Flagged households</span>
          <strong>{collection?.reportCount ?? 0} investigations</strong>
        </div>
        <span className="live-dot" aria-label="Artifacts available" />
      </div>

      <label className="rail-search">
        <Search size={15} aria-hidden="true" />
        <span className="sr-only">Search households</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find household"
        />
      </label>

      <div className="candidate-list" role="group" aria-label="Investigations">
        {reports.map((report, index) => (
          <CandidateButton
            key={report.runId || report.householdId}
            report={report}
            rank={index + 1}
            selected={report.householdId === householdId}
            onSelect={() => onHouseholdChange(report.householdId)}
          />
        ))}
        {reports.length === 0 && <p className="empty-rail">No matching households.</p>}
      </div>

      <div className="rail-note">
        <AlertTriangle size={16} aria-hidden="true" />
        <p>
          Decline score is a transparent heuristic, <strong>not</strong> a churn
          probability.
        </p>
      </div>
    </aside>
  );
}

function CandidateButton({
  report,
  rank,
  selected,
  onSelect,
}: {
  report: ReportSummary;
  rank: number;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={`candidate ${selected ? "candidate--selected" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
      type="button"
    >
      <span className="candidate__rank">{String(rank).padStart(2, "0")}</span>
      <span className="candidate__body">
        <span className="candidate__topline">
          <strong>Household {report.householdId}</strong>
          <span>{formatPercent(report.declineScore)}</span>
        </span>
        <span className="score-track" aria-hidden="true">
          <i style={{ width: `${Math.min(100, report.declineScore * 100)}%` }} />
        </span>
        <span className="candidate__meta">
          {report.runStatus === "completed" ? <Check size={12} /> : <AlertTriangle size={12} />}
          {report.evidenceCount} evidence records
          {report.warningCount > 0 && ` · ${report.warningCount} warning`}
        </span>
      </span>
    </button>
  );
}
