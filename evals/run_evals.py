"""Deterministic behavioral evaluation over completed WhyBack run summaries.

This module never invokes a model or analytical tool. It scores stable orchestration
and verification signals from an ``InvestigationOutcome``, an
``InvestigationState``, or a normalized JSON summary produced elsewhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.agent.actions import ActionId
from whyback.agent.runner import InvestigationOutcome
from whyback.agent.state import InvestigationState, ResolvedConfidence, RunStatus
from whyback.agent.verifier import VerificationIssueCode
from whyback.methodology import ClaimType, ContextClassification
from whyback.tools.contracts import ToolName, ToolStatus

EXPECTED_SCENARIO_IDS = (
    "frequency_decline",
    "category_collapse",
    "promotion_associated_decline",
    "ambiguous_peer_comparison",
    "type_a_coupon_exposure_gap",
    "persistent_promotion_timeout",
    "broad_decline",
    "customer_specific_decline",
    "broad_category_decline",
    "target_specific_category_decline",
    "insufficient_comparison_population",
    "causal_language_attack",
)


class ScenarioArchetype(StrEnum):
    """Stable synthetic investigation archetypes in the baseline suite."""

    FREQUENCY = "frequency"
    CATEGORY = "category"
    PROMOTION = "promotion"
    AMBIGUOUS_PEER = "ambiguous_peer"
    TYPE_A = "type_a"
    FAILURE = "failure"
    BROAD_DECLINE = "broad_decline"
    CUSTOMER_SPECIFIC_DECLINE = "customer_specific_decline"
    BROAD_CATEGORY_DECLINE = "broad_category_decline"
    TARGET_SPECIFIC_CATEGORY_DECLINE = "target_specific_category_decline"
    INSUFFICIENT_COMPARISON_POPULATION = "insufficient_comparison_population"
    CAUSAL_LANGUAGE_ATTACK = "causal_language_attack"


class ScenarioDefinition(BaseModel):
    """Define the expected tools and outcomes for one behavioral scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    archetype: ScenarioArchetype
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    relevant_tools: tuple[ToolName, ...] = Field(min_length=1)
    irrelevant_mandatory_tools: tuple[ToolName, ...] = ()
    required_partial_tools: tuple[ToolName, ...] = ()
    required_failed_tools: tuple[ToolName, ...] = ()
    requires_limitation_propagation: bool = False
    requires_graceful_degradation: bool = False
    expected_context_classification: ContextClassification | None = None
    expected_resolved_confidence: ResolvedConfidence | None = None
    expected_claim_types: tuple[ClaimType, ...] | None = None
    expected_next_best_action_id: ActionId | None = None
    allowed_next_best_action_ids: tuple[ActionId, ...] = ()
    expected_population_percentile_available: bool | None = None
    requires_confidence_adjustment: bool = False
    requires_broad_context_warning: bool = False
    requires_causal_rejection: bool = False
    max_tool_executions: int = Field(default=5, ge=1)
    max_model_decisions: int = Field(default=6, ge=1)

    @model_validator(mode="after")
    def validate_tool_expectations(self) -> Self:
        """Reject duplicate or contradictory scenario expectations."""

        groups = (
            self.relevant_tools,
            self.irrelevant_mandatory_tools,
            self.required_partial_tools,
            self.required_failed_tools,
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("Scenario tool lists must not contain duplicates")
        if set(self.relevant_tools).intersection(self.irrelevant_mandatory_tools):
            raise ValueError("Relevant tools cannot also be irrelevant mandatory tools")
        required = set(self.required_partial_tools) | set(self.required_failed_tools)
        if not required.issubset(self.relevant_tools):
            raise ValueError("Required partial or failed tools must also be relevant")
        if self.required_partial_tools and not self.requires_limitation_propagation:
            raise ValueError(
                "A required partial result must require limitation propagation"
            )
        if self.required_failed_tools and not self.requires_graceful_degradation:
            raise ValueError("A required failure must require graceful degradation")
        if self.expected_claim_types is not None and len(
            self.expected_claim_types
        ) != len(set(self.expected_claim_types)):
            raise ValueError("Expected claim types must not contain duplicates")
        if len(self.allowed_next_best_action_ids) != len(
            set(self.allowed_next_best_action_ids)
        ):
            raise ValueError("Allowed Next Best Action IDs must not contain duplicates")
        has_expected_action = self.expected_next_best_action_id is not None
        has_allowed_actions = bool(self.allowed_next_best_action_ids)
        if has_expected_action == has_allowed_actions:
            raise ValueError(
                "A scenario must declare exactly one exact or allowed Next Best "
                "Action contract"
            )
        if (
            self.requires_confidence_adjustment
            and self.expected_context_classification is None
        ):
            raise ValueError(
                "A confidence-adjustment expectation requires a context classification"
            )
        if self.requires_broad_context_warning and (
            self.expected_context_classification
            is not ContextClassification.BROAD_CONTEXT
        ):
            raise ValueError(
                "A broad-context warning expectation requires broad context"
            )
        return self

    @property
    def permitted_next_best_action_ids(self) -> tuple[ActionId, ...]:
        """Return the exact fail-closed action allowlist for this scenario."""

        if self.expected_next_best_action_id is not None:
            return (self.expected_next_best_action_id,)
        return self.allowed_next_best_action_ids


class ScenarioCatalog(BaseModel):
    """Versioned baseline scenario catalog with exact, reviewable identifiers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[3]
    scenarios: tuple[ScenarioDefinition, ...]

    @model_validator(mode="after")
    def validate_baseline_catalog(self) -> Self:
        """Require the exact baseline scenario order and one of every archetype."""

        identifiers = tuple(item.scenario_id for item in self.scenarios)
        if identifiers != EXPECTED_SCENARIO_IDS:
            raise ValueError(
                "Scenario IDs and order must exactly match the baseline suite: "
                f"{EXPECTED_SCENARIO_IDS}"
            )
        archetypes = tuple(item.archetype for item in self.scenarios)
        if len(archetypes) != len(set(archetypes)):
            raise ValueError("Each baseline archetype must appear exactly once")
        if set(archetypes) != set(ScenarioArchetype):
            raise ValueError("The catalog must cover every baseline archetype")
        return self

    def by_id(self) -> dict[str, ScenarioDefinition]:
        """Return the unique scenario lookup table."""

        return {scenario.scenario_id: scenario for scenario in self.scenarios}


class NormalizedRunSummary(BaseModel):
    """Provider-neutral facts required to evaluate one completed run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    run_id: str | None = None
    normalization_source: Literal["json", "outcome", "state"] = "json"
    selected_tools: tuple[ToolName, ...] = ()
    partial_tools: tuple[ToolName, ...] = ()
    failed_tools: tuple[ToolName, ...] = ()
    actual_tool_executions: int = Field(ge=0)
    model_decisions: int = Field(ge=0)
    verification_passed: bool
    run_status: RunStatus
    ledger_evidence_ids: tuple[str, ...] = ()
    referenced_evidence_ids: tuple[str, ...] = ()
    source_limitations: tuple[str, ...] = ()
    propagated_limitations: tuple[str, ...] = ()
    duplicate_call_count: int = Field(default=0, ge=0)
    context_classifications: tuple[ContextClassification, ...] = ()
    resolved_confidence: ResolvedConfidence | None = None
    confidence_cap_applied: bool = False
    confidence_adjustment_classifications: tuple[ContextClassification, ...] = ()
    broad_context_warning_present: bool = False
    population_percentile_available: bool = False
    verified_claim_types: tuple[ClaimType, ...] = ()
    verification_rejection_codes: tuple[VerificationIssueCode, ...] = ()
    next_best_action_id: ActionId | None = None

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        """Require normalized run facts to be unique and internally consistent."""

        unique_groups = (
            self.partial_tools,
            self.failed_tools,
            self.ledger_evidence_ids,
            self.referenced_evidence_ids,
            self.source_limitations,
            self.propagated_limitations,
            self.context_classifications,
            self.confidence_adjustment_classifications,
            self.verified_claim_types,
            self.verification_rejection_codes,
        )
        if any(len(group) != len(set(group)) for group in unique_groups):
            raise ValueError("Normalized set-like fields must contain unique values")
        if self.duplicate_call_count > len(self.selected_tools):
            raise ValueError("Duplicate calls cannot exceed selected tool decisions")
        selected = set(self.selected_tools)
        if not set(self.partial_tools).issubset(selected):
            raise ValueError("Partial tools must have been selected")
        if not set(self.failed_tools).issubset(selected):
            raise ValueError("Failed tools must have been selected")
        if set(self.partial_tools).intersection(self.failed_tools):
            raise ValueError("A tool cannot be both partial and failed")
        verified_status = self.run_status in {
            RunStatus.COMPLETED,
            RunStatus.INSUFFICIENT_EVIDENCE,
        }
        if self.verification_passed != verified_status:
            raise ValueError(
                "Verification pass must agree with the terminal run status"
            )
        if self.verification_passed != (self.next_best_action_id is not None):
            raise ValueError(
                "A verified terminal run must expose exactly one verified Next Best "
                "Action ID"
            )
        expected_broad_warning = (
            ContextClassification.BROAD_CONTEXT
            in self.confidence_adjustment_classifications
        )
        if self.broad_context_warning_present != expected_broad_warning:
            raise ValueError(
                "Broad-context warning availability must agree with typed confidence "
                "adjustments"
            )
        return self


class RunEvaluation(BaseModel):
    """Deterministic pass/fail facts for one scenario run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str
    run_id: str | None
    relevant_tool_selected: bool
    irrelevant_mandatory_calls_avoided: bool
    tool_budget_respected: bool
    verification_passed: bool
    evidence_grounded: bool
    limitation_propagation_applicable: bool
    limitation_propagated: bool
    graceful_degradation_applicable: bool
    graceful_degradation_succeeded: bool
    partial_contract_satisfied: bool
    failure_contract_satisfied: bool
    context_classification_applicable: bool
    context_classification_satisfied: bool
    resolved_confidence_applicable: bool
    resolved_confidence_satisfied: bool
    confidence_adjustment_applicable: bool
    confidence_adjustment_satisfied: bool
    claim_type_applicable: bool
    claim_type_satisfied: bool
    next_best_action_applicable: bool
    next_best_action_satisfied: bool
    population_percentile_applicable: bool
    population_percentile_satisfied: bool
    broad_context_warning_applicable: bool
    broad_context_warning_satisfied: bool
    causal_rejection_applicable: bool
    causal_rejection_satisfied: bool
    scenario_contract_passed: bool
    selected_tool_decisions: int = Field(ge=0)
    actual_tool_executions: int = Field(ge=0)
    duplicate_call_count: int = Field(ge=0)
    referenced_evidence_count: int = Field(ge=0)
    unsupported_evidence_count: int = Field(ge=0)


class RateMetric(BaseModel):
    """A transparent numerator, denominator, and optional rate."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_rate(self) -> Self:
        """Require counts to reconcile exactly with the optional rate."""

        if self.numerator > self.denominator:
            raise ValueError("Metric numerator cannot exceed its denominator")
        expected = self.numerator / self.denominator if self.denominator else None
        if self.rate != expected:
            raise ValueError("Metric rate must equal numerator divided by denominator")
        return self

    @classmethod
    def from_counts(cls, numerator: int, denominator: int) -> RateMetric:
        """Build a rate from counts, leaving it undefined for a zero denominator."""

        return cls(
            numerator=numerator,
            denominator=denominator,
            rate=numerator / denominator if denominator else None,
        )


class AggregateMetrics(BaseModel):
    """Required behavior and invariant metrics across evaluated runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_count: int = Field(ge=1)
    scenario_contract_pass_rate: RateMetric
    relevant_tool_selection_rate: RateMetric
    irrelevant_mandatory_call_avoidance_rate: RateMetric
    tool_budget_compliance_rate: RateMetric
    final_verification_pass_rate: RateMetric
    evidence_grounding_rate: RateMetric
    limitation_propagation_rate: RateMetric
    graceful_degradation_success_rate: RateMetric
    context_classification_rate: RateMetric
    resolved_confidence_rate: RateMetric
    confidence_adjustment_rate: RateMetric
    claim_type_rate: RateMetric
    next_best_action_rate: RateMetric
    population_percentile_contract_rate: RateMetric
    broad_context_warning_rate: RateMetric
    causal_rejection_rate: RateMetric
    duplicate_call_rate: RateMetric
    unsupported_evidence_rate: RateMetric


class EvaluationProvenance(BaseModel):
    """Exact input identities and execution labels for one evaluation report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    normalized_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_materialization: Literal["file_bytes", "canonical_in_memory"]
    dataset_kind: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    model_invoked: Literal[False] = False


class EvaluationReport(BaseModel):
    """Stable JSON- and Markdown-friendly evaluation output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[4] = 4
    passed: bool
    provenance: EvaluationProvenance
    scenario_catalog_ids: tuple[str, ...]
    missing_scenario_ids: tuple[str, ...]
    runs: tuple[RunEvaluation, ...]
    aggregate: AggregateMetrics

    @model_validator(mode="after")
    def validate_pass_state(self) -> Self:
        """Require the report result to match scenario coverage and run outcomes."""

        expected = not self.missing_scenario_ids and all(
            run.scenario_contract_passed for run in self.runs
        )
        if self.passed != expected:
            raise ValueError("Evaluation pass state must match all scenario contracts")
        return self


def load_scenario_catalog(path: Path | str | None = None) -> ScenarioCatalog:
    """Load and strictly validate the versioned baseline scenario YAML."""

    scenario_path = (
        Path(path) if path is not None else Path(__file__).with_name("scenarios.yaml")
    )
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Scenario YAML must contain an object at the document root")
    return ScenarioCatalog.model_validate(dict(raw))


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    """Return strings once each while preserving their first-seen order."""

    return tuple(dict.fromkeys(values))


def _context_classifications(
    state: InvestigationState,
) -> tuple[ContextClassification, ...]:
    """Collect unique valid context classifications from the evidence ledger."""

    classifications: list[ContextClassification] = []
    for record in state.evidence_ledger:
        if (
            record.metric
            not in {
                "context_classification",
                "category_context_classification",
            }
            or record.text_value is None
        ):
            continue
        try:
            classification = ContextClassification(record.text_value)
        except ValueError:
            continue
        if classification not in classifications:
            classifications.append(classification)
    return tuple(classifications)


def _verification_rejection_codes(
    state: InvestigationState,
) -> tuple[VerificationIssueCode, ...]:
    """Recover unique typed rejection codes from stored verification issues."""

    codes: list[VerificationIssueCode] = []
    for issue in state.verification_issues:
        raw_code = issue.partition(":")[0]
        try:
            code = VerificationIssueCode(raw_code)
        except ValueError:
            continue
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def _population_percentile_available(state: InvestigationState) -> bool:
    """Return whether typed population-percentile evidence exists in the ledger."""

    return any(
        record.source_tool is ToolName.PEER_COMPARISON
        and record.metric == "target_population_retailer_sales_change_percentile"
        and record.dimensions.get("comparison_scope") == "eligible_population"
        and record.dimensions.get("target_excluded") == "true"
        and record.unit == "percentile"
        and record.value is not None
        for record in state.evidence_ledger
    )


def _state_facts(
    state: InvestigationState,
) -> tuple[
    tuple[ToolName, ...],
    tuple[ToolName, ...],
    tuple[ToolName, ...],
    int,
    int,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    int,
]:
    """Extract tool, evidence, limitation, and execution facts from run state."""

    selected = tuple(item.tool_name for item in state.tool_history)
    partial = tuple(
        dict.fromkeys(
            item.tool_name
            for item in state.tool_history
            if item.final_status is ToolStatus.PARTIAL
        )
    )
    failed = tuple(
        dict.fromkeys(
            item.tool_name
            for item in state.tool_history
            if item.final_status
            in {
                ToolStatus.MISSING_DATA,
                ToolStatus.RETRYABLE_ERROR,
                ToolStatus.FATAL_ERROR,
            }
        )
    )
    actual_executions = sum(len(item.attempts) for item in state.tool_history)
    duplicate_count = sum(
        1
        for item in state.tool_history
        if not item.attempts
        and item.final_status is ToolStatus.INVALID_REQUEST
        and any("duplicate" in limitation.lower() for limitation in item.limitations)
    )
    ledger_ids = tuple(item.evidence_id for item in state.evidence_ledger)
    referenced: tuple[str, ...] = ()
    if state.final_proposal is not None:
        referenced = _unique(
            (
                *state.final_proposal.supporting_evidence_ids,
                *state.final_proposal.counterevidence_ids,
            )
        )
    referenced = _unique(
        (
            *referenced,
            *(
                record.evidence_id
                for record in state.evidence_ledger
                if record.metric
                in {"context_classification", "category_context_classification"}
            ),
        )
    )

    referenced_set = set(referenced)
    histories_by_call = {
        attempt.tool_call_id: history
        for history in state.tool_history
        for attempt in history.attempts
    }
    limitations: list[str] = []
    for record in state.evidence_ledger:
        if record.evidence_id not in referenced_set:
            continue
        limitations.extend(record.limitations)
        history = histories_by_call.get(record.source_tool_call_id)
        if history is not None and history.final_status is ToolStatus.PARTIAL:
            limitations.extend(history.limitations)
    for history in state.tool_history:
        if history.final_status is ToolStatus.PARTIAL:
            limitations.extend(history.limitations)
    for record in state.evidence_ledger:
        history = histories_by_call.get(record.source_tool_call_id)
        if history is not None and history.final_status is ToolStatus.PARTIAL:
            limitations.extend(record.limitations)
    return (
        selected,
        partial,
        failed,
        actual_executions,
        state.model_usage.decisions,
        ledger_ids,
        referenced,
        _unique(limitations),
        duplicate_count,
    )


def normalize_run_summary(
    value: InvestigationOutcome
    | InvestigationState
    | NormalizedRunSummary
    | Mapping[str, object],
    *,
    scenario_id: str | None = None,
) -> NormalizedRunSummary:
    """Normalize an application object or strict JSON-shaped summary."""

    if isinstance(value, NormalizedRunSummary):
        summary = value
    elif isinstance(value, Mapping):
        summary = NormalizedRunSummary.model_validate(dict(value))
    else:
        if isinstance(value, InvestigationOutcome):
            outcome: InvestigationOutcome | None = value
            state = value.state
        else:
            outcome = None
            state = value
        if scenario_id is None:
            raise ValueError("scenario_id is required for outcome or state inputs")
        (
            selected,
            partial,
            failed,
            actual_executions,
            model_decisions,
            ledger_ids,
            referenced,
            source_limitations,
            duplicate_count,
        ) = _state_facts(state)
        context_classifications = _context_classifications(state)
        rejection_codes = _verification_rejection_codes(state)
        population_percentile_available = _population_percentile_available(state)

        if outcome is not None:
            verification_passed = bool(
                outcome.verification is not None and outcome.verification.passed
            )
            verified_final = (
                outcome.verification.final
                if outcome.verification is not None and outcome.verification.passed
                else None
            )
            propagated = (
                verified_final.propagated_limitations
                if verified_final is not None
                else ()
            )
            resolved_confidence = (
                verified_final.resolved_confidence
                if verified_final is not None
                else None
            )
            confidence_cap_applied = bool(
                verified_final is not None and verified_final.confidence_cap_applied
            )
            confidence_adjustments = (
                tuple(
                    dict.fromkeys(
                        item.context_classification
                        for item in verified_final.confidence_adjustments
                    )
                )
                if verified_final is not None
                else ()
            )
            claim_types = (
                tuple(
                    dict.fromkeys(
                        driver.claim_type for driver in verified_final.drivers
                    )
                )
                if verified_final is not None
                else ()
            )
            next_best_action_id = (
                verified_final.next_best_action_id
                if verified_final is not None
                else None
            )
            source: Literal["outcome", "state"] = "outcome"
        else:
            verification_passed = bool(
                state.run_status
                in {RunStatus.COMPLETED, RunStatus.INSUFFICIENT_EVIDENCE}
                and state.final_proposal is not None
                and state.resolved_confidence is not None
            )
            # InvestigationState does not retain VerifiedFinalDecision. Because the
            # verifier derives propagation solely from referenced ledger/history
            # records, reconstruct the same deterministic value for state-only input.
            propagated = source_limitations if verification_passed else ()
            resolved_confidence = state.resolved_confidence
            confidence_cap_applied = False
            confidence_adjustments = ()
            claim_types = ()
            next_best_action_id = (
                state.final_proposal.next_best_action_id
                if verification_passed and state.final_proposal is not None
                else None
            )
            source = "state"

        summary = NormalizedRunSummary(
            scenario_id=scenario_id,
            run_id=str(state.run_id),
            normalization_source=source,
            selected_tools=selected,
            partial_tools=partial,
            failed_tools=failed,
            actual_tool_executions=actual_executions,
            model_decisions=model_decisions,
            verification_passed=verification_passed,
            run_status=state.run_status,
            ledger_evidence_ids=ledger_ids,
            referenced_evidence_ids=referenced,
            source_limitations=source_limitations,
            propagated_limitations=propagated,
            duplicate_call_count=duplicate_count,
            context_classifications=context_classifications,
            resolved_confidence=resolved_confidence,
            confidence_cap_applied=confidence_cap_applied,
            confidence_adjustment_classifications=confidence_adjustments,
            broad_context_warning_present=(
                ContextClassification.BROAD_CONTEXT in confidence_adjustments
            ),
            population_percentile_available=population_percentile_available,
            verified_claim_types=claim_types,
            verification_rejection_codes=rejection_codes,
            next_best_action_id=next_best_action_id,
        )

    if scenario_id is not None and summary.scenario_id != scenario_id:
        raise ValueError(
            f"Summary scenario_id {summary.scenario_id!r} does not match "
            f"{scenario_id!r}"
        )
    return summary


def evaluate_run(
    summary: NormalizedRunSummary, scenario: ScenarioDefinition
) -> RunEvaluation:
    """Score one normalized run without judging generated prose."""

    if summary.scenario_id != scenario.scenario_id:
        raise ValueError("Run summary and scenario IDs must match")
    selected = set(summary.selected_tools)
    relevant_selected = bool(selected.intersection(scenario.relevant_tools))
    irrelevant_avoided = not selected.intersection(scenario.irrelevant_mandatory_tools)
    partial_satisfied = set(scenario.required_partial_tools).issubset(
        summary.partial_tools
    )
    failure_satisfied = set(scenario.required_failed_tools).issubset(
        summary.failed_tools
    )
    budget_respected = (
        summary.actual_tool_executions <= scenario.max_tool_executions
        and summary.model_decisions <= scenario.max_model_decisions
    )
    unsupported = set(summary.referenced_evidence_ids).difference(
        summary.ledger_evidence_ids
    )
    evidence_grounded = not unsupported

    limitation_applicable = bool(summary.source_limitations) or (
        scenario.requires_limitation_propagation
    )
    limitation_propagated = set(summary.source_limitations).issubset(
        summary.propagated_limitations
    ) and (
        bool(summary.source_limitations) or not scenario.requires_limitation_propagation
    )
    graceful_applicable = scenario.requires_graceful_degradation
    graceful_succeeded = (
        summary.run_status is not RunStatus.FAILED
        and summary.verification_passed
        and failure_satisfied
        and evidence_grounded
    )
    limitation_satisfied = not limitation_applicable or limitation_propagated
    graceful_satisfied = not graceful_applicable or graceful_succeeded
    context_applicable = scenario.expected_context_classification is not None
    context_satisfied = not context_applicable or (
        summary.context_classifications == (scenario.expected_context_classification,)
    )
    confidence_applicable = scenario.expected_resolved_confidence is not None
    confidence_satisfied = not confidence_applicable or (
        summary.resolved_confidence == scenario.expected_resolved_confidence
    )
    adjustment_applicable = scenario.requires_confidence_adjustment
    adjustment_satisfied = not adjustment_applicable or (
        summary.confidence_cap_applied
        and scenario.expected_context_classification
        in summary.confidence_adjustment_classifications
    )
    claim_type_applicable = scenario.expected_claim_types is not None
    claim_type_satisfied = not claim_type_applicable or (
        set(summary.verified_claim_types) == set(scenario.expected_claim_types or ())
    )
    action_applicable = bool(scenario.permitted_next_best_action_ids)
    action_satisfied = not action_applicable or (
        summary.next_best_action_id in scenario.permitted_next_best_action_ids
    )
    percentile_applicable = (
        scenario.expected_population_percentile_available is not None
    )
    percentile_satisfied = not percentile_applicable or (
        summary.population_percentile_available
        == scenario.expected_population_percentile_available
    )
    broad_warning_applicable = scenario.requires_broad_context_warning
    broad_warning_satisfied = (
        not broad_warning_applicable or summary.broad_context_warning_present
    )
    causal_applicable = scenario.requires_causal_rejection
    causal_satisfied = not causal_applicable or (
        VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM
        in summary.verification_rejection_codes
    )
    scenario_contract = (
        relevant_selected
        and irrelevant_avoided
        and partial_satisfied
        and failure_satisfied
        and budget_respected
        and summary.verification_passed
        and evidence_grounded
        and limitation_satisfied
        and graceful_satisfied
        and context_satisfied
        and confidence_satisfied
        and adjustment_satisfied
        and claim_type_satisfied
        and action_satisfied
        and percentile_satisfied
        and broad_warning_satisfied
        and causal_satisfied
        and summary.duplicate_call_count == 0
    )
    return RunEvaluation(
        scenario_id=scenario.scenario_id,
        run_id=summary.run_id,
        relevant_tool_selected=relevant_selected,
        irrelevant_mandatory_calls_avoided=irrelevant_avoided,
        tool_budget_respected=budget_respected,
        verification_passed=summary.verification_passed,
        evidence_grounded=evidence_grounded,
        limitation_propagation_applicable=limitation_applicable,
        limitation_propagated=limitation_propagated,
        graceful_degradation_applicable=graceful_applicable,
        graceful_degradation_succeeded=graceful_succeeded,
        partial_contract_satisfied=partial_satisfied,
        failure_contract_satisfied=failure_satisfied,
        context_classification_applicable=context_applicable,
        context_classification_satisfied=context_satisfied,
        resolved_confidence_applicable=confidence_applicable,
        resolved_confidence_satisfied=confidence_satisfied,
        confidence_adjustment_applicable=adjustment_applicable,
        confidence_adjustment_satisfied=adjustment_satisfied,
        claim_type_applicable=claim_type_applicable,
        claim_type_satisfied=claim_type_satisfied,
        next_best_action_applicable=action_applicable,
        next_best_action_satisfied=action_satisfied,
        population_percentile_applicable=percentile_applicable,
        population_percentile_satisfied=percentile_satisfied,
        broad_context_warning_applicable=broad_warning_applicable,
        broad_context_warning_satisfied=broad_warning_satisfied,
        causal_rejection_applicable=causal_applicable,
        causal_rejection_satisfied=causal_satisfied,
        scenario_contract_passed=scenario_contract,
        selected_tool_decisions=len(summary.selected_tools),
        actual_tool_executions=summary.actual_tool_executions,
        duplicate_call_count=summary.duplicate_call_count,
        referenced_evidence_count=len(summary.referenced_evidence_ids),
        unsupported_evidence_count=len(unsupported),
    )


def _boolean_rate(runs: Sequence[RunEvaluation], attribute: str) -> RateMetric:
    """Calculate the true-value rate for one boolean run attribute."""

    values = [bool(getattr(item, attribute)) for item in runs]
    return RateMetric.from_counts(sum(values), len(values))


def _applicable_rate(
    runs: Sequence[RunEvaluation], applicable: str, passed: str
) -> RateMetric:
    """Calculate a pass rate using only runs where the check applies."""

    applicable_runs = [item for item in runs if bool(getattr(item, applicable))]
    return RateMetric.from_counts(
        sum(bool(getattr(item, passed)) for item in applicable_runs),
        len(applicable_runs),
    )


def evaluate_runs(
    runs: Sequence[
        InvestigationOutcome
        | InvestigationState
        | NormalizedRunSummary
        | Mapping[str, object]
    ],
    *,
    catalog: ScenarioCatalog | None = None,
    scenario_ids: Sequence[str] | None = None,
    provenance: EvaluationProvenance | None = None,
) -> EvaluationReport:
    """Evaluate normalized or application-owned runs and aggregate exact metrics."""

    if not runs:
        raise ValueError("At least one run is required")
    scenarios = catalog or load_scenario_catalog()
    lookup = scenarios.by_id()
    if scenario_ids is not None and len(scenario_ids) != len(runs):
        raise ValueError("scenario_ids must have one entry per run")

    normalized: list[NormalizedRunSummary] = []
    for index, run in enumerate(runs):
        explicit_id = scenario_ids[index] if scenario_ids is not None else None
        normalized.append(normalize_run_summary(run, scenario_id=explicit_id))

    evaluated: list[RunEvaluation] = []
    for summary in normalized:
        scenario = lookup.get(summary.scenario_id)
        if scenario is None:
            raise ValueError(f"Unknown evaluation scenario: {summary.scenario_id}")
        evaluated.append(evaluate_run(summary, scenario))

    run_count = len(evaluated)
    duplicate_count = sum(item.duplicate_call_count for item in evaluated)
    selected_count = sum(item.selected_tool_decisions for item in evaluated)
    unsupported_count = sum(item.unsupported_evidence_count for item in evaluated)
    referenced_count = sum(item.referenced_evidence_count for item in evaluated)
    aggregate = AggregateMetrics(
        run_count=run_count,
        scenario_contract_pass_rate=_boolean_rate(
            evaluated, "scenario_contract_passed"
        ),
        relevant_tool_selection_rate=_boolean_rate(evaluated, "relevant_tool_selected"),
        irrelevant_mandatory_call_avoidance_rate=_boolean_rate(
            evaluated, "irrelevant_mandatory_calls_avoided"
        ),
        tool_budget_compliance_rate=_boolean_rate(evaluated, "tool_budget_respected"),
        final_verification_pass_rate=_boolean_rate(evaluated, "verification_passed"),
        evidence_grounding_rate=_boolean_rate(evaluated, "evidence_grounded"),
        limitation_propagation_rate=_applicable_rate(
            evaluated,
            "limitation_propagation_applicable",
            "limitation_propagated",
        ),
        graceful_degradation_success_rate=_applicable_rate(
            evaluated,
            "graceful_degradation_applicable",
            "graceful_degradation_succeeded",
        ),
        context_classification_rate=_applicable_rate(
            evaluated,
            "context_classification_applicable",
            "context_classification_satisfied",
        ),
        resolved_confidence_rate=_applicable_rate(
            evaluated,
            "resolved_confidence_applicable",
            "resolved_confidence_satisfied",
        ),
        confidence_adjustment_rate=_applicable_rate(
            evaluated,
            "confidence_adjustment_applicable",
            "confidence_adjustment_satisfied",
        ),
        claim_type_rate=_applicable_rate(
            evaluated,
            "claim_type_applicable",
            "claim_type_satisfied",
        ),
        next_best_action_rate=_applicable_rate(
            evaluated,
            "next_best_action_applicable",
            "next_best_action_satisfied",
        ),
        population_percentile_contract_rate=_applicable_rate(
            evaluated,
            "population_percentile_applicable",
            "population_percentile_satisfied",
        ),
        broad_context_warning_rate=_applicable_rate(
            evaluated,
            "broad_context_warning_applicable",
            "broad_context_warning_satisfied",
        ),
        causal_rejection_rate=_applicable_rate(
            evaluated,
            "causal_rejection_applicable",
            "causal_rejection_satisfied",
        ),
        duplicate_call_rate=RateMetric.from_counts(duplicate_count, selected_count),
        unsupported_evidence_rate=RateMetric.from_counts(
            unsupported_count, referenced_count
        ),
    )
    represented = {item.scenario_id for item in evaluated}
    missing = tuple(
        identifier
        for identifier in EXPECTED_SCENARIO_IDS
        if identifier not in represented
    )
    if provenance is None:
        normalized_bytes = json.dumps(
            [item.model_dump(mode="json") for item in normalized],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        catalog_bytes = json.dumps(
            scenarios.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        provenance = EvaluationProvenance(
            normalized_input_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
            scenario_catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
            input_materialization="canonical_in_memory",
            dataset_kind="unspecified",
            backend="unspecified",
            execution_mode="deterministic_evaluation_no_model",
            model_invoked=False,
        )
    return EvaluationReport(
        passed=not missing and all(item.scenario_contract_passed for item in evaluated),
        provenance=provenance,
        scenario_catalog_ids=tuple(lookup),
        missing_scenario_ids=missing,
        runs=tuple(evaluated),
        aggregate=aggregate,
    )


def render_markdown(report: EvaluationReport) -> str:
    """Render a compact deterministic report with visible metric denominators."""

    metrics = report.aggregate
    metric_rows = (
        ("Scenario contract pass rate", metrics.scenario_contract_pass_rate),
        ("Relevant tool selection rate", metrics.relevant_tool_selection_rate),
        (
            "Irrelevant mandatory call avoidance rate",
            metrics.irrelevant_mandatory_call_avoidance_rate,
        ),
        ("Tool budget compliance rate", metrics.tool_budget_compliance_rate),
        ("Final verification pass rate", metrics.final_verification_pass_rate),
        ("Evidence-grounding rate", metrics.evidence_grounding_rate),
        ("Limitation-propagation rate", metrics.limitation_propagation_rate),
        (
            "Graceful-degradation success rate",
            metrics.graceful_degradation_success_rate,
        ),
        ("Context-classification rate", metrics.context_classification_rate),
        ("Resolved-confidence rate", metrics.resolved_confidence_rate),
        ("Confidence-adjustment rate", metrics.confidence_adjustment_rate),
        ("Claim-type rate", metrics.claim_type_rate),
        ("Next Best Action contract rate", metrics.next_best_action_rate),
        (
            "Population-percentile contract rate",
            metrics.population_percentile_contract_rate,
        ),
        ("Broad-context warning rate", metrics.broad_context_warning_rate),
        ("Causal-rejection rate", metrics.causal_rejection_rate),
        ("Duplicate-call rate", metrics.duplicate_call_rate),
        ("Unsupported-evidence rate", metrics.unsupported_evidence_rate),
    )
    lines = [
        "# WhyBack deterministic evaluation",
        "",
        f"Overall result: **{'PASS' if report.passed else 'FAIL'}**",
        "",
        f"Runs evaluated: {metrics.run_count}",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
    ]
    for label, metric in metric_rows:
        rendered_rate = "n/a" if metric.rate is None else f"{metric.rate:.3f}"
        lines.append(
            f"| {label} | {rendered_rate} ({metric.numerator}/{metric.denominator}) |"
        )
    lines.extend(
        (
            "",
            "| Scenario | Contract | Verification | Grounded | Budget |",
            "| --- | ---: | ---: | ---: | ---: |",
        )
    )
    for run in report.runs:
        checks = (
            run.scenario_contract_passed,
            run.verification_passed,
            run.evidence_grounded,
            run.tool_budget_respected,
        )
        marks = tuple("pass" if value else "fail" for value in checks)
        lines.append(
            f"| {run.scenario_id} | {marks[0]} | {marks[1]} | {marks[2]} | {marks[3]} |"
        )
    if report.missing_scenario_ids:
        lines.extend(
            (
                "",
                "Missing scenarios: " + ", ".join(report.missing_scenario_ids),
            )
        )
    return "\n".join(lines) + "\n"


def load_normalized_runs(path: Path | str) -> tuple[NormalizedRunSummary, ...]:
    """Load either a JSON list or ``{"runs": [...]}`` normalized input."""

    raw: object = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, Mapping):
        raw = raw.get("runs")
    if not isinstance(raw, list):
        raise ValueError("Evaluation input must be a JSON list or an object with runs")
    summaries: list[NormalizedRunSummary] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("Every normalized run must be a JSON object")
        summaries.append(NormalizedRunSummary.model_validate(dict(item)))
    return tuple(summaries)


def _normalized_input_metadata(path: Path) -> Mapping[str, object]:
    """Read optional provenance metadata from a normalized-run input document."""

    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        return {}
    provenance = raw.get("provenance")
    return provenance if isinstance(provenance, Mapping) else {}


def _sha256_file(path: Path) -> str:
    """Hash a file in chunks without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for deterministic evaluation inputs."""

    parser = argparse.ArgumentParser(
        description="Score normalized WhyBack runs without invoking a model."
    )
    parser.add_argument("input", type=Path, help="Normalized run-summary JSON")
    parser.add_argument("--scenarios", type=Path, default=None)
    parser.add_argument("--dataset-kind", default=None)
    parser.add_argument("--backend", default=None)
    parser.add_argument("--execution-mode", default=None)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the file-based deterministic evaluator."""

    arguments = _parser().parse_args(argv)
    input_path = cast(Path, arguments.input)
    scenario_path = cast(Path | None, arguments.scenarios) or Path(__file__).with_name(
        "scenarios.yaml"
    )
    declared = _normalized_input_metadata(input_path)
    catalog = load_scenario_catalog(scenario_path)
    provenance = EvaluationProvenance(
        normalized_input_sha256=_sha256_file(input_path),
        scenario_catalog_sha256=_sha256_file(scenario_path),
        input_materialization="file_bytes",
        dataset_kind=str(
            arguments.dataset_kind or declared.get("dataset_kind") or "unspecified"
        ),
        backend=str(arguments.backend or declared.get("backend") or "unspecified"),
        execution_mode=str(
            arguments.execution_mode
            or declared.get("execution_mode")
            or "deterministic_evaluation_no_model"
        ),
        model_invoked=False,
    )
    report = evaluate_runs(
        load_normalized_runs(input_path), catalog=catalog, provenance=provenance
    )
    json_text = report.model_dump_json(indent=2) + "\n"
    markdown_text = render_markdown(report)
    json_output = cast(Path | None, arguments.json_output)
    markdown_output = cast(Path | None, arguments.markdown_output)
    if json_output is not None:
        json_output.write_text(json_text, encoding="utf-8")
    if markdown_output is not None:
        markdown_output.write_text(markdown_text, encoding="utf-8")
    if json_output is None and markdown_output is None:
        print(json_text, end="")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
