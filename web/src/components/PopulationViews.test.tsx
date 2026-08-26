/** Exercises population charts, partial states, filtering, and household drill-down. */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  InvestigatedPopulationHousehold,
  PopulationMetric,
  PopulationSummary,
} from "../types";
import { ExecutiveHome } from "./ExecutiveHome";
import { FactorMap } from "./FactorMap";
import { PopulationExplorer } from "./PopulationExplorer";

const distribution: PopulationMetric = {
  metric: "decline_score",
  unit: "share",
  count: 100,
  mean: 0.24,
  minimum: 0,
  q25: 0.1,
  median: 0.2,
  q75: 0.35,
  maximum: 0.9,
  deciles: Array.from({ length: 9 }, (_, index) => ({
    probability: (index + 1) / 10,
    value: (index + 1) / 12,
  })),
  histogram: [
    { lower: 0, upper: 0.3, count: 70, share: 0.7 },
    { lower: 0.3, upper: 1, count: 30, share: 0.3 },
  ],
};

const rows: InvestigatedPopulationHousehold[] = [
  {
    household_id: "101",
    rank: 1,
    status: "completed",
    context_classification: "customer_specific",
    decline_score: 0.78,
    sales_drop: 0.8,
    trip_drop: 0.7,
    active_week_drop: 0.5,
    baseline_retailer_sales_value: 240,
    recent_retailer_sales_value: 48,
    recorded_value_change: -192,
    population_gap: -0.22,
    peer_gap: -0.14,
    identified_factor: {
      factor_type: "cadence",
      label: "Visit cadence",
      detail: "Recorded cadence declined.",
    },
    action_id: "VISIT_FREQUENCY_REACTIVATION",
    action_label: "Restore visit rhythm",
    confidence: "medium",
    warnings: [],
  },
  {
    household_id: "102",
    rank: 2,
    status: "insufficient_evidence",
    context_classification: "broad_pattern",
    decline_score: 0.68,
    sales_drop: 0.7,
    trip_drop: 0.6,
    active_week_drop: 0.4,
    baseline_retailer_sales_value: 180,
    recent_retailer_sales_value: 54,
    recorded_value_change: -126,
    population_gap: -0.12,
    peer_gap: -0.04,
    identified_factor: {
      factor_type: "insufficient_evidence",
      label: "Insufficient evidence",
      detail: "No differentiating factor cleared verification.",
    },
    action_id: "INSUFFICIENT_EVIDENCE",
    action_label: "Gather more evidence",
    confidence: "insufficient",
    warnings: ["One tool was partial."],
  },
  {
    household_id: "103",
    rank: 3,
    status: "failed",
    context_classification: "insufficient_context",
    decline_score: 0.61,
    sales_drop: 0.62,
    trip_drop: 0.58,
    active_week_drop: 0.43,
    baseline_retailer_sales_value: 150,
    recent_retailer_sales_value: 57,
    recorded_value_change: -93,
    population_gap: null,
    peer_gap: null,
    identified_factor: {
      factor_type: "failed",
      label: "Investigation failed",
      detail: "No governed conclusion was published.",
    },
    action_id: null,
    action_label: "No governed action",
    confidence: "unavailable",
    warnings: ["Provider response failed."],
  },
];

