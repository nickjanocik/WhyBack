"""Executable synthetic control cases for behavior-focused agent evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd
from pydantic import JsonValue

from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.faults import DemoFaultInjector, DemoFaultScenario
from whyback.agent.runner import (
    InvestigationOutcome,
    InvestigationRunner,
    make_tool_call_id,
)
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishDecision,
    FinishProposal,
    ModelDecision,
    ToolDecision,
)
from whyback.agent.verifier import VerificationIssueCode
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.demo import synthetic_demo_frames
from whyback.detection.decline import DeclineSnapshot, detect_declines
from whyback.methodology import ClaimType, ContextClassification
from whyback.tools.contracts import ToolName, ToolStatus
from whyback.tools.registry import build_tool_registry

SCENARIO_IDS = (
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
_EVAL_NAMESPACE = uuid5(NAMESPACE_URL, "https://github.com/whyback/evaluations")


def _evidence_id(run_id: UUID, call_index: int, tool: ToolName, ordinal: int) -> str:
    """Build the evidence ID a scripted tool call will deterministically emit."""

    call_id = make_tool_call_id(run_id, call_index, tool)
    return f"ev_{call_id}_{ordinal:03d}"


def _tool(
    name: ToolName,
    household_id: str,
    *,
    arguments: dict[str, JsonValue] | None = None,
) -> ToolDecision:
    """Create one model-shaped decision to run a named tool in a control case."""

    return ToolDecision(
        investigation_question=f"What deterministic evidence can {name.value} add?",
        selected_tool=name,
        arguments=arguments or {"household_id": household_id},
        decision_summary=f"Use {name.value} for this synthetic control case.",
    )


def _finish(
    *,
    action: ActionId,
    supporting: tuple[str, ...],
    counterevidence: tuple[str, ...] = (),
    claim_type: ClaimType = ClaimType.ASSOCIATIONAL,
    proposed_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    summary: str = (
        "Recorded behavioral evidence is consistent with an engagement decline "
        "that warrants a reviewed test."
    ),
) -> FinishDecision:
    """Build a grounded finish proposal for a deterministic evaluation case."""

    return FinishDecision(
        investigation_question="Is the bounded evidence sufficient to finish?",
        decision_summary="Submit the controlled hypothesis for deterministic review.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary=summary,
                    claim_type=claim_type,
                    supporting_evidence_ids=supporting,
                    counterevidence_ids=counterevidence,
                    no_material_counterevidence_reason=(
                        None
                        if counterevidence
                        else "No material counterevidence was identified in this "
                        "controlled case."
                    ),
                    limitations=(
                        "The controlled evidence is observational and does not "
                        "establish causality.",
                    ),
                ),
            ),
            proposed_confidence=proposed_confidence,
            supporting_evidence_ids=supporting,
            counterevidence_ids=counterevidence,
            next_best_action_id=action,
            rationale=(
                "The catalog action is supported by deterministic evidence and "
                "remains subject to human review."
            ),
            alternative_explanations=(
                "The household may have shifted behavior outside recorded data.",
            ),
            uncertainties=("Customer intent is not observed.",),
        ),
    )


def _fallback() -> FinishDecision:
    """Return the safe no-action proposal appended to every scripted case."""

    return FinishDecision(
        investigation_question="Can any customer action be supported safely?",
        decision_summary="Use the governed evidence-insufficiency fallback.",
        final=FinishProposal(
            driver_summary=(),
            proposed_confidence=ConfidenceLevel.LOW,
            supporting_evidence_ids=(),
            counterevidence_ids=(),
            next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE,
            rationale="Available evidence does not support a customer action.",
            alternative_explanations=(
                "The decline may reflect activity outside recorded data.",
            ),
            uncertainties=("Additional valid evidence is required.",),
        ),
    )


def _decisions(
    scenario_id: str,
    run_id: UUID,
    household_id: str,
) -> tuple[ModelDecision, ...]:
    """Return the tool sequence and finish proposals for one evaluation scenario."""

    if scenario_id == "frequency_decline":
        support = (_evidence_id(run_id, 1, ToolName.CUSTOMER_TREND, 2),)
        steps: tuple[ModelDecision, ...] = (
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _tool(ToolName.BASKET_BEHAVIOR, household_id),
            _finish(action=ActionId.VISIT_FREQUENCY_REACTIVATION, supporting=support),
        )
    elif scenario_id == "category_collapse":
        support = (
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 9),
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 13),
        )
        counterevidence = (
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 26),
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 31),
        )
        steps = (
            _tool(ToolName.CATEGORY_DECOMPOSITION, household_id),
            _finish(
                action=ActionId.CATEGORY_WINBACK,
                supporting=support,
                counterevidence=counterevidence,
            ),
        )
    elif scenario_id == "promotion_associated_decline":
        support = (_evidence_id(run_id, 1, ToolName.PROMOTION_RESPONSE, 1),)
        steps = (
            _tool(ToolName.PROMOTION_RESPONSE, household_id),
            _finish(action=ActionId.PROMOTION_VALUE_REENGAGEMENT, supporting=support),
        )
    elif scenario_id == "ambiguous_peer_comparison":
        support = (_evidence_id(run_id, 1, ToolName.PEER_COMPARISON, 1),)
        steps = (
            _tool(
                ToolName.PEER_COMPARISON,
                household_id,
                arguments={"household_id": household_id, "peer_count": 5},
            ),
            _finish(action=ActionId.MONITOR, supporting=support),
        )
    elif scenario_id == "type_a_coupon_exposure_gap":
        support = (_evidence_id(run_id, 2, ToolName.CUSTOMER_TREND, 2),)
        steps = (
            _tool(ToolName.COUPON_CAMPAIGN_HISTORY, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(
                action=ActionId.VISIT_FREQUENCY_REACTIVATION,
                supporting=support,
            ),
        )
    elif scenario_id == "persistent_promotion_timeout":
        support = (_evidence_id(run_id, 3, ToolName.CUSTOMER_TREND, 2),)
        steps = (
            _tool(ToolName.PROMOTION_RESPONSE, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(
                action=ActionId.VISIT_FREQUENCY_REACTIVATION,
                supporting=support,
            ),
        )
    elif scenario_id in {
        "broad_decline",
        "customer_specific_decline",
        "insufficient_comparison_population",
    }:
        support = (_evidence_id(run_id, 2, ToolName.CUSTOMER_TREND, 2),)
        counterevidence = (
            (_evidence_id(run_id, 1, ToolName.PEER_COMPARISON, 17),)
            if scenario_id == "broad_decline"
            else ()
        )
        steps = (
            _tool(
                ToolName.PEER_COMPARISON,
                household_id,
                arguments={"household_id": household_id, "peer_count": 5},
            ),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(
                action=ActionId.VISIT_FREQUENCY_REACTIVATION,
                supporting=support,
                counterevidence=counterevidence,
                proposed_confidence=ConfidenceLevel.HIGH,
            ),
        )
    elif scenario_id in {
        "broad_category_decline",
        "target_specific_category_decline",
    }:
        support = (
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 9),
            _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 13),
        )
        counterevidence = (
            (
                _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 26),
                _evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 31),
            )
            if scenario_id == "broad_category_decline"
            else ()
        )
        steps = (
            _tool(ToolName.CATEGORY_DECOMPOSITION, household_id),
            _finish(
                action=ActionId.CATEGORY_WINBACK,
                supporting=support,
                counterevidence=counterevidence,
                proposed_confidence=ConfidenceLevel.HIGH,
            ),
        )
    elif scenario_id == "causal_language_attack":
        support = (_evidence_id(run_id, 1, ToolName.CUSTOMER_TREND, 2),)
        steps = (
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(
                action=ActionId.VISIT_FREQUENCY_REACTIVATION,
                supporting=support,
                claim_type=ClaimType.CAUSAL,
                proposed_confidence=ConfidenceLevel.HIGH,
                summary=(
                    "Reduced recorded visit cadence caused the customer to disengage."
                ),
            ),
        )
    else:
        raise ValueError(f"Unknown synthetic evaluation scenario: {scenario_id}")
    return (*steps, _fallback())


def _run_case(
    repository: DataRepository,
    snapshot: DeclineSnapshot,
    scenario_id: str,
) -> InvestigationOutcome:
    """Execute one scenario through the real runner using its stable run identity."""

    run_id = uuid5(_EVAL_NAMESPACE, scenario_id)
    injector = (
        DemoFaultInjector(
            DemoFaultScenario.PROMOTION_TIMEOUT_ALWAYS,
            enabled=True,
        )
        if scenario_id == "persistent_promotion_timeout"
        else None
    )
    runner = InvestigationRunner(
        backend=ScriptedBackend(_decisions(scenario_id, run_id, snapshot.household_id)),
        registry=build_tool_registry(),
        repository=repository,
        action_catalog=load_action_catalog(),
        fault_injector=injector,
    )
    return runner.run(snapshot, run_id=run_id)


def _unique(values: list[str]) -> list[str]:
    """Remove repeated strings while preserving their first-seen order."""

    return list(dict.fromkeys(values))


def _scenario_frames(scenario_id: str) -> dict[str, pd.DataFrame]:
    """Build a scenario-local population while preserving source-shaped frames."""

    frames = {name: frame.copy() for name, frame in synthetic_demo_frames().items()}
    transactions = frames["transactions"]
    comparison_ids = tuple(
        sorted(
            set(transactions["household_id"].astype(str)).difference({"101"}),
            key=int,
        )
    )

    if scenario_id in {
        "customer_specific_decline",
        "target_specific_category_decline",
    }:
        baseline = transactions.loc[
            transactions["household_id"].isin(comparison_ids)
            & transactions["week"].between(1, 8)
        ].copy()
        baseline["week"] = baseline["week"] + 8
        baseline["basket_id"] = baseline.apply(
            lambda row: f"{row['household_id']}{int(row['week']):02d}{row.name}",
            axis=1,
        )
        baseline["transaction_timestamp"] = pd.to_datetime(
            baseline["transaction_timestamp"]
        ) + pd.Timedelta(days=56)
        target_rows = transactions.loc[
            (transactions["household_id"] == "101") | transactions["week"].between(1, 8)
        ]
        frames["transactions"] = pd.concat([target_rows, baseline], ignore_index=True)
    elif scenario_id in {"broad_decline", "broad_category_decline"}:
        target_recent = transactions.loc[
            (transactions["household_id"] == "101")
            & transactions["week"].between(9, 16)
        ]
        broad_recent: list[pd.DataFrame] = []
        for household_id in comparison_ids:
            household_rows = target_recent.copy()
            household_rows["household_id"] = household_id
            if household_id == comparison_ids[-1]:
                household_rows.loc[household_rows.index[-1], "week"] = 16
            household_rows["basket_id"] = [
                f"{household_id}{int(week):02d}0" for week in household_rows["week"]
            ]
            broad_recent.append(household_rows)
        baseline_and_target = transactions.loc[
            (transactions["household_id"] == "101") | transactions["week"].between(1, 8)
        ]
        frames["transactions"] = pd.concat(
            [baseline_and_target, *broad_recent], ignore_index=True
        )
    elif scenario_id == "insufficient_comparison_population":
        retained = ("101", "102", "103", "104", "105", "106")
        frames["transactions"] = transactions.loc[
            transactions["household_id"].isin(retained)
        ].copy()
        frames["demographics"] = (
            frames["demographics"]
            .loc[frames["demographics"]["household_id"].isin(retained)]
            .copy()
        )

    return frames


def normalize_synthetic_outcome(
    outcome: InvestigationOutcome, scenario_id: str
) -> dict[str, object]:
    """Materialize the public evaluator's exact typed outcome facts."""

    state = outcome.state
    selected = [item.tool_name.value for item in state.tool_history]
    partial = _unique(
        [
            item.tool_name.value
            for item in state.tool_history
            if item.final_status is ToolStatus.PARTIAL
        ]
    )
    failed = _unique(
        [
            item.tool_name.value
            for item in state.tool_history
            if item.final_status
            in {
                ToolStatus.MISSING_DATA,
                ToolStatus.RETRYABLE_ERROR,
                ToolStatus.FATAL_ERROR,
            }
        ]
    )
    referenced = (
        _unique(
            [
                *state.final_proposal.supporting_evidence_ids,
                *state.final_proposal.counterevidence_ids,
            ]
        )
        if state.final_proposal is not None
        else []
    )
    referenced = _unique(
        [
            *referenced,
            *(
                record.evidence_id
                for record in state.evidence_ledger
                if record.metric
                in {"context_classification", "category_context_classification"}
            ),
        ]
    )
    histories = {
        attempt.tool_call_id: history
        for history in state.tool_history
        for attempt in history.attempts
    }
    referenced_set = set(referenced)
    source_limitations: list[str] = []
    for record in state.evidence_ledger:
        if record.evidence_id not in referenced_set:
            continue
        source_limitations.extend(record.limitations)
        history = histories.get(record.source_tool_call_id)
        if history is not None and history.final_status is ToolStatus.PARTIAL:
            source_limitations.extend(history.limitations)
    for history in state.tool_history:
        if history.final_status is ToolStatus.PARTIAL:
            source_limitations.extend(history.limitations)
    for record in state.evidence_ledger:
        history = histories.get(record.source_tool_call_id)
        if history is not None and history.final_status is ToolStatus.PARTIAL:
            source_limitations.extend(record.limitations)
    verified = outcome.verification is not None and outcome.verification.passed
    final = outcome.verification.final if outcome.verification is not None else None
    contexts = _unique(
        [
            record.text_value
            for record in state.evidence_ledger
            if record.metric
            in {"context_classification", "category_context_classification"}
            and record.text_value in {item.value for item in ContextClassification}
        ]
    )
    rejection_codes = _unique(
        [
            issue.partition(":")[0]
            for issue in state.verification_issues
            if issue.partition(":")[0] in {item.value for item in VerificationIssueCode}
        ]
    )
    duplicate_call_count = sum(
        1
        for item in state.tool_history
        if not item.attempts
        and item.final_status is ToolStatus.INVALID_REQUEST
        and any("duplicate" in limitation.lower() for limitation in item.limitations)
    )
    population_percentile_available = any(
        record.source_tool is ToolName.PEER_COMPARISON
        and record.metric == "target_population_retailer_sales_change_percentile"
        and record.dimensions.get("comparison_scope") == "eligible_population"
        and record.dimensions.get("target_excluded") == "true"
        and record.unit == "percentile"
        and record.value is not None
        for record in state.evidence_ledger
    )
    adjustment_classifications = (
        _unique(
            [item.context_classification.value for item in final.confidence_adjustments]
        )
        if final is not None
        else []
    )
    return {
        "scenario_id": scenario_id,
        "run_id": str(state.run_id),
        "normalization_source": "outcome",
        "selected_tools": selected,
        "partial_tools": partial,
        "failed_tools": failed,
        "actual_tool_executions": sum(
            len(item.attempts) for item in state.tool_history
        ),
        "model_decisions": state.model_usage.decisions,
        "verification_passed": verified,
        "run_status": state.run_status.value,
        "ledger_evidence_ids": [item.evidence_id for item in state.evidence_ledger],
        "referenced_evidence_ids": referenced,
        "source_limitations": _unique(source_limitations),
        "propagated_limitations": (
            list(final.propagated_limitations) if final is not None else []
        ),
        "duplicate_call_count": duplicate_call_count,
        "context_classifications": contexts,
        "resolved_confidence": (
            final.resolved_confidence.value if final is not None else None
        ),
        "confidence_cap_applied": bool(
            final is not None and final.confidence_cap_applied
        ),
        "confidence_adjustment_classifications": adjustment_classifications,
        "broad_context_warning_present": (
            ContextClassification.BROAD_CONTEXT.value in adjustment_classifications
        ),
        "population_percentile_available": population_percentile_available,
        "verified_claim_types": (
            _unique([item.claim_type.value for item in final.drivers])
            if final is not None
            else []
        ),
        "verification_rejection_codes": rejection_codes,
        "next_best_action_id": (
            final.next_best_action_id.value if final is not None else None
        ),
    }


def build_normalized_synthetic_runs(output_path: Path) -> tuple[dict[str, object], ...]:
    """Execute all twelve real scripted control paths and write normalized outcomes."""

    with TemporaryDirectory(prefix="whyback-evals-") as temporary:
        summaries_list: list[dict[str, object]] = []
        for scenario_id in SCENARIO_IDS:
            prepared_dir = Path(temporary) / scenario_id / "prepared"
            prepare_frames_for_tests(_scenario_frames(scenario_id), prepared_dir)
            with DataRepository(prepared_dir) as repository:
                snapshots = detect_declines(repository)
                snapshot = next(
                    item for item in snapshots if item.household_id == "101"
                )
                summaries_list.append(
                    normalize_synthetic_outcome(
                        _run_case(repository, snapshot, scenario_id),
                        scenario_id,
                    )
                )
        summaries = tuple(summaries_list)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": 3,
        "provenance": {
            "dataset_kind": "synthetic",
            "backend": "scripted_control",
            "execution_mode": "deterministic_evaluation_no_model",
            "model_invoked": False,
        },
        "runs": summaries,
    }
    output_path.write_text(
        f"{json.dumps(document, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return summaries
