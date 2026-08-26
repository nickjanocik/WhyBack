/** Tests localhost security, live-run subprocess boundaries, and graceful shutdown. */

import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { setImmediate } from "node:timers";

import {
  configuredGeminiModel,
  createDashboardShutdown,
  describeLiveRun,
  hostHeaderAllowed,
  liveDemoArguments,
  liveManifestIsVerified,
  liveRunCapability,
  liveRunRequestError,
  liveRunTimeoutMs,
  mutationHeaderError,
  preparedDataIsValidated,
  runLiveDemo,
  startLiveRun,
  stopActiveLiveProcesses,
} from "./index.mjs";

/** Creates a temporary repository root and registers cleanup with the test. */
async function makeRoot(context) {
  const root = await mkdtemp(path.join(os.tmpdir(), "whyback-index-test-"));
  context.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

/** Writes the minimum owned live output expected before independent verification. */
async function writeVerifiedLiveOutput(descriptor, householdIds) {
  await mkdir(descriptor.directory, { recursive: true });
  await writeFile(
    path.join(descriptor.directory, ".whyback-owned-artifact-root.json"),
    `${JSON.stringify({
      schema_version: 1,
      product: "WhyBack",
      scope: "replaceable_generated_artifact_tree",
    })}\n`,
  );
  for (const householdId of householdIds) {
    const customer = path.join(descriptor.directory, `customer_${householdId}`);
    await mkdir(customer);
    await Promise.all([
      writeFile(path.join(customer, "report.json"), "{}\n"),
      writeFile(path.join(customer, "trace.jsonl"), "{}\n"),
    ]);
  }
  await writeFile(
    path.join(descriptor.directory, "population_summary.json"),
    `${JSON.stringify({
      schema_version: 1,
      detector_policy: {
        decline_threshold: descriptor.declineThreshold ?? 0.3,
      },
    })}\n`,
  );
  await writeFile(
    path.join(descriptor.directory, "manifest.json"),
    `${JSON.stringify({
      dataset_kind: "official_complete_journey",
      backend: "gemini",
      execution_mode: "live",
      model_execution: "live_gemini",
      population_summary: "population_summary.json",
      population_schema_version: 1,
      selected_household_ids: householdIds,
      completed_household_ids: householdIds,
      failed_household_ids: [],
      skipped_household_ids: [],
      human_review_required: true,
      customer_outreach_executed: false,
    })}\n`,
  );
}

test("accepts same-origin JSON mutation requests", () => {
  assert.equal(
    mutationHeaderError({
      "content-type": "application/json; charset=utf-8",
      origin: "http://127.0.0.1:4173",
      "sec-fetch-site": "same-origin",
    }),
    null,
  );
});

test("rejects non-JSON and cross-site mutation requests", () => {
  assert.equal(
    mutationHeaderError({ "content-type": "text/plain" }),
    "Content-Type must be application/json.",
  );
  assert.equal(
    mutationHeaderError({
      "content-type": "application/json",
      origin: "https://malicious.example",
      "sec-fetch-site": "cross-site",
    }),
    "Cross-site requests are not allowed.",
  );
});

test("allows only localhost Host headers", () => {
  assert.equal(hostHeaderAllowed("127.0.0.1:4173"), true);
  assert.equal(hostHeaderAllowed("localhost:5163"), true);
  assert.equal(hostHeaderAllowed("malicious.example"), false);
  assert.equal(hostHeaderAllowed(undefined), false);
});

test("publishes secret-free live readiness and requires official prepared data", async (context) => {
  const root = await makeRoot(context);
  const secret = "sentinel-live-key-that-must-not-be-serialized";
  const unavailable = await liveRunCapability({
    root,
    environment: {},
    validatePrepared: async () => false,
  });
  assert.equal(unavailable.ready, false);
  assert.match(unavailable.blockedReason, /GEMINI_API_KEY/u);
  assert.match(unavailable.blockedReason, /prepared data/u);

  const prepared = path.join(root, "data", "prepared");
  await mkdir(prepared, { recursive: true });
  await Promise.all([
    writeFile(path.join(prepared, "manifest.json"), "{}\n"),
    writeFile(path.join(prepared, "household_week.parquet"), "fixture\n"),
  ]);
  const available = await liveRunCapability({
    root,
    environment: {
      GEMINI_API_KEY: secret,
      RETENTION_MODEL: "gemini-test-model",
    },
    validatePrepared: async () => true,
  });
  assert.deepEqual(available, {
    backend: "gemini",
    model: "gemini-test-model",
    ready: true,
    blockedReason: null,
  });
  assert.equal(JSON.stringify(available).includes(secret), false);

  let validations = 0;
  const shuttingDown = await liveRunCapability({
    root,
    environment: { GEMINI_API_KEY: secret },
    canStartProcess: () => false,
    validatePrepared: async () => {
      validations += 1;
      return true;
    },
  });
  assert.equal(shuttingDown.ready, false);
  assert.match(shuttingDown.blockedReason, /shutting down/u);
  assert.equal(validations, 0);
});

test("validates official prepared data without passing the Gemini credential", async () => {
  const secret = "preflight-secret-sentinel";
  let spawnCall = null;
  const ready = await preparedDataIsValidated({
    root: "/workspace/WhyBack",
    environment: { GEMINI_API_KEY: secret, WHYBACK_DATA_DIR: "data" },
    spawnProcess: (command, args, options) => {
      const child = new EventEmitter();
      child.kill = () => true;
      spawnCall = { command, args, options };
      setImmediate(() => child.emit("close", 0));
      return child;
    },
  });

  assert.equal(ready, true);
  assert.equal(spawnCall.command, "uv");
  assert.deepEqual(spawnCall.args, [
    "run",
    "whyback",
    "data",
    "validate",
    "--official",
  ]);
  assert.equal(spawnCall.options.env.GEMINI_API_KEY, undefined);
});

test("fails closed without live readiness before invoking the run manager", () => {
  const starts = [];
  const manager = {
    /** Records whether readiness allowed the test manager to start. */
    start(...args) {
      starts.push(args);
      return {};
    },
  };
  assert.throws(
    () =>
      startLiveRun(manager, 5, {
        ready: false,
        blockedReason: "Server credential unavailable.",
      }),
    (error) => error?.statusCode === 503,
  );
  assert.equal(starts.length, 0);
  assert.deepEqual(startLiveRun(manager, 5, { ready: true }), {});
  assert.deepEqual(starts, [[5, 0.3]]);
  assert.deepEqual(startLiveRun(manager, 5, { ready: true }, 0.4), {});
  assert.deepEqual(starts.at(-1), [5, 0.4]);
  assert.throws(
    () => startLiveRun(manager, 5, { ready: true }, 0.25),
    (error) => error?.statusCode === 400,
  );
  assert.equal(starts.length, 2);
});

test("accepts only a customer count and governed decline threshold", () => {
  assert.equal(liveRunRequestError({ customers: 5 }), null);
  assert.equal(
    liveRunRequestError({ customers: 5, declineThreshold: 0.2 }),
    null,
  );
  assert.equal(
    liveRunRequestError({ customers: 5, declineThreshold: 0.4 }),
    null,
  );
  assert.equal(
    liveRunRequestError({ customers: 5, backend: "scripted" }),
    "The live run request may contain only customers and declineThreshold.",
  );
  assert.equal(
    liveRunRequestError({ customers: 5, apiKey: "browser-key" }),
    "The live run request may contain only customers and declineThreshold.",
  );
  assert.match(
    liveRunRequestError({ customers: 5, declineThreshold: 0.25 }),
    /0\.2, 0\.3, or 0\.4/u,
  );
  assert.match(
    liveRunRequestError({ customers: 5, declineThreshold: null }),
    /0\.2, 0\.3, or 0\.4/u,
  );
  assert.equal(liveRunRequestError({ customers: 3 }), null);
  assert.equal(liveRunRequestError({ customers: 4 }), null);
  assert.match(liveRunRequestError({ customers: 2 }), /3 through 24/u);
});

test("constructs only the fixed Gemini command in a unique live collection", () => {
  const jobId = "123e4567-e89b-42d3-a456-426614174000";
  const descriptor = describeLiveRun(24, jobId, {
    root: "/workspace/WhyBack",
    declineThreshold: 0.4,
    environment: {
      GEMINI_API_KEY: "must-not-appear",
      RETENTION_MODEL: "gemini-test-model",
    },
  });
  const exactArguments = [
    "run",
    "whyback",
    "demo",
    "--customers",
    "24",
    "--decline-threshold",
    "0.4",
    "--backend",
    "gemini",
    "--output-dir",
    "artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  ];
  assert.deepEqual(descriptor.args, exactArguments);
  assert.deepEqual(
    liveDemoArguments(24, descriptor.relativePath, 0.4),
    exactArguments,
  );
  assert.equal(descriptor.command, `uv ${exactArguments.join(" ")}`);
  assert.match(descriptor.collectionId, /^live-/u);
  assert.equal(descriptor.backend, "gemini");
  assert.equal(descriptor.declineThreshold, 0.4);
  assert.equal(descriptor.model, "gemini-test-model");
  assert.match(descriptor.command, /--backend gemini/u);
  assert.match(descriptor.command, /artifacts[/\\]local[/\\]live-runs/u);
  assert.equal(descriptor.command.includes("scripted"), false);
  assert.equal(descriptor.command.includes("must-not-appear"), false);
  assert.throws(
    () => liveDemoArguments(5, descriptor.relativePath, "0.3 --backend scripted"),
    /declineThreshold must be one of/u,
  );
});

test("accepts only reconciled manifests that prove a live Gemini execution", () => {
  const valid = {
    dataset_kind: "official_complete_journey",
    backend: "gemini",
    execution_mode: "live",
    model_execution: "live_gemini",
    selected_household_ids: ["7", "8"],
    completed_household_ids: ["7"],
    failed_household_ids: ["8"],
    skipped_household_ids: [],
    human_review_required: true,
    customer_outreach_executed: false,
  };
  assert.equal(liveManifestIsVerified(valid, 2), true);
  assert.equal(
    liveManifestIsVerified({ ...valid, backend: "scripted" }, 2),
    false,
  );
  assert.equal(
    liveManifestIsVerified({ ...valid, execution_mode: "skipped" }, 2),
    false,
  );
  assert.equal(
    liveManifestIsVerified(
      { ...valid, completed_household_ids: ["7", "8"] },
      2,
    ),
    false,
  );
});

test("uses bounded live timeouts and the configured Gemini model", () => {
  assert.equal(configuredGeminiModel({}), "gemini-3.7-flash");
  assert.equal(configuredGeminiModel({ RETENTION_MODEL: "  gemini-custom  " }), "gemini-custom");
  assert.equal(liveRunTimeoutMs({ WHYBACK_LIVE_TIMEOUT_MS: "60000" }), 60_000);
  assert.equal(liveRunTimeoutMs({ WHYBACK_LIVE_TIMEOUT_MS: "10" }), 14_400_000);
  assert.equal(liveRunTimeoutMs({ WHYBACK_LIVE_TIMEOUT_MS: "not-a-number" }), 14_400_000);
});

test("publishes independently verified terminal output after a nonzero CLI exit", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "123e4567-e89b-42d3-a456-426614174000",
    { root, environment: { RETENTION_MODEL: "gemini-test-model" } },
  );
  await writeVerifiedLiveOutput(descriptor, ["7", "8", "9", "10", "11"]);
  const secret = "child-only-sentinel";
  const spawnCalls = [];
  const completed = runLiveDemo(5, descriptor, {
    environment: { GEMINI_API_KEY: secret },
    spawnProcess: (command, args, options) => {
      const child = new EventEmitter();
      child.kill = () => true;
      const exitCode = spawnCalls.length === 0 ? 9 : 0;
      spawnCalls.push({ command, args, options });
      setImmediate(() => child.emit("close", exitCode));
      return child;
    },
    timeoutMs: 60_000,
  });

  const result = await completed;
  assert.equal(spawnCalls.length, 2);
  assert.equal(spawnCalls[0].command, "uv");
  assert.deepEqual(spawnCalls[0].args, [
    "run",
    "whyback",
    "demo",
    "--customers",
    "5",
    "--decline-threshold",
    "0.3",
    "--backend",
    "gemini",
    "--output-dir",
    "artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  ]);
  assert.equal(spawnCalls[0].options.shell, false);
  assert.equal(spawnCalls[0].options.stdio, "ignore");
  assert.equal(spawnCalls[0].options.env.GEMINI_API_KEY, secret);
  assert.deepEqual(spawnCalls[1].args, [
    "run",
    "python",
    "scripts/verify_artifacts.py",
    "artifacts/local/live-runs/live-123e4567-e89b-42d3-a456-426614174000",
  ]);
  assert.equal(spawnCalls[1].options.env.GEMINI_API_KEY, undefined);
  assert.equal(result.command.includes(secret), false);
  assert.match(result.command, /--backend gemini/u);
  const seal = JSON.parse(
    await readFile(
      path.join(descriptor.directory, ".whyback-live-verification.json"),
      "utf8",
    ),
  );
  assert.equal(seal.status, "verified_live_gemini");
});

test("rejects a nonzero CLI exit when its terminal output is missing", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "223e4567-e89b-42d3-b456-426614174000",
    { root },
  );
  const spawnCalls = [];

  await assert.rejects(
    runLiveDemo(5, descriptor, {
      environment: { GEMINI_API_KEY: "sentinel" },
      spawnProcess: (command, args, options) => {
        const child = new EventEmitter();
        child.kill = () => true;
        spawnCalls.push({ command, args, options });
        setImmediate(() => child.emit("close", 7));
        return child;
      },
      timeoutMs: 60_000,
    }),
    /did not publish a verified live artifact collection/u,
  );
  assert.equal(spawnCalls.length, 1);
  assert.deepEqual(spawnCalls[0].args, [
    "run",
    "whyback",
    "demo",
    "--customers",
    "5",
    "--decline-threshold",
    "0.3",
    "--backend",
    "gemini",
    "--output-dir",
    "artifacts/local/live-runs/live-223e4567-e89b-42d3-b456-426614174000",
  ]);
});

