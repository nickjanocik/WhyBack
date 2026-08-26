import { spawn } from "node:child_process";
import { Buffer } from "node:buffer";
import { createReadStream } from "node:fs";
import { lstat, readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import process from "node:process";
import { clearTimeout, setTimeout } from "node:timers";
import { fileURLToPath, URL } from "node:url";

import {
  loadInvestigation,
  loadWorkspace,
  resolveArtifactFile,
} from "./artifacts.mjs";
import { demoCustomerCountError } from "./demo-limits.mjs";
import { createDemoRunManager, DemoRunError } from "./live-trace.mjs";
import {
  createLiveRunDescriptor,
  markLiveRunVerified,
  resolveOwnedLiveRunDirectory,
} from "./live-runs.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(webRoot, "..");
const distRoot = path.join(webRoot, "dist");
const host = "127.0.0.1";
const parsedPort = Number(process.env.WHYBACK_DASHBOARD_PORT || 4173);
const port = Number.isInteger(parsedPort) && parsedPort > 0 ? parsedPort : 4173;
const MAX_BODY_BYTES = 4_096;
const DEFAULT_LIVE_TIMEOUT_MS = 4 * 60 * 60 * 1_000;
const MIN_LIVE_TIMEOUT_MS = 60_000;
const MAX_LIVE_TIMEOUT_MS = 6 * 60 * 60 * 1_000;
const ARTIFACT_VERIFICATION_TIMEOUT_MS = 10 * 60 * 1_000;
const DEFAULT_GEMINI_MODEL = "gemini-3.7-flash";
let dashboardShuttingDown = false;

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml",
};

function securityHeaders(response, api = false) {
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Referrer-Policy", "no-referrer");
  response.setHeader("X-Frame-Options", "DENY");
  response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
  response.setHeader(
    "Content-Security-Policy",
    "default-src 'none'; connect-src 'self'; font-src 'self'; img-src 'self' data:; " +
      "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
      "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  );
  if (api) response.setHeader("Cache-Control", "no-store");
}

export function mutationHeaderError(headers) {
  const contentType = String(headers["content-type"] || "").toLowerCase();
  if (!contentType.startsWith("application/json")) {
    return "Content-Type must be application/json.";
  }
  const fetchSite = String(headers["sec-fetch-site"] || "").toLowerCase();
  if (fetchSite === "cross-site") return "Cross-site requests are not allowed.";
  const origin = headers.origin ? String(headers.origin) : null;
  const allowedOrigins = new Set([
    `http://${host}:${port}`,
    `http://${host}:5163`,
    "http://localhost:4173",
    "http://localhost:5163",
    "http://127.0.0.1:4173",
    "http://127.0.0.1:5163",
  ]);
  return origin && !allowedOrigins.has(origin)
    ? "Cross-origin requests are not allowed."
    : null;
}

export function hostHeaderAllowed(value) {
  if (!value) return false;
  try {
    const hostname = new URL(`http://${String(value)}`).hostname.toLowerCase();
    return hostname === "127.0.0.1" || hostname === "localhost";
  } catch {
    return false;
  }
}

function sendJson(response, statusCode, value) {
  const payload = `${JSON.stringify(value)}\n`;
  response.statusCode = statusCode;
  response.setHeader("Content-Type", contentTypes[".json"]);
  securityHeaders(response, true);
  response.end(payload);
}

function sendError(response, statusCode, message) {
  sendJson(response, statusCode, { error: message });
}

async function readJsonBody(request) {
  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) {
      const error = new Error("Request body is too large.");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    const error = new Error("Request body must be valid JSON.");
    error.statusCode = 400;
    throw error;
  }
}

export function configuredGeminiModel(environment = process.env) {
  const configured = String(environment.RETENTION_MODEL || "").trim();
  return configured ? configured.slice(0, 128) : DEFAULT_GEMINI_MODEL;
}

export function liveRunTimeoutMs(environment = process.env) {
  const configured = Number(environment.WHYBACK_LIVE_TIMEOUT_MS);
  return Number.isInteger(configured) &&
    configured >= MIN_LIVE_TIMEOUT_MS &&
    configured <= MAX_LIVE_TIMEOUT_MS
    ? configured
    : DEFAULT_LIVE_TIMEOUT_MS;
}

async function isRealFile(filePath) {
  try {
    const details = await lstat(filePath);
    return details.isFile() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT" || error?.code === "ENOTDIR") return false;
    throw error;
  }
}

