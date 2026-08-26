/** Exercises dashboard navigation, live-run controls, accessibility, and report states. */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { runDemo } from "../api";
import type {
  ArtifactCollection,
  DemoStatusResponse,
  LiveRunConfiguration,
  ReportData,
} from "../types";
import { AuditPanel } from "./AuditPanel";
import { CandidateRail } from "./CandidateRail";
import { LiveTraceDrawer } from "./LiveTraceDrawer";
import { OverviewPanel } from "./OverviewPanel";
import { RunCliDialog } from "./RunCliDialog";
import { TrendChart } from "./TrendChart";

const collections: ArtifactCollection[] = [
  {
    id: "live-123e4567-e89b-42d3-a456-426614174000",
    title: "Run · 123e4567",
    datasetKind: "official_complete_journey",
    executionMode: "live",
    backend: "gemini",
    modelExecution: "live_gemini",
    reportCount: 2,
    completedCount: 2,
    humanReviewRequired: true,
    reports: [
      {
        householdId: "101",
        runId: "run-101",
        runStatus: "completed",
        declineScore: 0.875,
        salesDrop: 0.925,
        tripDrop: 0.875,
        activeWeekDrop: 0.75,
        baselineSales: 160,
        recentSales: 12,
        actionId: "VISIT_FREQUENCY_REACTIVATION",
        confidence: "high",
        evidenceCount: 58,
        warningCount: 0,
        generatedAt: "2026-08-25T00:00:00Z",
      },
      {
        householdId: "102",
        runId: "run-102",
        runStatus: "completed",
        declineScore: 0.8,
        salesDrop: 0.86,
        tripDrop: 0.81,
        activeWeekDrop: 0.62,
        baselineSales: 160,
        recentSales: 21,
        actionId: "VISIT_FREQUENCY_REACTIVATION",
        confidence: "high",
        evidenceCount: 58,
        warningCount: 1,
        generatedAt: "2026-08-25T00:00:01Z",
      },
    ],
  },
  {
    id: "live-223e4567-e89b-42d3-b456-426614174000",
    title: "Run · 223e4567",
    datasetKind: "official_complete_journey",
    executionMode: "live",
    backend: "gemini",
    modelExecution: "live_gemini",
    reportCount: 0,
    completedCount: 0,
    humanReviewRequired: true,
    reports: [],
  },
];

const demoCustomerLimits = { minimum: 3, maximum: 24 };
const readyLiveRun: LiveRunConfiguration = {
  backend: "gemini",
  model: "gemini-2.5-flash",
  ready: true,
  blockedReason: null,
};

const idleStatus: DemoStatusResponse = {
  jobId: null,
  status: "idle",
  backend: "gemini",
  model: "gemini-2.5-flash",
  customers: null,
  declineThreshold: null,
  command: null,
  startedAt: null,
  completedAt: null,
  cursor: 0,
  eventCount: 0,
  eventCapacity: 5_000,
  droppedEventCount: 0,
  events: [],
  error: null,
  traceWarning: null,
  collectionId: null,
};

