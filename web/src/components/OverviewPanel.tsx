import {
  ArrowDownRight,
  ArrowRight,
  BadgeCheck,
  Beaker,
  CircleAlert,
  CircleCheck,
  Eye,
  Fingerprint,
  Gauge,
  Info,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { CSSProperties } from "react";

import {
  actionLabel,
  compactId,
  formatCurrency,
  formatNumber,
  formatPercent,
  humanize,
  uniqueLimitations,
  weeklyTrend,
} from "../lib/report";
import type { EvidenceRecord, ReportData } from "../types";
import { TrendChart } from "./TrendChart";

interface OverviewPanelProps {
  report: ReportData;
  onEvidenceSelect: (evidenceId: string) => void;
}

export function OverviewPanel({ report, onEvidenceSelect }: OverviewPanelProps) {
  const reduceMotion = useReducedMotion();
  const decline = report.decline;
  const trend = weeklyTrend(report);
  const limitations = uniqueLimitations(report);
  const heroStyle = {
    "--score": `${Math.round(decline.decline_score * 360)}deg`,
  } as CSSProperties;

  return (
    <motion.div
      className="panel-stack"
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
    >
      <section className="report-hero">
        <div className="report-hero__glow" aria-hidden="true" />
        <div className="hero-copy">
          <div className="hero-kicker">
            <StatusPill status={report.run_status} />
            <span>
              <Fingerprint size={13} /> Run {compactId(report.run_id, 5)}
            </span>
          </div>
          <p className="eyebrow eyebrow--light">Investigation brief</p>
          <h1>
            Household <em>{report.household_id}</em>
          </h1>
          <p className="hero-summary">
            {report.likely_drivers[0]?.summary ??
              report.failure_reason ??
              "The bounded investigation did not publish a supported driver."}
          </p>
          <div className="hero-provenance">
            <span>{humanize(report.provenance.dataset_kind)}</span>
            <i />
            <span>{humanize(report.provenance.execution_mode)}</span>
            <i />
            <span>{report.provenance.model}</span>
          </div>
        </div>
        <div className="score-orbit" style={heroStyle}>
          <div className="score-orbit__inner">
            <small>Decline</small>
            <strong>{formatPercent(decline.decline_score)}</strong>
            <span>heuristic</span>
          </div>
          <span className="score-orbit__dot" aria-hidden="true" />
        </div>
      </section>

      <section className="metric-grid" aria-label="Baseline and recent comparison">
        <MetricCard
          label="Retailer sales value"
          baseline={formatCurrency(decline.baseline_retailer_sales_value)}
          recent={formatCurrency(decline.recent_retailer_sales_value)}
          drop={decline.sales_drop}
          period={`Weeks ${decline.baseline_start_week}–${decline.baseline_end_week} vs ${decline.recent_start_week}–${decline.recent_end_week}`}
        />
        <MetricCard
          label="Distinct baskets"
          baseline={formatNumber(decline.baseline_distinct_baskets, 0)}
          recent={formatNumber(decline.recent_distinct_baskets, 0)}
          drop={decline.trip_drop}
          period="Recorded shopping trips"
        />
        <MetricCard
          label="Active weeks"
          baseline={formatNumber(decline.baseline_active_weeks, 0)}
          recent={formatNumber(decline.recent_active_weeks, 0)}
          drop={decline.active_week_drop}
          period="Weeks with observed activity"
        />
      </section>

      <section className="surface trend-surface">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Observed engagement</span>
            <h2>Weekly retailer sales value</h2>
          </div>
          <div className="legend">
            <span><i /> Recorded value</span>
            <span><i className="legend__divider" /> Window change</span>
          </div>
        </div>
        <TrendChart points={trend} recentStartWeek={decline.recent_start_week} />
      </section>

      <div className="overview-split">
        <section className="surface driver-card">
          <div className="icon-chip icon-chip--warm"><Sparkles size={18} /></div>
          <span className="eyebrow">Verified interpretation</span>
          <h2>{report.likely_drivers.length ? "What changed" : "No supported driver"}</h2>
          {report.likely_drivers.length > 0 ? (
            report.likely_drivers.map((driver, index) => (
              <div className="driver" key={`${driver.summary}-${index}`}>
                <p>{driver.summary}</p>
                <div className="citation-list">
                  {driver.supporting_evidence_ids.map((evidenceId) => (
                    <button
                      type="button"
                      key={evidenceId}
                      onClick={() => onEvidenceSelect(evidenceId)}
                    >
                      <BadgeCheck size={14} /> {evidenceMetric(report, evidenceId)}
                    </button>
                  ))}
                </div>
                {(driver.counterevidence_ids?.length ?? 0) > 0 && (
                  <div className="counterevidence-block">
                    <small>Counterevidence retained</small>
                    <div className="citation-list citation-list--counter">
                      {driver.counterevidence_ids?.map((evidenceId) => (
                        <button
                          type="button"
                          key={evidenceId}
                          onClick={() => onEvidenceSelect(evidenceId)}
                        >
                          <CircleAlert size={14} /> {evidenceMetric(report, evidenceId)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {driver.no_material_counterevidence_reason && (
                  <p className="driver-counter-note">
                    <strong>Counterevidence check:</strong>{" "}
                    {driver.no_material_counterevidence_reason}
                  </p>
                )}
                {driver.claim_type && (
                  <span className="claim-chip">
                    <LockKeyhole size={12} /> {humanize(driver.claim_type)} claim
                  </span>
                )}
              </div>
            ))
          ) : (
            <p className="muted-copy">
              {report.failure_reason || "Evidence did not clear the deterministic verifier."}
            </p>
          )}
          <div className="driver-footer">
            <ShieldCheck size={17} />
            <p>Every displayed quantity resolves to detector or immutable tool evidence.</p>
          </div>
        </section>

        <ActionCard report={report} onEvidenceSelect={onEvidenceSelect} />
      </div>

      {report.population_context && (
        <PopulationCard report={report} onEvidenceSelect={onEvidenceSelect} />
      )}

      {(report.tool_warnings.length > 0 || report.verification_issues.length > 0) && (
        <section className="surface warning-surface">
          <div className="icon-chip icon-chip--warning"><CircleAlert size={18} /></div>
          <div>
            <span className="eyebrow">Visible reliability state</span>
            <h2>{report.tool_warnings.length} analytical warning{report.tool_warnings.length === 1 ? "" : "s"}</h2>
            {report.tool_warnings.map((warning) => (
              <p key={warning.tool_name}>
                <strong>{humanize(warning.tool_name)}:</strong>{" "}
                {warning.limitations.join(" ") || humanize(warning.final_status)}
              </p>
            ))}
            {report.verification_issues.map((issue) => <p key={issue}>{issue}</p>)}
          </div>
        </section>
      )}

      <section className="surface limits-surface">
        <div className="section-heading section-heading--compact">
          <div>
            <span className="eyebrow">Interpretation boundary</span>
            <h2>What this evidence cannot say</h2>
          </div>
          <Eye size={20} aria-hidden="true" />
        </div>
        <div className="limit-grid">
          {limitations.map((limitation, index) => (
            <div key={limitation}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <small>
                  {report.alternative_explanations.includes(limitation)
                    ? "Alternative explanation"
                    : "Interpretation limit"}
                </small>
                <p>{limitation}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </motion.div>
  );
}

function StatusPill({ status }: { status: ReportData["run_status"] }) {
  const completed = status === "completed";
  return (
    <span className={`status-pill status-pill--${status}`}>
      {completed ? <CircleCheck size={13} /> : <CircleAlert size={13} />}
      {humanize(status)}
    </span>
  );
}

function MetricCard({
  label,
  baseline,
  recent,
  drop,
  period,
}: {
  label: string;
  baseline: string;
  recent: string;
  drop: number;
  period: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-card__topline">
        <span>{label}</span>
        <span className="drop-badge"><ArrowDownRight size={13} /> {formatPercent(drop)} drop</span>
      </div>
      <div className="metric-values">
        <div><small>Baseline</small><strong>{baseline}</strong></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div><small>Recent</small><strong>{recent}</strong></div>
      </div>
      <p>{period}</p>
    </article>
  );
}

function ActionCard({
  report,
  onEvidenceSelect,
}: {
  report: ReportData;
  onEvidenceSelect: (evidenceId: string) => void;
}) {
  if (!report.action) {
    return (
      <section className="action-card action-card--empty">
        <CircleAlert size={22} />
        <span className="eyebrow eyebrow--light">No action published</span>
        <h2>Verifier held the line.</h2>
        <p>{report.failure_reason || "The run ended without a supported catalog action."}</p>
      </section>
    );
  }
  return (
    <section className="action-card">
      <div className="action-card__orb" aria-hidden="true" />
      <div className="action-topline">
        <span className="eyebrow eyebrow--light">Next best action</span>
        <span>
          <Gauge size={13} /> {humanize(report.action.resolved_confidence)} confidence
          {report.action.confidence_cap_applied ? " · capped" : ""}
        </span>
      </div>
      <h2>{actionLabel(report.action.action_id)}</h2>
      <p>{report.action.description}</p>
      <div className="experiment-box">
        <Beaker size={18} />
        <div><small>Suggested experiment</small><p>{report.action.suggested_experiment}</p></div>
      </div>
      <details className="review-basis">
        <summary><Info size={15} /> Review basis and measurement plan</summary>
        <div className="review-basis__content">
          <div>
            <small>Why this catalog action</small>
            <p>{report.action.rationale}</p>
          </div>
          <div>
            <small>Recommended success metric</small>
            <p>{report.action.recommended_success_metric}</p>
          </div>
          {(report.action.confidence_adjustments ?? []).map((adjustment, index) => (
            <div className="confidence-adjustment" key={`${adjustment.context_classification}-${index}`}>
              <small>
                Confidence adjustment · {humanize(adjustment.context_classification)} · ceiling {humanize(adjustment.maximum_confidence)}
              </small>
              <p>{adjustment.reason}</p>
              {adjustment.evidence_ids.length > 0 && (
                <div className="citation-list citation-list--dark">
                  {adjustment.evidence_ids.map((evidenceId) => (
                    <button type="button" key={evidenceId} onClick={() => onEvidenceSelect(evidenceId)}>
                      <BadgeCheck size={13} /> {evidenceMetric(report, evidenceId)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </details>
      <div className="action-footer">
        <span><UsersRound size={15} /> Human review required</span>
        <span>No outreach executed</span>
      </div>
    </section>
  );
}

function PopulationCard({
  report,
  onEvidenceSelect,
}: {
  report: ReportData;
  onEvidenceSelect: (evidenceId: string) => void;
}) {
  const context = report.population_context;
  if (!context) return null;
  const population = context.eligible_population;
  const peers = context.behavioral_peers;
  return (
    <section className="surface population-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Comparison context</span>
          <h2>{humanize(context.context_classification)}</h2>
        </div>
        <span className="context-chip"><UsersRound size={15} /> Target excluded from cohorts</span>
      </div>
      <div className="cohort-grid">
        <CohortStat label="Eligible population" cohort={population} />
        <CohortStat label="Behavioral peers" cohort={peers} />
        <div className="cohort-stat cohort-stat--context">
          <Info size={18} />
          <div>
            <small>Classification</small>
            <strong>{humanize(context.context_classification)}</strong>
            <p>Context shapes confidence; it does not establish cause.</p>
          </div>
        </div>
      </div>
      {context.category_context.length > 0 && (
        <div className="category-context">
          <div>
            <span className="eyebrow">Category comparison</span>
            <p>Target-excluded context for the largest observed category losses.</p>
          </div>
          <div className="category-context__grid">
            {context.category_context.slice(0, 3).map((category) => (
              <article key={`${category.department}-${category.product_category}`}>
                <span>{humanize(category.context_classification)}</span>
                <strong>{humanize(category.department)} · {humanize(category.product_category)}</strong>
                {category.available && category.target_change !== null ? (
                  <p>
                    Target {formatPercent(category.target_change, 1)} · population median{" "}
                    {category.population_median_change === null
                      ? "unavailable"
                      : formatPercent(category.population_median_change, 1)}
                  </p>
                ) : (
                  <p>Comparison context is below the declared availability boundary.</p>
                )}
                {category.evidence_ids[0] && (
                  <button type="button" onClick={() => onEvidenceSelect(category.evidence_ids[0]!)}>
                    Inspect evidence <ArrowRight size={13} />
                  </button>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
      {context.classification_evidence_id && (
        <button
          className="text-link"
          type="button"
          onClick={() => onEvidenceSelect(context.classification_evidence_id as string)}
        >
          Inspect classification evidence <ArrowRight size={14} />
        </button>
      )}
    </section>
  );
}

function CohortStat({
  label,
  cohort,
}: {
  label: string;
  cohort: NonNullable<ReportData["population_context"]>["eligible_population"];
}) {
  return (
    <div className="cohort-stat">
      <small>{label}</small>
      {cohort.available ? (
        <>
          <strong>
            {cohort.target_percentile === null
              ? `${cohort.cohort_count} households`
              : `${formatNumber(cohort.target_percentile, 0)}th percentile`}
          </strong>
          <p>Target-excluded comparison · n={cohort.cohort_count}</p>
        </>
      ) : (
        <><strong>Not available</strong><p>Below the declared cohort minimum.</p></>
      )}
    </div>
  );
}

function evidenceMetric(report: ReportData, evidenceId: string): string {
  const record: EvidenceRecord | undefined = report.evidence_ledger.find(
    (item) => item.evidence_id === evidenceId,
  );
  return record ? humanize(record.metric) : compactId(evidenceId, 6);
}
