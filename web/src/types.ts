/** Describes the validated report, workspace, API, and live-trace data shown by React. */

export type RunStatus = "completed" | "insufficient_evidence" | "failed";
export type EvidenceRole = "supporting" | "counterevidence" | "context";

export interface ReportSummary {
  householdId: string;
  runId: string;
  runStatus: RunStatus;
  declineScore: number;
  salesDrop: number;
  tripDrop: number;
  activeWeekDrop: number;
  baselineSales: number;
  recentSales: number;
  actionId: string | null;
  confidence: string | null;
  evidenceCount: number;
  warningCount: number;
  generatedAt: string;
}

export interface ArtifactCollection {
  id: string;
  title: string;
  datasetKind: string;
  executionMode: string;
  backend: string;
  modelExecution: string;
  reportCount: number;
  completedCount: number;
  humanReviewRequired: boolean;
  reports: ReportSummary[];
}

export interface DemoCustomerLimits {
  minimum: number;
  maximum: number;
}

export interface LiveRunConfiguration {
  backend: "gemini";
  model: string;
  ready: boolean;
  blockedReason: string | null;
}

export interface Workspace {
  schemaVersion: 1;
  productName: "WhyBack";
  demoCustomerLimits: DemoCustomerLimits;
  liveRun: LiveRunConfiguration;
  collectionWarnings: string[];
  collections: ArtifactCollection[];
}

export interface Provenance {
  application_version: string;
  backend: string;
  dataset_kind: string;
  dataset_source_commit: string;
  dataset_source_repository: string;
  execution_mode: string;
  generated_at: string;
  model: string;
  prompt_hash: string;
  prompt_version: string;
  source_hashes: Record<string, string>;
  timing_mode: string;
}

export interface DeclineData {
  evidence_id: string;
  run_id: string;
  household_id: string;
  source: "decline_detector";
  baseline_start_week: number;
  baseline_end_week: number;
  recent_start_week: number;
  recent_end_week: number;
  baseline_retailer_sales_value: number;
  recent_retailer_sales_value: number;
  baseline_distinct_baskets: number;
  recent_distinct_baskets: number;
  baseline_active_weeks: number;
  recent_active_weeks: number;
  sales_drop: number;
  trip_drop: number;
  active_week_drop: number;
  decline_score: number;
  eligible: boolean;
  flagged: boolean;
  partial_week_limitation: string | null;
}

export interface EvidenceRecord {
  evidence_id: string;
  run_id: string;
  household_id: string;
  role: EvidenceRole;
  source_tool: string;
  source_tool_call_id: string;
  source_status: string | null;
  metric: string;
  dimensions: Record<string, string>;
  baseline_value: number | null;
  recent_value: number | null;
  value: number | null;
  text_value?: string | null;
  change: number | null;
  unit: string | null;
  maximum_claim_type?: string;
  limitations: string[];
  query_hash: string | null;
}

export interface DriverData {
  summary: string;
  claim_type?: string;
  supporting_evidence_ids: string[];
  counterevidence_ids?: string[];
  no_material_counterevidence_reason?: string | null;
  limitations?: string[];
}

export interface InvestigationStep {
  decision_number: number;
  tool_name: string;
  tool_label: string;
  investigation_question: string;
  final_status: string;
  attempt_count: number;
  retry_count: number;
  total_latency_ms: number;
  evidence_ids: string[];
  limitations: string[];
}

export interface ToolWarning {
  tool_name: string;
  final_status: string;
  attempt_count: number;
  retry_count: number;
  attempt_statuses: string[];
  total_latency_ms: number;
  limitations: string[];
  unavailable: boolean;
}

export interface ConfidenceAdjustment {
  context_classification: string;
  maximum_confidence: string;
  reason: string;
  evidence_ids: string[];
}

export interface ActionData {
  action_id: string;
  description: string;
  rationale: string;
  resolved_confidence: string;
  confidence_cap_applied: boolean;
  confidence_adjustments?: ConfidenceAdjustment[];
  recommended_success_metric: string;
  suggested_experiment: string;
  human_review_required: true;
}

export interface CohortComparison {
  cohort: "eligible_population" | "behavioral_peers";
  available: boolean;
  cohort_count: number;
  median_change: number | null;
  q25_change: number | null;
  q75_change: number | null;
  target_percentile: number | null;
  declining_household_share: number | null;
  target_minus_median_change: number | null;
  target_excluded: boolean;
  construction_method: string;
  evidence_ids: string[];
  limitations: string[];
}

export interface PopulationContext {
  context_classification: string;
  target_retailer_sales_change: number | null;
  eligible_population: CohortComparison;
  behavioral_peers: CohortComparison;
  category_context: Array<{
    department: string;
    product_category: string;
    available: boolean;
    context_classification: string;
    target_change: number | null;
    population_median_change: number | null;
    target_percentile?: number | null;
    evidence_ids: string[];
    limitations: string[];
  }>;
  classification_evidence_id: string | null;
  limitations: string[];
}

export interface InterpretationLimits {
  observed_scope: string[];
  unobserved_factors: string[];
  causal_limitations: string[];
}

export interface ReportData {
  schema_version: 2;
  product_name: "WhyBack";
  tagline: string;
  investigator_name: string;
  provenance: Provenance;
  run_id: string;
  household_id: string;
  run_status: RunStatus;
  decline: DeclineData;
  population_context?: PopulationContext;
  investigation_path: InvestigationStep[];
  likely_drivers: DriverData[];
  supporting_evidence: EvidenceRecord[];
  counterevidence: EvidenceRecord[];
  evidence_ledger: EvidenceRecord[];
  alternative_explanations: string[];
  uncertainties: string[];
  interpretation_limits?: InterpretationLimits;
  action: ActionData | null;
  limitations: string[];
  tool_warnings: ToolWarning[];
  verification_issues: string[];
  failure_reason: string | null;
  human_review_required: true;
}

export interface TraceEvent {
  schemaVersion: number;
  timestamp: string;
  event: string;
  runId: string;
  householdId: string;
  details: Record<string, unknown>;
}

export interface LiveTraceEvent extends TraceEvent {
  id: string;
  cursor: number;
  source: string;
  sourceLabel: string;
}

export type DemoRunPhase = "idle" | "running" | "completed" | "failed";

export interface DemoStatusResponse {
  jobId: string | null;
  status: DemoRunPhase;
  backend: "gemini";
  model: string;
  customers: number | null;
  command: string | null;
  startedAt: string | null;
  completedAt: string | null;
  cursor: number;
  eventCount: number;
  eventCapacity: number;
  droppedEventCount: number;
  events: LiveTraceEvent[];
  error: string | null;
  traceWarning: string | null;
  collectionId: string | null;
}

export interface InvestigationResponse {
  report: ReportData;
  trace: TraceEvent[];
}
