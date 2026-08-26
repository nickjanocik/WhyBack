import assert from "node:assert/strict";
import {
  appendFile,
  mkdir,
  mkdtemp,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import {
  createDemoRunManager,
  createLiveTraceReader,
} from "./live-trace.mjs";

function auditEvent({
  event = "run_started",
  householdId = "7",
  timestamp = "2026-08-25T12:00:00.000Z",
  details = {},
} = {}) {
  return {
    schema_version: 1,
    timestamp,
    event,
    run_id: `run-${householdId}`,
    household_id: householdId,
    details,
  };
}

function asJsonl(...events) {
  return `${events.map((event) => JSON.stringify(event)).join("\n")}\n`;
}

async function makeRoot(context) {
  const root = await mkdtemp(path.join(os.tmpdir(), "whyback-live-trace-test-"));
  context.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

async function makeStaging(root, name = ".dashboard.staging-current") {
  const staging = path.join(root, "artifacts", "local", name);
  await mkdir(staging, { recursive: true });
  await writeFile(
    path.join(staging, ".whyback-owned-artifact-root.json"),
    `${JSON.stringify({
      schema_version: 1,
      product: "WhyBack",
      scope: "replaceable_generated_artifact_tree",
    })}\n`,
  );
  return staging;
}

async function makePublished(root) {
  const published = path.join(root, "artifacts", "local", "dashboard");
  await mkdir(published, { recursive: true });
  await writeFile(
    path.join(published, ".whyback-owned-artifact-root.json"),
    `${JSON.stringify({
      schema_version: 1,
      product: "WhyBack",
      scope: "replaceable_generated_artifact_tree",
    })}\n`,
  );
  return published;
}

async function writeCustomerTrace(root, householdId, content) {
  const directory = path.join(root, `customer_${householdId}`);
  await mkdir(directory, { recursive: true });
  const tracePath = path.join(directory, "trace.jsonl");
  await writeFile(tracePath, content);
  return tracePath;
}

async function waitForStatus(manager, jobId, expected) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const current = manager.status(jobId);
    if (current?.status === expected) return current;
    await delay(5);
  }
  assert.fail(`Live trace job did not reach ${expected}.`);
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

test("publishes only newline-terminated JSONL records and resumes a partial line", async (context) => {
  const root = await makeRoot(context);
  const staging = await makeStaging(root);
  const first = auditEvent();
  const second = auditEvent({
    event: "tool_started",
    timestamp: "2026-08-25T12:00:01.000Z",
    details: { tool_name: "customer_trend" },
  });
  const serializedSecond = JSON.stringify(second);
  const splitAt = Math.floor(serializedSecond.length / 2);
  const tracePath = await writeCustomerTrace(
    staging,
    "7",
    `${JSON.stringify(first)}\n${serializedSecond.slice(0, splitAt)}`,
  );
  const reader = createLiveTraceReader(root, Date.now());

  const initial = await reader.readNew();
  assert.equal(initial.length, 1);
  assert.equal(initial[0].event, "run_started");

  assert.deepEqual(await reader.readNew(), []);
  await appendFile(tracePath, `${serializedSecond.slice(splitAt)}\n`);

  const completed = await reader.readNew();
  assert.equal(completed.length, 1);
  assert.equal(completed[0].event, "tool_started");
  assert.equal(completed[0].details.tool_name, "customer_trend");
  assert.equal(completed[0].id, "customer_7:2");
});

test("allow-lists display details and omits raw, sensitive, and reasoning fields", async (context) => {
  const root = await makeRoot(context);
  const staging = await makeStaging(root);
  await writeCustomerTrace(
    staging,
    "7",
    asJsonl(
      auditEvent({
        event: "model_decision_received",
        details: {
          selected_tool: "customer_trend",
          investigation_question: "Which observed behavior changed?",
          evidence_ids: ["ev-1", "ev-2"],
          supporting_evidence_ids: ["ev-1", "ev-2"],
          counterevidence_ids: ["ev-3"],
          detector_snapshot: { retailer_sales_value: 123 },
          normalized_arguments: { household_id: "7" },
          tool_result: { raw: "large deterministic envelope" },
          chain_of_thought: "must not cross the bridge",
          password: "must not cross the bridge either",
          message: { chain_of_thought: "nested content must not cross either" },
        },
      }),
    ),
  );

  const [event] = await createLiveTraceReader(root, Date.now()).readNew();
  assert.deepEqual(event.details, {
    selected_tool: "customer_trend",
    investigation_question: "Which observed behavior changed?",
    evidence_count: 2,
    supporting_evidence_count: 2,
    counterevidence_count: 1,
  });
  const serialized = JSON.stringify(event);
  assert.equal(serialized.includes("chain_of_thought"), false);
  assert.equal(serialized.includes("must not cross"), false);
  assert.equal(serialized.includes("detector_snapshot"), false);
  assert.equal(serialized.includes("normalized_arguments"), false);
  assert.equal(serialized.includes("tool_result"), false);
});

test("reads only real customer trace sources and ignores demo-control or symlink sources", async (context) => {
  const root = await makeRoot(context);
  const staging = await makeStaging(root);
  const customer = await writeCustomerTrace(
    staging,
    "7",
    asJsonl(auditEvent()),
  );

  for (const directoryName of [
    "failure_example",
    "type_a_partial_example",
    "customer_$invalid",
  ]) {
    const directory = path.join(staging, directoryName);
    await mkdir(directory, { recursive: true });
    await writeFile(
      path.join(directory, "trace.jsonl"),
      asJsonl(auditEvent({ householdId: "ignored" })),
    );
  }
  await writeFile(path.join(staging, "customer_9"), "not a directory");
  await symlink(path.dirname(customer), path.join(staging, "customer_999"));

  const events = await createLiveTraceReader(root, Date.now()).readNew();
  assert.equal(events.length, 1);
  assert.equal(events[0].source, "customer_7");
  assert.equal(events[0].sourceLabel, "Household 7");
  assert.equal(events[0].householdId, "7");
});

test("ignores unowned and malformed-marker staging directories", async (context) => {
  const root = await makeRoot(context);
  const reader = createLiveTraceReader(root, Date.now());
  const localRoot = path.join(root, "artifacts", "local");
  const unowned = path.join(localRoot, ".dashboard.staging-unowned");
  await writeCustomerTrace(
    unowned,
    "999",
    asJsonl(auditEvent({ householdId: "999" })),
  );
  const malformed = path.join(localRoot, ".dashboard.staging-malformed");
  await mkdir(malformed, { recursive: true });
  await writeFile(
    path.join(malformed, ".whyback-owned-artifact-root.json"),
    "not-json\n",
  );
  await writeCustomerTrace(
    malformed,
    "998",
    asJsonl(auditEvent({ householdId: "998" })),
  );

  assert.deepEqual(await reader.readNew(), []);

  const owned = await makeStaging(root, ".dashboard.staging-owned");
  await writeCustomerTrace(
    owned,
    "7",
    asJsonl(auditEvent({ householdId: "7" })),
  );
  const events = await reader.readNew();
  assert.deepEqual(events.map((event) => event.householdId), ["7"]);
});

test("returns monotonic reader deltas without replaying previously consumed lines", async (context) => {
  const root = await makeRoot(context);
  const staging = await makeStaging(root);
  const first = auditEvent();
  const second = auditEvent({
    event: "model_decision_requested",
    timestamp: "2026-08-25T12:00:01.000Z",
  });
  const third = auditEvent({
    event: "tool_started",
    timestamp: "2026-08-25T12:00:02.000Z",
  });
  const tracePath = await writeCustomerTrace(staging, "7", asJsonl(first, second));
  const reader = createLiveTraceReader(root, Date.now());

  assert.deepEqual(
    (await reader.readNew()).map((event) => event.id),
    ["customer_7:1", "customer_7:2"],
  );
  assert.deepEqual(await reader.readNew(), []);

  await appendFile(tracePath, asJsonl(third));
  assert.deepEqual(
    (await reader.readNew()).map((event) => event.id),
    ["customer_7:3"],
  );
  assert.deepEqual(await reader.readNew(), []);
});

test("does not consume valid trace batches when another source is malformed", async (context) => {
  const root = await makeRoot(context);
  const staging = await makeStaging(root);
  await writeCustomerTrace(
    staging,
    "7",
    asJsonl(auditEvent({ householdId: "7" })),
  );
  const malformedPath = await writeCustomerTrace(staging, "8", "not-json\n");
  const reader = createLiveTraceReader(root, Date.now());

  await assert.rejects(reader.readNew(), /customer_8 is invalid/u);
  await writeFile(
    malformedPath,
    asJsonl(auditEvent({ householdId: "8" })),
  );
  const recovered = await reader.readNew();
  assert.deepEqual(
    recovered.map((event) => event.householdId),
    ["7", "8"],
  );
  assert.deepEqual(await reader.readNew(), []);
});

test("streams only from an explicit owned live-run directory", async (context) => {
  const root = await makeRoot(context);
  const liveRun = await makeStaging(
    root,
    "live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  );
  await writeCustomerTrace(
    liveRun,
    "7",
    asJsonl(auditEvent({ householdId: "7" })),
  );
  const distractor = await makeStaging(root, ".dashboard.staging-distractor");
  await writeCustomerTrace(
    distractor,
    "999",
    asJsonl(auditEvent({ householdId: "999" })),
  );
  const reader = createLiveTraceReader(root, Date.now(), {
    runDirectory: liveRun,
  });

  const events = await reader.readNew();
  assert.deepEqual(events.map((event) => event.householdId), ["7"]);
  assert.equal(JSON.stringify(events).includes("999"), false);
});

test("rejects an explicit trace root outside the repository", async (context) => {
  const root = await makeRoot(context);
  const outside = await makeRoot(context);
  const liveRun = await makeStaging(
    outside,
    "live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  );
  await writeCustomerTrace(liveRun, "7", asJsonl(auditEvent()));

  const reader = createLiveTraceReader(root, Date.now(), {
    runDirectory: liveRun,
  });
  assert.deepEqual(await reader.readNew(), []);
});

test("manager ignores staging directories that existed before its run", async (context) => {
  const root = await makeRoot(context);
  const stale = await makeStaging(root, ".dashboard.staging-stale");
  await writeCustomerTrace(
    stale,
    "999",
    asJsonl(auditEvent({ householdId: "999" })),
  );
  const run = deferred();
  const executeStarted = deferred();
  const manager = createDemoRunManager({
    repositoryRoot: root,
    execute: async () => {
      const current = await makeStaging(root, ".dashboard.staging-current");
      await writeCustomerTrace(
        current,
        "7",
        asJsonl(auditEvent({ householdId: "7" })),
      );
      executeStarted.resolve();
      return run.promise;
    },
    intervalMs: 60_000,
  });
  context.after(() => manager.dispose());

  const started = manager.start(1);
  await executeStarted.promise;
  await manager.refresh(started.jobId);

  const current = manager.status(started.jobId);
  assert.deepEqual(current.events.map((event) => event.householdId), ["7"]);
  assert.equal(JSON.stringify(current).includes("999"), false);

  run.resolve({});
  await waitForStatus(manager, started.jobId, "completed");
});

test("a successful published scan clears a transient staging warning", async (context) => {
  const root = await makeRoot(context);
  const run = deferred();
  const executeStarted = deferred();
  const manager = createDemoRunManager({
    repositoryRoot: root,
    execute: async () => {
      const staging = await makeStaging(root);
      await writeCustomerTrace(staging, "7", "not-json\n");
      executeStarted.resolve();
      return run.promise;
    },
    intervalMs: 60_000,
  });
  context.after(() => manager.dispose());

  const started = manager.start(1);
  await executeStarted.promise;
  await manager.refresh(started.jobId);
  assert.match(
    manager.status(started.jobId).traceWarning,
    /could not be read/u,
  );

  const published = await makePublished(root);
  await writeCustomerTrace(
    published,
    "7",
    asJsonl(auditEvent({ event: "run_completed" })),
  );
  run.resolve({});

  const completed = await waitForStatus(manager, started.jobId, "completed");
  assert.equal(completed.traceWarning, null);
  assert.equal(completed.events.at(-1).event, "run_completed");
});

test("manager reports its capacity and drops only the oldest retained events", async (context) => {
  const root = await makeRoot(context);
  const run = deferred();
  const executeStarted = deferred();
  const manager = createDemoRunManager({
    repositoryRoot: root,
    execute: async () => {
      const staging = await makeStaging(root);
      await writeCustomerTrace(
        staging,
        "7",
        asJsonl(
          auditEvent(),
          auditEvent({
            event: "model_decision_requested",
            timestamp: "2026-08-25T12:00:01.000Z",
          }),
          auditEvent({
            event: "run_completed",
            timestamp: "2026-08-25T12:00:02.000Z",
          }),
        ),
      );
      executeStarted.resolve();
      return run.promise;
    },
    intervalMs: 60_000,
    maxEvents: 2,
  });
  context.after(() => manager.dispose());

  const started = manager.start(5);
  assert.equal(started.eventCapacity, 2);
  await executeStarted.promise;
  await manager.refresh(started.jobId);

  const current = manager.status(started.jobId);
  assert.equal(current.eventCapacity, 2);
  assert.equal(current.eventCount, 3);
  assert.equal(current.droppedEventCount, 1);
  assert.deepEqual(
    current.events.map((event) => [event.cursor, event.event]),
    [
      [2, "model_decision_requested"],
      [3, "run_completed"],
    ],
  );

  run.resolve({});
  await waitForStatus(manager, started.jobId, "completed");
});

test("manager gates concurrent starts, exposes cursor deltas, and releases after completion", async (context) => {
  const root = await makeRoot(context);
  const first = auditEvent();
  const second = auditEvent({
    event: "run_completed",
    timestamp: "2026-08-25T12:00:01.000Z",
    details: { status: "completed" },
  });
  const run = deferred();
  const executeStarted = deferred();
  let tracePath;
  const manager = createDemoRunManager({
    repositoryRoot: root,
    execute: async () => {
      const staging = await makeStaging(root);
      tracePath = await writeCustomerTrace(staging, "7", asJsonl(first));
      executeStarted.resolve();
      return run.promise;
    },
    intervalMs: 60_000,
  });
  context.after(() => manager.dispose());

  const started = manager.start(2);
  assert.equal(started.status, "running");
  assert.equal(started.customers, 2);
  assert.equal(manager.running, true);
  assert.throws(
    () => manager.start(1),
    (error) => error.statusCode === 409,
  );

  await executeStarted.promise;
  await manager.refresh(started.jobId);
  const firstStatus = manager.status(started.jobId, 0);
  assert.deepEqual(firstStatus.events.map((event) => event.cursor), [1]);
  assert.equal(firstStatus.cursor, 1);

  await appendFile(tracePath, asJsonl(second));
  await manager.refresh(started.jobId);
  const delta = manager.status(started.jobId, 1);
  assert.deepEqual(delta.events.map((event) => event.cursor), [2]);
  assert.equal(delta.events[0].event, "run_completed");
  assert.equal(delta.cursor, 2);

  const published = await makePublished(root);
  await writeCustomerTrace(published, "7", asJsonl(first, second));
  run.resolve({});

  const completed = await waitForStatus(manager, started.jobId, "completed");
  assert.equal(completed.eventCount, 2);
  assert.equal(completed.collectionId, "dashboard");
  assert.ok(completed.completedAt);
  assert.equal(manager.running, false);

  const replacement = manager.start(1);
  assert.notEqual(replacement.jobId, started.jobId);
  assert.equal(replacement.status, "running");
  await waitForStatus(manager, replacement.jobId, "completed");
  assert.equal(manager.status(started.jobId)?.status, "completed");
});

test("manager preserves partial events, records failure, and releases the running gate", async (context) => {
  const root = await makeRoot(context);
  const run = deferred();
  const executeStarted = deferred();
  let callCount = 0;
  const manager = createDemoRunManager({
    repositoryRoot: root,
    execute: async () => {
      callCount += 1;
      if (callCount === 1) {
        const staging = await makeStaging(root);
        await writeCustomerTrace(
          staging,
          "7",
          asJsonl(
            auditEvent(),
            auditEvent({
              event: "tool_failed",
              timestamp: "2026-08-25T12:00:01.000Z",
              details: {
                tool_name: "promotion_response",
                status: "retryable_error",
              },
            }),
          ),
        );
        executeStarted.resolve();
        return run.promise;
      }
      return {};
    },
    intervalMs: 60_000,
  });
  context.after(() => manager.dispose());

  const started = manager.start(1);
  await executeStarted.promise;
  await manager.refresh(started.jobId);
  run.reject(new Error("password=must-not-cross-the-bridge"));

  const failed = await waitForStatus(manager, started.jobId, "failed");
  assert.equal(failed.eventCount, 2);
  assert.equal(failed.events.at(-1).event, "tool_failed");
  assert.equal(failed.error, "The live Gemini run failed before completion.");
  assert.equal(JSON.stringify(failed).includes("must-not-cross"), false);
  assert.ok(failed.completedAt);
  assert.equal(manager.running, false);

  const next = manager.start(1);
  assert.notEqual(next.jobId, started.jobId);
  await waitForStatus(manager, next.jobId, "completed");
});

test("manager carries a unique live descriptor through execution and status", async (context) => {
  const root = await makeRoot(context);
  let receivedDescriptor = null;
  const manager = createDemoRunManager({
    repositoryRoot: root,
    backend: "gemini",
    model: "gemini-test-model",
    describeRun: (customers, jobId) => ({
      backend: "gemini",
      collectionId: `live-${jobId}`,
      command: `uv run whyback demo --customers ${customers} --backend gemini`,
      model: "gemini-test-model",
      runDirectory: path.join(root, "artifacts", "local", "live-runs", `live-${jobId}`),
    }),
    execute: async (_customers, descriptor) => {
      receivedDescriptor = descriptor;
      await mkdir(descriptor.runDirectory, { recursive: true });
      await writeFile(
        path.join(descriptor.runDirectory, ".whyback-owned-artifact-root.json"),
        `${JSON.stringify({
          schema_version: 1,
          product: "WhyBack",
          scope: "replaceable_generated_artifact_tree",
        })}\n`,
      );
      await writeCustomerTrace(
        descriptor.runDirectory,
        "7",
        asJsonl(auditEvent({ event: "run_completed" })),
      );
    },
    intervalMs: 60_000,
  });
  context.after(() => manager.dispose());

  const started = manager.start(5);
  assert.equal(started.backend, "gemini");
  assert.equal(started.model, "gemini-test-model");
  assert.match(started.collectionId, /^live-/u);
  assert.match(started.command, /--backend gemini/u);

  const completed = await waitForStatus(manager, started.jobId, "completed");
  assert.equal(receivedDescriptor.collectionId, completed.collectionId);
  assert.equal(completed.events.at(-1).event, "run_completed");
});
