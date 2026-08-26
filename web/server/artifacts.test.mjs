/** Exercises artifact discovery, sanitization, and path-safety contracts. */

import assert from "node:assert/strict";
import {
  mkdir,
  mkdtemp,
  rm,
  symlink,
  utimes,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  loadInvestigation,
  loadPopulation,
  loadWorkspace,
  populationCsv,
  resolveArtifactFile,
  resolveCollection,
  validateHouseholdId,
} from "./artifacts.mjs";
import {
  createLiveRunDescriptor,
  markLiveRunVerified,
} from "./live-runs.mjs";

const OWNERSHIP = {
  schema_version: 1,
  product: "WhyBack",
  scope: "replaceable_generated_artifact_tree",
};
const FIRST_LIVE_JOB = "123e4567-e89b-42d3-a456-426614174000";
const SECOND_LIVE_JOB = "223e4567-e89b-42d3-b456-426614174000";

/** Creates a disposable repository root for sealed live-run fixtures. */
async function fixtureRoot() {
  return mkdtemp(path.join(os.tmpdir(), "whyback-dashboard-test-"));
}

/** Writes a sealed live collection fixture, with optional deliberate tampering. */
async function writeLiveCollection(
  root,
  {
    jobId,
    householdId,
    generatedAt,
    modifiedAt,
    population = null,
    baselineValue = 200,
    recentValue = 80,
  },
) {
  const descriptor = createLiveRunDescriptor(root, jobId);
  const customer = path.join(descriptor.directory, `customer_${householdId}`);
  await mkdir(customer, { recursive: true });
  await writeFile(
    path.join(descriptor.directory, ".whyback-owned-artifact-root.json"),
    `${JSON.stringify(OWNERSHIP)}\n`,
  );
  const report = {
    schema_version: 2,
    run_id: `live-run-${householdId}`,
    household_id: householdId,
    run_status: "completed",
    decline: {
      decline_score: 0.7,
      sales_drop: 0.6,
      trip_drop: 0.5,
      active_week_drop: 0.4,
      baseline_retailer_sales_value: baselineValue,
      recent_retailer_sales_value: recentValue,
    },
    action: null,
    evidence_ledger: [],
    tool_warnings: [],
    provenance: {
      backend: "gemini",
      execution_mode: "live_gemini",
      generated_at: generatedAt,
    },
  };
  await writeFile(path.join(customer, "report.json"), JSON.stringify(report));
  await writeFile(path.join(customer, "report.html"), "<h1>Live Gemini</h1>");
  await writeFile(path.join(customer, "report.md"), "# Live Gemini\n");
  await writeFile(path.join(customer, "trace.html"), "<h1>Trace</h1>");
  await writeFile(
    path.join(customer, "trace.jsonl"),
    `${JSON.stringify({
      schema_version: 1,
      timestamp: generatedAt,
      event: "model_decision_received",
      run_id: `live-run-${householdId}`,
      household_id: householdId,
      details: {
        model: "gemini-3.7-flash",
        selected_tool: "customer_trend",
        chain_of_thought: "must not cross bridge",
      },
    })}\n`,
  );
  if (population) {
    await writeFile(
      path.join(descriptor.directory, "population_summary.json"),
      JSON.stringify(population),
    );
  }
  await writeFile(
    path.join(descriptor.directory, "manifest.json"),
    JSON.stringify({
      dataset_kind: "official_complete_journey",
      execution_mode: "live",
      backend: "gemini",
      model_execution: "live_gemini",
      human_review_required: true,
      customer_outreach_executed: false,
      selected_household_ids: [householdId],
      completed_household_ids: [householdId],
      failed_household_ids: [],
      skipped_household_ids: [],
      ...(population
        ? {
            population_summary: "population_summary.json",
            population_schema_version: 1,
            files: { "population_summary.json": "0".repeat(64) },
          }
        : {}),
    }),
  );
  await markLiveRunVerified(root, descriptor.collectionId);
  await utimes(descriptor.directory, modifiedAt, modifiedAt);
  return { ...descriptor, customer };
}

test("loads summaries only from sealed CLI artifacts", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
  });

  const workspace = await loadWorkspace(root);
  assert.deepEqual(workspace.demoCustomerLimits, { minimum: 3, maximum: 24 });
  assert.equal(workspace.collections.length, 1);
  assert.equal(workspace.collections[0].id, live.collectionId);
  assert.equal(workspace.collections[0].reports[0].householdId, "7");
  assert.equal(workspace.collections[0].reports[0].declineScore, 0.7);
  assert.equal(workspace.collections[0].humanReviewRequired, true);
});

test("loads a report and emits only allow-listed trace detail", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
  });

  const investigation = await loadInvestigation(root, live.collectionId, "7");
  assert.equal(investigation.report.run_id, "live-run-7");
  assert.deepEqual(investigation.trace[0].details, {
    model: "gemini-3.7-flash",
    selected_tool: "customer_trend",
  });
});

