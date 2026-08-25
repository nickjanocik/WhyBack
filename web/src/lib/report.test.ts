import { describe, expect, it } from "vitest";

import type { EvidenceRecord, ReportData } from "../types";
import {
  evidenceDisplayValue,
  formatMetricValue,
  humanize,
  meaningfulTrace,
  uniqueLimitations,
  weeklyTrend,
} from "./report";

function evidence(overrides: Partial<EvidenceRecord>): EvidenceRecord {
  return {
    evidence_id: "ev-1",
    run_id: "run-1",
    household_id: "101",
    role: "context",
    source_tool: "customer_trend",
    source_tool_call_id: "call-1",
    source_status: "ok",
    metric: "weekly_retailer_sales_value",
    dimensions: {},
    baseline_value: null,
    recent_value: null,
    value: null,
    change: null,
    unit: "retailer_sales_value",
    limitations: [],
    query_hash: "hash",
    ...overrides,
  };
}

function report(records: EvidenceRecord[]): ReportData {
  return {
    schema_version: 2,
    product_name: "WhyBack",
    tagline: "Find the why. Choose the way back.",
    investigator_name: "WhyBack Investigator",
    provenance: {
      application_version: "0.1.0",
      backend: "scripted",
      dataset_kind: "synthetic",
      dataset_source_commit: "fixture-v1",
      dataset_source_repository: "fixture",
      execution_mode: "scripted_control",
      generated_at: "2026-08-25T00:00:00Z",
      model: "scripted/whyback-v1",
      prompt_hash: "hash",
      prompt_version: "v1",
      source_hashes: {},
      timing_mode: "actual",
    },
    run_id: "run-1",
    household_id: "101",
    run_status: "completed",
    decline: {
      evidence_id: "detector-1",
      run_id: "run-1",
      household_id: "101",
      source: "decline_detector",
      baseline_start_week: 1,
      baseline_end_week: 8,
      recent_start_week: 9,
      recent_end_week: 16,
      baseline_retailer_sales_value: 160,
      recent_retailer_sales_value: 12,
      baseline_distinct_baskets: 16,
      recent_distinct_baskets: 2,
      baseline_active_weeks: 8,
      recent_active_weeks: 2,
      sales_drop: 0.925,
      trip_drop: 0.875,
      active_week_drop: 0.75,
      decline_score: 0.875,
      eligible: true,
      flagged: true,
      partial_week_limitation: null,
    },
    investigation_path: [],
    likely_drivers: [],
    supporting_evidence: [],
    counterevidence: [],
    evidence_ledger: records,
    alternative_explanations: [],
    uncertainties: ["Outside-retailer activity is unavailable."],
    action: {
      action_id: "VISIT_FREQUENCY_REACTIVATION",
      description: "Human-reviewed cadence test.",
      rationale: "Evidence policy passed.",
      resolved_confidence: "high",
      confidence_cap_applied: false,
      recommended_success_metric: "Trips per week.",
      suggested_experiment: "Compare a holdout.",
      human_review_required: true,
    },
    limitations: ["Outside-retailer activity is unavailable."],
    tool_warnings: [],
    verification_issues: [],
    failure_reason: null,
    human_review_required: true,
  };
}

describe("report presentation helpers", () => {
  it("sorts valid weekly ledger records and ignores other evidence", () => {
    const value = report([
      evidence({ evidence_id: "ev-3", dimensions: { week: "3" }, value: 6 }),
      evidence({ evidence_id: "ev-other", metric: "distinct_trips", value: 2 }),
      evidence({ evidence_id: "ev-1", dimensions: { week: "1" }, value: 20 }),
      evidence({ evidence_id: "ev-invalid", dimensions: { week: "unknown" }, value: 4 }),
    ]);

    expect(weeklyTrend(value)).toEqual([
      { week: 1, value: 20 },
      { week: 3, value: 6 },
    ]);
  });

  it("renders paired, scalar, text, and unavailable evidence values", () => {
    expect(
      evidenceDisplayValue(
        evidence({ baseline_value: 16, recent_value: 3, unit: "count" }),
      ),
    ).toBe("16 → 3");
    expect(evidenceDisplayValue(evidence({ text_value: "unusual decline" }))).toBe(
      "unusual decline",
    );
    expect(evidenceDisplayValue(evidence({ value: 12.5 }))).toBe("$12.50");
    expect(evidenceDisplayValue(evidence({}))).toBe("Not available");
  });

  it("formats ratio and proportion evidence as percentages", () => {
    expect(formatMetricValue(-0.9, "ratio")).toBe("-90%");
    expect(formatMetricValue(1, "proportion")).toBe("100%");
  });

  it("deduplicates visible interpretation limits", () => {
    const value = report([]);
    value.interpretation_limits = {
      observed_scope: [],
      unobserved_factors: ["Competitor purchases are unavailable."],
      causal_limitations: ["Outside-retailer activity is unavailable."],
    };
    expect(uniqueLimitations(value)).toEqual([
      "Outside-retailer activity is unavailable.",
      "Competitor purchases are unavailable.",
    ]);
  });

  it("humanizes contract identifiers and hides noisy evidence-write events", () => {
    expect(humanize("VISIT_FREQUENCY_REACTIVATION")).toBe(
      "VISIT FREQUENCY REACTIVATION",
    );
    expect(
      meaningfulTrace([
        {
          schemaVersion: 1,
          timestamp: "",
          event: "evidence_added",
          runId: "run-1",
          householdId: "101",
          details: {},
        },
        {
          schemaVersion: 1,
          timestamp: "",
          event: "verification_passed",
          runId: "run-1",
          householdId: "101",
          details: {},
        },
      ]),
    ).toHaveLength(1);
  });
});