export async function liveRunCapability({
  root = repositoryRoot,
  environment = process.env,
  validatePrepared = preparedDataIsValidated,
  canStartProcess = () => true,
} = {}) {
  const blockedReasons = [];
  if (!canStartProcess()) {
    blockedReasons.push("The dashboard is shutting down.");
  }
  if (!String(environment.GEMINI_API_KEY || "").trim()) {
    blockedReasons.push(
      "GEMINI_API_KEY is not configured on the dashboard server. Add it to the repository .env or server environment, then restart the dashboard.",
    );
  }
  const preparedReady = canStartProcess()
    ? await validatePrepared({ root, environment, canStartProcess })
    : false;
  if (!preparedReady) {
    blockedReasons.push(
      "Official prepared data is unavailable. Run the WhyBack prepare workflow before starting a live batch.",
    );
  }
  return {
    backend: "gemini",
    model: configuredGeminiModel(environment),
    ready: blockedReasons.length === 0,
    blockedReason: blockedReasons.length ? blockedReasons.join(" ") : null,
  };
}

export function liveDemoArguments(customers, relativeOutputPath) {
  return [
    "run",
    "whyback",
    "demo",
    "--customers",
    String(customers),
    "--backend",
    "gemini",
    "--output-dir",
    relativeOutputPath,
  ];
}

export function describeLiveRun(
  customers,
  jobId,
  { root = repositoryRoot, environment = process.env } = {},
) {
  const target = createLiveRunDescriptor(root, jobId);
  const args = liveDemoArguments(customers, target.relativePath);
  return {
    ...target,
    args,
    backend: "gemini",
    command: `uv ${args.join(" ")}`,
    model: configuredGeminiModel(environment),
    repositoryRoot: root,
    runDirectory: target.directory,
  };
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function liveManifestIsVerified(manifest, customers) {
  if (
    !isPlainObject(manifest) ||
    manifest.dataset_kind !== "official_complete_journey" ||
    manifest.backend !== "gemini" ||
    manifest.execution_mode !== "live" ||
    manifest.model_execution !== "live_gemini" ||
    manifest.customer_outreach_executed !== false ||
    manifest.human_review_required !== true
  ) {
    return false;
  }
  const selected = manifest.selected_household_ids;
  const completed = manifest.completed_household_ids;
  const failed = manifest.failed_household_ids;
  const skipped = manifest.skipped_household_ids;
  if (
    !Array.isArray(selected) ||
    !Array.isArray(completed) ||
    !Array.isArray(failed) ||
    !Array.isArray(skipped) ||
    selected.length !== customers ||
    skipped.length !== 0
  ) {
    return false;
  }
  const householdId = /^[A-Za-z0-9_-]{1,64}$/u;
  if (
    ![selected, completed, failed, skipped].every((items) =>
      items.every((item) => typeof item === "string" && householdId.test(item)),
    )
  ) {
    return false;
  }
  const normalizedSelected = selected;
  const normalizedCompleted = completed;
  const normalizedFailed = failed;
  const selectedSet = new Set(normalizedSelected);
  const terminal = [...normalizedCompleted, ...normalizedFailed];
  return (
    selectedSet.size === customers &&
    terminal.length === customers &&
    new Set(terminal).size === customers &&
    terminal.every((householdId) => selectedSet.has(householdId))
  );
}

async function verifyLiveOutput(descriptor, customers) {
  try {
    const ownedDirectory = await resolveOwnedLiveRunDirectory(
      descriptor.repositoryRoot ?? repositoryRoot,
      descriptor.collectionId,
    );
    if (!ownedDirectory || ownedDirectory !== path.resolve(descriptor.directory)) {
      return false;
    }
    const manifest = JSON.parse(
      await readFile(path.join(ownedDirectory, "manifest.json"), "utf8"),
    );
    if (!liveManifestIsVerified(manifest, customers)) return false;
    const artifactChecks = manifest.selected_household_ids.flatMap((householdId) => {
      const customerDirectory = path.join(ownedDirectory, `customer_${householdId}`);
      return [
        isRealFile(path.join(customerDirectory, "report.json")),
        isRealFile(path.join(customerDirectory, "trace.jsonl")),
      ];
    });
    return (await Promise.all(artifactChecks)).every(Boolean);
  } catch (error) {
    if (error?.code === "ENOENT" || error instanceof SyntaxError) return false;
    throw error;
  }
}

const activeLiveProcesses = new Set();
const activeProcessWaiters = new Set();

function trackLiveProcess(child) {
  activeLiveProcesses.add(child);
  const remove = () => {
    activeLiveProcesses.delete(child);
    if (activeLiveProcesses.size === 0) {
      for (const resolve of activeProcessWaiters) resolve();
      activeProcessWaiters.clear();
    }
  };
  child.once("close", remove);
  return remove;
}

function waitForActiveProcesses(timeoutMs) {
  if (activeLiveProcesses.size === 0) return Promise.resolve(true);
  return new Promise((resolve) => {
    let settled = false;
    const onEmpty = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      activeProcessWaiters.delete(onEmpty);
      resolve(true);
    };
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      activeProcessWaiters.delete(onEmpty);
      resolve(false);
    }, timeoutMs);
    activeProcessWaiters.add(onEmpty);
  });
}