test("rejects traversal-shaped IDs and non-allow-listed artifact files", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
  });

  assert.equal(validateHouseholdId("../7"), false);
  assert.equal(await loadInvestigation(root, live.collectionId, "../7"), null);
  assert.equal(
    await resolveArtifactFile(
      root,
      live.collectionId,
      "7",
      "../../manifest.json",
    ),
    null,
  );
  assert.equal(
    await resolveArtifactFile(root, live.collectionId, "7", "report.html"),
    path.join(live.customer, "report.html"),
  );
});

test("does not expose bundled examples or boundary fixtures", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const example = path.join(root, "artifacts", "demo", "customer_7");
  await mkdir(example, { recursive: true });
  await writeFile(path.join(example, "report.json"), "{}\n");
  await writeFile(path.join(example, "report.html"), "<h1>Example</h1>\n");
  await writeFile(path.join(example, "trace.jsonl"), "{}\n");

  const workspace = await loadWorkspace(root);
  assert.deepEqual(workspace.collections, []);
  assert.equal(await resolveCollection(root, "demo"), null);
  assert.equal(await loadInvestigation(root, "demo", "7"), null);
  assert.equal(await resolveArtifactFile(root, "demo", "7", "report.html"), null);
});

test("discovers and loads preserved Live Gemini collections newest first", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const older = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "181",
    generatedAt: "2026-08-25T12:00:00Z",
    modifiedAt: new Date("2026-08-25T12:00:00Z"),
  });
  const newer = await writeLiveCollection(root, {
    jobId: SECOND_LIVE_JOB,
    householdId: "182",
    generatedAt: "2026-08-25T12:01:00Z",
    modifiedAt: new Date("2026-08-25T12:01:00Z"),
  });

  const workspace = await loadWorkspace(root);
  assert.deepEqual(
    workspace.collections.map((item) => item.id),
    [newer.collectionId, older.collectionId],
  );
  assert.deepEqual(
    workspace.collections.slice(0, 2).map((item) => item.title),
    ["Run · 223e4567", "Run · 123e4567"],
  );
  assert.equal(workspace.collections[0].backend, "gemini");
  assert.equal(workspace.collections[0].executionMode, "live");
  assert.equal(workspace.collections[0].reports[0].householdId, "182");

  const investigation = await loadInvestigation(root, newer.collectionId, "182");
  assert.equal(investigation.report.run_id, "live-run-182");
  assert.deepEqual(investigation.trace[0].details, {
    model: "gemini-3.7-flash",
    selected_tool: "customer_trend",
  });
  assert.equal(
    await resolveCollection(root, newer.collectionId),
    newer.directory,
  );
  assert.equal(
    await resolveArtifactFile(root, newer.collectionId, "182", "report.html"),
    path.join(newer.customer, "report.html"),
  );
});

test("rejects unsafe dynamic collections and files", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const valid = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "181",
    generatedAt: "2026-08-25T12:00:00Z",
    modifiedAt: new Date("2026-08-25T12:00:00Z"),
  });
  const outside = await mkdtemp(path.join(os.tmpdir(), "whyback-artifact-outside-"));
  context.after(() => rm(outside, { recursive: true, force: true }));
  await writeFile(path.join(outside, "report.html"), "outside");
  await writeFile(path.join(outside, "trace.jsonl"), "{}\n");
  await rm(path.join(valid.customer, "report.html"));
  await symlink(
    path.join(outside, "report.html"),
    path.join(valid.customer, "report.html"),
  );

  const malformed = createLiveRunDescriptor(root, SECOND_LIVE_JOB);
  await mkdir(path.join(malformed.directory, "customer_999"), { recursive: true });
  await writeFile(
    path.join(malformed.directory, ".whyback-owned-artifact-root.json"),
    "not-json\n",
  );
  const linkedJob = "323e4567-e89b-42d3-8456-426614174000";
  const linked = createLiveRunDescriptor(root, linkedJob);
  await mkdir(path.dirname(linked.directory), { recursive: true });
  await symlink(outside, linked.directory);

  const workspace = await loadWorkspace(root);
  assert.deepEqual(workspace.collections, []);
  assert.equal(await resolveCollection(root, valid.collectionId), null);
  assert.equal(await resolveCollection(root, `live-../${FIRST_LIVE_JOB}`), null);
  assert.equal(await resolveCollection(root, malformed.collectionId), null);
  assert.equal(await resolveCollection(root, linked.collectionId), null);
  assert.equal(
    await resolveArtifactFile(root, valid.collectionId, "181", "report.html"),
    null,
  );
  await rm(path.join(valid.customer, "trace.jsonl"));
  await symlink(
    path.join(outside, "trace.jsonl"),
    path.join(valid.customer, "trace.jsonl"),
  );
  assert.equal(await loadInvestigation(root, valid.collectionId, "181"), null);
  assert.equal(await loadInvestigation(root, "demo", "7"), null);
});

