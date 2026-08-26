/** Converts validated report contracts into consistent human-readable dashboard values. */

import type { EvidenceRecord, ReportData, TraceEvent } from "../types";

export interface TrendPoint {
  week: number;
  value: number;
}

const currencyUnits = new Set([
  "retailer_sales_value",
  "retailer_sales_value_per_trip",
  "retailer_sales_value_per_basket",
]);

const percentageUnits = new Set(["share", "fraction", "proportion", "rate", "ratio"]);

/** Converts a machine identifier into a title-like display label. */
export function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/gu, (character) => character.toUpperCase());
}

/** Formats retailer sales value in the dashboard's fixed US-dollar presentation. */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1_000 ? 0 : 2,
  }).format(value);
}

/** Formats a finite metric with a bounded number of decimal places. */
export function formatNumber(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

/** Formats a stored ratio as a percentage for reviewer display. */
export function formatPercent(value: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: digits,
  }).format(value);
}

/** Chooses currency, percent, or numeric formatting from an evidence unit. */
export function formatMetricValue(value: number, unit: string | null): string {
  if (unit && currencyUnits.has(unit)) return formatCurrency(value);
  if (unit && percentageUnits.has(unit)) return formatPercent(value, 1);
  return formatNumber(value, Math.abs(value) < 10 ? 2 : 1);
}

/** Extracts and sorts valid weekly retailer-sales evidence from a report ledger. */
export function weeklyTrend(report: ReportData): TrendPoint[] {
  return report.evidence_ledger
    .filter(
      (item) =>
        item.metric === "weekly_retailer_sales_value" &&
        typeof item.value === "number" &&
        Number.isFinite(Number(item.dimensions.week)),
    )
    .map((item) => ({ week: Number(item.dimensions.week), value: item.value as number }))
    .sort((left, right) => left.week - right.week);
}

/** Selects the paired, scalar, text, or unavailable display form for one record. */
export function evidenceDisplayValue(record: EvidenceRecord): string {
  if (record.text_value) return record.text_value;
  if (record.baseline_value !== null || record.recent_value !== null) {
    const baseline =
      record.baseline_value === null
        ? "—"
        : formatMetricValue(record.baseline_value, record.unit);
    const recent =
      record.recent_value === null
        ? "—"
        : formatMetricValue(record.recent_value, record.unit);
    return `${baseline} → ${recent}`;
  }
  if (record.value !== null) return formatMetricValue(record.value, record.unit);
  return "Not available";
}

/** Shortens a long identifier for display while leaving short identifiers intact. */
export function compactId(value: string, length = 8): string {
  if (value.length <= length * 2 + 1) return value;
  return `${value.slice(0, length)}…${value.slice(-length)}`;
}

/** Removes evidence-write noise from the default audit timeline. */
export function meaningfulTrace<T extends TraceEvent>(trace: T[]): T[] {
  return trace.filter((item) => item.event !== "evidence_added");
}

/** Removes implementation vocabulary from errors before they reach product UI. */
export function productMessage(message: string, fallback: string): string {
  if (/GEMINI_API_KEY|API key/iu.test(message)) {
    return "The secure model connection is not configured. Ask an administrator to enable live analysis.";
  }
  const normalized = message
    .replace(/\bWhyBack CLI\b/giu, "analysis")
    .replace(/\bCLI\b/giu, "analysis")
    .replace(/\bsubprocess\b/giu, "analysis job")
    .replace(/\bprocess\b/giu, "analysis job")
    .replace(/\bdashboard bridge\b/giu, "analytics service")
    .replace(/\bbridge\b/giu, "analytics service")
    .replace(/\bartifact collection\b/giu, "result set")
    .replace(/\bartifacts\b/giu, "results")
    .replace(/\bartifact\b/giu, "result")
    .replace(/\bmanifest\b/giu, "verification record")
    .replace(/\btrace JSONL\b/giu, "decision history")
    .replace(/\bJSONL\b/giu, "decision history")
    .replace(/\brepository \.env or server environment\b/giu, "secure configuration")
    .trim();
  return normalized || fallback;
}

/** Returns a reviewer-friendly label for known audit events. */
export function eventLabel(event: string): string {
  const labels: Record<string, string> = {
    run_started: "Investigation started",
    model_decision_requested: "Question prepared",
    model_decision_rejected: "Invalid analytical response rejected",
    model_decision_received: "Analytical choice made",
    tool_started: "Analytical check started",
    tool_completed: "Analytical check completed",
    tool_partial: "Analytical check returned partial evidence",
    tool_failed: "Analytical check failed",
    retry_scheduled: "Retry scheduled",
    evidence_added: "Evidence recorded",
    evidence_batch: "Evidence summary",
    finish_requested: "Recommendation proposed",
    verification_started: "Verification started",
    verification_rejected: "Verification requested repair",
    verification_passed: "Verification passed",
    run_completed: "Investigation completed",
  };
  return labels[event] ?? humanize(event);
}

/** Returns the governed display name for a catalog action ID. */
export function actionLabel(actionId: string): string {
  const labels: Record<string, string> = {
    VISIT_FREQUENCY_REACTIVATION: "Restore visit rhythm",
    CATEGORY_REENGAGEMENT: "Rebuild category relevance",
    BASKET_BUILDING: "Rebuild basket depth",
    PROMOTION_REENGAGEMENT: "Test promotion relevance",
    COUPON_REENGAGEMENT: "Test coupon relevance",
    INSUFFICIENT_EVIDENCE: "Gather more evidence",
  };
  return labels[actionId] ?? humanize(actionId);
}

/** Collects visible limitations once while preserving their first-seen order. */
export function uniqueLimitations(report: ReportData): string[] {
  const values = [
    ...report.limitations,
    ...report.uncertainties,
    ...report.alternative_explanations,
    ...report.likely_drivers.flatMap((driver) => driver.limitations ?? []),
    ...(report.population_context?.limitations ?? []),
    ...(report.interpretation_limits?.causal_limitations ?? []),
    ...(report.interpretation_limits?.unobserved_factors ?? []),
  ];
  return [...new Set(values)];
}
