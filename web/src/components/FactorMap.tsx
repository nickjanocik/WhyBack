/** Investigated-household factor, context, and governed-action comparison view. */

import { ArrowRight, CircleAlert, Filter, Network, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";

import { formatNumber, formatPercent, humanize } from "../lib/report";
import type { InvestigatedPopulationHousehold, PopulationSummary } from "../types";

interface FactorMapProps {
  population: PopulationSummary;
  onOpenHousehold: (householdId: string) => void;
}

type SortKey = "rank" | "decline_score" | "sales_drop" | "population_gap" | "warnings";

const NO_ACTION_KEY = "NO_PUBLISHED_RECOMMENDATION";

/** Keeps failed investigations visible without presenting missing output as data loss. */
function actionKey(row: InvestigatedPopulationHousehold): string {
  return row.action_id ?? NO_ACTION_KEY;
}

/** Renders cross-household differences without hiding insufficient or failed outcomes. */
export function FactorMap({ population, onOpenHousehold }: FactorMapProps) {
  const reduced = useReducedMotion();
  const rows = population.investigated_households;
  const [factorType, setFactorType] = useState("all");
  const [factorLabel, setFactorLabel] = useState("all");
  const [status, setStatus] = useState("all");
  const [context, setContext] = useState("all");
  const [action, setAction] = useState("all");
  const [confidence, setConfidence] = useState("all");
  const [sort, setSort] = useState<SortKey>("rank");
  const filtered = useMemo(() => rows.filter((row) =>
    (factorType === "all" || row.identified_factor.factor_type === factorType) &&
    (factorLabel === "all" || row.identified_factor.label === factorLabel) &&
    (status === "all" || row.status === status) &&
    (context === "all" || row.context_classification === context) &&
    (action === "all" || actionKey(row) === action) &&
    (confidence === "all" || row.confidence === confidence),
  ), [action, confidence, context, factorLabel, factorType, rows, status]);
  const sorted = useMemo(() => [...filtered].sort((left, right) => {
    if (sort === "rank") return left.rank - right.rank;
    if (sort === "warnings") return right.warnings.length - left.warnings.length;
    return (right[sort] ?? Number.NEGATIVE_INFINITY) - (left[sort] ?? Number.NEGATIVE_INFINITY);
  }), [filtered, sort]);

  return (
    <div className="population-page factor-map-page">
      <header className="population-page__heading">
        <div><span className="eyebrow">Household-difference view</span><h1>Factor Map</h1><p>Trace observed context into verified factors and governed actions.</p></div>
        <div className="factor-denominator"><strong>{filtered.length}</strong><span>of {rows.length} investigated</span></div>
      </header>

      <div className="method-banner" role="note"><CircleAlert size={17} /><p><strong>Every outcome stays visible.</strong> Insufficient-evidence and failed investigations remain in denominators unless a visible filter excludes them.</p></div>

      <section className="factor-filters" aria-label="Factor map filters">
        <span><Filter size={15} /> Filters</span>
        <FilterSelect label="Status" value={status} onChange={setStatus} rows={rows} getValue={(row) => row.status} />
        <FilterSelect label="Context" value={context} onChange={setContext} rows={rows} getValue={(row) => row.context_classification} />
        <FilterSelect label="Factor type" value={factorType} onChange={(value) => { setFactorType(value); setFactorLabel("all"); }} rows={rows} getValue={(row) => row.identified_factor.factor_type} />
        <FilterSelect label="Action" value={action} onChange={setAction} rows={rows} getValue={actionKey} />
        <FilterSelect label="Confidence" value={confidence} onChange={setConfidence} rows={rows} getValue={(row) => row.confidence} />
        <button type="button" onClick={() => { setStatus("all"); setContext("all"); setFactorType("all"); setFactorLabel("all"); setAction("all"); setConfidence("all"); }}>Clear all</button>
      </section>

      <div className="factor-grid">
        <section className="population-card population-card--wide" aria-labelledby="factor-flow-title">
          <header className="population-card__header"><div><span className="eyebrow">Investigated flow</span><h2 id="factor-flow-title">Context → factor → action</h2></div><Network size={19} /></header>
          <AnimatePresence mode="wait"><motion.div key={`${factorType}-${factorLabel}-${status}-${context}-${action}-${confidence}`} initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><FactorFlow rows={filtered} reduced={Boolean(reduced)} /></motion.div></AnimatePresence>
        </section>

        <section className="population-card" aria-labelledby="factor-rankings-title">
          <header className="population-card__header"><div><span className="eyebrow">Ranked differences</span><h2 id="factor-rankings-title">Factors and actions</h2></div></header>
          <FactorRankings rows={filtered} selectedFactor={factorLabel} onSelectFactor={setFactorLabel} reduced={Boolean(reduced)} />
        </section>
      </div>

      <section className="population-card household-heatmap-card" aria-labelledby="household-heatmap-title">
        <header className="population-card__header"><div><span className="eyebrow">Comparable household rows</span><h2 id="household-heatmap-title">Household difference heatmap</h2></div><label>Sort by<select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}><option value="rank">Batch rank</option><option value="decline_score">Decline score</option><option value="sales_drop">Sales drop</option><option value="population_gap">Population gap</option><option value="warnings">Warnings</option></select></label></header>
        <HouseholdHeatmap rows={sorted} onOpenHousehold={onOpenHousehold} />
      </section>
    </div>
  );
}