describe("dashboard interactions", () => {
  it("switches artifact collections and household investigations", async () => {
    const user = userEvent.setup();
    const onCollectionChange = vi.fn();
    const onHouseholdChange = vi.fn();
    render(
      <CandidateRail
        collections={collections}
        collectionId={collections[0]!.id}
        householdId="101"
        onCollectionChange={onCollectionChange}
        onHouseholdChange={onHouseholdChange}
      />,
    );

    expect(screen.getByRole("button", { name: /household 101/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Official data · Gemini · 2 completed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /household 102/i }));
    expect(onHouseholdChange).toHaveBeenCalledWith("102");

    await user.selectOptions(screen.getByLabelText("Analysis run"), collections[1]!.id);
    expect(onCollectionChange).toHaveBeenCalledWith(collections[1]!.id);
  });

  it("preserves the original candidate rank when filtering households", async () => {
    const user = userEvent.setup();
    render(
      <CandidateRail
        collections={collections}
        collectionId={collections[0]!.id}
        householdId="101"
        onCollectionChange={vi.fn()}
        onHouseholdChange={vi.fn()}
      />,
    );

    await user.type(screen.getByPlaceholderText("Find household or action"), "102");

    const candidate = screen.getByRole("button", { name: /household 102/i });
    expect(within(candidate).getByText("02")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /household 101/i })).not.toBeInTheDocument();
  });

  it("runs the selected batch with an explicit review sensitivity", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RunCliDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={readyLiveRun}
        onClose={vi.fn()}
        onRun={onRun}
      />,
    );

    const count = screen.getByRole("spinbutton", { name: "Households to investigate" });
    expect(count).toHaveValue(5);
    expect(screen.getByRole("radio", { name: /standard/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /broad/i })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: /focused/i })).not.toBeChecked();
    await user.clear(count);
    await user.type(count, "24");
    await user.click(screen.getByRole("radio", { name: /focused/i }));
    await user.click(screen.getByRole("button", { name: /start analysis/i }));
    expect(onRun).toHaveBeenCalledWith(24, 0.4);
  });

  it("states product guardrails without exposing implementation details", () => {
    render(
      <RunCliDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={readyLiveRun}
        onClose={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByText("Official data")).toBeInTheDocument();
    expect(screen.getByText("Nested cohorts")).toBeInTheDocument();
    expect(screen.getByText(/previous analyses remain available/i)).toBeInTheDocument();
    expect(screen.getByText(/every metric is verified/i)).toBeInTheDocument();
    expect(screen.getByText(/no outreach is executed automatically/i)).toBeInTheDocument();
    expect(screen.getByText(/sets which eligible households enter the flagged cohort/i)).toBeInTheDocument();
    expect(screen.getByText(/recommendation evidence rules stay fixed/i)).toBeInTheDocument();
    expect(screen.getByText(/not a churn probability/i)).toBeInTheDocument();
    expect(screen.queryByText(/\bcli\b|command|server environment/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
  });

  it("reuses the current verified sensitivity and previews its cohort counts", () => {
    render(
      <RunCliDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={readyLiveRun}
        initialDeclineThreshold={0.2}
        thresholdSensitivity={[
          {
            threshold: 0.2,
            eligible_households: 1_313,
            flagged_households: 430,
            flagged_share: 430 / 1_313,
          },
        ]}
        onClose={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByRole("radio", { name: /broad/i })).toBeChecked();
    expect(screen.getByText("430 / 1,313 flagged")).toBeInTheDocument();
  });

  it("explains blocked live readiness without collecting a credential or starting", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RunCliDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={{
          ...readyLiveRun,
          ready: false,
          blockedReason: "GEMINI_API_KEY is not configured. Restart the local bridge after adding it.",
        }}
        onClose={vi.fn()}
        onRun={onRun}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/secure model connection is not configured/i);
    expect(screen.getByRole("alert")).not.toHaveTextContent(/gemini_api_key|api key/i);
    const start = screen.getByRole("button", { name: /start analysis/i });
    expect(start).toBeDisabled();
    for (const option of screen.getAllByRole("radio")) {
      expect(option).toBeDisabled();
    }
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
    await user.click(start);
    expect(onRun).not.toHaveBeenCalled();
  });

  it("submits only the selected run inputs to the analysis service", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => idleStatus,
    });
    vi.stubGlobal("fetch", fetchMock);

    try {
      await runDemo(5, 0.2);
      const request = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
      expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/demo");
      expect(request?.method).toBe("POST");
      expect(JSON.parse(String(request?.body))).toEqual({
        customers: 5,
        declineThreshold: 0.2,
      });
      expect(String(request?.body)).not.toMatch(/api.?key|credential|gemini/i);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("renders sanitized live activity while hiding evidence writes by default", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const status: DemoStatusResponse = {
      jobId: "job-12345678",
      status: "running",
      backend: "gemini",
      model: "gemini-2.5-flash",
      customers: 5,
      declineThreshold: 0.3,
      command: "uv run whyback demo --customers 5 --backend gemini",
      startedAt: "2026-08-25T12:00:00Z",
      completedAt: null,
      cursor: 3,
      eventCount: 3,
      eventCapacity: 5_000,
      droppedEventCount: 4,
      events: [
        {
          id: "job-12345678:1",
          cursor: 1,
          source: "customer_101/trace.jsonl",
          sourceLabel: "Household 101",
          schemaVersion: 1,
          timestamp: "2026-08-25T12:00:01Z",
          event: "model_decision_received",
          runId: "run-101",
          householdId: "101",
          details: {
            investigation_question: "Did visit frequency change?",
            decision_summary: "Use the observed weekly trend to check visit frequency.",
            selected_tool: "customer_trend",
            model: "gemini-3.7-flash",
            prompt_version: "whyback-investigator-v3",
            allowed_tools: ["customer_trend", "category_decomposition"],
            provider_call_id: "provider-call-1",
          },
        },
        {
          id: "job-12345678:2",
          cursor: 2,
          source: "customer_101/trace.jsonl",
          sourceLabel: "Household 101",
          schemaVersion: 1,
          timestamp: "2026-08-25T12:00:02Z",
          event: "evidence_added",
          runId: "run-101",
          householdId: "101",
          details: {
            evidence_id: "ev-1",
            source_tool: "customer_trend",
            source_tool_call_id: "call-1",
            metric: "weekly_retailer_sales_value",
            limitations: ["Observed retailer activity only."],
          },
        },
        {
          id: "job-12345678:3",
          cursor: 3,
          source: "customer_101/trace.jsonl",
          sourceLabel: "Household 101",
          schemaVersion: 1,
          timestamp: "2026-08-25T12:00:03Z",
          event: "evidence_added",
          runId: "run-101",
          householdId: "101",
          details: {
            evidence_id: "ev-2",
            source_tool: "customer_trend",
            source_tool_call_id: "call-1",
            metric: "distinct_trips",
          },
        },
      ],
      error: null,
      traceWarning: "Load failed",
      collectionId: null,
    };
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    render(
      <LiveTraceDrawer
        open
        status={status}
        reportRefreshFailed={false}
        onClose={onClose}
        onRefreshReports={vi.fn()}
        onStartRun={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Live progress" })).toBeInTheDocument();
    expect(screen.getByText("Standard · ≥30%")).toBeInTheDocument();
    expect(screen.queryByText(status.command!)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Analysis stage: Investigate")).toBeInTheDocument();
    expect(screen.getByText(/private model reasoning is never collected/i)).toBeInTheDocument();
    expect(screen.queryByText(/existing verified report remains visible/i)).not.toBeInTheDocument();
    expect(screen.getByText(/reconnecting live updates/i)).toBeInTheDocument();
    expect(screen.queryByText("Load failed")).not.toBeInTheDocument();
    expect(screen.getByText(/4 earlier updates were omitted/i)).toBeInTheDocument();
    expect(screen.getByText("Did visit frequency change?")).toBeInTheDocument();
    expect(
      screen.getByText("Did visit frequency change?").closest(".trace-detail"),
    ).toHaveClass("trace-detail--narrative");
    expect(
      screen
        .getByText("Use the observed weekly trend to check visit frequency.")
        .closest(".trace-detail"),
    ).toHaveClass("trace-detail--narrative");
    expect(screen.getByText("Household 101")).toBeInTheDocument();
    expect(screen.queryByText("gemini-3.7-flash")).not.toBeInTheDocument();
    expect(screen.queryByText("whyback-investigator-v3")).not.toBeInTheDocument();
    expect(screen.queryByText(/provider-call-1|category_decomposition/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence recorded")).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Evidence summaries" }));
    const summary = screen.getByText("Evidence summary").closest("article")!;
    expect(summary).toHaveTextContent("Customer Trend");
    expect(summary).toHaveTextContent("Weekly Retailer Sales Value");
    expect(summary).toHaveTextContent("Distinct Trips");
    expect(summary).toHaveTextContent("Evidence Count2");
    expect(summary).not.toHaveTextContent(/ev-1|ev-2|call-1/i);
    await user.click(screen.getByRole("button", { name: "Close live analysis progress" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("contains live trace focus, closes with Escape, and restores its trigger", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const drawerProps = {
      status: idleStatus,
      reportRefreshFailed: false,
      onClose,
      onRefreshReports: vi.fn(),
      onStartRun: vi.fn(),
    };
    const { rerender } = render(
      <>
        <a className="skip-link" href="#investigation">Skip to investigation</a>
        <header className="app-header">
          <button type="button" aria-controls="live-trace-drawer">Open activity</button>
        </header>
        <div className="workspace-layout" id="investigation">
          <button type="button">Background action</button>
        </div>
        <LiveTraceDrawer {...drawerProps} open={false} />
      </>,
    );
    const trigger = screen.getByRole("button", { name: "Open activity" });
    trigger.focus();

    rerender(
      <>
        <a className="skip-link" href="#investigation">Skip to investigation</a>
        <header className="app-header">
          <button type="button" aria-controls="live-trace-drawer">Open activity</button>
        </header>
        <div className="workspace-layout" id="investigation">
          <button type="button">Background action</button>
        </div>
        <LiveTraceDrawer {...drawerProps} open />
      </>,
    );

    const drawer = await screen.findByRole("dialog", { name: "Live progress" });
    const close = within(drawer).getByRole("button", { name: "Close live analysis progress" });
    await waitFor(() => expect(close).toHaveFocus());
    expect(document.querySelector(".skip-link")).toHaveAttribute("inert");
    expect(document.querySelector(".app-header")).toHaveAttribute("inert");
    expect(document.querySelector(".workspace-layout")).toHaveAttribute("inert");
    expect(within(drawer).getByRole("log", { name: "Live analysis activity" })).toHaveAttribute(
      "tabindex",
      "0",
    );

    within(drawer).getByRole("button", { name: "Configure analysis" }).focus();
    await user.tab();
    expect(close).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();

    rerender(
      <>
        <a className="skip-link" href="#investigation">Skip to investigation</a>
        <header className="app-header">
          <button type="button" aria-controls="live-trace-drawer">Open activity</button>
        </header>
        <div className="workspace-layout" id="investigation">
          <button type="button">Background action</button>
        </div>
        <LiveTraceDrawer {...drawerProps} open={false} />
      </>,
    );

    await waitFor(() => expect(screen.getByRole("button", { name: "Open activity" })).toHaveFocus());
    expect(document.querySelector(".skip-link")).not.toHaveAttribute("inert");
    expect(document.querySelector(".app-header")).not.toHaveAttribute("inert");
    expect(document.querySelector(".workspace-layout")).not.toHaveAttribute("inert");
  });

  it("offers a genuinely new analysis after a completed review", async () => {
    const user = userEvent.setup();
    const onStartRun = vi.fn();
    const completedStatus: DemoStatusResponse = {
      ...idleStatus,
      jobId: "123e4567-e89b-42d3-a456-426614174000",
      status: "completed",
      customers: 5,
      command:
        "uv run whyback demo --customers 5 --backend gemini --output-dir artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
      completedAt: "2026-08-25T12:00:00Z",
      collectionId: "live-123e4567-e89b-42d3-a456-426614174000",
    };

    render(
      <LiveTraceDrawer
        open
        status={completedStatus}
        reportRefreshFailed={false}
        onClose={vi.fn()}
        onRefreshReports={vi.fn()}
        onStartRun={onStartRun}
      />,
    );

    expect(screen.queryByRole("button", { name: "Refresh verified reports" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start new analysis" }));
    expect(onStartRun).toHaveBeenCalledOnce();
  });

  it("offers report reload only after automatic publication refresh is exhausted", async () => {
    const user = userEvent.setup();
    const onRefreshReports = vi.fn();
    const completedStatus: DemoStatusResponse = {
      ...idleStatus,
      jobId: "123e4567-e89b-42d3-a456-426614174000",
      status: "completed",
      customers: 5,
      completedAt: "2026-08-25T12:00:00Z",
      collectionId: "live-123e4567-e89b-42d3-a456-426614174000",
    };

    render(
      <LiveTraceDrawer
        open
        status={completedStatus}
        reportRefreshFailed
        onClose={vi.fn()}
        onRefreshReports={onRefreshReports}
        onStartRun={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Start new analysis" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reload dashboard results" }));
    expect(onRefreshReports).toHaveBeenCalledOnce();
  });

  it("prefills and clamps a visible run size each time the launcher opens", async () => {
    const props = {
      running: false,
      error: null,
      customerLimits: demoCustomerLimits,
      liveRun: readyLiveRun,
      onClose: vi.fn(),
      onRun: vi.fn(),
    };
    const { rerender } = render(
      <RunCliDialog {...props} open initialCustomers={8} />,
    );

    expect(screen.getByRole("spinbutton", { name: "Households to investigate" })).toHaveValue(8);
    rerender(<RunCliDialog {...props} open={false} initialCustomers={99} />);
    await waitFor(() => {
      expect(screen.queryByRole("spinbutton", { name: "Households to investigate" })).not.toBeInTheDocument();
    });
    rerender(<RunCliDialog {...props} open initialCustomers={99} />);

    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: "Households to investigate" })).toHaveValue(24);
    });
  });

  it("contains modal focus, makes the workspace inert, and restores focus", async () => {
    const props = {
      running: false,
      error: null,
      customerLimits: demoCustomerLimits,
      liveRun: readyLiveRun,
      onClose: vi.fn(),
      onRun: vi.fn(),
    };
    const { rerender } = render(
      <>
        <button type="button">Open demo</button>
        <div className="app-content"><button type="button">Background action</button></div>
        <RunCliDialog {...props} open={false} />
      </>,
    );
    const trigger = screen.getByRole("button", { name: "Open demo" });
    trigger.focus();

    rerender(
      <>
        <button type="button">Open demo</button>
        <div className="app-content"><button type="button">Background action</button></div>
        <RunCliDialog {...props} open />
      </>,
    );

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog).toHaveFocus());
    expect(document.querySelector(".app-content")).toHaveAttribute("inert");

    rerender(
      <>
        <button type="button">Open demo</button>
        <div className="app-content"><button type="button">Background action</button></div>
        <RunCliDialog {...props} open={false} />
      </>,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Open demo" })).toHaveFocus());
    expect(document.querySelector(".app-content")).not.toHaveAttribute("inert");
  });

  it("gives the trend chart an exact non-pointer text alternative", () => {
    render(
      <TrendChart
        points={[{ week: 1, value: 20 }, { week: 2, value: 6 }]}
        recentStartWeek={2}
      />,
    );
    expect(
      screen.getByRole("img", { name: /week 1: \$20\.00; week 2: \$6\.00/i }),
    ).toBeInTheDocument();
  });

  it("states the execution boundary on every recommendation state", () => {
    const report = {
      schema_version: 2,
      product_name: "WhyBack",
      tagline: "",
      investigator_name: "WhyBack Investigator",
      run_id: "run-101",
      household_id: "101",
      run_status: "completed",
      decline: {
        baseline_start_week: 1,
        baseline_end_week: 4,
        recent_start_week: 5,
        recent_end_week: 8,
        baseline_retailer_sales_value: 160,
        recent_retailer_sales_value: 12,
        baseline_distinct_baskets: 8,
        recent_distinct_baskets: 1,
        baseline_active_weeks: 4,
        recent_active_weeks: 1,
        sales_drop: 0.925,
        trip_drop: 0.875,
        active_week_drop: 0.75,
        decline_score: 0.875,
      },
      investigation_path: [],
      likely_drivers: [],
      supporting_evidence: [],
      counterevidence: [],
      evidence_ledger: [],
      alternative_explanations: [],
      uncertainties: [],
      limitations: [],
      tool_warnings: [],
      verification_issues: [],
      failure_reason: null,
      action: {
        action_id: "VISIT_FREQUENCY_REACTIVATION",
        description: "Review a bounded visit-frequency experiment.",
        rationale: "Observed visits declined.",
        resolved_confidence: "medium",
        confidence_cap_applied: false,
        recommended_success_metric: "Distinct baskets",
        suggested_experiment: "Holdout-tested reminder",
        human_review_required: true,
      },
      human_review_required: true,
    } as unknown as ReportData;

    const { rerender } = render(
      <OverviewPanel report={report} onEvidenceSelect={vi.fn()} />,
    );

    expect(screen.getByText("Human review required")).toBeInTheDocument();
    expect(screen.getByText("No outreach or action executed")).toBeInTheDocument();

    rerender(
      <OverviewPanel
        report={{ ...report, action: null }}
        onEvidenceSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("No action recommended")).toBeInTheDocument();
    expect(screen.getByText("No outreach or action executed")).toBeInTheDocument();
  });

  it("describes a failed run as a terminal outcome with separate backend and model", () => {
    const failedReport = {
      schema_version: 2,
      run_id: "run-failed",
      household_id: "101",
      run_status: "failed",
      action: null,
      evidence_ledger: [],
      provenance: {
        backend: "gemini",
        model: "gemini-2.5-flash",
        dataset_kind: "synthetic",
        generated_at: "2026-08-25T00:00:00Z",
        source_hashes: {},
      },
    } as unknown as ReportData;

    render(<AuditPanel collectionId="failure" report={failedReport} trace={[]} />);
    expect(screen.getByText(/recorded analytical steps for this household/i)).toBeInTheDocument();
    expect(screen.getByText("Gemini")).toBeInTheDocument();
    expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
  });
});
