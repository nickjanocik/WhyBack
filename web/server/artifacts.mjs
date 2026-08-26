/** Reads verified WhyBack artifacts and exposes only safe summaries to the dashboard. */

import { lstat, readFile, readdir } from "node:fs/promises";
import path from "node:path";

import { DEMO_CUSTOMER_LIMITS } from "./demo-limits.mjs";
import {
  discoverLiveRunCollections,
  liveRunCollectionDefinition,
  resolveVerifiedLiveRunDirectory,
} from "./live-runs.mjs";

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
  "repair_available",
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

/** Returns a finite number or a deliberate null for unavailable legacy values. */
function finiteOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/** Bounds public strings while preserving explicit missing-data text. */
function safeString(value, fallback = "") {
  return String(value ?? fallback).slice(0, 2_000);
}

/** Projects one mix list to its documented aggregate-only fields. */
function sanitizeMix(value) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isPlainObject(item)) return [];
    const count = finiteOrNull(item.count);
    const share = finiteOrNull(item.share);
    if (count === null || share === null) return [];
    return [{
      key: safeString(item.key, "unknown"),
      label: safeString(item.label, "Unknown"),
      count,
      share,
    }];
  });
}

/** Projects distributions without permitting hidden identifiers or extra fields. */
function sanitizeMetric(metric) {
  if (!isPlainObject(metric)) return null;
  return {
    metric: safeString(metric.metric),
    unit: safeString(metric.unit),
    count: finiteOrNull(metric.count) ?? 0,
    mean: finiteOrNull(metric.mean),
    minimum: finiteOrNull(metric.minimum),
    q25: finiteOrNull(metric.q25),
    median: finiteOrNull(metric.median),
    q75: finiteOrNull(metric.q75),
    maximum: finiteOrNull(metric.maximum),
    deciles: Array.isArray(metric.deciles)
      ? metric.deciles.flatMap((item) =>
          isPlainObject(item) && finiteOrNull(item.probability) !== null && finiteOrNull(item.value) !== null
            ? [{ probability: Number(item.probability), value: Number(item.value) }]
            : [],
        )
      : [],
    histogram: Array.isArray(metric.histogram)
      ? metric.histogram.flatMap((item) =>
          isPlainObject(item) &&
          finiteOrNull(item.lower) !== null &&
          finiteOrNull(item.upper) !== null &&
          finiteOrNull(item.count) !== null &&
          finiteOrNull(item.share) !== null
            ? [{
                lower: Number(item.lower),
                upper: Number(item.upper),
                count: Number(item.count),
                share: Number(item.share),
              }]
            : [],
        )
      : [],
  };
}

