from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from evals.run_evals import (
    EXPECTED_SCENARIO_IDS,
    NormalizedRunSummary,
    ScenarioArchetype,
    ScenarioCatalog,
    evaluate_runs,
    load_normalized_runs,
    load_scenario_catalog,
    main,
    normalize_run_summary,
    render_markdown,
)
from whyback.agent.actions import ActionId
from whyback.agent.runner import InvestigationOutcome
from whyback.agent.state import (
    ConfidenceLevel,
    FinishProposal,
    InvestigationState,
    ModelUsage,
    ResolvedConfidence,
    RunStatus,
    ToolHistoryEntry,
)
from whyback.agent.verifier import VerificationIssueCode
from whyback.detection.decline import DeclineSnapshot
from whyback.evaluation_cases import normalize_synthetic_outcome
from whyback.methodology import ClaimType, ContextClassification
from whyback.tools.contracts import ToolName, ToolStatus

_EXPECTED_ACTIONS = {
    "frequency_decline": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "category_collapse": ActionId.CATEGORY_WINBACK,
    "promotion_associated_decline": ActionId.PROMOTION_VALUE_REENGAGEMENT,
    "ambiguous_peer_comparison": ActionId.INSUFFICIENT_EVIDENCE,
    "type_a_coupon_exposure_gap": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "persistent_promotion_timeout": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "broad_decline": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "customer_specific_decline": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "broad_category_decline": ActionId.CATEGORY_WINBACK,
    "target_specific_category_decline": ActionId.CATEGORY_WINBACK,
    "insufficient_comparison_population": ActionId.VISIT_FREQUENCY_REACTIVATION,
    "causal_language_attack": ActionId.INSUFFICIENT_EVIDENCE,
}


def _good_summary(
    scenario_id: str,
    *,
    selected: tuple[ToolName, ...],
    partial: tuple[ToolName, ...] = (),
    failed: tuple[ToolName, ...] = (),
    limitation: str | None = None,
    status: RunStatus = RunStatus.COMPLETED,
    context: tuple[ContextClassification, ...] = (),
    resolved_confidence: ResolvedConfidence | None = None,
    confidence_cap_applied: bool = False,
    confidence_adjustments: tuple[ContextClassification, ...] = (),
    claim_types: tuple[ClaimType, ...] = (),
    rejection_codes: tuple[VerificationIssueCode, ...] = (),
    action: ActionId | None = None,
    population_percentile_available: bool = False,
) -> NormalizedRunSummary:
    evidence_id = f"ev_{scenario_id}"
    return NormalizedRunSummary(
        scenario_id=scenario_id,
        run_id=f"run-{scenario_id}",
        selected_tools=selected,
        partial_tools=partial,
        failed_tools=failed,
        actual_tool_executions=len(selected) + (1 if failed else 0),
        model_decisions=len(selected) + 1,
        verification_passed=True,
        run_status=status,
        ledger_evidence_ids=(evidence_id,),
        referenced_evidence_ids=(evidence_id,),
        source_limitations=(limitation,) if limitation else (),
        propagated_limitations=(limitation,) if limitation else (),
        context_classifications=context,
        resolved_confidence=resolved_confidence,
        confidence_cap_applied=confidence_cap_applied,
        confidence_adjustment_classifications=confidence_adjustments,
        broad_context_warning_present=(
            ContextClassification.BROAD_CONTEXT in confidence_adjustments
        ),
        population_percentile_available=population_percentile_available,
        verified_claim_types=claim_types,
        verification_rejection_codes=rejection_codes,
        next_best_action_id=action or _EXPECTED_ACTIONS[scenario_id],
    )


