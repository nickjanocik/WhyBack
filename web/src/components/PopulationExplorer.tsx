/** Data-science population explorer for descriptive nested-cohort comparisons. */

import { CircleAlert, Download, Info, ScatterChart } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";

import { populationExportUrl } from "../api";
import { formatCurrency, formatPercent, humanize } from "../lib/report";
import type {
  PopulationCohortId,
  PopulationMetric,
  PopulationMetricId,
  PopulationSummary,
} from "../types";

interface PopulationExplorerProps {
  collectionId: string;
  population: PopulationSummary;
  onOpenHousehold: (householdId: string) => void;
}

const cohorts: Array<{ id: PopulationCohortId; label: string }> = [
  { id: "eligible", label: "Eligible" },
  { id: "flagged", label: "Flagged" },
  { id: "investigated", label: "Investigated" },
];

const metrics: Array<{ id: PopulationMetricId; label: string }> = [
  { id: "decline_score", label: "Decline score" },
  { id: "sales_drop", label: "Sales drop" },
  { id: "trip_drop", label: "Trip drop" },
  { id: "active_week_drop", label: "Active-week drop" },
  { id: "baseline_retailer_sales_value", label: "Baseline retailer value" },
  { id: "recent_retailer_sales_value", label: "Recent retailer value" },
  { id: "recorded_value_change", label: "Recorded value change" },
];

const cohortColors: Record<PopulationCohortId, string> = {
  eligible: "#9aa39e",
  flagged: "#4c9c7d",
  investigated: "#f2a86f",
};