test("rejects output whose published detector threshold differs from the request", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "273e4567-e89b-42d3-b456-426614174000",
    { root, declineThreshold: 0.4 },
  );
  await writeVerifiedLiveOutput(descriptor, ["7", "8", "9", "10", "11"]);
  await writeFile(
    path.join(descriptor.directory, "population_summary.json"),
    `${JSON.stringify({
      schema_version: 1,
      detector_policy: { decline_threshold: 0.3 },
    })}\n`,
  );
  const spawnCalls = [];

  await assert.rejects(
    runLiveDemo(5, descriptor, {
      environment: { GEMINI_API_KEY: "sentinel" },
      spawnProcess: (command, args, options) => {
        const child = new EventEmitter();
        child.kill = () => true;
        spawnCalls.push({ command, args, options });
        setImmediate(() => child.emit("close", 0));
        return child;
      },
      timeoutMs: 60_000,
    }),
    /did not publish a verified live artifact collection/u,
  );
  assert.equal(spawnCalls.length, 1);
});

test("does not seal terminal output when independent verification fails", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "323e4567-e89b-42d3-8456-426614174000",
    { root },
  );
  await writeVerifiedLiveOutput(descriptor, ["7", "8", "9", "10", "11"]);
  const secret = "verifier-secret-sentinel";
  const spawnCalls = [];

  await assert.rejects(
    runLiveDemo(5, descriptor, {
      environment: { GEMINI_API_KEY: secret },
      spawnProcess: (command, args, options) => {
        const child = new EventEmitter();
        child.kill = () => true;
        const exitCode = spawnCalls.length === 0 ? 4 : 1;
        spawnCalls.push({ command, args, options });
        setImmediate(() => child.emit("close", exitCode));
        return child;
      },
      timeoutMs: 60_000,
    }),
    /failed deterministic verification/u,
  );
  assert.equal(spawnCalls.length, 2);
  assert.equal(spawnCalls[0].options.env.GEMINI_API_KEY, secret);
  assert.equal(spawnCalls[1].options.env.GEMINI_API_KEY, undefined);
  await assert.rejects(
    readFile(path.join(descriptor.directory, ".whyback-live-verification.json")),
    (error) => error?.code === "ENOENT",
  );
});

