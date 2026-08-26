/** Collection-level executive summary with descriptive, selection-aware visuals. */

import { ArrowRight, CheckCircle2, CircleAlert, Scale, UsersRound } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { formatCurrency, formatNumber, formatPercent, humanize } from "../lib/report";
import type { PopulationMix, PopulationSummary } from "../types";

interface ExecutiveHomeProps {
  population: PopulationSummary;
  onNavigate: (view: "population" | "factors") => void;
}

const mixColors = ["var(--forest)", "var(--chart)", "var(--accent)", "var(--blue)", "var(--faint)"];

/** Renders the default collection view for business leadership. */
export function ExecutiveHome({ population, onNavigate }: ExecutiveHomeProps) {
  const reduced = useReducedMotion();
  const totals = population.executive;
  const eligible = totals.eligible_count;
  const flagged = totals.flagged_count;
  const investigated = totals.investigated_count;
  const hasCounts = eligible !== null && flagged !== null && investigated !== null;

  return (
    <div className="population-page executive-home">
      <section className="executive-hero" aria-labelledby="executive-title">
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <span className="eyebrow">Executive summary · one analysis window</span>
          <h1 id="executive-title">What changed across the household population?</h1>
          <p className="executive-lede">
            {hasCounts
              ? `${formatNumber(flagged)} of ${formatNumber(eligible)} eligible households were flagged; ${formatNumber(investigated)} were investigated.`
              : `${formatNumber(investigated ?? 0)} household investigations are available; historic population totals are incomplete.`}
          </p>
          <p className="selection-note">
            These cohorts are nested and intentionally selected. Differences are descriptive,
            selection-affected observations—not causal effects or representative estimates.
          </p>
        </motion.div>
        <div className={`availability-badge availability-badge--${population.availability}`}>
          <span aria-hidden="true">●</span> {humanize(population.availability)} population coverage
        </div>
      </section>

      {population.missing_data_reasons.length > 0 && (
        <div className="population-notice" role="status">
          <CircleAlert size={17} />
          <div><strong>Partial population context</strong><p>{population.missing_data_reasons.join(" ")}</p></div>
        </div>
      )}

      <section className="executive-kpis" aria-label="Executive indicators">
        <KpiCard
          index={0}
          reduced={Boolean(reduced)}
          label="Flagged share"
          value={totals.flagged_share === null ? "Unavailable" : formatPercent(totals.flagged_share, 1)}
          detail={flagged === null || eligible === null ? "Historic aggregate unavailable" : `${formatNumber(flagged)} of ${formatNumber(eligible)} eligible`}
        />
        <KpiCard
          index={1}
          reduced={Boolean(reduced)}
          label="Investigated outcomes"
          value={`${totals.completed_count ?? 0} supported`}
          detail={`${totals.insufficient_count ?? 0} insufficient · ${totals.failed_count ?? 0} failed`}
        />
        <KpiCard
          index={2}
          reduced={Boolean(reduced)}
          label="Recorded value change"
          value={totals.recorded_value_change === null ? "Unavailable" : formatCurrency(totals.recorded_value_change)}
          detail="Observed retailer value; not recoverable revenue"
          tone={totals.recorded_value_change !== null && totals.recorded_value_change < 0 ? "warning" : undefined}
        />
        <KpiCard
          index={3}
          reduced={Boolean(reduced)}
          label="Verified action rate"
          value={totals.verified_action_rate === null ? "Unavailable" : formatPercent(totals.verified_action_rate)}
          detail="Supported governed actions / investigated"
        />
      </section>

      <div className="executive-grid">
        <section className="population-card cohort-funnel-card" aria-labelledby="cohort-funnel-title">
          <header className="population-card__header">
            <div><span className="eyebrow">Selection path</span><h2 id="cohort-funnel-title">Cohort funnel</h2></div>
            <UsersRound size={19} />
          </header>
          <CohortFunnel population={population} reduced={Boolean(reduced)} />
        </section>

        <section className="population-card" aria-labelledby="action-mix-title">
          <header className="population-card__header">
            <div><span className="eyebrow">Governed outcomes</span><h2 id="action-mix-title">Action mix</h2></div>
            <CheckCircle2 size={19} />
          </header>
          <SegmentedMix items={totals.action_mix} reduced={Boolean(reduced)} />
        </section>

        <section className="population-card population-card--wide" aria-labelledby="factor-rank-title">
          <header className="population-card__header">
            <div><span className="eyebrow">Household differences</span><h2 id="factor-rank-title">Identified factors</h2></div>
            <Scale size={19} />
          </header>
          <RankedMix items={totals.factor_mix} reduced={Boolean(reduced)} />
        </section>

        <section className="population-card" aria-labelledby="context-mix-title">
          <header className="population-card__header">
            <div><span className="eyebrow">Comparison context</span><h2 id="context-mix-title">Context classifications</h2></div>
          </header>
          <ul className="context-list">
            {totals.context_mix.map((item) => (
              <li key={item.key}><span aria-hidden="true">◆</span><strong>{humanize(item.key)}</strong><b>{item.count}</b></li>
            ))}
            {totals.context_mix.length === 0 && <li>Context classifications unavailable.</li>}
          </ul>
        </section>
      </div>

      <section className="leadership-panels">
        <article className="leadership-panel leadership-panel--act">
          <span className="eyebrow">What leadership can act on</span>
          <h2>Prioritize governed tests where household evidence is differentiated.</h2>
          <p>
            Use the factor and action mix to allocate human review, then inspect how each
            selected household differs from its population and behavioral-peer context.
          </p>
          <button type="button" onClick={() => onNavigate("factors")}>Open Factor Map <ArrowRight size={15} /></button>
        </article>
        <article className="leadership-panel leadership-panel--limit">
          <span className="eyebrow">What the data cannot establish</span>
          <h2>No causal explanation, recoverable revenue, or expected uplift.</h2>
          <p>
            Recorded purchases cover one retailer and one window. The nested selection
            process prevents independent-population inference, and intent or activity
            outside the data remains unobserved.
          </p>
          <button type="button" onClick={() => onNavigate("population")}>Inspect population evidence <ArrowRight size={15} /></button>
        </article>
      </section>
    </div>
  );
}

