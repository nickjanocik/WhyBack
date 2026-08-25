import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ArtifactCollection, ReportData } from "../types";
import { AuditPanel } from "./AuditPanel";
import { CandidateRail } from "./CandidateRail";
import { RunDemoDialog } from "./RunDemoDialog";
import { TrendChart } from "./TrendChart";

const collections: ArtifactCollection[] = [
  {
    id: "demo",
    title: "Guided demo",
    description: "Deterministic fixture investigations.",
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
    description: "Partial-evidence official control.",
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
    await user.click(screen.getByRole("button", { name: /household 102/i }));
    expect(onHouseholdChange).toHaveBeenCalledWith("102");

    await user.selectOptions(screen.getByLabelText("Artifact collection"), "official-type-a");
    expect(onCollectionChange).toHaveBeenCalledWith("official-type-a");
  });

  it("runs the selected bounded demo size", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RunDemoDialog
        open
        running={false}
        error={null}
        onClose={vi.fn()}
        onRun={onRun}
      />,
    );

    await user.click(screen.getByRole("button", { name: "3" }));
    expect(screen.getByRole("button", { name: "3" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/--customers 3/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /generate investigations/i }));
    expect(onRun).toHaveBeenCalledWith(3);
  });

  it("keeps the safety boundary visible in the run dialog", () => {
    render(
      <RunDemoDialog
        open
        running={false}
        error={null}
        onClose={vi.fn()}
        onRun={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/no model key, raw-data upload, outreach, or crm mutation/i),
    ).toBeInTheDocument();
  });

  it("contains modal focus, makes the workspace inert, and restores focus", async () => {
    const props = {
      running: false,
      error: null,
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