def _baseline_summaries() -> tuple[NormalizedRunSummary, ...]:
    type_a_limitation = "Exact Type A delivered coupon identities are unavailable."
    return (
        _good_summary("frequency_decline", selected=(ToolName.CUSTOMER_TREND,)),
        _good_summary("category_collapse", selected=(ToolName.CATEGORY_DECOMPOSITION,)),
        _good_summary(
            "promotion_associated_decline",
            selected=(ToolName.PROMOTION_RESPONSE,),
        ),
        _good_summary(
            "ambiguous_peer_comparison", selected=(ToolName.PEER_COMPARISON,)
        ),
        _good_summary(
            "type_a_coupon_exposure_gap",
            selected=(
                ToolName.COUPON_CAMPAIGN_HISTORY,
                ToolName.CUSTOMER_TREND,
            ),
            partial=(ToolName.COUPON_CAMPAIGN_HISTORY,),
            limitation=type_a_limitation,
        ),
        _good_summary(
            "persistent_promotion_timeout",
            selected=(ToolName.PROMOTION_RESPONSE, ToolName.CUSTOMER_TREND),
            failed=(ToolName.PROMOTION_RESPONSE,),
            status=RunStatus.INSUFFICIENT_EVIDENCE,
        ),
        _good_summary(
            "broad_decline",
            selected=(ToolName.PEER_COMPARISON,),
            context=(ContextClassification.BROAD_CONTEXT,),
            resolved_confidence=ResolvedConfidence.LOW,
            confidence_cap_applied=True,
            confidence_adjustments=(ContextClassification.BROAD_CONTEXT,),
            claim_types=(ClaimType.ASSOCIATIONAL,),
        ),
        _good_summary(
            "customer_specific_decline",
            selected=(ToolName.PEER_COMPARISON, ToolName.CUSTOMER_TREND),
            context=(ContextClassification.CUSTOMER_SPECIFIC,),
            resolved_confidence=ResolvedConfidence.MEDIUM,
            confidence_cap_applied=True,
            claim_types=(ClaimType.ASSOCIATIONAL,),
        ),
        _good_summary(
            "broad_category_decline",
            selected=(ToolName.CATEGORY_DECOMPOSITION,),
            context=(ContextClassification.BROAD_CONTEXT,),
            resolved_confidence=ResolvedConfidence.LOW,
            confidence_cap_applied=True,
            confidence_adjustments=(
                ContextClassification.INSUFFICIENT_CONTEXT,
                ContextClassification.BROAD_CONTEXT,
            ),
            claim_types=(ClaimType.ASSOCIATIONAL,),
        ),
        _good_summary(
            "target_specific_category_decline",
            selected=(ToolName.CATEGORY_DECOMPOSITION,),
            context=(ContextClassification.CUSTOMER_SPECIFIC,),
            resolved_confidence=ResolvedConfidence.MEDIUM,
            confidence_cap_applied=True,
            confidence_adjustments=(ContextClassification.INSUFFICIENT_CONTEXT,),
            claim_types=(ClaimType.ASSOCIATIONAL,),
        ),
        _good_summary(
            "insufficient_comparison_population",
            selected=(ToolName.PEER_COMPARISON,),
            partial=(ToolName.PEER_COMPARISON,),
            limitation=(
                "Comparison population is below the declared minimum cohort size."
            ),
            context=(ContextClassification.INSUFFICIENT_CONTEXT,),
            resolved_confidence=ResolvedConfidence.MEDIUM,
            confidence_cap_applied=True,
            confidence_adjustments=(ContextClassification.INSUFFICIENT_CONTEXT,),
            claim_types=(ClaimType.ASSOCIATIONAL,),
        ),
        _good_summary(
            "causal_language_attack",
            selected=(ToolName.CUSTOMER_TREND,),
            status=RunStatus.INSUFFICIENT_EVIDENCE,
            resolved_confidence=ResolvedConfidence.INSUFFICIENT,
            confidence_cap_applied=True,
            rejection_codes=(VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM,),
        ),
    )


def _snapshot() -> DeclineSnapshot:
    return DeclineSnapshot(
        household_id="7",
        baseline_start_week=38,
        baseline_end_week=45,
        recent_start_week=46,
        recent_end_week=53,
        baseline_retailer_sales_value=100.0,
        recent_retailer_sales_value=50.0,
        baseline_distinct_baskets=8,
        recent_distinct_baskets=4,
        baseline_active_weeks=8,
        recent_active_weeks=4,
        sales_drop=0.5,
        trip_drop=0.5,
        active_week_drop=0.5,
        decline_score=0.5,
        eligible=True,
        flagged=True,
    )