function terminateProcessTree(child, signal) {
  let groupError = null;
  if (process.platform !== "win32" && Number.isInteger(child.pid)) {
    try {
      process.kill(-child.pid, signal);
      return;
    } catch (error) {
      if (error?.code !== "ESRCH") groupError = error;
    }
  }
  try {
    if (child.kill(signal) !== false) return;
  } catch (error) {
    if (error?.code !== "ESRCH" && !groupError) groupError = error;
  }
  if (groupError) throw groupError;
}

export async function stopActiveLiveProcesses({
  graceMs = 5_000,
  forceMs = 1_000,
} = {}) {
  for (const child of activeLiveProcesses) {
    try {
      terminateProcessTree(child, "SIGTERM");
    } catch {
      // Keep the process registered and continue to the mandatory force pass.
    }
  }
  if (await waitForActiveProcesses(graceMs)) return true;
  for (const child of activeLiveProcesses) {
    try {
      terminateProcessTree(child, "SIGKILL");
    } catch {
      // A failed kill remains active and makes shutdown return false.
    }
  }
  return waitForActiveProcesses(forceMs);
}

function runBoundedChild({
  args,
  canStartProcess,
  environment,
  failureMessage,
  spawnProcess,
  startFailureMessage,
  timeoutMessage,
  timeoutMs,
  workingDirectory,
}) {
  return new Promise((resolve, reject) => {
    if (!canStartProcess()) {
      reject(
        new DemoRunError(
          "The dashboard is shutting down; no new subprocess was started.",
        ),
      );
      return;
    }
    const child = spawnProcess("uv", args, {
      cwd: workingDirectory,
      detached: process.platform !== "win32",
      env: environment,
      shell: false,
      stdio: "ignore",
    });
    const untrack = trackLiveProcess(child);
    let timedOut = false;
    let processError = false;
    let forceTimer = null;
    let settled = false;
    const rejectOnce = (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };
    const timer = setTimeout(() => {
      timedOut = true;
      try {
        terminateProcessTree(child, "SIGTERM");
      } catch {
        // Do not release the run gate until the child emits close.
      }
      forceTimer = setTimeout(() => {
        try {
          terminateProcessTree(child, "SIGKILL");
        } catch {
          // Keep waiting for close so another paid run cannot start concurrently.
        }
      }, 5_000);
      forceTimer.unref();
    }, timeoutMs);
    timer.unref();
    child.once("error", () => {
      if (!Number.isInteger(child.pid)) {
        clearTimeout(timer);
        if (forceTimer) clearTimeout(forceTimer);
        untrack();
        rejectOnce(new DemoRunError(startFailureMessage));
      } else {
        processError = true;
      }
    });
    child.once("close", (code) => {
      clearTimeout(timer);
      if (forceTimer) clearTimeout(forceTimer);
      if (settled) return;
      if (timedOut) {
        try {
          terminateProcessTree(child, "SIGKILL");
        } catch {
          // The close event is authoritative: no process remains to gate.
        }
        rejectOnce(new DemoRunError(timeoutMessage));
      } else if (processError || code !== 0) {
        rejectOnce(new DemoRunError(failureMessage));
      } else {
        settled = true;
        resolve();
      }
    });
  });
}

export async function preparedDataIsValidated({
  root = repositoryRoot,
  environment = process.env,
  spawnProcess = spawn,
  canStartProcess = () => true,
} = {}) {
  const validationEnvironment = { ...environment };
  delete validationEnvironment.GEMINI_API_KEY;
  try {
    await runBoundedChild({
      args: ["run", "whyback", "data", "validate", "--official"],
      canStartProcess,
      environment: validationEnvironment,
      failureMessage: "Official prepared data failed validation.",
      spawnProcess,
      startFailureMessage: "Prepared-data validation could not be started.",
      timeoutMessage: "Prepared-data validation exceeded its time boundary.",
      timeoutMs: 60_000,
      workingDirectory: root,
    });
    return true;
  } catch (error) {
    if (error instanceof DemoRunError) return false;
    throw error;
  }
}

