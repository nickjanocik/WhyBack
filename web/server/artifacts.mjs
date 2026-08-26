/** Reads verified WhyBack artifacts and exposes only safe summaries to the dashboard. */

import { lstat, readFile, readdir } from "node:fs/promises";
import path from "node:path";

import { DEMO_CUSTOMER_LIMITS } from "./demo-limits.mjs";
import {
  discoverLiveRunCollections,
  liveRunCollectionDefinition,
  resolveVerifiedLiveRunDirectory,
} from "./live-runs.mjs";

const COLLECTIONS = [
  {
    id: "dashboard",
    relativePath: "artifacts/local/dashboard",
    title: "Generated runs",
  },
  {
    id: "demo",
    relativePath: "artifacts/demo",
    title: "Committed sample",
  },
  {
    id: "official",
    relativePath: "artifacts/official",
    title: "Official detector",
  },
  {
    id: "official-type-a",
    relativePath: "artifacts/official-type-a",
    title: "Official Type A",
  },
  {
    id: "live-gemini-synthetic-failure",
    relativePath: "artifacts/live-gemini-synthetic-failure",
    title: "Live boundary case",
    flat: true,
  },
];

const TRACE_DETAIL_KEYS = new Set([
  "allowed_tools",
  "arguments_valid",
  "attempt",
  "attempt_count",
  "attempt_number",
  "confidence_cap_applied",
  "counterevidence_ids",
  "decision_kind",
  "decision_summary",
  "decline_score",
  "demo_fault",
  "evidence_count",
  "evidence_id",
  "failure_type",
  "finish_available",
  "human_review_required",
  "input_tokens",
  "investigation_question",
  "latency_ms",
  "limitations",
  "message",
  "model",
  "metric",
  "next_best_action_id",
  "output_tokens",
  "provider_call_id",
  "prompt_version",
  "proposed_confidence",
  "referenced_evidence_count",
  "remaining_tool_budget",
  "remaining_turn_budget",
  "repair_attempted",
  "repair_requested",
  "resolved_confidence",
  "retryable",
  "rows_examined",
  "selected_tool",
  "source_tool",
  "source_tool_call_id",
  "status",
  "supporting_evidence_ids",
  "tool_call_id",
  "tool_name",
  "unavailable_tools",
]);

/** Distinguishes record-shaped JSON values from arrays and null. */
function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Bounds one trace detail to the primitive values that the UI may display. */
function safeTraceDetailValue(value) {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined;
  if (typeof value === "string") return value.slice(0, 1_000);
  if (!Array.isArray(value)) return undefined;
  return value
    .filter(
      (item) =>
        typeof item === "string" ||
        typeof item === "boolean" ||
        (typeof item === "number" && Number.isFinite(item)),
    )
    .slice(0, 20)
    .map((item) => (typeof item === "string" ? item.slice(0, 1_000) : item));
}

/** Reads a JSON file and requires its top-level value to be an object. */
async function readJson(filePath) {
  const value = JSON.parse(await readFile(filePath, "utf8"));
  if (!isPlainObject(value)) {
    throw new Error(`Expected an object in ${filePath}`);
  }
  return value;
}