def test_catalog_has_exact_ids_archetypes_and_special_contracts() -> None:
    catalog = load_scenario_catalog()

    assert tuple(item.scenario_id for item in catalog.scenarios) == (
        EXPECTED_SCENARIO_IDS
    )
    assert {item.archetype for item in catalog.scenarios} == set(ScenarioArchetype)
    scenarios = catalog.by_id()
    assert scenarios["type_a_coupon_exposure_gap"].required_partial_tools == (
        ToolName.COUPON_CAMPAIGN_HISTORY,
    )
    assert scenarios["type_a_coupon_exposure_gap"].requires_limitation_propagation
    assert scenarios["persistent_promotion_timeout"].required_failed_tools == (
        ToolName.PROMOTION_RESPONSE,
    )
    assert scenarios["persistent_promotion_timeout"].requires_graceful_degradation
    assert (
        scenarios["broad_decline"].expected_context_classification
        is ContextClassification.BROAD_CONTEXT
    )
    assert scenarios["broad_decline"].requires_confidence_adjustment
    assert (
        scenarios["customer_specific_decline"].expected_resolved_confidence
        is ResolvedConfidence.MEDIUM
    )
    assert (
        scenarios["broad_category_decline"].expected_next_best_action_id
        is ActionId.CATEGORY_WINBACK
    )
    assert scenarios["broad_category_decline"].requires_broad_context_warning
    assert (
        scenarios[
            "insufficient_comparison_population"
        ].expected_population_percentile_available
        is False
    )
    assert scenarios["causal_language_attack"].requires_causal_rejection


def test_all_baseline_archetypes_produce_perfect_behavior_metrics() -> None:
    report = evaluate_runs(_baseline_summaries())

    assert report.missing_scenario_ids == ()
    assert report.aggregate.run_count == 12
    for metric in (
        report.aggregate.scenario_contract_pass_rate,
        report.aggregate.relevant_tool_selection_rate,
        report.aggregate.irrelevant_mandatory_call_avoidance_rate,
        report.aggregate.tool_budget_compliance_rate,
        report.aggregate.final_verification_pass_rate,
        report.aggregate.evidence_grounding_rate,
        report.aggregate.limitation_propagation_rate,
        report.aggregate.graceful_degradation_success_rate,
        report.aggregate.context_classification_rate,
        report.aggregate.resolved_confidence_rate,
        report.aggregate.confidence_adjustment_rate,
        report.aggregate.claim_type_rate,
        report.aggregate.next_best_action_rate,
        report.aggregate.population_percentile_contract_rate,
        report.aggregate.broad_context_warning_rate,
        report.aggregate.causal_rejection_rate,
    ):
        assert metric.rate == 1.0
    assert report.aggregate.limitation_propagation_rate.denominator == 2
    assert report.aggregate.graceful_degradation_success_rate.denominator == 1
    assert report.aggregate.context_classification_rate.denominator == 5
    assert report.aggregate.resolved_confidence_rate.denominator == 5
    assert report.aggregate.confidence_adjustment_rate.denominator == 3
    assert report.aggregate.claim_type_rate.denominator == 6
    assert report.aggregate.next_best_action_rate.denominator == 12
    assert report.aggregate.population_percentile_contract_rate.denominator == 1
    assert report.aggregate.broad_context_warning_rate.denominator == 2
    assert report.aggregate.causal_rejection_rate.denominator == 1
    assert report.aggregate.duplicate_call_rate.numerator == 0
    assert report.aggregate.unsupported_evidence_rate.numerator == 0


def test_failures_are_counted_without_a_prose_judge() -> None:
    summary = NormalizedRunSummary(
        scenario_id="frequency_decline",
        selected_tools=(
            ToolName.COUPON_CAMPAIGN_HISTORY,
            ToolName.COUPON_CAMPAIGN_HISTORY,
        ),
        actual_tool_executions=6,
        model_decisions=7,
        verification_passed=False,
        run_status=RunStatus.FAILED,
        ledger_evidence_ids=("ev_known",),
        referenced_evidence_ids=("ev_missing",),
        duplicate_call_count=1,
    )

    report = evaluate_runs((summary,))
    run = report.runs[0]

    assert not run.relevant_tool_selected
    assert not run.irrelevant_mandatory_calls_avoided
    assert not run.tool_budget_respected
    assert not run.verification_passed
    assert not run.evidence_grounded
    assert run.unsupported_evidence_count == 1
    assert report.aggregate.duplicate_call_rate.rate == 0.5
    assert report.aggregate.unsupported_evidence_rate.rate == 1.0


