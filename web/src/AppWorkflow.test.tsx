/** Proves the operational UI reaches the real CLI bridge from an empty workspace. */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { DemoStatusResponse, Workspace } from "./types";

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
  command:
    "uv run whyback demo --customers 4 --backend gemini --output-dir artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  startedAt: "2026-08-26T12:00:00Z",
  collectionId: "live-123e4567-e89b-42d3-a456-426614174000",
};

/** Creates the minimal response contract used by the typed API wrapper. */
function jsonResponse(value: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => value,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("CLI application workflow", () => {
  it("starts the CLI from an honest empty state and opens its live activity", async () => {
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
      await screen.findByRole("heading", { name: "No verified CLI runs yet" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/excludes bundled examples and unverified output/i)).toBeInTheDocument();
    expect(screen.queryByText(/committed sample|official type a|boundary case/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start a new WhyBack CLI run" }));
    const launchDialog = screen.getByRole("dialog", { name: "Start a new investigation run" });
    const count = screen.getByRole("spinbutton", { name: "Households" });
    await user.clear(count);
    await user.type(count, "4");
    await user.click(
      launchDialog.querySelector<HTMLButtonElement>(".run-submit")!,
    );

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([url, init]) => url === "/api/demo" && init?.method === "POST",
      );
      expect(post).toBeDefined();
      expect(post?.[1]?.headers).toMatchObject({ "Content-Type": "application/json" });
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({ customers: 4 });
    });

    const drawer = await screen.findByRole("dialog", { name: "Live run activity" });
    expect(drawer).toHaveTextContent(runningStatus.command!);
    expect(drawer).toHaveTextContent(/cli run not published/i);
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
  });

  it("reruns the visible batch without clearing its verified collection", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });
    const existingWorkspace: Workspace = {
      ...workspace,
      collections: [
        {
          id: "live-ceff4f61-0000-4000-8000-000000000000",
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
      collectionId: "live-223e4567-e89b-42d3-a456-426614174000",
    };
    const never = new Promise<never>(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/workspace") return jsonResponse(existingWorkspace);
      if (url === "/api/demo/status?after=0") return jsonResponse(idleStatus);
      if (url.startsWith("/api/investigation?")) return never;
      if (url === "/api/demo" && init?.method === "POST") {
        return jsonResponse(nextRunningStatus, 202);
      }
      if (url.startsWith("/api/demo/status?after=0&job=")) return never;
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("combobox", { name: "CLI run" })).toHaveValue(
      existingWorkspace.collections[0]!.id,
    );
    await user.click(screen.getByRole("button", { name: "Start a new WhyBack CLI run" }));
    expect(screen.getByRole("spinbutton", { name: "Households" })).toHaveValue(5);
    await user.click(screen.getByRole("button", { name: "Start new run" }));

    const drawer = await screen.findByRole("dialog", { name: "Live run activity" });
    expect(drawer).toHaveTextContent(nextRunningStatus.command!);
    expect(drawer).toHaveTextContent(/existing verified report remains visible/i);
    expect(screen.getByRole("combobox", { name: "CLI run" })).toHaveValue(
      existingWorkspace.collections[0]!.id,
    );
    expect(document.querySelector<HTMLButtonElement>(".run-button")).toBeDisabled();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/workspace")).toHaveLength(1);

    const post = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/demo" && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ customers: 5 });
  });
});
