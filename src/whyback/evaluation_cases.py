"""Executable synthetic control cases for behavior-focused agent evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, UUID, uuid5

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
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.demo import synthetic_demo_frames
from whyback.detection.decline import DeclineSnapshot, detect_declines
from whyback.tools.contracts import ToolName, ToolStatus
from whyback.tools.registry import build_tool_registry

SCENARIO_IDS = (
    "frequency_decline",
    "category_collapse",
    "promotion_associated_decline",
    "ambiguous_peer_comparison",
    "type_a_coupon_exposure_gap",
    "persistent_promotion_timeout",
)
_EVAL_NAMESPACE = uuid5(NAMESPACE_URL, "https://github.com/whyback/evaluations")


def _evidence_id(run_id: UUID, call_index: int, tool: ToolName, ordinal: int) -> str:
    call_id = make_tool_call_id(run_id, call_index, tool)
    return f"ev_{call_id}_{ordinal:03d}"


def _tool(
    name: ToolName,
    household_id: str,
    *,
    arguments: dict[str, JsonValue] | None = None,
) -> ToolDecision:
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
) -> FinishDecision:
    return FinishDecision(
        investigation_question="Is the bounded evidence sufficient to finish?",
        decision_summary="Submit the controlled hypothesis for deterministic review.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary=(
                        "Recorded behavioral evidence is consistent with an "
                        "engagement decline that warrants a reviewed test."
                    ),
                    supporting_evidence_ids=supporting,
                ),
            ),
            proposed_confidence=ConfidenceLevel.MEDIUM,
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
    if scenario_id == "frequency_decline":
        support = (_evidence_id(run_id, 1, ToolName.CUSTOMER_TREND, 2),)
        steps: tuple[ModelDecision, ...] = (
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _tool(ToolName.BASKET_BEHAVIOR, household_id),
            _finish(action=ActionId.VISIT_FREQUENCY_REACTIVATION, supporting=support),
        )
    elif scenario_id == "category_collapse":
        support = (_evidence_id(run_id, 1, ToolName.CATEGORY_DECOMPOSITION, 5),)
        steps = (
            _tool(ToolName.CATEGORY_DECOMPOSITION, household_id),
            _finish(action=ActionId.CATEGORY_WINBACK, supporting=support),
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
        support = (_evidence_id(run_id, 2, ToolName.CUSTOMER_TREND, 1),)
        counter = (_evidence_id(run_id, 1, ToolName.COUPON_CAMPAIGN_HISTORY, 1),)
        steps = (
            _tool(ToolName.COUPON_CAMPAIGN_HISTORY, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(
                action=ActionId.MONITOR,
                supporting=support,
                counterevidence=counter,
            ),
        )
    elif scenario_id == "persistent_promotion_timeout":
        support = (_evidence_id(run_id, 3, ToolName.CUSTOMER_TREND, 1),)
        steps = (
            _tool(ToolName.PROMOTION_RESPONSE, household_id),
            _tool(ToolName.CUSTOMER_TREND, household_id),
            _finish(action=ActionId.MONITOR, supporting=support),
        )
    else:
        raise ValueError(f"Unknown synthetic evaluation scenario: {scenario_id}")
    return (*steps, _fallback())


def _run_case(
    repository: DataRepository,
    snapshot: DeclineSnapshot,
    scenario_id: str,
) -> InvestigationOutcome:
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
    return list(dict.fromkeys(values))


def _normalize(outcome: InvestigationOutcome, scenario_id: str) -> dict[str, object]:
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
    verified = outcome.verification is not None and outcome.verification.passed
    final = outcome.verification.final if outcome.verification is not None else None
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
        "duplicate_call_count": 0,
    }


def build_normalized_synthetic_runs(output_path: Path) -> tuple[dict[str, object], ...]:
    """Execute all six real scripted control paths and write normalized outcomes."""

    with TemporaryDirectory(prefix="whyback-evals-") as temporary:
        prepared_dir = Path(temporary) / "prepared"
        prepare_frames_for_tests(synthetic_demo_frames(), prepared_dir)
        with DataRepository(prepared_dir) as repository:
            snapshots = detect_declines(repository)
            snapshot = next(item for item in snapshots if item.household_id == "101")
            summaries = tuple(
                _normalize(
                    _run_case(repository, snapshot, scenario_id),
                    scenario_id,
                )
                for scenario_id in SCENARIO_IDS
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"{json.dumps({'runs': summaries}, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return summaries
