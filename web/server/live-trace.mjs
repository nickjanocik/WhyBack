import { randomUUID } from "node:crypto";
import { Buffer } from "node:buffer";
import { lstat, open, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { clearInterval, setInterval } from "node:timers";
import { TextDecoder } from "node:util";

import { normalizeTraceEvent } from "./artifacts.mjs";
import { MAX_LIVE_TRACE_EVENTS } from "./demo-limits.mjs";
import { resolveOwnedLiveRunDirectory } from "./live-runs.mjs";

const STAGING_NAME = /^\.dashboard\.staging-[A-Za-z0-9._-]+$/u;
const CUSTOMER_NAME = /^customer_([A-Za-z0-9_-]+)$/u;
const OWNERSHIP_MARKER = ".whyback-owned-artifact-root.json";
const OWNERSHIP_DOCUMENT = {
  schema_version: 1,
  product: "WhyBack",
  scope: "replaceable_generated_artifact_tree",
};
const MAX_JOB_HISTORY = 8;

async function isRealDirectory(directory) {
  try {
    const details = await lstat(directory);
    return details.isDirectory() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function isRealFile(filePath) {
  try {
    const details = await lstat(filePath);
    return details.isFile() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function isOwnedArtifactDirectory(directory) {
  if (!(await isRealDirectory(directory))) return false;
  const marker = path.join(directory, OWNERSHIP_MARKER);
  if (!(await isRealFile(marker))) return false;
  try {
    const document = JSON.parse(await readFile(marker, "utf8"));
    return (
      document?.schema_version === OWNERSHIP_DOCUMENT.schema_version &&
      document?.product === OWNERSHIP_DOCUMENT.product &&
      document?.scope === OWNERSHIP_DOCUMENT.scope &&
      Object.keys(document).length === Object.keys(OWNERSHIP_DOCUMENT).length
    );
  } catch (error) {
    if (error?.code === "ENOENT" || error instanceof SyntaxError) return false;
    throw error;
  }
}

async function localStagingEntries(repositoryRoot) {
  const localRoot = path.join(repositoryRoot, "artifacts", "local");
  if (!(await isRealDirectory(localRoot))) return [];
  try {
    return await readdir(localRoot, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}

export async function stagingDirectoryNames(repositoryRoot) {
  const entries = await localStagingEntries(repositoryRoot);
  return new Set(
    entries
      .filter(
        (entry) =>
          entry.isDirectory() &&
          !entry.isSymbolicLink() &&
          STAGING_NAME.test(entry.name),
      )
      .map((entry) => entry.name),
  );
}

async function newestStagingDirectory(
  repositoryRoot,
  startedAtMs,
  excludedStagingNames,
) {
  const localRoot = path.join(repositoryRoot, "artifacts", "local");
  const entries = await localStagingEntries(repositoryRoot);
  const candidates = [];
  for (const entry of entries) {
    if (
      !entry.isDirectory() ||
      entry.isSymbolicLink() ||
      !STAGING_NAME.test(entry.name) ||
      excludedStagingNames.has(entry.name)
    ) {
      continue;
    }
    const directory = path.join(localRoot, entry.name);
    let details;
    try {
      details = await lstat(directory);
    } catch (error) {
      if (error?.code === "ENOENT") continue;
      throw error;
    }
    if (!(await isOwnedArtifactDirectory(directory))) continue;
    const createdAt = Math.max(details.birthtimeMs || 0, details.ctimeMs || 0);
    if (createdAt >= startedAtMs - 2_000) {
      candidates.push({ directory, createdAt });
    }
  }
  candidates.sort((left, right) => right.createdAt - left.createdAt);
  return candidates[0]?.directory ?? null;
}

async function customerTraceFiles(root) {
  if (!(await isRealDirectory(root))) return [];
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  return entries
    .filter(
      (entry) =>
        entry.isDirectory() &&
        !entry.isSymbolicLink() &&
        CUSTOMER_NAME.test(entry.name),
    )
    .sort((left, right) =>
      left.name.localeCompare(right.name, undefined, { numeric: true }),
    )
    .map((entry) => ({
      filePath: path.join(root, entry.name, "trace.jsonl"),
      source: entry.name,
      sourceLabel: `Household ${entry.name.slice("customer_".length)}`,
    }));
}

export function createLiveTraceReader(
  repositoryRoot,
  startedAtMs,
  { excludedStagingNames = new Set(), runDirectory = null } = {},
) {
  const files = new Map();
  let activeStaging = null;
  const excludedNames = new Set(excludedStagingNames);
  const explicitRoot = runDirectory ? path.resolve(runDirectory) : null;

  async function traceRoot(includePublished) {
    if (explicitRoot) {
      const owned = await resolveOwnedLiveRunDirectory(
        repositoryRoot,
        path.basename(explicitRoot),
      );
      return owned === explicitRoot ? owned : null;
    }
    if (includePublished) {
      const published = path.join(
        repositoryRoot,
        "artifacts",
        "local",
        "dashboard",
      );
      return (await isOwnedArtifactDirectory(published)) ? published : null;
    }
    if (activeStaging && (await isRealDirectory(activeStaging))) {
      return activeStaging;
    }
    activeStaging = await newestStagingDirectory(
      repositoryRoot,
      startedAtMs,
      excludedNames,
    );
    return activeStaging;
  }

  async function previewFileIncrement(file) {
    if (!(await isRealFile(file.filePath))) {
      return { events: [], commit() {} };
    }
    const previous = files.get(file.filePath) ?? { lineNumber: 0, offset: 0 };
    let handle;
    try {
      handle = await open(file.filePath, "r");
    } catch (error) {
      if (error?.code === "ENOENT") return { events: [], commit() {} };
      throw error;
    }
    try {
      const details = await handle.stat();
      const baseOffset = details.size < previous.offset ? 0 : previous.offset;
      const baseLineNumber = details.size < previous.offset
        ? 0
        : previous.lineNumber;
      const byteCount = details.size - baseOffset;
      if (byteCount <= 0) {
        return {
          events: [],
          commit() {
            files.set(file.filePath, {
              lineNumber: baseLineNumber,
              offset: baseOffset,
            });
          },
        };
      }
      const buffer = Buffer.allocUnsafe(byteCount);
      const { bytesRead } = await handle.read(buffer, 0, byteCount, baseOffset);
      const appended = buffer.subarray(0, bytesRead);
      const finalNewline = appended.lastIndexOf(0x0a);
      if (finalNewline < 0) return { events: [], commit() {} };
      let decoded;
      try {
        decoded = new TextDecoder("utf-8", { fatal: true }).decode(
          appended.subarray(0, finalNewline + 1),
        );
      } catch (error) {
        throw new Error(`Live trace ${file.source} is not valid UTF-8.`, {
          cause: error,
        });
      }
      const lines = decoded.split("\n");
      lines.pop();
      const events = [];
      let nextLineNumber = baseLineNumber;
      for (const rawLine of lines) {
        const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
        nextLineNumber += 1;
        if (!line) {
          throw new Error(
            `Live trace ${file.source} contains a blank record at line ${nextLineNumber}.`,
          );
        }
        let parsed;
        try {
          parsed = JSON.parse(line);
        } catch (error) {
          throw new Error(
            `Live trace ${file.source} is invalid at line ${nextLineNumber}: ${error.message}`,
            { cause: error },
          );
        }
        const event = normalizeTraceEvent(parsed);
        if (!event) {
          throw new Error(
            `Live trace ${file.source} contains a non-object record at line ${nextLineNumber}.`,
          );
        }
        events.push({
          ...event,
          id: `${file.source}:${nextLineNumber}`,
          source: file.source,
          sourceLabel: file.sourceLabel,
        });
      }
      return {
        events,
        commit() {
          files.set(file.filePath, {
            lineNumber: nextLineNumber,
            offset: baseOffset + finalNewline + 1,
          });
        },
      };
    } finally {
      await handle.close();
    }
  }

  return {
    async readNew({ includePublished = false } = {}) {
      const root = await traceRoot(includePublished);
      if (!root) return [];
      const traceFiles = await customerTraceFiles(root);
      const previews = await Promise.all(traceFiles.map(previewFileIncrement));
      previews.forEach((preview) => preview.commit());
      return previews.flatMap((preview) => preview.events).sort((left, right) => {
        const timeOrder = left.timestamp.localeCompare(right.timestamp);
        return timeOrder || left.id.localeCompare(right.id, undefined, { numeric: true });
      });
    },
  };
}

export class DemoRunError extends Error {
  constructor(message) {
    super(message);
    this.name = "DemoRunError";
  }
}

function publicRunError(error) {
  return error instanceof DemoRunError
    ? error.message.slice(0, 1_000)
    : "The live Gemini run failed before completion.";
}

function traceWarningMessage() {
  return "Some live audit events could not be read. The generated report remains authoritative.";
}

function idleStatus(eventCapacity, backend, model) {
  return {
    jobId: null,
    status: "idle",
    customers: null,
    command: null,
    startedAt: null,
    completedAt: null,
    cursor: 0,
    eventCount: 0,
    eventCapacity,
    droppedEventCount: 0,
    events: [],
    error: null,
    traceWarning: null,
    collectionId: null,
    backend,
    model,
  };
}

export function createDemoRunManager({
  repositoryRoot,
  execute,
  describeRun = null,
  backend = "gemini",
  model = "configured Gemini model",
  intervalMs = 250,
  maxEvents = MAX_LIVE_TRACE_EVENTS,
  now = () => Date.now(),
}) {
  const jobs = new Map();
  let latestJobId = null;
  let runningJobId = null;
  let timer = null;
  let collectionChain = Promise.resolve();

  function clearTimer(jobId = null) {
    if (jobId && runningJobId !== jobId) return;
    if (timer) clearInterval(timer);
    timer = null;
  }

  function status(jobId = null, after = 0) {
    const target = jobId
      ? jobs.get(jobId)
      : latestJobId
        ? jobs.get(latestJobId)
        : null;
    if (!target) return jobId ? null : idleStatus(maxEvents, backend, model);
    return {
      jobId: target.jobId,
      status: target.status,
      customers: target.customers,
      command: target.command,
      startedAt: target.startedAt,
      completedAt: target.completedAt,
      cursor: target.cursor,
      eventCount: target.cursor,
      eventCapacity: maxEvents,
      droppedEventCount: target.droppedEventCount,
      events: target.events.filter((event) => event.cursor > after),
      error: target.error,
      traceWarning: target.traceWarning,
      collectionId: target.collectionId,
      backend: target.backend,
      model: target.model,
    };
  }

  function collect(jobId, includePublished) {
    const target = jobs.get(jobId);
    if (!target?.reader) return Promise.resolve(true);
    collectionChain = collectionChain.then(async () => {
      try {
        const events = await target.reader.readNew({ includePublished });
        if (jobs.get(jobId) !== target) return true;
        for (const event of events) {
          if (target.eventIds.has(event.id)) continue;
          target.eventIds.add(event.id);
          target.cursor += 1;
          target.events.push({ ...event, cursor: target.cursor });
        }
        if (target.events.length > maxEvents) {
          const removed = target.events.splice(
            0,
            target.events.length - maxEvents,
          );
          target.droppedEventCount += removed.length;
        }
        return true;
      } catch {
        if (jobs.get(jobId) === target) {
          target.traceWarning = traceWarningMessage();
        }
        return false;
      }
    });
    return collectionChain;
  }

  function pruneHistory() {
    if (jobs.size <= MAX_JOB_HISTORY) return;
    for (const [jobId, target] of jobs) {
      if (jobs.size <= MAX_JOB_HISTORY) break;
      if (jobId !== runningJobId && target.status !== "running") {
        jobs.delete(jobId);
      }
    }
  }

  function start(customers) {
    if (runningJobId && jobs.get(runningJobId)?.status === "running") {
      const error = new Error("A live Gemini run is already active.");
      error.statusCode = 409;
      throw error;
    }
    clearTimer();
    const jobId = randomUUID();
    const startedAtMs = now();
    const descriptor = describeRun
      ? describeRun(customers, jobId)
      : {
          backend,
          collectionId: "dashboard",
          command: `uv run whyback demo --customers ${customers} --backend gemini --output-dir artifacts/local/dashboard`,
          model,
          runDirectory: null,
        };
    const job = {
      jobId,
      status: "running",
      customers,
      command: descriptor.command,
      startedAt: new Date(startedAtMs).toISOString(),
      completedAt: null,
      cursor: 0,
      events: [],
      eventIds: new Set(),
      droppedEventCount: 0,
      error: null,
      traceWarning: null,
      collectionId: descriptor.collectionId ?? null,
      backend: descriptor.backend ?? backend,
      model: descriptor.model ?? model,
      reader: null,
    };
    jobs.set(jobId, job);
    latestJobId = jobId;
    runningJobId = jobId;
    pruneHistory();
    timer = setInterval(() => {
      void collect(jobId, false);
    }, intervalMs);
    timer.unref?.();

    void (async () => {
      try {
        const excludedStagingNames = descriptor.runDirectory
          ? new Set()
          : await stagingDirectoryNames(repositoryRoot);
        job.reader = createLiveTraceReader(repositoryRoot, startedAtMs, {
          excludedStagingNames,
          runDirectory: descriptor.runDirectory ?? null,
        });
        await execute(customers, descriptor);
        const finalCollectionSucceeded = await collect(jobId, true);
        if (finalCollectionSucceeded) job.traceWarning = null;
        job.status = "completed";
        job.completedAt = new Date(now()).toISOString();
        job.collectionId = descriptor.collectionId ?? null;
      } catch (error) {
        await collect(jobId, false);
        job.status = "failed";
        job.completedAt = new Date(now()).toISOString();
        job.error = publicRunError(error);
      } finally {
        if (runningJobId === jobId) {
          clearTimer(jobId);
          runningJobId = null;
        }
        pruneHistory();
      }
    })();

    return status(jobId, 0);
  }

  return {
    get running() {
      return Boolean(
        runningJobId && jobs.get(runningJobId)?.status === "running",
      );
    },
    start,
    status,
    async refresh(jobId) {
      const target = jobs.get(jobId);
      if (target?.status === "running") {
        await collect(jobId, false);
      }
      return status(jobId, 0);
    },
    dispose: clearTimer,
  };
}
