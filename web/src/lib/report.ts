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

export function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/gu, (character) => character.toUpperCase());
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1_000 ? 0 : 2,
  }).format(value);
}

export function formatNumber(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

export function formatPercent(value: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatMetricValue(value: number, unit: string | null): string {
  if (unit && currencyUnits.has(unit)) return formatCurrency(value);
  if (unit && percentageUnits.has(unit)) return formatPercent(value, 1);
  return formatNumber(value, Math.abs(value) < 10 ? 2 : 1);
}

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

export function compactId(value: string, length = 8): string {
  if (value.length <= length * 2 + 1) return value;
  return `${value.slice(0, length)}…${value.slice(-length)}`;
}

export function meaningfulTrace(trace: TraceEvent[]): TraceEvent[] {
  return trace.filter((item) => item.event !== "evidence_added");
}

export function eventLabel(event: string): string {
  const labels: Record<string, string> = {
    run_started: "Investigation started",
    model_decision_requested: "Question prepared",
    model_decision_received: "Analytical choice made",
    tool_started: "Tool started",
    tool_completed: "Tool completed",
    tool_failed: "Tool failed",
    tool_retried: "Tool retried",
    evidence_added: "Evidence recorded",
    finish_requested: "Recommendation proposed",
    verification_started: "Verification started",
    verification_failed: "Verification requested repair",
    verification_passed: "Verification passed",
    fallback_applied: "Safe fallback applied",
    run_completed: "Investigation completed",
  };
  return labels[event] ?? humanize(event);
}

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