const population: PopulationSummary = {
  schema_version: 1,
  availability: "full",
  missing_data_reasons: [],
  cohort_definitions: {
    eligible: "All baseline-eligible households.",
    flagged: "Eligible households at or above the decline threshold.",
    investigated: "The selected ranked batch.",
  },
  analysis_windows: {
    baseline_start_week: 1,
    baseline_end_week: 8,
    recent_start_week: 9,
    recent_end_week: 16,
  },
  detector_policy: {
    minimum_baseline_active_weeks: 4,
    minimum_baseline_distinct_baskets: 6,
    minimum_baseline_retailer_sales_value: 0,
    decline_threshold: 0.3,
    sensitivity_thresholds: [0.2, 0.3, 0.4],
  },
  threshold_sensitivity: [
    { threshold: 0.2, eligible_households: 1_313, flagged_households: 420, flagged_share: 420 / 1_313 },
    { threshold: 0.3, eligible_households: 1_313, flagged_households: 304, flagged_share: 304 / 1_313 },
    { threshold: 0.4, eligible_households: 1_313, flagged_households: 190, flagged_share: 190 / 1_313 },
  ],
  data_quality_warnings: [],
  cohorts: [
    { cohort: "eligible", definition: "All baseline-eligible households.", household_count: 1_313, aggregate_baseline_value: 500_000, aggregate_recent_value: 430_000, gross_recorded_decrease: 90_000, metrics: [distribution] },
    { cohort: "flagged", definition: "Eligible households at or above the decline threshold.", household_count: 304, aggregate_baseline_value: 180_000, aggregate_recent_value: 95_000, gross_recorded_decrease: 88_000, metrics: [{ ...distribution, count: 304, median: 0.48, histogram: [{ lower: 0, upper: 0.3, count: 0, share: 0 }, { lower: 0.3, upper: 1, count: 304, share: 1 }] }] },
    { cohort: "investigated", definition: "The selected ranked batch.", household_count: 3, aggregate_baseline_value: 570, aggregate_recent_value: 159, gross_recorded_decrease: 411, metrics: [{ ...distribution, count: 3, median: 0.68, histogram: [{ lower: 0, upper: 0.3, count: 0, share: 0 }, { lower: 0.3, upper: 1, count: 3, share: 1 }] }] },
  ],
  density_grid: {
    x_metric: "baseline_retailer_sales_value",
    y_metric: "decline_score",
    x_scale: "log1p",
    x_edges: [0, 100, 300],
    y_edges: [0, 0.5, 1],
    cells: [
      { x_lower: 0, x_upper: 100, y_lower: 0, y_upper: 0.5, eligible_count: 900, flagged_count: 80, investigated_count: 0 },
      { x_lower: 100, x_upper: 300, y_lower: 0.5, y_upper: 1, eligible_count: 413, flagged_count: 224, investigated_count: 3 },
    ],
  },
  investigated_households: rows,
  executive: {
    eligible_count: 1_313,
    flagged_count: 304,
    flagged_share: 304 / 1_313,
    selected_count: 3,
    investigated_count: 3,
    completed_count: 1,
    insufficient_count: 1,
    failed_count: 1,
    aggregate_baseline_value: 500_000,
    aggregate_recent_value: 430_000,
    recorded_value_change: -70_000,
    gross_recorded_decrease: 90_000,
    verified_action_rate: 1 / 3,
    action_mix: [
      { key: "VISIT_FREQUENCY_REACTIVATION", label: "Restore visit rhythm", count: 1, share: 1 / 3 },
      { key: "INSUFFICIENT_EVIDENCE", label: "Gather more evidence", count: 1, share: 1 / 3 },
      { key: "NO_PUBLISHED_RECOMMENDATION", label: "No recommendation published", count: 1, share: 1 / 3 },
    ],
    factor_mix: [
      { key: "cadence", label: "Visit cadence", count: 1, share: 1 / 3 },
      { key: "insufficient_evidence", label: "Insufficient evidence", count: 1, share: 1 / 3 },
      { key: "failed", label: "Investigation failed", count: 1, share: 1 / 3 },
    ],
    context_mix: [
      { key: "customer_specific", label: "Customer specific", count: 1, share: 1 / 3 },
      { key: "broad_pattern", label: "Broad pattern", count: 1, share: 1 / 3 },
      { key: "insufficient_context", label: "Insufficient context", count: 1, share: 1 / 3 },
    ],
  },
  provenance: {
    dataset_kind: "official_complete_journey",
    dataset_source_repository: "source",
    dataset_source_commit: "commit",
    backend: "gemini",
    source_manifest: "data_provenance.json",
    generated_at: "2026-08-26T12:00:00Z",
  },
};