/** Renders one staggered executive indicator without inferring missing values. */
function KpiCard({
  label,
  value,
  detail,
  index,
  reduced,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  index: number;
  reduced: boolean;
  tone?: "warning";
}) {
  return (
    <motion.article
      className={`executive-kpi ${tone ? `executive-kpi--${tone}` : ""}`}
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
    >
      <span>{label}</span><strong>{value}</strong><small>{detail}</small>
    </motion.article>
  );
}

/** Shows the exact nested cohort counts as a width-scaled funnel. */
function CohortFunnel({ population, reduced }: { population: PopulationSummary; reduced: boolean }) {
  const values = [
    ["Eligible", population.executive.eligible_count],
    ["Flagged", population.executive.flagged_count],
    ["Investigated", population.executive.investigated_count],
  ] as const;
  const maximum = population.executive.eligible_count ?? 1;
  return (
    <figure className="cohort-funnel">
      {values.map(([label, value], index) => {
        const width = value === null ? 0 : Math.max(12, (value / maximum) * 100);
        return (
          <div className="cohort-funnel__row" key={label}>
            <span>{label}</span>
            <div><motion.i initial={reduced ? false : { width: 0 }} animate={{ width: `${width}%` }} transition={{ delay: index * 0.12, duration: 0.55 }} /></div>
            <strong>{value === null ? "—" : formatNumber(value)}</strong>
          </div>
        );
      })}
      <figcaption>Each lower cohort is selected from the cohort above it.</figcaption>
    </figure>
  );
}

/** Shows an aggregate mix as a segmented bar and equivalent labeled list. */
function SegmentedMix({ items, reduced }: { items: PopulationMix[]; reduced: boolean }) {
  return (
    <div className="segmented-mix">
      <div className="segmented-mix__bar" role="img" aria-label={items.map((item) => `${item.label}: ${item.count}`).join(", ")}>
        {items.map((item, index) => (
          <motion.span
            key={item.key}
            style={{ background: mixColors[index % mixColors.length] }}
            initial={reduced ? false : { flexGrow: 0, opacity: 0 }}
            animate={{ flexGrow: item.count, opacity: 1 }}
            transition={{ delay: index * 0.08, duration: 0.45 }}
          />
        ))}
      </div>
      <ul>{items.map((item, index) => <li key={item.key}><i style={{ background: mixColors[index % mixColors.length] }} /><span>{humanize(item.key)}</span><strong>{item.count}</strong></li>)}</ul>
      {items.length === 0 && <p className="chart-unavailable">Action mix unavailable.</p>}
    </div>
  );
}

/** Ranks aggregate mix entries with count-proportional animated bars. */
function RankedMix({ items, reduced }: { items: PopulationMix[]; reduced: boolean }) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className="ranked-mix">
      {items.map((item, index) => (
        <div className="ranked-mix__row" key={`${item.key}-${item.label}`}>
          <span><b>{item.label}</b><small>{humanize(item.key)}</small></span>
          <div><motion.i initial={reduced ? false : { width: 0 }} animate={{ width: `${(item.count / maximum) * 100}%` }} transition={{ delay: index * 0.08, duration: 0.5 }} /></div>
          <strong>{item.count}</strong>
        </div>
      ))}
      {items.length === 0 && <p className="chart-unavailable">Identified factors unavailable.</p>}
    </div>
  );
}