export async function runLiveDemo(
  customers,
  descriptor,
  {
    environment = process.env,
    spawnProcess = spawn,
    timeoutMs = liveRunTimeoutMs(environment),
    verificationTimeoutMs = ARTIFACT_VERIFICATION_TIMEOUT_MS,
    canStartProcess = () => true,
  } = {},
) {
  const root = descriptor.repositoryRoot ?? repositoryRoot;
  await runBoundedChild({
    args: descriptor.args,
    canStartProcess,
    environment,
    failureMessage: "The live Gemini process exited before completion.",
    spawnProcess,
    startFailureMessage: "The live Gemini process could not be started.",
    timeoutMessage: "The live Gemini run exceeded its configured time boundary.",
    timeoutMs,
    workingDirectory: root,
  });
  if (!(await verifyLiveOutput(descriptor, customers))) {
    throw new DemoRunError(
      "The live Gemini run did not publish a verified live artifact collection.",
    );
  }
  const verificationEnvironment = { ...environment };
  delete verificationEnvironment.GEMINI_API_KEY;
  await runBoundedChild({
    args: [
      "run",
      "python",
      "scripts/verify_artifacts.py",
      descriptor.relativePath,
    ],
    canStartProcess,
    environment: verificationEnvironment,
    failureMessage: "The live Gemini artifacts failed deterministic verification.",
    spawnProcess,
    startFailureMessage: "The live artifact verifier could not be started.",
    timeoutMessage: "The live artifact verifier exceeded its time boundary.",
    timeoutMs: verificationTimeoutMs,
    workingDirectory: root,
  });
  try {
    await markLiveRunVerified(root, descriptor.collectionId);
  } catch {
    throw new DemoRunError(
      "The live Gemini run could not publish its verified artifact collection.",
    );
  }
  return { command: `uv ${descriptor.args.join(" ")}` };
}

const demoManager = createDemoRunManager({
  repositoryRoot,
  backend: "gemini",
  model: configuredGeminiModel(),
  describeRun: (customers, jobId) => describeLiveRun(customers, jobId),
  execute: (customers, descriptor) =>
    runLiveDemo(customers, descriptor, {
      canStartProcess: () => !dashboardShuttingDown,
    }),
});

export function startLiveRun(manager, customers, capability) {
  if (!capability.ready) {
    const error = new Error(
      capability.blockedReason || "The live Gemini run is not configured.",
    );
    error.statusCode = 503;
    throw error;
  }
  return manager.start(customers);
}

export function liveRunRequestError(body) {
  if (
    !isPlainObject(body) ||
    Object.keys(body).length !== 1 ||
    !Object.hasOwn(body, "customers")
  ) {
    return "The live run request may contain only customers.";
  }
  return demoCustomerCountError(body.customers);
}

async function serveFile(response, filePath, contentType) {
  const details = await stat(filePath);
  response.statusCode = 200;
  response.setHeader(
    "Content-Type",
    contentType || contentTypes[path.extname(filePath)] || "application/octet-stream",
  );
  response.setHeader("Content-Length", details.size);
  securityHeaders(response);
  createReadStream(filePath).pipe(response);
}

async function handleApi(request, response, url) {
  if (request.method === "GET" && url.pathname === "/api/workspace") {
    const [workspace, liveRun] = await Promise.all([
      loadWorkspace(repositoryRoot),
      liveRunCapability({ canStartProcess: () => !dashboardShuttingDown }),
    ]);
    sendJson(response, 200, { ...workspace, liveRun });
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/demo/status") {
    const requestedJob = url.searchParams.get("job");
    const afterValue = url.searchParams.get("after") ?? "0";
    const after = Number(afterValue);
    if (!Number.isInteger(after) || after < 0) {
      sendError(response, 400, "after must be a non-negative integer.");
      return;
    }
    let status = demoManager.status(requestedJob, after);
    if (!status) {
      sendError(response, 404, "Live run status not found.");
      return;
    }
    if (status.status === "running" && status.jobId) {
      await demoManager.refresh(status.jobId);
      status = demoManager.status(requestedJob, after);
    }
    sendJson(response, 200, status);
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/investigation") {
    const collection = url.searchParams.get("collection") || "";
    const household = url.searchParams.get("household") || "";
    const investigation = await loadInvestigation(
      repositoryRoot,
      collection,
      household,
    );
    if (!investigation) {
      sendError(response, 404, "Investigation artifact not found.");
      return;
    }
    sendJson(response, 200, investigation);
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/artifact") {
    const collection = url.searchParams.get("collection") || "";
    const household = url.searchParams.get("household") || "";
    const file = url.searchParams.get("file") || "";
    const artifactPath = await resolveArtifactFile(
      repositoryRoot,
      collection,
      household,
      file,
    );
    if (!artifactPath) {
      sendError(response, 404, "Artifact file not found.");
      return;
    }
    await serveFile(response, artifactPath);
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/demo") {
    if (dashboardShuttingDown) {
      sendError(response, 503, "The dashboard is shutting down.");
      return;
    }
    const headerError = mutationHeaderError(request.headers);
    if (headerError) {
      sendError(response, headerError.startsWith("Content-Type") ? 415 : 403, headerError);
      return;
    }
    const body = await readJsonBody(request);
    const customers = body?.customers;
    const requestError = liveRunRequestError(body);
    if (requestError) {
      sendError(response, 400, requestError);
      return;
    }
    const capability = await liveRunCapability({
      canStartProcess: () => !dashboardShuttingDown,
    });
    if (dashboardShuttingDown) {
      sendError(response, 503, "The dashboard is shutting down.");
      return;
    }
    sendJson(response, 202, startLiveRun(demoManager, customers, capability));
    return;
  }

  if (["GET", "POST"].includes(request.method || "")) {
    sendError(response, 404, "API route not found.");
  } else {
    sendError(response, 405, "Method not allowed.");
  }
}

