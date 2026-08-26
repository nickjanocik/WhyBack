import { spawn } from "node:child_process";
import { Buffer } from "node:buffer";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
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

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(webRoot, "..");
const distRoot = path.join(webRoot, "dist");
const host = "127.0.0.1";
const parsedPort = Number(process.env.WHYBACK_DASHBOARD_PORT || 4173);
const port = Number.isInteger(parsedPort) && parsedPort > 0 ? parsedPort : 4173;
const MAX_BODY_BYTES = 4_096;
const DEMO_TIMEOUT_MS = 120_000;

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

export function runScriptedDemo(customers) {
  return new Promise((resolve, reject) => {
    const args = [
      "run",
      "whyback",
      "demo",
      "--customers",
      String(customers),
      "--backend",
      "scripted",
      "--output-dir",
      "artifacts/local/dashboard",
    ];
    const child = spawn("uv", args, {
      cwd: repositoryRoot,
      env: process.env,
      shell: false,
      stdio: "ignore",
    });
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 5_000).unref();
    }, DEMO_TIMEOUT_MS);
    timer.unref();
    child.once("error", () => {
      clearTimeout(timer);
      reject(new DemoRunError("The scripted WhyBack process could not be started."));
    });
    child.once("close", (code) => {
      clearTimeout(timer);
      if (timedOut) {
        reject(new DemoRunError("The scripted run exceeded its 120-second boundary."));
      } else if (code !== 0) {
        reject(new DemoRunError(`The scripted WhyBack run exited with status ${code}.`));
      } else {
        resolve({
          command: `uv ${args.join(" ")}`,
        });
      }
    });
  });
}

const demoManager = createDemoRunManager({
  repositoryRoot,
  execute: runScriptedDemo,
});

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
    sendJson(response, 200, await loadWorkspace(repositoryRoot));
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
    const headerError = mutationHeaderError(request.headers);
    if (headerError) {
      sendError(response, headerError.startsWith("Content-Type") ? 415 : 403, headerError);
      return;
    }
    const body = await readJsonBody(request);
    const customers = body?.customers;
    const customerCountError = demoCustomerCountError(customers);
    if (customerCountError) {
      sendError(response, 400, customerCountError);
      return;
    }
    sendJson(response, 202, demoManager.start(customers));
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

export function startServer() {
  const server = createServer(handleRequest);
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
