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
import { RunDemoDialog } from "./RunDemoDialog";
import { TrendChart } from "./TrendChart";

const collections: ArtifactCollection[] = [
  {
    id: "demo",
    title: "Guided demo",
    datasetKind: "synthetic",
    executionMode: "scripted",
    backend: "scripted",
    modelExecution: "scripted_control",
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
    id: "official-type-a",
    title: "Official Type A",
    datasetKind: "official_complete_journey",
    executionMode: "scripted",
    backend: "scripted",
    modelExecution: "scripted_control",
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
        collectionId="demo"
        householdId="101"
        onCollectionChange={onCollectionChange}
        onHouseholdChange={onHouseholdChange}
      />,
    );

    expect(screen.getByRole("button", { name: /household 101/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Dataset: Synthetic")).toBeInTheDocument();
    expect(screen.getByText("Execution: Scripted")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /household 102/i }));
    expect(onHouseholdChange).toHaveBeenCalledWith("102");

    await user.selectOptions(screen.getByLabelText("Artifact collection"), "official-type-a");
    expect(onCollectionChange).toHaveBeenCalledWith("official-type-a");
  });

  it("preserves the original candidate rank when filtering households", async () => {
    const user = userEvent.setup();
    render(
      <CandidateRail
        collections={collections}
        collectionId="demo"
        householdId="101"
        onCollectionChange={vi.fn()}
        onHouseholdChange={vi.fn()}
      />,
    );

    await user.type(screen.getByPlaceholderText("Find household"), "102");

    const candidate = screen.getByRole("button", { name: /household 102/i });
    expect(within(candidate).getByText("02")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /household 101/i })).not.toBeInTheDocument();
  });

  it("runs the selected bounded live Gemini batch size", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RunDemoDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={readyLiveRun}
        onClose={vi.fn()}
        onRun={onRun}
      />,
    );

    expect(screen.getByRole("button", { name: "5" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "4" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "24" }));
    expect(screen.getByRole("button", { name: "24" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /start live run/i }));
    expect(onRun).toHaveBeenCalledWith(24);
  });

  it("states the live Gemini and customer-action boundaries in the run dialog", () => {
    render(
      <RunDemoDialog
        open
        running={false}
        error={null}
        customerLimits={demoCustomerLimits}
        liveRun={readyLiveRun}
        onClose={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(screen.getByText(/the api key stays in local server-side processes/i)).toBeInTheDocument();
    expect(screen.getByText(/real provider calls and may consume quota/i)).toBeInTheDocument();
    expect(screen.getByText(/up to six live gemini decisions/i)).toBeInTheDocument();
    expect(screen.getByText(/no outreach or customer action is executed/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
  });

  it("explains blocked live readiness without collecting a credential or starting", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RunDemoDialog
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

    expect(screen.getByRole("alert")).toHaveTextContent(/gemini_api_key is not configured/i);
    const start = screen.getByRole("button", { name: /start live run/i });
    expect(start).toBeDisabled();
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
    await user.click(start);
    expect(onRun).not.toHaveBeenCalled();
  });

  it("submits only the selected household count to the local live-run bridge", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => idleStatus,
    });
    vi.stubGlobal("fetch", fetchMock);

    try {
      await runDemo(5);
      const request = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
      expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/demo");
      expect(request?.method).toBe("POST");
      expect(JSON.parse(String(request?.body))).toEqual({ customers: 5 });
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
      command: "uv run whyback demo --customers 5 --backend gemini",
      startedAt: "2026-08-25T12:00:00Z",
      completedAt: null,
      cursor: 2,
      eventCount: 2,
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
          details: { evidence_id: "ev-1" },
        },
      ],
      error: null,
      traceWarning: null,
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
        onClose={onClose}
        onOpenResults={vi.fn()}
        onStartRun={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Live audit trace" })).toBeInTheDocument();
    expect(screen.getByText(/private model reasoning is not collected/i)).toBeInTheDocument();
    expect(screen.getByText(/4 earlier audit events were omitted/i)).toBeInTheDocument();
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
    expect(screen.queryByText("Evidence recorded")).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Evidence writes" }));
    expect(screen.getByText("Evidence recorded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close live audit trace" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("contains live trace focus, closes with Escape, and restores its trigger", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const drawerProps = {
      status: idleStatus,
      onClose,
      onOpenResults: vi.fn(),
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

    const drawer = await screen.findByRole("dialog", { name: "Live audit trace" });
    const close = within(drawer).getByRole("button", { name: "Close live audit trace" });
    await waitFor(() => expect(close).toHaveFocus());
    expect(document.querySelector(".skip-link")).toHaveAttribute("inert");
    expect(document.querySelector(".app-header")).toHaveAttribute("inert");
    expect(document.querySelector(".workspace-layout")).toHaveAttribute("inert");
    expect(within(drawer).getByRole("log", { name: "Live audit event log" })).toHaveAttribute(
      "tabindex",
      "0",
    );

    within(drawer).getByRole("button", { name: "Start live run" }).focus();
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
        <RunDemoDialog {...props} open={false} />
      </>,
    );
    const trigger = screen.getByRole("button", { name: "Open demo" });
    trigger.focus();

    rerender(
      <>
        <button type="button">Open demo</button>
        <div className="app-content"><button type="button">Background action</button></div>
        <RunDemoDialog {...props} open />
      </>,
    );

    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog).toHaveFocus());
    expect(document.querySelector(".app-content")).toHaveAttribute("inert");

    rerender(
      <>
        <button type="button">Open demo</button>
        <div className="app-content"><button type="button">Background action</button></div>
        <RunDemoDialog {...props} open={false} />
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
    expect(screen.getByText(/terminal investigation outcome/i)).toBeInTheDocument();
    expect(screen.getByText("Gemini")).toBeInTheDocument();
    expect(screen.getByText("gemini-2.5-flash")).toBeInTheDocument();
  });
});