/** Renders one categorical household filter from values present in the batch. */
function FilterSelect({ label, value, onChange, rows, getValue }: { label: string; value: string; onChange: (value: string) => void; rows: InvestigatedPopulationHousehold[]; getValue: (row: InvestigatedPopulationHousehold) => string }) {
  const values = [...new Set(rows.map(getValue))].sort();
  return <label><span>{label}</span><select aria-label={`Filter by ${label.toLowerCase()}`} value={value} onChange={(event) => onChange(event.target.value)}><option value="all">All</option>{values.map((item) => <option value={item} key={item}>{humanize(item)}</option>)}</select></label>;
}

/** Draws count-weighted context-to-factor-to-action paths and a text table. */
function FactorFlow({ rows, reduced }: { rows: InvestigatedPopulationHousehold[]; reduced: boolean }) {
  if (rows.length === 0) return <div className="chart-unavailable"><CircleAlert size={20} />No households match these filters.</div>;
  const contexts = [...new Set(rows.map((row) => row.context_classification))];
  const factors = [...new Set(rows.map((row) => row.identified_factor.label))];
  const actions = [...new Set(rows.map(actionKey))];
  /** Positions a category evenly within its flow column. */
  const yFor = (value: string, values: string[]) => 42 + values.indexOf(value) * (230 / Math.max(1, values.length - 1));
  const paths = new Map<string, { context: string; factor: string; action: string; count: number }>();
  for (const row of rows) {
    const actionId = actionKey(row);
    const key = `${row.context_classification}|${row.identified_factor.label}|${actionId}`;
    const item = paths.get(key) ?? { context: row.context_classification, factor: row.identified_factor.label, action: actionId, count: 0 };
    item.count += 1;
    paths.set(key, item);
  }
  return <figure className="factor-flow"><svg viewBox="0 0 850 320" role="img" aria-label="Flow from context classification through identified factor to governed action; line width represents household count"><text x="30" y="20" className="flow-heading">CONTEXT</text><text x="345" y="20" className="flow-heading">IDENTIFIED FACTOR</text><text x="675" y="20" className="flow-heading">GOVERNED ACTION</text>{[...paths.values()].map((item) => {
    const contextY = yFor(item.context, contexts);
    const factorY = yFor(item.factor, factors);
    const actionY = yFor(item.action, actions);
    return <g key={`${item.context}-${item.factor}-${item.action}`}><motion.path d={`M 185 ${contextY} C 250 ${contextY}, 280 ${factorY}, 350 ${factorY}`} fill="none" stroke="var(--chart)" strokeOpacity="0.48" strokeWidth={3 + item.count * 3} initial={reduced ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.6 }} /><motion.path d={`M 515 ${factorY} C 580 ${factorY}, 610 ${actionY}, 680 ${actionY}`} fill="none" stroke="var(--accent)" strokeOpacity="0.58" strokeWidth={3 + item.count * 3} initial={reduced ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.6, delay: 0.15 }} /></g>;
  })}{contexts.map((item) => <FlowNode key={item} x={28} y={yFor(item, contexts)} label={humanize(item)} count={rows.filter((row) => row.context_classification === item).length} />)}{factors.map((item) => <FlowNode key={item} x={350} y={yFor(item, factors)} label={item} count={rows.filter((row) => row.identified_factor.label === item).length} />)}{actions.map((item) => <FlowNode key={item} x={680} y={yFor(item, actions)} label={humanize(item)} count={rows.filter((row) => actionKey(row) === item).length} />)}</svg><figcaption><table><thead><tr><th>Context</th><th>Factor</th><th>Action</th><th>Households</th></tr></thead><tbody>{[...paths.values()].map((item) => <tr key={`${item.context}-${item.factor}-${item.action}`}><td>{humanize(item.context)}</td><td>{item.factor}</td><td>{humanize(item.action)}</td><td>{item.count}</td></tr>)}</tbody></table></figcaption></figure>;
}

/** Draws one labeled flow node with its non-color count cue. */
function FlowNode({ x, y, label, count }: { x: number; y: number; label: string; count: number }) {
  return <g><rect x={x} y={y - 18} width="165" height="36" rx="10" className="flow-node" /><text x={x + 10} y={y + 3}>{label.length > 20 ? `${label.slice(0, 19)}…` : label}</text><text x={x + 150} y={y + 3} textAnchor="end" className="flow-count">{count}</text></g>;
}