/** Accepts only a real directory and rejects symlinks at the artifact boundary. */
async function isRealDirectory(directory) {
  try {
    const details = await lstat(directory);
    return details.isDirectory() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

/** Accepts only a real file and rejects missing paths and symlinks. */
async function isRealFile(filePath) {
  try {
    const details = await lstat(filePath);
    return details.isFile() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT" || error?.code === "ENOTDIR") return false;
    throw error;
  }
}

/** Reduces a full report to the fields needed by the household selection rail. */
function summarizeReport(report) {
  const decline = isPlainObject(report.decline) ? report.decline : {};
  const action = isPlainObject(report.action) ? report.action : null;
  const provenance = isPlainObject(report.provenance) ? report.provenance : {};
  return {
    householdId: String(report.household_id ?? "unknown"),
    runId: String(report.run_id ?? ""),
    runStatus: String(report.run_status ?? "failed"),
    declineScore: Number(decline.decline_score ?? 0),
    salesDrop: Number(decline.sales_drop ?? 0),
    tripDrop: Number(decline.trip_drop ?? 0),
    activeWeekDrop: Number(decline.active_week_drop ?? 0),
    baselineSales: Number(decline.baseline_retailer_sales_value ?? 0),
    recentSales: Number(decline.recent_retailer_sales_value ?? 0),
    actionId: action ? String(action.action_id ?? "") : null,
    confidence: action ? String(action.resolved_confidence ?? "") : null,
    evidenceCount: Array.isArray(report.evidence_ledger)
      ? report.evidence_ledger.length
      : 0,
    warningCount: Array.isArray(report.tool_warnings)
      ? report.tool_warnings.length
      : 0,
    generatedAt: String(provenance.generated_at ?? ""),
  };
}

/** Finds canonical customer directories in stable household-number order. */
async function reportDirectories(collectionPath) {
  const entries = await readdir(collectionPath, { withFileTypes: true });
  return entries
    .filter(
      (entry) =>
        entry.isDirectory() &&
        !entry.isSymbolicLink() &&
        /^customer_[A-Za-z0-9_-]+$/.test(entry.name),
    )
    .sort((left, right) => left.name.localeCompare(right.name, undefined, { numeric: true }));
}

/** Loads one fixed or verified live collection without exposing unsafe paths. */
async function loadCollection(repositoryRoot, definition) {
  const collectionPath = definition.liveRun
    ? await resolveVerifiedLiveRunDirectory(repositoryRoot, definition.id)
    : path.resolve(repositoryRoot, definition.relativePath);
  if (!collectionPath) return null;
  if (!(await isRealDirectory(collectionPath))) return null;

  let manifest = {};
  const manifestPath = path.join(collectionPath, "manifest.json");
  if (!definition.liveRun || (await isRealFile(manifestPath))) {
    try {
      manifest = await readJson(manifestPath);
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
  }

  const reportFiles = definition.flat
    ? [path.join(collectionPath, "report.json")]
    : (await reportDirectories(collectionPath)).map((entry) =>
        path.join(collectionPath, entry.name, "report.json"),
      );
  const reports = [];
  for (const reportFile of reportFiles) {
    if (definition.liveRun && !(await isRealFile(reportFile))) continue;
    try {
      const report = await readJson(reportFile);
      reports.push(summarizeReport(report));
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
  }

  if (reports.length === 0) return null;
  const selected = Array.isArray(manifest.selected_household_ids)
    ? manifest.selected_household_ids.map(String)
    : [];
  const order = new Map(selected.map((householdId, index) => [householdId, index]));
  reports.sort(
    (left, right) =>
      (order.get(left.householdId) ?? Number.MAX_SAFE_INTEGER) -
        (order.get(right.householdId) ?? Number.MAX_SAFE_INTEGER) ||
      right.declineScore - left.declineScore,
  );

  return {
    id: definition.id,
    title: definition.title,
    datasetKind: String(manifest.dataset_kind ?? "unknown"),
    executionMode: String(manifest.execution_mode ?? "artifact_replay"),
    backend: String(manifest.backend ?? "unknown"),
    modelExecution: String(manifest.model_execution ?? "unknown"),
    reportCount: reports.length,
    completedCount: Array.isArray(manifest.completed_household_ids)
      ? manifest.completed_household_ids.length
      : reports.filter((item) => item.runStatus === "completed").length,
    humanReviewRequired: manifest.human_review_required !== false,
    reports,
  };
}

/** Builds the dashboard workspace while isolating unreadable collections as warnings. */
export async function loadWorkspace(repositoryRoot) {
  let liveRunDefinitions = [];
  const collectionWarnings = [];
  try {
    liveRunDefinitions = await discoverLiveRunCollections(repositoryRoot);
  } catch {
    collectionWarnings.push("Live Gemini runs could not be discovered.");
  }
  const definitions = [...liveRunDefinitions, ...COLLECTIONS];
  // One malformed optional collection must not hide every valid reviewer artifact.
  const results = await Promise.allSettled(
    definitions.map((definition) => loadCollection(repositoryRoot, definition)),
  );
  const collections = results
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value)
    .filter(Boolean);
  collectionWarnings.push(
    ...results.flatMap((result, index) =>
      result.status === "rejected"
        ? [`${definitions[index].title} artifacts could not be read.`]
        : [],
    ),
  );
  return {
    schemaVersion: 1,
    productName: "WhyBack",
    demoCustomerLimits: DEMO_CUSTOMER_LIMITS,
    collectionWarnings,
    collections,
  };
}

/** Resolves only a fixed collection or a sealed live-run collection. */
export async function resolveCollection(repositoryRoot, collectionId) {
  const definition = COLLECTIONS.find((item) => item.id === collectionId);
  if (definition) return path.resolve(repositoryRoot, definition.relativePath);
  return resolveVerifiedLiveRunDirectory(repositoryRoot, collectionId);
}

/** Returns display and layout metadata for an allow-listed collection ID. */
function collectionDefinition(collectionId) {
  return (
    COLLECTIONS.find((item) => item.id === collectionId) ??
    liveRunCollectionDefinition(collectionId)
  );
}

/** Restricts household IDs to the safe filename alphabet used by artifacts. */
export function validateHouseholdId(householdId) {
  return /^[A-Za-z0-9_-]{1,64}$/.test(householdId);
}

/** Removes unapproved trace fields and replaces evidence ID arrays with counts. */
export function summarizeTraceDetails(details) {
  if (!isPlainObject(details)) return {};
  const summary = Object.fromEntries(
    Object.entries(details).flatMap(([key, value]) => {
      if (!TRACE_DETAIL_KEYS.has(key)) return [];
      const safeValue = safeTraceDetailValue(value);
      return safeValue === undefined ? [] : [[key, safeValue]];
    }),
  );
  for (const [sourceKey, countKey] of [
    ["supporting_evidence_ids", "supporting_evidence_count"],
    ["counterevidence_ids", "counterevidence_count"],
  ]) {
    if (Array.isArray(details[sourceKey])) {
      delete summary[sourceKey];
      summary[countKey] = details[sourceKey].filter(
        (item) => typeof item === "string",
      ).length;
    }
  }
  if (Array.isArray(details.evidence_ids)) {
    summary.evidence_count = details.evidence_ids.filter(
      (item) => typeof item === "string",
    ).length;
  }
  return summary;
}

/** Converts a snake-case audit record into the browser's sanitized trace contract. */
export function normalizeTraceEvent(event) {
  if (!isPlainObject(event)) return null;
  return {
    schemaVersion: Number(event.schema_version ?? 1),
    timestamp: String(event.timestamp ?? ""),
    event: String(event.event ?? "unknown"),
    runId: String(event.run_id ?? ""),
    householdId: String(event.household_id ?? ""),
    details: summarizeTraceDetails(event.details),
  };
}

/** Reads an append-only JSONL trace and drops records that cannot be normalized. */
async function readTrace(tracePath) {
  let raw;
  try {
    raw = await readFile(tracePath, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  return raw
    .split(/\r?\n/u)
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .map(normalizeTraceEvent)
    .filter(Boolean);
}

/** Loads one report and trace only when their collection and household agree. */
export async function loadInvestigation(repositoryRoot, collectionId, householdId) {
  if (!validateHouseholdId(householdId)) return null;
  const definition = collectionDefinition(collectionId);
  const collectionPath = await resolveCollection(repositoryRoot, collectionId);
  if (!definition || !collectionPath || !(await isRealDirectory(collectionPath))) {
    return null;
  }
  const customerDirectory = definition.flat
    ? collectionPath
    : path.join(collectionPath, `customer_${householdId}`);
  if (!(await isRealDirectory(customerDirectory))) return null;
  if (
    definition.liveRun &&
    (!(await isRealFile(path.join(customerDirectory, "report.json"))) ||
      !(await isRealFile(path.join(customerDirectory, "trace.jsonl"))))
  ) {
    return null;
  }
  try {
    const [report, trace] = await Promise.all([
      readJson(path.join(customerDirectory, "report.json")),
      readTrace(path.join(customerDirectory, "trace.jsonl")),
    ]);
    if (String(report.household_id ?? "") !== householdId) return null;
    return { report, trace };
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}

/** Resolves one allow-listed rendered artifact without permitting path traversal. */
export async function resolveArtifactFile(
  repositoryRoot,
  collectionId,
  householdId,
  fileName,
) {
  const allowedFiles = new Set(["report.html", "report.md", "trace.html"]);
  if (!allowedFiles.has(fileName) || !validateHouseholdId(householdId)) return null;
  const definition = collectionDefinition(collectionId);
  const collectionPath = await resolveCollection(repositoryRoot, collectionId);
  if (!definition || !collectionPath || !(await isRealDirectory(collectionPath))) {
    return null;
  }
  const customerPath = definition.flat
    ? collectionPath
    : path.join(collectionPath, `customer_${householdId}`);
  if (!(await isRealDirectory(customerPath))) return null;
  if (definition.flat) {
    try {
      const report = await readJson(path.join(customerPath, "report.json"));
      if (String(report.household_id ?? "") !== householdId) return null;
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      throw error;
    }
  }
  const filePath = path.join(customerPath, fileName);
  try {
    const details = await lstat(filePath);
    return details.isFile() && !details.isSymbolicLink() ? filePath : null;
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}
