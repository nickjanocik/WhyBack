/** Lets reviewers choose an artifact collection and ranked household investigation. */

import { AlertTriangle, Check, ChevronDown, History, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { formatPercent, humanize } from "../lib/report";
import type { ArtifactCollection, ReportSummary } from "../types";

interface CandidateRailProps {
  collections: ArtifactCollection[];
  collectionId: string;
  householdId: string;
  onCollectionChange: (collectionId: string) => void;
  onHouseholdChange: (householdId: string) => void;
}

/** Renders verified CLI history and ranked household navigation. */
export function CandidateRail({
  collections,
  collectionId,
  householdId,
  onCollectionChange,
  onHouseholdChange,
}: CandidateRailProps) {
  const [query, setQuery] = useState("");
  const collection = collections.find((item) => item.id === collectionId);
  // Preserve each report's original rank even when the search narrows visible rows.
  const reports = useMemo(() => {
    if (!collection) return [];
    const normalized = query.trim().toLocaleLowerCase();
    return collection.reports
      .map((report, index) => ({ report, rank: index + 1 }))
      .filter(
        ({ report }) =>
          !normalized ||
          report.householdId.toLocaleLowerCase().includes(normalized) ||
          (report.actionId ?? "").toLocaleLowerCase().includes(normalized),
      );
  }, [collection, query]);

  return (
    <aside className="candidate-rail" id="candidate-rail">
      <div className="collection-picker">
        <label htmlFor="collection">CLI run</label>
        <div className="select-wrap">
          <History size={15} aria-hidden="true" />
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
        {collection && (
          <p className="collection-meta" aria-label="Collection metadata">
            Official data · {humanize(collection.backend)} · {collection.completedCount} completed
          </p>
        )}
      </div>

      <div className="rail-heading">
        <div>
          <strong>Households</strong>
          <span>{collection?.reportCount ?? 0} investigations</span>
        </div>
      </div>

      <label className="rail-search">
        <Search size={15} aria-hidden="true" />
        <span className="sr-only">Search households</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find household or action"
        />
      </label>

      <div className="candidate-list" role="group" aria-label="Investigations">
        {reports.map(({ report, rank }) => (
          <CandidateButton
            key={report.runId || report.householdId}
            report={report}
            rank={rank}
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

/** Renders one ranked household summary and reports selection through the rail. */
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
        <span className="candidate__meta">
          {report.runStatus === "completed" ? <Check size={12} /> : <AlertTriangle size={12} />}
          {report.evidenceCount} evidence records
          {report.warningCount > 0 && ` · ${report.warningCount} warning`}
        </span>
      </span>
    </button>
  );
}