/** Ranks factor and action counts while making factor bars keyboard-filterable. */
function FactorRankings({ rows, selectedFactor, onSelectFactor, reduced }: { rows: InvestigatedPopulationHousehold[]; selectedFactor: string; onSelectFactor: (factor: string) => void; reduced: boolean }) {
  /** Counts and sorts one selected row dimension. */
  const count = (getKey: (row: InvestigatedPopulationHousehold) => string) => [...rows.reduce((map, row) => map.set(getKey(row), (map.get(getKey(row)) ?? 0) + 1), new Map<string, number>())].sort((left, right) => right[1] - left[1]);
  const factorRows = [...rows.reduce((map, row) => {
    const key = `${row.identified_factor.factor_type}|${row.identified_factor.label}`;
    const current = map.get(key) ?? {
      factorType: row.identified_factor.factor_type,
      label: row.identified_factor.label,
      count: 0,
    };
    current.count += 1;
    map.set(key, current);
    return map;
  }, new Map<string, { factorType: string; label: string; count: number }>()).values()].sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  const actions = count(actionKey);
  const maximum = Math.max(1, ...factorRows.map((item) => item.count), ...actions.map((item) => item[1]));
  return <div className="factor-rankings"><h3>Factors</h3>{factorRows.map((item, index) => <button type="button" className={selectedFactor === item.label ? "selected" : ""} onClick={() => onSelectFactor(selectedFactor === item.label ? "all" : item.label)} key={`${item.factorType}-${item.label}`}><span>{item.label}</span><i><motion.b initial={reduced ? false : { width: 0 }} animate={{ width: `${(item.count / maximum) * 100}%` }} transition={{ delay: index * 0.05 }} /></i><strong>{item.count}</strong></button>)}<h3>Actions</h3>{actions.map(([key, value], index) => <div className="factor-ranking-row" key={key}><span>{humanize(key)}</span><i><motion.b initial={reduced ? false : { width: 0 }} animate={{ width: `${(value / maximum) * 100}%` }} transition={{ delay: index * 0.05 }} /></i><strong>{value}</strong></div>)}</div>;
}

/** Converts one bounded magnitude into a CSS heat-cell intensity. */
function heatStyle(value: number | null, signed = false) {
  if (value === null) return undefined;
  const magnitude = Math.min(1, Math.abs(value));
  return { "--heat": magnitude, "--heat-hue": signed && value > 0 ? "145" : "25" } as React.CSSProperties;
}

/** Renders sortable household differences with explicit status and warning cues. */
function HouseholdHeatmap({ rows, onOpenHousehold }: { rows: InvestigatedPopulationHousehold[]; onOpenHousehold: (id: string) => void }) {
  /** Formats nullable household gaps without replacing missing values with zero. */
  const pct = (value: number | null) => value === null ? "—" : formatPercent(value, 1);
  return <div className="population-table-wrap"><table className="population-table household-heatmap"><caption>Filtered investigated-household metrics and governed outcomes</caption><thead><tr><th>Household</th><th>Status</th><th>Sales drop</th><th>Trip drop</th><th>Week drop</th><th>Population gap</th><th>Peer gap</th><th>Category-specific</th><th>Confidence</th><th>Warnings</th><th>Factor</th></tr></thead><tbody>{rows.map((row) => <tr key={row.household_id}><th><button type="button" onClick={() => onOpenHousehold(row.household_id)}>#{formatNumber(row.rank)} · {row.household_id}<ArrowRight size={13} /></button></th><td><span className={`outcome-chip outcome-chip--${row.status}`}>{row.status === "completed" ? "✓" : row.status === "failed" ? "×" : "!"} {humanize(row.status)}</span></td><td className="heat-cell" style={heatStyle(row.sales_drop)}>{pct(row.sales_drop)}</td><td className="heat-cell" style={heatStyle(row.trip_drop)}>{pct(row.trip_drop)}</td><td className="heat-cell" style={heatStyle(row.active_week_drop)}>{pct(row.active_week_drop)}</td><td className="heat-cell" style={heatStyle(row.population_gap, true)}>{pct(row.population_gap)}</td><td className="heat-cell" style={heatStyle(row.peer_gap, true)}>{pct(row.peer_gap)}</td><td>{row.identified_factor.factor_type === "category" ? "✓ Specific" : "— No"}</td><td>{humanize(row.confidence)}</td><td>{row.warnings.length > 0 ? <span title={row.warnings.join("\n")}><TriangleAlert size={14} /> {row.warnings.length}</span> : "✓ 0"}</td><td><button type="button" className="factor-link" onClick={() => onOpenHousehold(row.household_id)}>{row.identified_factor.label}</button></td></tr>)}{rows.length === 0 && <tr><td colSpan={11}>No households match the current filters.</td></tr>}</tbody></table></div>;
}