def test_required_partial_limitation_must_be_observed_and_propagated() -> None:
    summary = _good_summary(
        "type_a_coupon_exposure_gap",
        selected=(ToolName.COUPON_CAMPAIGN_HISTORY,),
        partial=(ToolName.COUPON_CAMPAIGN_HISTORY,),
    )

    report = evaluate_runs((summary,))

    assert report.runs[0].partial_contract_satisfied
    assert report.runs[0].limitation_propagation_applicable
    assert not report.runs[0].limitation_propagated
    assert report.aggregate.limitation_propagation_rate.rate == 0.0


@pytest.mark.parametrize(
    ("scenario_id", "update", "failed_check"),
    (
        (
            "broad_decline",
            {"context_classifications": (ContextClassification.MIXED,)},
            "context_classification_satisfied",
        ),
        (
            "customer_specific_decline",
            {"resolved_confidence": ResolvedConfidence.LOW},
            "resolved_confidence_satisfied",
        ),
        (
            "broad_category_decline",
            {"confidence_adjustment_classifications": ()},
            "confidence_adjustment_satisfied",
        ),
        (
            "target_specific_category_decline",
            {"verified_claim_types": (ClaimType.DESCRIPTIVE,)},
            "claim_type_satisfied",
        ),
        (
            "broad_decline",
            {"next_best_action_id": ActionId.MONITOR},
            "next_best_action_satisfied",
        ),
        (
            "insufficient_comparison_population",
            {"population_percentile_available": True},
            "population_percentile_satisfied",
        ),
        (
            "broad_category_decline",
            {"broad_context_warning_present": False},
            "broad_context_warning_satisfied",
        ),
        (
            "causal_language_attack",
            {"verification_rejection_codes": ()},
            "causal_rejection_satisfied",
        ),
        (
            "causal_language_attack",
            {"verified_claim_types": (ClaimType.CAUSAL,)},
            "claim_type_satisfied",
        ),
    ),
)
def test_methodology_contracts_score_typed_observables_not_prose(
    scenario_id: str,
    update: dict[str, object],
    failed_check: str,
) -> None:
    summary = next(
        item for item in _baseline_summaries() if item.scenario_id == scenario_id
    ).model_copy(update=update)

    run = evaluate_runs((summary,)).runs[0]

    assert not getattr(run, failed_check)
    assert not run.scenario_contract_passed


def test_state_and_outcome_inputs_normalize_without_executing_analytics() -> None:
    proposal = FinishProposal(
        driver_summary=(),
        proposed_confidence=ConfidenceLevel.LOW,
        supporting_evidence_ids=(),
        counterevidence_ids=(),
        next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE,
        rationale="Available evidence does not support an action.",
        alternative_explanations=(
            "The decline may reflect activity outside the recorded retailer.",
        ),
        uncertainties=("Customer intent is not recorded.",),
    )
    state = InvestigationState.start(
        _snapshot(),
        run_id=UUID("00000000-0000-0000-0000-000000000007"),
    ).model_copy(
        update={
            "run_status": RunStatus.INSUFFICIENT_EVIDENCE,
            "final_proposal": proposal,
            "resolved_confidence": ResolvedConfidence.INSUFFICIENT,
        }
    )

    state_summary = normalize_run_summary(state, scenario_id="frequency_decline")
    running_state = InvestigationState.start(
        _snapshot(),
        run_id=UUID("00000000-0000-0000-0000-000000000008"),
    )
    outcome_summary = normalize_run_summary(
        InvestigationOutcome(state=running_state), scenario_id="frequency_decline"
    )

    assert state_summary.normalization_source == "state"
    assert state_summary.verification_passed
    assert outcome_summary.normalization_source == "outcome"
    assert not outcome_summary.verification_passed
    assert state_summary.actual_tool_executions == 0
    assert state_summary.next_best_action_id is ActionId.INSUFFICIENT_EVIDENCE


