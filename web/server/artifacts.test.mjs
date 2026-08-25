import assert from "node:assert/strict";
import { copyFile, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  loadInvestigation,
  loadWorkspace,
  resolveArtifactFile,
  validateHouseholdId,
} from "./artifacts.mjs";

async function fixtureRoot() {
  const root = await mkdtemp(path.join(os.tmpdir(), "whyback-dashboard-test-"));
  const collection = path.join(root, "artifacts", "demo");
  const customer = path.join(collection, "customer_7");
  await mkdir(customer, { recursive: true });
  const report = {
    schema_version: 2,
    run_id: "run-7",
    household_id: "7",
    run_status: "completed",
    decline: {
      decline_score: 0.8,
      sales_drop: 0.9,
      trip_drop: 0.7,
      active_week_drop: 0.6,
      baseline_retailer_sales_value: 100,
      recent_retailer_sales_value: 10,
    },
    action: {
      action_id: "VISIT_FREQUENCY_REACTIVATION",
      resolved_confidence: "high",
    },
    evidence_ledger: [{ evidence_id: "ev-1" }],
    tool_warnings: [],
    provenance: { generated_at: "2026-08-25T00:00:00Z" },
  };
  await writeFile(path.join(customer, "report.json"), JSON.stringify(report));
  await writeFile(path.join(customer, "report.html"), "<h1>WhyBack</h1>");
  await writeFile(
    path.join(customer, "trace.jsonl"),
    `${JSON.stringify({
      schema_version: 1,
      timestamp: "2026-08-25T00:00:00Z",
      event: "tool_completed",
      run_id: "run-7",
      household_id: "7",
      details: {
        tool_name: "customer_trend",
        status: "ok",
        detector_snapshot: { raw: "must not cross bridge" },
      },
    })}\n`,
  );
  await writeFile(
    path.join(collection, "manifest.json"),
    JSON.stringify({
      dataset_kind: "synthetic",
      execution_mode: "scripted",
      backend: "scripted",
      human_review_required: true,
      selected_household_ids: ["7"],
      completed_household_ids: ["7"],
    }),
  );
  return root;
}

test("loads collection summaries from canonical report artifacts", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));

  const workspace = await loadWorkspace(root);
  assert.equal(workspace.collections.length, 1);
  assert.equal(workspace.collections[0].id, "demo");
  assert.equal(workspace.collections[0].reports[0].householdId, "7");
  assert.equal(workspace.collections[0].reports[0].declineScore, 0.8);
  assert.equal(workspace.collections[0].humanReviewRequired, true);
});

test("loads a report and emits only allow-listed trace detail", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));

  const investigation = await loadInvestigation(root, "demo", "7");
  assert.equal(investigation.report.run_id, "run-7");
  assert.deepEqual(investigation.trace[0].details, {
    tool_name: "customer_trend",
    status: "ok",
  });
});

test("rejects traversal-shaped IDs and non-allow-listed artifact files", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));

  assert.equal(validateHouseholdId("../7"), false);
  assert.equal(await loadInvestigation(root, "demo", "../7"), null);
  assert.equal(
    await resolveArtifactFile(root, "demo", "7", "../../manifest.json"),
    null,
  );
  assert.equal(
    await resolveArtifactFile(root, "demo", "7", "report.html"),
    path.join(root, "artifacts", "demo", "customer_7", "report.html"),
  );
});

test("loads preserved flat-layout boundary artifacts", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const source = path.join(root, "artifacts", "demo", "customer_7");
  const flat = path.join(root, "artifacts", "live-gemini-synthetic-failure");
  await mkdir(flat, { recursive: true });
  await Promise.all(
    ["report.json", "report.html", "trace.jsonl"].map((fileName) =>
      copyFile(path.join(source, fileName), path.join(flat, fileName)),
    ),
  );

  const workspace = await loadWorkspace(root);
  const collection = workspace.collections.find(
    (item) => item.id === "live-gemini-synthetic-failure",
  );
  assert.equal(collection.reports[0].householdId, "7");
  assert.equal(
    (await loadInvestigation(root, "live-gemini-synthetic-failure", "7")).report
      .run_id,
    "run-7",
  );
  assert.equal(
    await resolveArtifactFile(
      root,
      "live-gemini-synthetic-failure",
      "7",
      "report.html",
    ),
    path.join(flat, "report.html"),
  );
});