/** Projects the versioned population file to the browser's strict safe contract. */
export function sanitizePopulationSummary(raw) {
  if (!isPlainObject(raw)) throw new Error("Population summary must be an object.");
  const executive = isPlainObject(raw.executive) ? raw.executive : {};
  const windows = isPlainObject(raw.analysis_windows) ? raw.analysis_windows : {};
  const policy = isPlainObject(raw.detector_policy) ? raw.detector_policy : {};
  const provenance = isPlainObject(raw.provenance) ? raw.provenance : {};
  return {
    schema_version: Number(raw.schema_version) === 1 ? 1 : 1,
    availability: ["full", "partial", "unavailable"].includes(raw.availability)
      ? raw.availability
      : "unavailable",
    missing_data_reasons: Array.isArray(raw.missing_data_reasons)
      ? raw.missing_data_reasons.map((item) => safeString(item)).slice(0, 20)
      : [],
    cohort_definitions: Object.fromEntries(
      ["eligible", "flagged", "investigated"].map((key) => [
        key,
        safeString(isPlainObject(raw.cohort_definitions) ? raw.cohort_definitions[key] : ""),
      ]),
    ),
    analysis_windows: {
      baseline_start_week: finiteOrNull(windows.baseline_start_week),
      baseline_end_week: finiteOrNull(windows.baseline_end_week),
      recent_start_week: finiteOrNull(windows.recent_start_week),
      recent_end_week: finiteOrNull(windows.recent_end_week),
    },
    detector_policy: {
      minimum_baseline_active_weeks: finiteOrNull(policy.minimum_baseline_active_weeks),
      minimum_baseline_distinct_baskets: finiteOrNull(policy.minimum_baseline_distinct_baskets),
      minimum_baseline_retailer_sales_value: finiteOrNull(
        policy.minimum_baseline_retailer_sales_value,
      ),
      decline_threshold: finiteOrNull(policy.decline_threshold),
      sensitivity_thresholds: Array.isArray(policy.sensitivity_thresholds)
        ? policy.sensitivity_thresholds.flatMap((item) =>
            finiteOrNull(item) === null ? [] : [Number(item)],
          )
        : [],
    },
    threshold_sensitivity: Array.isArray(raw.threshold_sensitivity)
      ? raw.threshold_sensitivity.flatMap((item) =>
          isPlainObject(item)
            ? [{
                threshold: finiteOrNull(item.threshold),
                eligible_households: finiteOrNull(item.eligible_households),
                flagged_households: finiteOrNull(item.flagged_households),
                flagged_share: finiteOrNull(item.flagged_share),
              }]
            : [],
        )
      : [],
    data_quality_warnings: Array.isArray(raw.data_quality_warnings)
      ? raw.data_quality_warnings.map((item) => safeString(item)).slice(0, 50)
      : [],
    cohorts: Array.isArray(raw.cohorts)
      ? raw.cohorts.flatMap((cohort) => {
          if (!isPlainObject(cohort)) return [];
          return [{
            cohort: safeString(cohort.cohort),
            definition: safeString(cohort.definition),
            household_count: finiteOrNull(cohort.household_count),
            aggregate_baseline_value: finiteOrNull(cohort.aggregate_baseline_value),
            aggregate_recent_value: finiteOrNull(cohort.aggregate_recent_value),
            gross_recorded_decrease: finiteOrNull(cohort.gross_recorded_decrease),
            metrics: Array.isArray(cohort.metrics)
              ? cohort.metrics.map(sanitizeMetric).filter(Boolean)
              : [],
          }];
        })
      : [],
    density_grid: isPlainObject(raw.density_grid)
      ? {
          x_metric: safeString(raw.density_grid.x_metric),
          y_metric: safeString(raw.density_grid.y_metric),
          x_scale: safeString(raw.density_grid.x_scale),
          x_edges: Array.isArray(raw.density_grid.x_edges)
            ? raw.density_grid.x_edges.flatMap((item) => finiteOrNull(item) === null ? [] : [Number(item)])
            : [],
          y_edges: Array.isArray(raw.density_grid.y_edges)
            ? raw.density_grid.y_edges.flatMap((item) => finiteOrNull(item) === null ? [] : [Number(item)])
            : [],
          cells: Array.isArray(raw.density_grid.cells)
            ? raw.density_grid.cells.flatMap((cell) =>
                isPlainObject(cell)
                  ? [{
                      x_lower: finiteOrNull(cell.x_lower),
                      x_upper: finiteOrNull(cell.x_upper),
                      y_lower: finiteOrNull(cell.y_lower),
                      y_upper: finiteOrNull(cell.y_upper),
                      eligible_count: finiteOrNull(cell.eligible_count) ?? 0,
                      flagged_count: finiteOrNull(cell.flagged_count) ?? 0,
                      investigated_count: finiteOrNull(cell.investigated_count) ?? 0,
                    }]
                  : [],
              )
            : [],
        }
      : null,
    investigated_households: Array.isArray(raw.investigated_households)
      ? raw.investigated_households.flatMap((row) => {
          if (!isPlainObject(row)) return [];
          const factor = isPlainObject(row.identified_factor) ? row.identified_factor : {};
          return [{
            household_id: safeString(row.household_id),
            rank: finiteOrNull(row.rank) ?? 0,
            status: safeString(row.status, "failed"),
            context_classification: safeString(row.context_classification, "insufficient_context"),
            decline_score: finiteOrNull(row.decline_score),
            sales_drop: finiteOrNull(row.sales_drop),
            trip_drop: finiteOrNull(row.trip_drop),
            active_week_drop: finiteOrNull(row.active_week_drop),
            baseline_retailer_sales_value: finiteOrNull(row.baseline_retailer_sales_value),
            recent_retailer_sales_value: finiteOrNull(row.recent_retailer_sales_value),
            recorded_value_change: finiteOrNull(row.recorded_value_change),
            population_gap: finiteOrNull(row.population_gap),
            peer_gap: finiteOrNull(row.peer_gap),
            identified_factor: {
              factor_type: safeString(factor.factor_type, "insufficient_evidence"),
              label: safeString(factor.label, "Insufficient evidence"),
              detail: safeString(factor.detail, "No differentiating factor was available."),
            },
            action_id: row.action_id === null ? null : safeString(row.action_id),
            action_label: safeString(row.action_label, "No recommendation published"),
            confidence: safeString(row.confidence, "unavailable"),
            warnings: Array.isArray(row.warnings)
              ? row.warnings.map((item) => safeString(item)).slice(0, 50)
              : [],
          }];
        })
      : [],
    executive: {
      eligible_count: finiteOrNull(executive.eligible_count),
      flagged_count: finiteOrNull(executive.flagged_count),
      flagged_share: finiteOrNull(executive.flagged_share),
      selected_count: finiteOrNull(executive.selected_count),
      investigated_count: finiteOrNull(executive.investigated_count),
      completed_count: finiteOrNull(executive.completed_count),
      insufficient_count: finiteOrNull(executive.insufficient_count),
      failed_count: finiteOrNull(executive.failed_count),
      aggregate_baseline_value: finiteOrNull(executive.aggregate_baseline_value),
      aggregate_recent_value: finiteOrNull(executive.aggregate_recent_value),
      recorded_value_change: finiteOrNull(executive.recorded_value_change),
      gross_recorded_decrease: finiteOrNull(executive.gross_recorded_decrease),
      verified_action_rate: finiteOrNull(executive.verified_action_rate),
      action_mix: sanitizeMix(executive.action_mix),
      factor_mix: sanitizeMix(executive.factor_mix),
      context_mix: sanitizeMix(executive.context_mix),
    },
    provenance: {
      dataset_kind: safeString(provenance.dataset_kind, "unknown"),
      dataset_source_repository: safeString(provenance.dataset_source_repository, "unknown"),
      dataset_source_commit: safeString(provenance.dataset_source_commit, "unknown"),
      backend: safeString(provenance.backend, "unknown"),
      source_manifest: provenance.source_manifest === null
        ? null
        : safeString(provenance.source_manifest),
      generated_at: safeString(provenance.generated_at),
    },
  };
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

/** Loads one sealed live CLI collection without exposing unsafe paths. */
async function loadCollection(repositoryRoot, definition) {
  const collectionPath = await resolveVerifiedLiveRunDirectory(
    repositoryRoot,
    definition.id,
  );
  if (!collectionPath) return null;
  if (!(await isRealDirectory(collectionPath))) return null;

  const manifestPath = path.join(collectionPath, "manifest.json");
  if (!(await isRealFile(manifestPath))) return null;
  const manifest = await readJson(manifestPath);

  /** Maps canonical customer directories to their required report source. */
  const reportFiles = (await reportDirectories(collectionPath)).map((entry) =>
    path.join(collectionPath, entry.name, "report.json"),
  );
  const reports = [];
  for (const reportFile of reportFiles) {
    if (!(await isRealFile(reportFile))) continue;
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
    populationAvailability:
      typeof manifest.population_summary === "string" &&
      Number(manifest.population_schema_version) === 1
        ? "full"
        : (await isRealFile(path.join(collectionPath, "sensitivity.csv")))
          ? "partial"
          : "unavailable",
    reports,
  };
}

/** Builds the operational workspace from verified CLI-produced runs only. */
export async function loadWorkspace(repositoryRoot) {
  let definitions = [];
  const collectionWarnings = [];
  try {
    definitions = await discoverLiveRunCollections(repositoryRoot);
  } catch {
    collectionWarnings.push("Verified CLI runs could not be discovered.");
  }
  // One malformed preserved run must not hide every other valid reviewer artifact.
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

/** Resolves only a sealed live CLI collection. */
export async function resolveCollection(repositoryRoot, collectionId) {
  return resolveVerifiedLiveRunDirectory(repositoryRoot, collectionId);
}

/** Returns display metadata only for a canonical live-run collection ID. */
function collectionDefinition(collectionId) {
  return liveRunCollectionDefinition(collectionId);
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
  const customerDirectory = path.join(
    collectionPath,
    `customer_${householdId}`,
  );
  if (!(await isRealDirectory(customerDirectory))) return null;
  if (
    !(await isRealFile(path.join(customerDirectory, "report.json"))) ||
    !(await isRealFile(path.join(customerDirectory, "trace.jsonl")))
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

/** Extracts a visible, governed factor from one legacy report. */
function legacyFactor(report) {
  const action = isPlainObject(report.action) ? report.action : null;
  const decline = isPlainObject(report.decline) ? report.decline : {};
  const declineScore = finiteOrNull(decline.decline_score);
  const detectorDrops = [
    ["sales", finiteOrNull(decline.sales_drop)],
    ["trip", finiteOrNull(decline.trip_drop)],
    ["active-week", finiteOrNull(decline.active_week_drop)],
  ].filter((item) => item[1] !== null).sort((left, right) => right[1] - left[1]);
  const dominant = detectorDrops[0];
  const actionId = action ? String(action.action_id ?? "") : "";
  if (String(report.run_status) === "failed" || !action) {
    return {
      factor_type: "failed",
      label: declineScore === null
        ? "Investigation failed"
        : `Failed investigation · ${Math.round(declineScore * 100)}% decline score`,
      detail: safeString(report.failure_reason, "No governed conclusion was published."),
    };
  }
  if (actionId === "INSUFFICIENT_EVIDENCE") {
    return {
      factor_type: "insufficient_evidence",
      label: dominant
        ? `Unresolved ${dominant[0]} signal · ${Math.round(dominant[1] * 100)}% drop`
        : "Insufficient evidence",
      detail: "No supported differentiating factor cleared verification.",
    };
  }
  const mapping = {
    CATEGORY_WINBACK: ["category", "Category-specific decline"],
    VISIT_FREQUENCY_REACTIVATION: [
      "cadence",
      finiteOrNull(decline.trip_drop) === null
        ? "Visit cadence"
        : `Visit cadence · ${Math.round(Number(decline.trip_drop) * 100)}% trip drop`,
    ],
    PROMOTION_VALUE_REENGAGEMENT: [
      "promotion_value",
      finiteOrNull(decline.sales_drop) === null
        ? "Promotion and value activity"
        : `Promotion/value · ${Math.round(Number(decline.sales_drop) * 100)}% sales drop`,
    ],
    PERSONALIZED_CHECK_IN: [
      "multifactor",
      "Multiple behavioral signals",
    ],
    MONITOR: [
      "monitoring",
      declineScore === null
        ? "Monitored decline signal"
        : `Monitoring · ${Math.round(declineScore * 100)}% decline score`,
    ],
  };
  const [factorType, fallback] = mapping[actionId] ?? ["insufficient_evidence", "Insufficient evidence"];
  let label = fallback;
  if (actionId === "CATEGORY_WINBACK" && Array.isArray(report.supporting_evidence)) {
    const categoryRecord = report.supporting_evidence.find(
      (item) => isPlainObject(item) && isPlainObject(item.dimensions) &&
        (item.dimensions.product_category || item.dimensions.department),
    );
    if (categoryRecord) {
      const category = safeString(categoryRecord.dimensions.product_category);
      const department = safeString(categoryRecord.dimensions.department);
      label = [department, category].filter(Boolean).join(" / ") || fallback;
    }
  }
  const driver = Array.isArray(report.likely_drivers) && isPlainObject(report.likely_drivers[0])
    ? report.likely_drivers[0].summary
    : action.rationale;
  return { factor_type: factorType, label, detail: safeString(driver, fallback) };
}

/** Converts one report into the same identifier-safe investigated row as new runs. */
function legacyInvestigatedRow(report, rank) {
  const decline = isPlainObject(report.decline) ? report.decline : {};
  const context = isPlainObject(report.population_context) ? report.population_context : {};
  const population = isPlainObject(context.eligible_population) ? context.eligible_population : {};
  const peers = isPlainObject(context.behavioral_peers) ? context.behavioral_peers : {};
  const action = isPlainObject(report.action) ? report.action : null;
  const baseline = finiteOrNull(decline.baseline_retailer_sales_value);
  const recent = finiteOrNull(decline.recent_retailer_sales_value);
  return {
    household_id: safeString(report.household_id),
    rank,
    status: safeString(report.run_status, "failed"),
    context_classification: safeString(context.context_classification, "insufficient_context"),
    decline_score: finiteOrNull(decline.decline_score),
    sales_drop: finiteOrNull(decline.sales_drop),
    trip_drop: finiteOrNull(decline.trip_drop),
    active_week_drop: finiteOrNull(decline.active_week_drop),
    baseline_retailer_sales_value: baseline,
    recent_retailer_sales_value: recent,
    recorded_value_change: baseline === null || recent === null ? null : recent - baseline,
    population_gap: finiteOrNull(population.target_minus_median_change),
    peer_gap: finiteOrNull(peers.target_minus_median_change),
    identified_factor: legacyFactor(report),
    action_id: action ? safeString(action.action_id) : null,
    action_label: action
      ? safeString(action.description, "Governed action")
      : "No recommendation published",
    confidence: action ? safeString(action.resolved_confidence, "unavailable") : "unavailable",
    warnings: [
      ...(Array.isArray(report.limitations) ? report.limitations : []),
      ...(Array.isArray(report.verification_issues) ? report.verification_issues : []),
      ...(report.failure_reason ? [report.failure_reason] : []),
    ].map((item) => safeString(item)).slice(0, 50),
  };
}

/** Reads the small detector sensitivity CSV used by legacy collections. */
async function readSensitivity(collectionPath) {
  const filePath = path.join(collectionPath, "sensitivity.csv");
  if (!(await isRealFile(filePath))) return [];
  const lines = (await readFile(filePath, "utf8")).trim().split(/\r?\n/u);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((item) => item.trim());
  return lines.slice(1).flatMap((line) => {
    const values = line.split(",");
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]));
    const parsed = {
      threshold: finiteOrNull(row.threshold),
      eligible_households: finiteOrNull(row.eligible_households),
      flagged_households: finiteOrNull(row.flagged_households),
      flagged_share: finiteOrNull(row.flagged_share),
    };
    return Object.values(parsed).some((item) => item === null) ? [] : [parsed];
  });
}

/** Loads all investigated reports in manifest order for legacy population fallback. */
async function loadOrderedReports(collectionPath, manifest) {
  const selected = Array.isArray(manifest.selected_household_ids)
    ? manifest.selected_household_ids.map(String)
    : [];
  const reports = [];
  for (const householdId of selected) {
    if (!validateHouseholdId(householdId)) continue;
    const reportPath = path.join(collectionPath, `customer_${householdId}`, "report.json");
    if (!(await isRealFile(reportPath))) continue;
    const report = await readJson(reportPath);
    if (String(report.household_id ?? "") === householdId) reports.push(report);
  }
  return reports;
}

/** Derives an honest partial population response for a pre-population artifact. */
async function legacyPopulation(collectionPath, manifest) {
  const [reports, sensitivity] = await Promise.all([
    loadOrderedReports(collectionPath, manifest),
    readSensitivity(collectionPath),
  ]);
  const rows = reports.map(legacyInvestigatedRow);
  const configured = sensitivity.find((item) => Math.abs(item.threshold - 0.3) < 1e-9)
    ?? sensitivity[0];
  const firstDecline = reports.length > 0 && isPlainObject(reports[0].decline)
    ? reports[0].decline
    : {};
  const firstProvenance = reports.length > 0 && isPlainObject(reports[0].provenance)
    ? reports[0].provenance
    : {};
  const completed = rows.filter((item) => item.status === "completed").length;
  const insufficient = rows.filter((item) => item.status === "insufficient_evidence").length;
  const failed = rows.filter((item) => item.status === "failed").length;
  const valueRows = rows.filter(
    (item) =>
      item.baseline_retailer_sales_value !== null &&
      item.recent_retailer_sales_value !== null &&
      item.recorded_value_change !== null,
  );
  const hasCompleteInvestigatedValues = rows.length > 0 && valueRows.length === rows.length;
  const investigatedBaseline = hasCompleteInvestigatedValues
    ? valueRows.reduce((total, item) => total + item.baseline_retailer_sales_value, 0)
    : null;
  const investigatedRecent = hasCompleteInvestigatedValues
    ? valueRows.reduce((total, item) => total + item.recent_retailer_sales_value, 0)
    : null;
  const investigatedChange =
    investigatedBaseline === null || investigatedRecent === null
      ? null
      : investigatedRecent - investigatedBaseline;
  const investigatedGrossDecrease = hasCompleteInvestigatedValues
    ? valueRows.reduce(
        (total, item) =>
          total + Math.max(
            0,
            item.baseline_retailer_sales_value - item.recent_retailer_sales_value,
          ),
        0,
      )
    : null;
  /** Counts one legacy categorical mix against all investigated rows. */
  const mixes = (pairs) => {
    const totals = new Map();
    for (const [key, label] of pairs) {
      const current = totals.get(key) ?? { key, label, count: 0 };
      current.count += 1;
      totals.set(key, current);
    }
    return [...totals.values()]
      .sort((left, right) => right.count - left.count || left.key.localeCompare(right.key))
      .map((item) => ({ ...item, share: rows.length ? item.count / rows.length : 0 }));
  };
  const definitions = {
    eligible: "All households meeting the detector's baseline eligibility policy.",
    flagged: "Eligible households at or above the configured decline-score threshold.",
    investigated: "The ranked batch selected from the flagged cohort for investigation.",
  };
  return sanitizePopulationSummary({
    schema_version: 1,
    availability: reports.length > 0 || sensitivity.length > 0 ? "partial" : "unavailable",
    missing_data_reasons: [
      "This preserved run predates population_summary.json.",
      "Eligible and flagged distributions and the density grid are unavailable; displayed counts come from detector sensitivity output.",
      ...(hasCompleteInvestigatedValues
        ? ["Recorded value totals cover investigated households only."]
        : ["Recorded value totals are unavailable because one or more investigated reports lack value fields."]),
    ],
    cohort_definitions: definitions,
    analysis_windows: {
      baseline_start_week: firstDecline.baseline_start_week,
      baseline_end_week: firstDecline.baseline_end_week,
      recent_start_week: firstDecline.recent_start_week,
      recent_end_week: firstDecline.recent_end_week,
    },
    detector_policy: {
      decline_threshold: configured?.threshold ?? null,
      sensitivity_thresholds: sensitivity.map((item) => item.threshold),
    },
    threshold_sensitivity: sensitivity,
    data_quality_warnings: [],
    cohorts: [
      { cohort: "eligible", definition: definitions.eligible, household_count: configured?.eligible_households ?? null, metrics: [] },
      { cohort: "flagged", definition: definitions.flagged, household_count: configured?.flagged_households ?? null, metrics: [] },
      {
        cohort: "investigated",
        definition: definitions.investigated,
        household_count: rows.length,
        aggregate_baseline_value: investigatedBaseline,
        aggregate_recent_value: investigatedRecent,
        gross_recorded_decrease: investigatedGrossDecrease,
        metrics: [],
      },
    ],
    density_grid: null,
    investigated_households: rows,
    executive: {
      eligible_count: configured?.eligible_households ?? null,
      flagged_count: configured?.flagged_households ?? null,
      flagged_share: configured?.flagged_share ?? null,
      selected_count: Array.isArray(manifest.selected_household_ids) ? manifest.selected_household_ids.length : rows.length,
      investigated_count: rows.length,
      completed_count: completed,
      insufficient_count: insufficient,
      failed_count: failed,
      aggregate_baseline_value: investigatedBaseline,
      aggregate_recent_value: investigatedRecent,
      recorded_value_change: investigatedChange,
      gross_recorded_decrease: investigatedGrossDecrease,
      verified_action_rate: rows.length ? completed / rows.length : 0,
      action_mix: mixes(rows.map((item) => item.action_id
        ? [item.action_id, item.action_label]
        : ["NO_PUBLISHED_RECOMMENDATION", "No recommendation published"])),
      factor_mix: mixes(rows.map((item) => [item.identified_factor.factor_type, item.identified_factor.label])),
      context_mix: mixes(rows.map((item) => [item.context_classification, item.context_classification.replaceAll("_", " ")])),
    },
    provenance: {
      dataset_kind: manifest.dataset_kind,
      dataset_source_repository: manifest.dataset_source_repository ?? firstProvenance.dataset_source_repository,
      dataset_source_commit: manifest.dataset_source_commit ?? firstProvenance.dataset_source_commit,
      backend: manifest.backend,
      source_manifest: manifest.source_manifest ?? null,
      generated_at: firstProvenance.generated_at,
    },
  });
}

/** Loads a full new artifact or an explicitly partial legacy derivation. */
export async function loadPopulation(repositoryRoot, collectionId) {
  const collectionPath = await resolveCollection(repositoryRoot, collectionId);
  if (!collectionPath || !(await isRealDirectory(collectionPath))) return null;
  const manifestPath = path.join(collectionPath, "manifest.json");
  if (!(await isRealFile(manifestPath))) return null;
  const manifest = await readJson(manifestPath);
  if (typeof manifest.population_summary !== "string") {
    return legacyPopulation(collectionPath, manifest);
  }
  if (Number(manifest.population_schema_version) !== 1) {
    throw new Error("Unsupported population summary schema version.");
  }
  const populationPath = path.resolve(collectionPath, manifest.population_summary);
  if (
    !populationPath.startsWith(`${path.resolve(collectionPath)}${path.sep}`) ||
    !isPlainObject(manifest.files) ||
    typeof manifest.files[manifest.population_summary] !== "string" ||
    !(await isRealFile(populationPath))
  ) {
    throw new Error("Population summary is not a verified manifest artifact.");
  }
  return sanitizePopulationSummary(await readJson(populationPath));
}

/** Escapes one CSV field according to RFC 4180-compatible quoting rules. */
function csvField(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]/u.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** Serializes the documented long-form aggregate population export. */
export function populationCsv(population) {
  const columns = [
    "record_type", "cohort", "metric", "key", "value", "count", "lower",
    "upper", "share", "household_id", "label", "status",
  ];
  const rows = [];
  const add = (row) => rows.push(columns.map((column) => csvField(row[column])).join(","));
  for (const cohort of population.cohorts) {
    add({ record_type: "cohort", cohort: cohort.cohort, key: "household_count", value: cohort.household_count });
    for (const metric of cohort.metrics) {
      for (const key of ["count", "mean", "minimum", "q25", "median", "q75", "maximum"]) {
        add({ record_type: "statistic", cohort: cohort.cohort, metric: metric.metric, key, value: metric[key] });
      }
      for (const bin of metric.histogram) {
        add({ record_type: "histogram", cohort: cohort.cohort, metric: metric.metric, count: bin.count, lower: bin.lower, upper: bin.upper, share: bin.share });
      }
    }
  }
  for (const item of population.threshold_sensitivity) {
    add({ record_type: "sensitivity", key: item.threshold, value: item.flagged_households, count: item.eligible_households, share: item.flagged_share });
  }
  for (const [kind, items] of [["action_mix", population.executive.action_mix], ["factor_mix", population.executive.factor_mix], ["context_mix", population.executive.context_mix]]) {
    for (const item of items) add({ record_type: kind, key: item.key, count: item.count, share: item.share, label: item.label });
  }
  for (const item of population.investigated_households) {
    add({ record_type: "investigated_household", household_id: item.household_id, key: item.identified_factor.factor_type, value: item.decline_score, label: item.identified_factor.label, status: item.status });
  }
  return `${columns.join(",")}\n${rows.join("\n")}\n`;
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
  const customerPath = path.join(collectionPath, `customer_${householdId}`);
  if (!(await isRealDirectory(customerPath))) return null;
  const filePath = path.join(customerPath, fileName);
  try {
    const details = await lstat(filePath);
    return details.isFile() && !details.isSymbolicLink() ? filePath : null;
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    throw error;
  }
}