/** Renders population distributions, density, sensitivity, and definitions. */
export function PopulationExplorer({
  collectionId,
  population,
  onOpenHousehold,
}: PopulationExplorerProps) {
  const reduced = useReducedMotion();
  const [focusCohort, setFocusCohort] = useState<PopulationCohortId>("flagged");
  const [metric, setMetric] = useState<PopulationMetricId>("decline_score");
  const distributions = useMemo(
    () => cohorts.map(({ id }) => ({
      cohort: id,
      data: population.cohorts.find((item) => item.cohort === id)?.metrics.find((item) => item.metric === metric) ?? null,
    })),
    [metric, population.cohorts],
  );
  const available = distributions.some((item) => item.data && item.data.count > 0);

  return (
    <div className="population-page population-explorer">
      <header className="population-page__heading">
        <div>
          <span className="eyebrow">Data-science view</span>
          <h1>Population Explorer</h1>
          <p>Compare nested cohorts descriptively within one detector window.</p>
        </div>
        <div className="export-actions" aria-label="Population exports">
          <a href={populationExportUrl(collectionId, "csv")} download><Download size={15} /> CSV</a>
          <a href={populationExportUrl(collectionId, "json")} download><Download size={15} /> JSON</a>
        </div>
      </header>

      <div className="method-banner" role="note">
        <Info size={17} />
        <p><strong>Descriptive and selection-affected.</strong> The cohorts are nested, so this view does not calculate p-values or treat them as statistically independent.</p>
      </div>

      {population.availability !== "full" && (
        <div className="population-notice" role="status"><CircleAlert size={17} /><div><strong>{humanize(population.availability)} population data</strong><p>{population.missing_data_reasons.join(" ")}</p></div></div>
      )}

      <section className="explorer-controls" aria-label="Population chart controls">
        <label>Cohort focus<select value={focusCohort} onChange={(event) => setFocusCohort(event.target.value as PopulationCohortId)}>{cohorts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>Metric<select value={metric} onChange={(event) => setMetric(event.target.value as PopulationMetricId)}>{metrics.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <span className="control-context">Focus changes emphasis; all available cohorts remain overlaid.</span>
      </section>

      <div className="explorer-grid">
        <section className="population-card population-card--wide" aria-labelledby="distribution-title">
          <header className="population-card__header"><div><span className="eyebrow">Normalized shape</span><h2 id="distribution-title">{metrics.find((item) => item.id === metric)?.label} distribution</h2></div></header>
          <AnimatePresence mode="wait">
            <motion.div key={metric} initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              {available ? <HistogramChart distributions={distributions} focus={focusCohort} reduced={Boolean(reduced)} /> : <UnavailableChart label="Distribution unavailable for this preserved run." />}
            </motion.div>
          </AnimatePresence>
          <DistributionTable distributions={distributions} metric={metric} />
        </section>

        <section className="population-card" aria-labelledby="percentile-title">
          <header className="population-card__header"><div><span className="eyebrow">Robust summaries</span><h2 id="percentile-title">Percentile ribbon</h2></div></header>
          {available ? <PercentileRibbon distributions={distributions} focus={focusCohort} reduced={Boolean(reduced)} /> : <UnavailableChart label="Percentiles unavailable." />}
        </section>

        <section className="population-card population-card--wide" aria-labelledby="density-title">
          <header className="population-card__header"><div><span className="eyebrow">Aggregate landscape</span><h2 id="density-title">Baseline value × decline score</h2></div><ScatterChart size={19} /></header>
          {population.density_grid ? <DensityPlot population={population} onOpenHousehold={onOpenHousehold} reduced={Boolean(reduced)} /> : <UnavailableChart label="Density grid unavailable for this preserved run." />}
        </section>

        <section className="population-card" aria-labelledby="sensitivity-title">
          <header className="population-card__header"><div><span className="eyebrow">Declared detector policy</span><h2 id="sensitivity-title">Threshold sensitivity</h2></div></header>
          {population.threshold_sensitivity.length > 0 ? <SensitivityChart population={population} reduced={Boolean(reduced)} /> : <UnavailableChart label="Sensitivity counts unavailable." />}
        </section>
      </div>

      <section className="population-card cohort-definition-card" aria-labelledby="definitions-title">
        <header className="population-card__header"><div><span className="eyebrow">Methods</span><h2 id="definitions-title">Cohort definitions and window</h2></div></header>
        <dl className="cohort-definitions">
          {cohorts.map((item) => <div key={item.id}><dt>{item.label}</dt><dd>{population.cohort_definitions[item.id]}</dd></div>)}
        </dl>
        <p className="window-note">
          Baseline weeks {population.analysis_windows.baseline_start_week ?? "—"}–{population.analysis_windows.baseline_end_week ?? "—"}; recent weeks {population.analysis_windows.recent_start_week ?? "—"}–{population.analysis_windows.recent_end_week ?? "—"}. Decline threshold {population.detector_policy.decline_threshold === null ? "unavailable" : formatPercent(population.detector_policy.decline_threshold)}.
        </p>
      </section>
    </div>
  );
}

type DistributionItem = { cohort: PopulationCohortId; data: PopulationMetric | null };

/** Draws normalized common-bin histograms for every available cohort. */
function HistogramChart({ distributions, focus, reduced }: { distributions: DistributionItem[]; focus: PopulationCohortId; reduced: boolean }) {
  const width = 720;
  const height = 250;
  const margin = { left: 38, right: 12, top: 20, bottom: 30 };
  const maximum = Math.max(0.01, ...distributions.flatMap((item) => item.data?.histogram.map((bin) => bin.share) ?? []));
  const bins = Math.max(1, ...distributions.map((item) => item.data?.histogram.length ?? 0));
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  return (
    <figure className="population-figure">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Overlaid normalized histograms for eligible, flagged, and investigated households">
        {[0, 0.5, 1].map((tick) => <g key={tick}><line x1={margin.left} x2={width - margin.right} y1={margin.top + innerHeight * (1 - tick)} y2={margin.top + innerHeight * (1 - tick)} className="chart-gridline" /><text x={margin.left - 7} y={margin.top + innerHeight * (1 - tick) + 4} textAnchor="end">{formatPercent(maximum * tick)}</text></g>)}
        {distributions.map(({ cohort, data }) => data?.histogram.map((bin, index) => {
          const slot = innerWidth / bins;
          const barWidth = Math.max(1, slot / 3 - 1);
          const cohortIndex = cohorts.findIndex((item) => item.id === cohort);
          const barHeight = (bin.share / maximum) * innerHeight;
          return <motion.rect key={`${cohort}-${index}`} x={margin.left + index * slot + cohortIndex * barWidth} width={barWidth} y={margin.top + innerHeight - barHeight} height={barHeight} fill={cohortColors[cohort]} opacity={focus === cohort ? 0.94 : 0.42} initial={reduced ? false : { height: 0, y: margin.top + innerHeight }} animate={{ height: barHeight, y: margin.top + innerHeight - barHeight }} transition={{ duration: 0.42, delay: index * 0.012 }} />;
        }))}
        <line x1={margin.left} x2={width - margin.right} y1={margin.top + innerHeight} y2={margin.top + innerHeight} className="chart-axis" />
      </svg>
      <figcaption className="chart-legend">{cohorts.map((item) => <span key={item.id}><i style={{ background: cohortColors[item.id] }} />{item.label}</span>)}</figcaption>
    </figure>
  );
}

/** Provides the visible tabular equivalent and descriptive cohort gaps. */
function DistributionTable({ distributions, metric }: { distributions: DistributionItem[]; metric: PopulationMetricId }) {
  /** Formats a nullable population metric according to its declared unit. */
  const format = (value: number | null, unit?: string) => value === null ? "Unavailable" : unit === "share" ? formatPercent(value, 1) : formatCurrency(value);
  return (
    <div className="population-table-wrap"><table className="population-table"><caption>Text equivalent for {humanize(metric)}</caption><thead><tr><th>Cohort</th><th>n</th><th>Median</th><th>IQR</th><th>Descriptive median gap vs eligible</th></tr></thead><tbody>{distributions.map(({ cohort, data }) => {
      const eligibleMedian = distributions.find((item) => item.cohort === "eligible")?.data?.median ?? null;
      const gap = data?.median !== null && data?.median !== undefined && eligibleMedian !== null ? data.median - eligibleMedian : null;
      return <tr key={cohort}><th>{humanize(cohort)}</th><td>{data?.count ?? "Unavailable"}</td><td>{format(data?.median ?? null, data?.unit)}</td><td>{data?.q25 === null || data?.q75 === null || !data ? "Unavailable" : `${format(data.q25, data.unit)} – ${format(data.q75, data.unit)}`}</td><td>{format(gap, data?.unit)}</td></tr>;
    })}</tbody></table></div>
  );
}

/** Draws ranges, interquartile ribbons, and median ticks on one shared scale. */
function PercentileRibbon({ distributions, focus, reduced }: { distributions: DistributionItem[]; focus: PopulationCohortId; reduced: boolean }) {
  const values = distributions.flatMap((item) => item.data ? [item.data.minimum, item.data.maximum] : []).filter((item): item is number => item !== null);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  /** Maps one metric value into the ribbon's shared horizontal coordinates. */
  const scale = (value: number) => 24 + ((value - minimum) / Math.max(1e-9, maximum - minimum)) * 452;
  return <figure className="percentile-ribbon"><svg viewBox="0 0 500 170" role="img" aria-label="Quartile and median ribbon by cohort">{distributions.map(({ cohort, data }, index) => {
    if (!data || data.minimum === null || data.maximum === null || data.q25 === null || data.q75 === null || data.median === null) return null;
    return <g key={cohort} opacity={focus === cohort ? 1 : 0.55}><text x="20" y={38 + index * 48}>{humanize(cohort)}</text><line x1={scale(data.minimum)} x2={scale(data.maximum)} y1={48 + index * 48} y2={48 + index * 48} stroke={cohortColors[cohort]} strokeWidth="2" /><motion.rect x={scale(data.q25)} y={39 + index * 48} width={scale(data.q75) - scale(data.q25)} height="18" rx="5" fill={cohortColors[cohort]} initial={reduced ? false : { scaleX: 0 }} animate={{ scaleX: 1 }} style={{ transformOrigin: `${scale(data.q25)}px center` }} /><line x1={scale(data.median)} x2={scale(data.median)} y1={36 + index * 48} y2={60 + index * 48} className="ribbon-median" /></g>;
  })}</svg><figcaption>Whiskers show range; bars show IQR; ticks show medians.</figcaption></figure>;
}

/** Draws aggregate density cells plus only the investigated identifiable points. */
function DensityPlot({ population, onOpenHousehold, reduced }: { population: PopulationSummary; onOpenHousehold: (id: string) => void; reduced: boolean }) {
  const grid = population.density_grid;
  if (!grid) return null;
  const width = 720;
  const height = 300;
  const xMin = grid.x_edges[0] ?? 0;
  const xMax = grid.x_edges.at(-1) ?? 1;
  const yMin = grid.y_edges[0] ?? 0;
  const yMax = grid.y_edges.at(-1) ?? 1;
  /** Maps baseline retailer value onto the declared log1p display scale. */
  const x = (value: number) => 52 + ((Math.log1p(value) - Math.log1p(xMin)) / Math.max(1e-9, Math.log1p(xMax) - Math.log1p(xMin))) * 646;
  /** Maps decline score onto the plot's vertical display scale. */
  const y = (value: number) => 266 - ((value - yMin) / Math.max(1e-9, yMax - yMin)) * 238;
  const maximum = Math.max(1, ...grid.cells.map((cell) => cell.eligible_count));
  return <figure className="density-plot"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Aggregate density of baseline retailer value versus decline score, with investigated households overlaid">{grid.cells.map((cell, index) => cell.x_lower === null || cell.x_upper === null || cell.y_lower === null || cell.y_upper === null ? null : <rect key={index} x={x(cell.x_lower)} y={y(cell.y_upper)} width={Math.max(1, x(cell.x_upper) - x(cell.x_lower))} height={Math.max(1, y(cell.y_lower) - y(cell.y_upper))} fill="var(--chart)" opacity={0.08 + 0.7 * (cell.eligible_count / maximum)} />)}{population.investigated_households.map((item) => item.baseline_retailer_sales_value === null || item.decline_score === null ? null : <motion.circle key={item.household_id} role="button" tabIndex={0} aria-label={`Open household ${item.household_id}, decline score ${formatPercent(item.decline_score)}`} cx={x(item.baseline_retailer_sales_value)} cy={y(item.decline_score)} r="6" fill="var(--accent)" stroke="var(--forest)" strokeWidth="2" initial={reduced ? false : { opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }} transition={reduced ? { duration: 0 } : { type: "spring", delay: item.rank * 0.05 }} onClick={() => onOpenHousehold(item.household_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onOpenHousehold(item.household_id); }} />)}<line x1="52" x2="698" y1="266" y2="266" className="chart-axis" /><line x1="52" x2="52" y1="28" y2="266" className="chart-axis" /><text x="375" y="294" textAnchor="middle">Baseline retailer sales value · log scale</text><text transform="translate(14 150) rotate(-90)" textAnchor="middle">Decline score</text></svg><figcaption>Cell shading contains aggregate counts only. Orange points are the identifiable investigated batch.</figcaption></figure>;
}

/** Draws the predeclared threshold sensitivity curve and exact text values. */
function SensitivityChart({ population, reduced }: { population: PopulationSummary; reduced: boolean }) {
  const rows = population.threshold_sensitivity.filter((item) => item.threshold !== null && item.flagged_share !== null);
  const points = rows.map((item, index) => ({ x: 38 + index * (410 / Math.max(1, rows.length - 1)), y: 150 - (item.flagged_share ?? 0) * 125, ...item }));
  const path = points.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  return <figure className="sensitivity-chart"><svg viewBox="0 0 470 190" role="img" aria-label="Flagged household share across declared decline thresholds"><line x1="38" x2="448" y1="150" y2="150" className="chart-axis" /><motion.path d={path} fill="none" stroke="var(--chart)" strokeWidth="4" initial={reduced ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.7 }} />{points.map((point) => <g key={point.threshold}><circle cx={point.x} cy={point.y} r="5" fill="var(--forest)" /><text x={point.x} y="174" textAnchor="middle">{formatPercent(point.threshold ?? 0)}</text><text x={point.x} y={point.y - 10} textAnchor="middle">{formatPercent(point.flagged_share ?? 0)}</text></g>)}</svg><figcaption>{rows.map((item) => `${formatPercent(item.threshold ?? 0)} threshold: ${item.flagged_households ?? "—"} flagged`).join(" · ")}</figcaption></figure>;
}

/** Shows an explicit unavailable state instead of a misleading zero-valued chart. */
function UnavailableChart({ label }: { label: string }) {
  return <div className="chart-unavailable" role="status"><CircleAlert size={20} /><span>{label}</span></div>;
}