test("terminates a timed-out live process before rejecting", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "123e4567-e89b-42d3-a456-426614174000",
    { root },
  );
  const child = new EventEmitter();
  const signals = [];
  child.kill = (signal) => {
    signals.push(signal);
    if (signal === "SIGTERM") setImmediate(() => child.emit("close", null));
    return true;
  };

  await assert.rejects(
    runLiveDemo(5, descriptor, {
      environment: { GEMINI_API_KEY: "sentinel" },
      spawnProcess: () => child,
      timeoutMs: 1,
    }),
    /configured time boundary/u,
  );
  assert.deepEqual(signals, ["SIGTERM", "SIGKILL"]);
});

test("keeps a post-spawn process error failed until the child closes", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "123e4567-e89b-42d3-a456-426614174000",
    { root },
  );
  const child = new EventEmitter();
  child.pid = 987_654_321;
  child.kill = () => true;

  const running = runLiveDemo(5, descriptor, {
    environment: { GEMINI_API_KEY: "sentinel" },
    spawnProcess: () => child,
    timeoutMs: 60_000,
  });
  child.emit("error", new Error("post-spawn failure"));
  setImmediate(() => child.emit("close", 0));

  await assert.rejects(running, /exited before completion/u);
});

test("does not start artifact verification after shutdown begins", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "123e4567-e89b-42d3-a456-426614174000",
    { root },
  );
  await writeVerifiedLiveOutput(descriptor, ["7", "8", "9", "10", "11"]);
  let acceptingProcesses = true;
  let spawnCount = 0;

  const running = runLiveDemo(5, descriptor, {
    environment: { GEMINI_API_KEY: "sentinel" },
    canStartProcess: () => acceptingProcesses,
    spawnProcess: () => {
      const child = new EventEmitter();
      child.kill = () => true;
      spawnCount += 1;
      setImmediate(() => {
        acceptingProcesses = false;
        child.emit("close", 0);
      });
      return child;
    },
    timeoutMs: 60_000,
  });

  await assert.rejects(running, /shutting down/u);
  assert.equal(spawnCount, 1);
});

