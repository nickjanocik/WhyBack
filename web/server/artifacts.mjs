import { lstat, readFile, readdir } from "node:fs/promises";
import path from "node:path";

const COLLECTIONS = [
  {
    id: "dashboard",
    relativePath: "artifacts/local/dashboard",
    title: "Dashboard run",
    description: "Fresh synthetic investigations generated from this interface.",
  },
  {
    id: "demo",
    relativePath: "artifacts/demo",
    title: "Guided demo",
    description: "Credential-free scripted investigations over auditable fixture data.",
  },
  {
    id: "official",
    relativePath: "artifacts/official",
    title: "Official detector",
    description: "Pinned Complete Journey detector artifacts and available reports.",
  },
  {
    id: "official-type-a",
    relativePath: "artifacts/official-type-a",
    title: "Official Type A",
    description: "A partial-evidence control using the official prepared dataset.",
  },
  {
    id: "live-gemini-synthetic-failure",
    relativePath: "artifacts/live-gemini-synthetic-failure",
    title: "Live boundary case",
    description: "A preserved provider-boundary failure with valid partial evidence.",
    flat: true,
  },
];

const TRACE_DETAIL_KEYS = new Set([
  "allowed_tools",
  "attempt",
  "attempt_count",
  "attempt_number",
  "confidence_cap_applied",
  "counterevidence_ids",
  "decision_kind",
  "decision_summary",
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
  "next_best_action_id",
  "output_tokens",
  "provider_call_id",
  "referenced_evidence_count",
  "remaining_tool_budget",
  "remaining_turn_budget",
  "repair_attempted",
  "repair_requested",
  "resolved_confidence",
  "retryable",
  "selected_tool",
  "source_tool",
  "source_tool_call_id",
  "status",
  "supporting_evidence_ids",
  "tool_call_id",
  "tool_name",
  "unavailable_tools",
]);

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function readJson(filePath) {
  const value = JSON.parse(await readFile(filePath, "utf8"));
  if (!isPlainObject(value)) {
    throw new Error(`Expected an object in ${filePath}`);
  }
  return value;
}

async function isRealDirectory(directory) {
  try {
    const details = await lstat(directory);
    return details.isDirectory() && !details.isSymbolicLink();
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

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

async function loadCollection(repositoryRoot, definition) {
  const collectionPath = path.resolve(repositoryRoot, definition.relativePath);
  if (!(await isRealDirectory(collectionPath))) return null;

  let manifest = {};
  try {
    manifest = await readJson(path.join(collectionPath, "manifest.json"));
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  const reportFiles = definition.flat
    ? [path.join(collectionPath, "report.json")]
    : (await reportDirectories(collectionPath)).map((entry) =>
        path.join(collectionPath, entry.name, "report.json"),
      );
  const reports = [];
  for (const reportFile of reportFiles) {
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
    description: definition.description,
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

export async function loadWorkspace(repositoryRoot) {
  const results = await Promise.allSettled(
    COLLECTIONS.map((definition) => loadCollection(repositoryRoot, definition)),
  );
  const collections = results
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value)
    .filter(Boolean);
  const collectionWarnings = results.flatMap((result, index) =>
    result.status === "rejected"
      ? [`${COLLECTIONS[index].title} artifacts could not be read.`]
      : [],
  );
  return {
    schemaVersion: 1,
    productName: "WhyBack",
    tagline: "Find the why. Choose the way back.",
    investigatorName: "WhyBack Investigator",
    canRunDemo: true,
    demoCommand:
      "uv run whyback demo --customers <1-5> --backend scripted --output-dir artifacts/local/dashboard",
    collectionWarnings,
    collections,
  };
}

export function resolveCollection(repositoryRoot, collectionId) {
  const definition = COLLECTIONS.find((item) => item.id === collectionId);
  if (!definition) return null;
  return path.resolve(repositoryRoot, definition.relativePath);
}

function collectionDefinition(collectionId) {
  return COLLECTIONS.find((item) => item.id === collectionId) ?? null;
}

export function validateHouseholdId(householdId) {
  return /^[A-Za-z0-9_-]{1,64}$/.test(householdId);
}

function summarizeTraceDetails(details) {
  if (!isPlainObject(details)) return {};
  return Object.fromEntries(
    Object.entries(details).filter(([key]) => TRACE_DETAIL_KEYS.has(key)),
  );
}

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
    .filter(isPlainObject)
    .map((event) => ({
      schemaVersion: Number(event.schema_version ?? 1),
      timestamp: String(event.timestamp ?? ""),
      event: String(event.event ?? "unknown"),
      runId: String(event.run_id ?? ""),
      householdId: String(event.household_id ?? ""),
      details: summarizeTraceDetails(event.details),
    }));
}

export async function loadInvestigation(repositoryRoot, collectionId, householdId) {
  if (!validateHouseholdId(householdId)) return null;
  const definition = collectionDefinition(collectionId);
  const collectionPath = resolveCollection(repositoryRoot, collectionId);
  if (!definition || !collectionPath || !(await isRealDirectory(collectionPath))) {
    return null;
  }
  const customerDirectory = definition.flat
    ? collectionPath
    : path.join(collectionPath, `customer_${householdId}`);
  if (!(await isRealDirectory(customerDirectory))) return null;
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

export async function resolveArtifactFile(
  repositoryRoot,
  collectionId,
  householdId,
  fileName,
) {
  const allowedFiles = new Set(["report.html", "report.md", "trace.html"]);
  if (!allowedFiles.has(fileName) || !validateHouseholdId(householdId)) return null;
  const definition = collectionDefinition(collectionId);
  const collectionPath = resolveCollection(repositoryRoot, collectionId);
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