async function handleRequest(request, response) {
  try {
    if (!hostHeaderAllowed(request.headers.host)) {
      sendError(response, 421, "The dashboard accepts localhost requests only.");
      return;
    }
    const url = new URL(request.url || "/", `http://${host}:${port}`);
    if (url.pathname.startsWith("/api/")) {
      await handleApi(request, response, url);
      return;
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      sendError(response, 405, "Method not allowed.");
      return;
    }
    const requested = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    const candidate = path.resolve(distRoot, requested);
    const withinDist =
      candidate === distRoot || candidate.startsWith(`${distRoot}${path.sep}`);
    if (withinDist) {
      try {
        await serveFile(response, candidate);
        return;
      } catch (error) {
        if (error?.code !== "ENOENT" && error?.code !== "EISDIR") throw error;
      }
    }
    try {
      await serveFile(response, path.join(distRoot, "index.html"));
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
      response.statusCode = 503;
      response.setHeader("Content-Type", "text/plain; charset=utf-8");
      securityHeaders(response);
      response.end(
        "WhyBack dashboard assets are not built. Run `npm run build` or use `npm run dev`.\n",
      );
    }
  } catch (error) {
    const statusCode = Number(error?.statusCode) || 500;
    const message =
      statusCode >= 500
        ? `Dashboard request failed: ${error instanceof Error ? error.message : "Unknown error"}`
        : String(error.message);
    if (statusCode >= 500) {
      process.stderr.write(`${message}\n`);
    }
    sendError(response, statusCode, message);
  }
}

export function createDashboardShutdown({
  server,
  beginShutdown = () => {},
  exitProcess = (code) => process.exit(code),
  stopProcesses = stopActiveLiveProcesses,
  retryDelayMs = 1_000,
}) {
  let shutdownPromise = null;
  return function shutdown() {
    if (shutdownPromise) return shutdownPromise;
    beginShutdown();
    shutdownPromise = (async () => {
      const serverClosed = new Promise((resolve) => {
        try {
          server.close(() => resolve(true));
        } catch (error) {
          resolve(error?.code === "ERR_SERVER_NOT_RUNNING");
        }
      });
      let warned = false;
      async function drainProcesses() {
        let processesStopped = false;
        while (!processesStopped) {
          try {
            processesStopped = await stopProcesses();
          } catch {
            processesStopped = false;
          }
          if (!processesStopped) {
            if (!warned) {
              process.stderr.write(
                "WhyBack is waiting for an active live process to stop.\n",
              );
              warned = true;
            }
            await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
          }
        }
        return true;
      }
      await drainProcesses();
      const listenerStopped = await serverClosed;
      const processesStopped = await drainProcesses();
      exitProcess(processesStopped && listenerStopped ? 0 : 1);
    })();
    return shutdownPromise;
  };
}

export function startServer() {
  dashboardShuttingDown = false;
  const server = createServer(handleRequest);
  const shutdown = createDashboardShutdown({
    server,
    beginShutdown: () => {
      dashboardShuttingDown = true;
    },
  });
  const onInterrupt = () => void shutdown();
  const onTerminate = () => void shutdown();
  process.on("SIGINT", onInterrupt);
  process.on("SIGTERM", onTerminate);
  server.listen(port, host, () => {
    process.stdout.write(
      `WhyBack dashboard bridge listening at http://${host}:${port}\n`,
    );
  });
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  startServer();
}