test("shutdown terminates an active live child before releasing it", async (context) => {
  const root = await makeRoot(context);
  const descriptor = describeLiveRun(
    5,
    "123e4567-e89b-42d3-a456-426614174000",
    { root },
  );
  const child = new EventEmitter();
  const signals = [];
  child.kill = (signal) => {
    signals.push(signal);
    setImmediate(() => child.emit("close", null));
    return true;
  };
  const running = runLiveDemo(5, descriptor, {
    environment: { GEMINI_API_KEY: "sentinel" },
    spawnProcess: () => child,
    timeoutMs: 60_000,
  });

  assert.equal(
    await stopActiveLiveProcesses({ graceMs: 100, forceMs: 100 }),
    true,
  );
  await assert.rejects(running, /exited before completion/u);
  assert.deepEqual(signals, ["SIGTERM"]);
});

test("dashboard shutdown closes the listener, stops processes, and exits once", async () => {
  const calls = [];
  const server = {
    /** Simulates an HTTP listener that closes immediately. */
    close(callback) {
      calls.push("server");
      callback();
    },
  };
  const shutdown = createDashboardShutdown({
    server,
    beginShutdown: () => calls.push("begin"),
    stopProcesses: async () => {
      calls.push("processes");
      return true;
    },
    exitProcess: (code) => calls.push(`exit:${code}`),
  });

  await Promise.all([shutdown(), shutdown()]);
  assert.deepEqual(calls, ["begin", "server", "processes", "processes", "exit:0"]);
});

test("dashboard shutdown performs its final process drain after HTTP close", async () => {
  const calls = [];
  let finishClose = null;
  const server = {
    /** Holds the HTTP close callback so the test can complete it later. */
    close(callback) {
      calls.push("server");
      finishClose = callback;
    },
  };
  const shutdown = createDashboardShutdown({
    server,
    beginShutdown: () => calls.push("begin"),
    stopProcesses: async () => {
      calls.push("processes");
      return true;
    },
    exitProcess: (code) => calls.push(`exit:${code}`),
  });

  const completion = shutdown();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(calls, ["begin", "server", "processes"]);
  finishClose();
  await completion;
  assert.deepEqual(calls, ["begin", "server", "processes", "processes", "exit:0"]);
});