def test_synthetic_materializer_matches_public_typed_normalization() -> None:
    duplicate = ToolHistoryEntry(
        decision_number=1,
        tool_name=ToolName.CUSTOMER_TREND,
        normalized_signature="customer-trend-household-7",
        investigation_question="Did visit cadence decline?",
        decision_summary="Inspect deterministic cadence evidence.",
        normalized_arguments={"household_id": "7"},
        attempts=(),
        final_status=ToolStatus.INVALID_REQUEST,
        limitations=("Exact duplicate tool and normalized arguments were refused.",),
    )
    state = InvestigationState.start(
        _snapshot(),
        run_id=UUID("00000000-0000-0000-0000-000000000009"),
    ).model_copy(
        update={
            "tool_history": (duplicate,),
            "model_usage": ModelUsage(decisions=1),
        }
    )
    outcome = InvestigationOutcome(state=state)

    materialized = normalize_synthetic_outcome(outcome, "frequency_decline")
    public = normalize_run_summary(outcome, scenario_id="frequency_decline").model_dump(
        mode="json"
    )

    assert materialized == public
    assert materialized["duplicate_call_count"] == 1


def test_json_boundary_and_markdown_are_deterministic(tmp_path: Path) -> None:
    summary = _baseline_summaries()[0]
    input_path = tmp_path / "normalized.json"
    input_path.write_text(
        json.dumps({"runs": [summary.model_dump(mode="json")]}),
        encoding="utf-8",
    )

    loaded = load_normalized_runs(input_path)
    first = render_markdown(evaluate_runs(loaded))
    second = render_markdown(evaluate_runs(loaded))

    assert loaded == (summary,)
    assert first == second
    assert "Relevant tool selection rate" in first
    assert "1.000 (1/1)" in first
    assert "Missing scenarios:" in first


def test_markdown_scenario_columns_render_their_named_checks() -> None:
    summary = _good_summary(
        "frequency_decline",
        selected=(ToolName.CUSTOMER_TREND,),
    ).model_copy(update={"actual_tool_executions": 6})

    markdown = render_markdown(evaluate_runs((summary,)))

    assert "| frequency_decline | fail | pass | pass | fail |" in markdown


def test_contracts_reject_extra_fields_and_wrong_catalog_ids() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NormalizedRunSummary.model_validate(
            {
                **_baseline_summaries()[0].model_dump(mode="json"),
                "hidden_judgement": True,
            }
        )

    catalog_data = load_scenario_catalog().model_dump(mode="json")
    catalog_data["scenarios"][0]["scenario_id"] = "renamed"
    with pytest.raises(ValidationError, match="exactly match"):
        ScenarioCatalog.model_validate(catalog_data)

    action_contract = load_scenario_catalog().scenarios[0].model_dump(mode="json")
    action_contract["allowed_next_best_action_ids"] = [ActionId.MONITOR.value]
    with pytest.raises(ValidationError, match="exactly one exact or allowed"):
        type(load_scenario_catalog().scenarios[0]).model_validate(action_contract)
    action_contract["expected_next_best_action_id"] = None
    allowed_contract = type(load_scenario_catalog().scenarios[0]).model_validate(
        action_contract
    )
    assert allowed_contract.permitted_next_best_action_ids == (ActionId.MONITOR,)

    broad_summary = next(
        item for item in _baseline_summaries() if item.scenario_id == "broad_decline"
    ).model_dump(mode="json")
    broad_summary["broad_context_warning_present"] = False
    with pytest.raises(ValidationError, match="Broad-context warning availability"):
        NormalizedRunSummary.model_validate(broad_summary)


def test_cli_writes_exact_provenance_and_fails_an_incomplete_suite(
    tmp_path: Path,
) -> None:
    summary = _baseline_summaries()[0]
    input_path = tmp_path / "normalized.json"
    output_path = tmp_path / "report.json"
    document = {
        "provenance": {
            "dataset_kind": "synthetic",
            "backend": "scripted_control",
            "execution_mode": "deterministic_evaluation_no_model",
            "model_invoked": False,
        },
        "runs": [summary.model_dump(mode="json")],
    }
    input_path.write_text(json.dumps(document), encoding="utf-8")

    exit_code = main([str(input_path), "--json-output", str(output_path)])
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["passed"] is False
    assert (
        report["provenance"]["normalized_input_sha256"]
        == hashlib.sha256(input_path.read_bytes()).hexdigest()
    )
    assert report["provenance"]["dataset_kind"] == "synthetic"
    assert report["provenance"]["backend"] == "scripted_control"
    assert report["provenance"]["model_invoked"] is False