describe("population intelligence views", () => {
  it("renders the deterministic executive narrative and decision boundaries", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<ExecutiveHome population={population} onNavigate={onNavigate} />);

    expect(screen.getByText("304 of 1,313 eligible households were flagged; 3 were investigated.")).toBeInTheDocument();
    expect(screen.getByText(/not recoverable revenue/i)).toBeInTheDocument();
    expect(screen.getByText("No recommendation published")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /no causal explanation/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /open factor map/i }));
    expect(onNavigate).toHaveBeenCalledWith("factors");
  });

  it("labels partial recorded value as investigated-household coverage", () => {
    render(
      <ExecutiveHome
        population={{
          ...population,
          availability: "partial",
          executive: {
            ...population.executive,
            aggregate_baseline_value: 570,
            aggregate_recent_value: 159,
            recorded_value_change: -411,
            gross_recorded_decrease: 411,
          },
        }}
        onNavigate={vi.fn()}
      />,
    );

    expect(screen.getByText(/across 3 investigated households only/i)).toBeInTheDocument();
    expect(screen.getByText("-$411.00")).toBeInTheDocument();
  });

  it("supports distribution controls, exports, partial states, and density drill-down", async () => {
    const user = userEvent.setup();
    const onOpenHousehold = vi.fn();
    const { rerender } = render(
      <PopulationExplorer collectionId="live-safe" population={population} onOpenHousehold={onOpenHousehold} />,
    );

    expect(screen.getByRole("link", { name: /csv/i })).toHaveAttribute("href", "/api/population/export?collection=live-safe&format=csv");
    expect(screen.getByRole("table", { name: /text equivalent for decline score/i })).toBeInTheDocument();
    const histogram = screen.getByRole("img", { name: /overlaid normalized histograms/i });
    expect(histogram.querySelector("#population-histogram-plot")).toBeInTheDocument();
    expect(histogram.querySelector('g[clip-path="url(#population-histogram-plot)"]')).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /quartile and median ribbon/i })).toHaveAttribute("viewBox", "0 0 520 218");
    await user.selectOptions(screen.getByLabelText("Metric"), "sales_drop");
    expect(await screen.findByText("Distribution unavailable for this preserved run.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /open household 101/i }));
    expect(onOpenHousehold).toHaveBeenCalledWith("101");

    rerender(
      <PopulationExplorer
        collectionId="live-safe"
        population={{ ...population, availability: "partial", missing_data_reasons: ["Historic distributions unavailable."], density_grid: null }}
        onOpenHousehold={onOpenHousehold}
      />,
    );
    expect(screen.getByText("Historic distributions unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Density grid unavailable for this preserved run.")).toBeInTheDocument();
  });

  it("keeps insufficient and failed outcomes filterable and drills into households", async () => {
    const user = userEvent.setup();
    const onOpenHousehold = vi.fn();
    render(<FactorMap population={population} onOpenHousehold={onOpenHousehold} />);

    expect(screen.getByText("of 3 investigated")).toBeInTheDocument();
    expect(screen.getAllByText("Insufficient Evidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Failed").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Filter by factor type"), "cadence");
    expect(screen.getByText("of 3 investigated").previousSibling).toHaveTextContent("1");
    const heatmap = screen.getByRole("table", { name: /filtered investigated-household metrics/i });
    expect(within(heatmap).getByText(/101/)).toBeInTheDocument();
    expect(within(heatmap).queryByText(/102/)).not.toBeInTheDocument();
    await user.click(within(heatmap).getByRole("button", { name: /101/i }));
    expect(onOpenHousehold).toHaveBeenCalledWith("101");
  });

  it("renders accessible text equivalents when reduced motion is requested", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      }),
    });
    render(<PopulationExplorer collectionId="live-safe" population={population} onOpenHousehold={vi.fn()} />);
    expect(screen.getByRole("table", { name: /text equivalent for decline score/i })).toBeInTheDocument();
    expect(screen.getByText(/cell shading contains aggregate counts only/i)).toBeInTheDocument();
  });
});
