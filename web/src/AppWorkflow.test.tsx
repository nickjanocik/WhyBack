/** Proves the operational UI reaches live analysis from an empty workspace. */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type {
  DemoStatusResponse,
  InvestigationResponse,
  PopulationSummary,
  Workspace,
} from "./types";

const workspace: Workspace = {
  schemaVersion: 1,
  productName: "WhyBack",
  demoCustomerLimits: { minimum: 3, maximum: 24 },
  liveRun: {
    backend: "gemini",
    model: "gemini-3.7-flash",
    ready: true,
    blockedReason: null,
  },
  collectionWarnings: [],
  collections: [],
};

const idleStatus: DemoStatusResponse = {
  jobId: null,
  status: "idle",
  backend: "gemini",
  model: "gemini-3.7-flash",
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

const runningStatus: DemoStatusResponse = {
  ...idleStatus,
  jobId: "123e4567-e89b-42d3-a456-426614174000",
  status: "running",
  customers: 4,
  declineThreshold: 0.4,
  command:
    "uv run whyback demo --customers 4 --backend gemini --output-dir artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  startedAt: "2026-08-26T12:00:00Z",
  collectionId: "live-123e4567-e89b-42d3-a456-426614174000",
};

const existingCollectionId = "live-ceff4f61-0000-4000-8000-000000000000";
const nextCollectionId = "live-223e4567-e89b-42d3-a456-426614174000";

const partialPopulation: PopulationSummary = {
  schema_version: 1,
  availability: "partial",
  missing_data_reasons: ["This preserved run predates population_summary.json."],
  cohort_definitions: {
    eligible: "Eligible households.",
    flagged: "Flagged eligible households.",
    investigated: "Selected investigated households.",
  },
  analysis_windows: {
    baseline_start_week: 1,
    baseline_end_week: 8,
    recent_start_week: 9,
    recent_end_week: 16,
  },
  detector_policy: {
    minimum_baseline_active_weeks: null,
    minimum_baseline_distinct_baskets: null,
    minimum_baseline_retailer_sales_value: null,
    decline_threshold: 0.3,
    sensitivity_thresholds: [0.2, 0.3, 0.4],
  },
  threshold_sensitivity: [],
  data_quality_warnings: [],
  cohorts: [
    { cohort: "eligible", definition: "Eligible households.", household_count: 100, aggregate_baseline_value: null, aggregate_recent_value: null, gross_recorded_decrease: null, metrics: [] },
    { cohort: "flagged", definition: "Flagged eligible households.", household_count: 20, aggregate_baseline_value: null, aggregate_recent_value: null, gross_recorded_decrease: null, metrics: [] },
    { cohort: "investigated", definition: "Selected investigated households.", household_count: 5, aggregate_baseline_value: null, aggregate_recent_value: null, gross_recorded_decrease: null, metrics: [] },
  ],
  density_grid: null,
  investigated_households: [],
  executive: {
    eligible_count: 100,
    flagged_count: 20,
    flagged_share: 0.2,
    selected_count: 5,
    investigated_count: 5,
    completed_count: 0,
    insufficient_count: 0,
    failed_count: 5,
    aggregate_baseline_value: null,
    aggregate_recent_value: null,
    recorded_value_change: null,
    gross_recorded_decrease: null,
    verified_action_rate: 0,
    action_mix: [],
    factor_mix: [],
    context_mix: [],
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

const existingWorkspace: Workspace = {
  ...workspace,
  collections: [
    {
      id: existingCollectionId,
      title: "Run · ceff4f61",
      datasetKind: "official_complete_journey",
      executionMode: "live",
      backend: "gemini",
      modelExecution: "live_gemini",
      reportCount: 5,
      completedCount: 0,
      humanReviewRequired: true,
      reports: Array.from({ length: 5 }, (_, index) => ({
        householdId: String(index + 1),
        runId: `run-${index + 1}`,
        runStatus: "failed" as const,
        declineScore: 1,
        salesDrop: 1,
        tripDrop: 1,
        activeWeekDrop: 1,
        baselineSales: 100,
        recentSales: 0,
        actionId: null,
        confidence: null,
        evidenceCount: 0,
        warningCount: 0,
        generatedAt: "2026-08-26T12:00:00Z",
      })),
    },
  ],
};

const nextRunningStatus: DemoStatusResponse = {
  ...runningStatus,
  jobId: "223e4567-e89b-42d3-a456-426614174000",
  customers: 5,
  command:
    "uv run whyback demo --customers 5 --backend gemini --output-dir artifacts/local/live-runs/live-223e4567-e89b-42d3-a456-426614174000",
  collectionId: nextCollectionId,
};

const publishedWorkspace: Workspace = {
  ...workspace,
  // Keeping the older collection first proves completion selects the requested new run.
  collections: [
    existingWorkspace.collections[0]!,
    {
      id: nextCollectionId,
      title: "Run · 223e4567",
      datasetKind: "official_complete_journey",
      executionMode: "live",
      backend: "gemini",
      modelExecution: "live_gemini",
      reportCount: 1,
      completedCount: 1,
      humanReviewRequired: true,
      reports: [
        {
          householdId: "900",
          runId: "run-900",
          runStatus: "completed",
          declineScore: 0.75,
          salesDrop: 0.8,
          tripDrop: 0.7,
          activeWeekDrop: 0.6,
          baselineSales: 100,
          recentSales: 20,
          actionId: "VISIT_FREQUENCY_REACTIVATION",
          confidence: "medium",
          evidenceCount: 12,
          warningCount: 0,
          generatedAt: "2026-08-26T12:05:00Z",
        },
      ],
    },
  ],
};

const staleInvestigation = {
  report: {
    schema_version: 2,
    product_name: "WhyBack",
    tagline: "",
    investigator_name: "WhyBack Investigator",
    run_id: "stale-run",
    household_id: "STALE HOUSEHOLD",
    run_status: "failed",
    decline: {
      baseline_start_week: 1,
      baseline_end_week: 4,
      recent_start_week: 5,
      recent_end_week: 8,
      baseline_retailer_sales_value: 100,
      recent_retailer_sales_value: 0,
      baseline_distinct_baskets: 5,
      recent_distinct_baskets: 0,
      baseline_active_weeks: 4,
      recent_active_weeks: 0,
      sales_drop: 1,
      trip_drop: 1,
      active_week_drop: 1,
      decline_score: 1,
    },
    investigation_path: [],
    likely_drivers: [],
    supporting_evidence: [],
    counterevidence: [],
    evidence_ledger: [],
    alternative_explanations: [],
    uncertainties: [],
    action: null,
    limitations: [],
    tool_warnings: [],
    verification_issues: [],
    failure_reason: "This stale report must never repaint after reset.",
    human_review_required: true,
  },
  trace: [],
} as unknown as InvestigationResponse;

/** Creates the minimal response contract used by the typed API wrapper. */
function jsonResponse(value: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => value,
  };
}

/** Exposes resolution so polling and publication races remain deterministic. */
function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("analysis application workflow", () => {
  it("opens on Home without loading a household report", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(existingWorkspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "What changed across the household population?",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/investigation?")),
    ).toBe(false);
  });

  it("maps the legacy overview query value to Investigation", async () => {
    window.history.replaceState(null, "", "/?view=overview");
    const never = new Promise<never>(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(existingWorkspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
      if (url.startsWith("/api/investigation?")) return never;
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Investigation" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/investigation?")),
      ).toBe(true);
    });
  });

  it("starts an analysis from an honest empty state and opens live progress", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const failedStatus: DemoStatusResponse = {
      ...runningStatus,
      status: "failed",
      completedAt: "2026-08-26T12:00:02Z",
      error: "The CLI did not publish a verified artifact collection.",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(workspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url === "/api/demo" && init?.method === "POST") {
        return jsonResponse(runningStatus, 202);
      }
      if (url.startsWith("/api/demo/status?after=0&job=")) {
        return jsonResponse(failedStatus);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Ready for your first portfolio review" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/launch a verified analysis of official household data/i)).toBeInTheDocument();
    expect(screen.queryByText(/committed sample|official type a|boundary case/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start a new analysis" }));
    const launchDialog = screen.getByRole("dialog", { name: "Review a household cohort" });
    const count = screen.getByRole("spinbutton", { name: "Households to investigate" });
    await user.clear(count);
    await user.type(count, "4");
    await user.click(screen.getByRole("radio", { name: /focused/i }));
    await user.click(
      launchDialog.querySelector<HTMLButtonElement>(".run-submit")!,
    );

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([url, init]) => url === "/api/demo" && init?.method === "POST",
      );
      expect(post).toBeDefined();
      expect(post?.[1]?.headers).toMatchObject({ "Content-Type": "application/json" });
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        customers: 4,
        declineThreshold: 0.4,
      });
    });

    const drawer = await screen.findByRole("dialog", { name: "Live progress" });
    expect(drawer).not.toHaveTextContent(runningStatus.command!);
    expect(drawer).toHaveTextContent(/analysis did not complete/i);
    expect(drawer).not.toHaveTextContent(/\bcli\b/i);
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
  });

  it("clears the candidate rail and main panel after a fresh run is accepted", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const staleReport = deferred<InvestigationResponse>();
    const never = new Promise<never>(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(existingWorkspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
      if (url.startsWith("/api/investigation?")) {
        return jsonResponse(await staleReport.promise);
      }
      if (url === "/api/demo" && init?.method === "POST") {
        return jsonResponse(nextRunningStatus, 202);
      }
      if (url.startsWith("/api/demo/status?after=0&job=")) return never;
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("combobox", { name: "Analysis run" })).toHaveValue(
      existingCollectionId,
    );
    expect(
      within(document.querySelector<HTMLElement>("#candidate-rail")!).getByText("Household 1"),
    ).toBeInTheDocument();
    expect(
      await within(document.querySelector<HTMLElement>(".main-workspace")!).findByRole(
        "heading",
        { name: "What changed across the household population?" },
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start a new analysis" }));
    expect(screen.getByRole("spinbutton", { name: "Households to investigate" })).toHaveValue(5);
    await user.click(screen.getByRole("button", { name: "Start analysis" }));

    const drawer = await screen.findByRole("dialog", { name: "Live progress" });
    expect(drawer).not.toHaveTextContent(nextRunningStatus.command!);
    expect(drawer).not.toHaveTextContent(/existing verified report remains visible/i);
    expect(document.querySelector("#candidate-rail")).not.toBeInTheDocument();
    const main = document.querySelector<HTMLElement>(".main-workspace")!;
    expect(within(main).queryByText("Household 1")).not.toBeInTheDocument();
    expect(within(main).queryByLabelText("Loading investigation")).not.toBeInTheDocument();
    expect(within(main).getByRole("heading", { name: "Portfolio analysis in progress" })).toBeInTheDocument();
    staleReport.resolve(staleInvestigation);
    await waitFor(() => {
      expect(within(main).queryByText("STALE HOUSEHOLD")).not.toBeInTheDocument();
      expect(within(main).queryByText(/stale report must never repaint/i)).not.toBeInTheDocument();
    });
    expect(document.querySelector<HTMLButtonElement>(".run-button")).toBeDisabled();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/workspace")).toHaveLength(1);

    const post = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/demo" && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      customers: 5,
      declineThreshold: 0.3,
    });
  });

  it("preserves the candidate rail and main panel when the bridge rejects a new run", async () => {
    const user = userEvent.setup();
    const never = new Promise<never>(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(existingWorkspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
      if (url.startsWith("/api/investigation?")) return never;
      if (url === "/api/demo" && init?.method === "POST") {
        return jsonResponse({ error: "Gemini rejected the launch." }, 503);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("combobox", { name: "Analysis run" })).toHaveValue(
      existingCollectionId,
    );
    await user.click(screen.getByRole("button", { name: "Start a new analysis" }));
    const launchDialog = screen.getByRole("dialog", { name: "Review a household cohort" });
    await user.click(within(launchDialog).getByRole("button", { name: "Start analysis" }));

    expect(await within(launchDialog).findByRole("alert")).toHaveTextContent(
      "Gemini rejected the launch.",
    );
    const rail = document.querySelector<HTMLElement>("#candidate-rail")!;
    const main = document.querySelector<HTMLElement>(".main-workspace")!;
    expect(within(rail).getByText("Household 1")).toBeInTheDocument();
    expect(within(main).getByRole("heading", { name: "What changed across the household population?" })).toBeInTheDocument();
    expect(within(main).queryByLabelText("Loading investigation")).not.toBeInTheDocument();
    expect(within(main).queryByRole("heading", { name: "Portfolio analysis in progress" })).not.toBeInTheDocument();
    expect((document.querySelector("#collection") as HTMLSelectElement).value).toBe(
      existingCollectionId,
    );
  });

  it("keeps the reset workspace empty through a publication race, then selects the new run", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const never = new Promise<never>(() => undefined);
    const completion = deferred<DemoStatusResponse>();
    const publication = deferred<Workspace>();
    const completedStatus: DemoStatusResponse = {
      ...nextRunningStatus,
      status: "completed",
      completedAt: "2026-08-26T12:05:00Z",
    };
    let workspaceReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/workspace") {
        workspaceReads += 1;
        if (workspaceReads === 1) return jsonResponse(existingWorkspace);
        if (workspaceReads === 2) return jsonResponse(existingWorkspace);
        return jsonResponse(await publication.promise);
      }
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
      if (url.startsWith("/api/investigation?")) return never;
      if (url === "/api/demo" && init?.method === "POST") {
        return jsonResponse(nextRunningStatus, 202);
      }
      if (url.startsWith("/api/demo/status?after=0&job=")) {
        return jsonResponse(await completion.promise);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await screen.findByRole("combobox", { name: "Analysis run" });
    await user.click(screen.getByRole("button", { name: "Start a new analysis" }));
    await user.click(screen.getByRole("button", { name: "Start analysis" }));

    const main = document.querySelector<HTMLElement>(".main-workspace")!;
    expect(await within(main).findByRole("heading", { name: "Portfolio analysis in progress" })).toBeInTheDocument();
    expect(document.querySelector("#candidate-rail")).not.toBeInTheDocument();

    completion.resolve(completedStatus);
    await waitFor(() => expect(workspaceReads).toBeGreaterThanOrEqual(3), { timeout: 3_000 });

    // The first completed-run refresh contained only the old collection. It must
    // be treated as a publication race instead of restoring stale results.
    expect(document.querySelector("#candidate-rail")).not.toBeInTheDocument();
    expect(within(main).queryByText("Household 1")).not.toBeInTheDocument();

    publication.resolve(publishedWorkspace);
    await waitFor(() => {
      expect((document.querySelector("#collection") as HTMLSelectElement | null)?.value).toBe(
        nextCollectionId,
      );
    });
    const rail = document.querySelector<HTMLElement>("#candidate-rail")!;
    expect(within(rail).getByText("Household 900")).toBeInTheDocument();
    expect(
      await within(document.querySelector<HTMLElement>(".main-workspace")!).findByRole(
        "heading",
        { name: "What changed across the household population?" },
      ),
    ).toBeInTheDocument();
    expect((document.querySelector("#collection") as HTMLSelectElement).value).not.toBe(
      existingCollectionId,
    );
  });

  it.each(["workspace first", "status first"] as const)(
    "restores an active run's cleared workspace when %s resolves",
    async (firstResponse) => {
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
        configurable: true,
        value: vi.fn(),
      });
      const workspaceResponse = deferred<Workspace>();
      const statusResponse = deferred<DemoStatusResponse>();
      const never = new Promise<never>(() => undefined);
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/workspace") {
          return jsonResponse(await workspaceResponse.promise);
        }
        if (url === "/api/demo/status?after=0") {
          return jsonResponse(await statusResponse.promise);
        }
        if (url.startsWith("/api/population?")) return jsonResponse(partialPopulation);
        if (url.startsWith("/api/investigation?")) return never;
        if (url.startsWith("/api/demo/status?after=0&job=")) return never;
        throw new Error(`Unexpected request: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      render(<App />);

      if (firstResponse === "workspace first") {
        workspaceResponse.resolve(existingWorkspace);
        await screen.findByRole("combobox", { name: "Analysis run" });
        statusResponse.resolve(nextRunningStatus);
      } else {
        statusResponse.resolve(nextRunningStatus);
        await screen.findByRole("dialog", { name: "Live progress" });
        workspaceResponse.resolve(existingWorkspace);
      }

      await waitFor(() => {
        expect(document.querySelector("#candidate-rail")).not.toBeInTheDocument();
        expect(
          within(document.querySelector<HTMLElement>(".main-workspace")!).getByRole(
            "heading",
            { name: "Portfolio analysis in progress" },
          ),
        ).toBeInTheDocument();
      });
    },
  );
});