test("derives explicit partial population context for a legacy run", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
  });

  const population = await loadPopulation(root, live.collectionId);
  assert.equal(population.availability, "partial");
  assert.equal(population.executive.eligible_count, null);
  assert.equal(population.executive.aggregate_baseline_value, 200);
  assert.equal(population.executive.aggregate_recent_value, 80);
  assert.equal(population.executive.recorded_value_change, -120);
  assert.equal(population.executive.gross_recorded_decrease, 120);
  assert.equal(population.cohorts[0].metrics.length, 0);
  assert.deepEqual(
    {
      baseline: population.cohorts[2].aggregate_baseline_value,
      recent: population.cohorts[2].aggregate_recent_value,
      decrease: population.cohorts[2].gross_recorded_decrease,
    },
    { baseline: 200, recent: 80, decrease: 120 },
  );
  assert.deepEqual(population.executive.action_mix, [
    {
      key: "NO_PUBLISHED_RECOMMENDATION",
      label: "No recommendation published",
      count: 1,
      share: 1,
    },
  ]);
  assert.deepEqual(
    population.investigated_households.map((item) => item.household_id),
    ["7"],
  );
  assert.match(population.missing_data_reasons.join(" "), /predates/u);
  assert.match(
    population.missing_data_reasons.join(" "),
    /investigated households only/u,
  );
  assert.equal(await loadPopulation(root, "../manifest.json"), null);
});

test("keeps partial recorded-value totals unavailable when report coverage is incomplete", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
    baselineValue: null,
  });

  const population = await loadPopulation(root, live.collectionId);
  assert.equal(population.executive.aggregate_baseline_value, null);
  assert.equal(population.executive.aggregate_recent_value, null);
  assert.equal(population.executive.recorded_value_change, null);
  assert.equal(population.executive.gross_recorded_decrease, null);
  assert.match(population.missing_data_reasons.join(" "), /lack value fields/u);
});

test("projects full population data without leaking non-investigated IDs", async (context) => {
  const root = await fixtureRoot();
  context.after(() => rm(root, { recursive: true, force: true }));
  const populationArtifact = {
    schema_version: 1,
    availability: "full",
    missing_data_reasons: [],
    eligible_household_ids: ["SECRET-ELIGIBLE-ID"],
    cohort_definitions: {
      eligible: "Eligible",
      flagged: "Flagged",
      investigated: "Investigated",
    },
    analysis_windows: {
      baseline_start_week: 1,
      baseline_end_week: 8,
      recent_start_week: 9,
      recent_end_week: 16,
    },
    detector_policy: { decline_threshold: 0.3, sensitivity_thresholds: [0.3] },
    threshold_sensitivity: [
      {
        threshold: 0.3,
        eligible_households: 100,
        flagged_households: 20,
        flagged_share: 0.2,
      },
    ],
    data_quality_warnings: [],
    cohorts: [
      {
        cohort: "eligible",
        definition: "Eligible",
        household_count: 100,
        household_ids: ["SECRET-FLAGGED-ID"],
        metrics: [
          {
            metric: "decline_score",
            unit: "share",
            count: 100,
            mean: 0.2,
            minimum: 0,
            q25: 0.1,
            median: 0.2,
            q75: 0.3,
            maximum: 1,
            deciles: [],
            histogram: [{ lower: 0, upper: 1, count: 100, share: 1 }],
          },
        ],
      },
    ],
    density_grid: null,
    investigated_households: [
      {
        household_id: "7",
        rank: 1,
        status: "completed",
        context_classification: "customer_specific",
        decline_score: 0.7,
        sales_drop: 0.6,
        trip_drop: 0.5,
        active_week_drop: 0.4,
        identified_factor: {
          factor_type: "cadence",
          label: "Visit cadence",
          detail: "Recorded cadence declined.",
        },
        action_id: "VISIT_FREQUENCY_REACTIVATION",
        action_label: "Restore cadence",
        confidence: "medium",
        warnings: [],
      },
    ],
    executive: {
      eligible_count: 100,
      flagged_count: 20,
      flagged_share: 0.2,
      selected_count: 1,
      investigated_count: 1,
      completed_count: 1,
      insufficient_count: 0,
      failed_count: 0,
      verified_action_rate: 1,
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
      generated_at: "2026-08-25T00:00:00Z",
    },
  };
  const live = await writeLiveCollection(root, {
    jobId: FIRST_LIVE_JOB,
    householdId: "7",
    generatedAt: "2026-08-25T00:00:00Z",
    modifiedAt: new Date("2026-08-25T00:00:00Z"),
    population: populationArtifact,
  });

  const population = await loadPopulation(root, live.collectionId);
  const serialized = JSON.stringify(population);
  assert.equal(population.availability, "full");
  assert.doesNotMatch(serialized, /SECRET-/u);
  assert.match(serialized, /"household_id":"7"/u);
  const csv = populationCsv(population);
  assert.match(csv, /statistic,eligible,decline_score,median,0.2/u);
  assert.match(csv, /investigated_household.*7/u);
  assert.doesNotMatch(csv, /SECRET-/u);
});
