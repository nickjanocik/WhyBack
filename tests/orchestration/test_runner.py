from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pydantic import JsonValue

from tests.fixtures.source_frames import minimal_source_frames
from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.faults import DemoFaultInjector
from whyback.agent.runner import InvestigationRunner
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishDecision,
    FinishProposal,
    RunStatus,
    ToolDecision,
)
from whyback.config import AgentConfig
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.detection.decline import DeclineSnapshot
from whyback.observability import AuditEventName, AuditJsonlWriter, read_audit_events
from whyback.tools.contracts import (
    CustomerTrendInput,
    ToolExecutionContext,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)
from whyback.tools.registry import RegisteredTool, ToolRegistry

RUN_ID = UUID("00000000-0000-0000-0000-000000000009")
TREND_CALL_ID = "call-0000000000-01-customer_trend"
TRIP_EVIDENCE_ID = f"ev_{TREND_CALL_ID}_002"


def _snapshot() -> DeclineSnapshot:
    return DeclineSnapshot(
        household_id="1",
        baseline_start_week=1,
        baseline_end_week=1,
        recent_start_week=2,
        recent_end_week=2,
        baseline_retailer_sales_value=8.0,
        recent_retailer_sales_value=0.0,
        baseline_distinct_baskets=6,
        recent_distinct_baskets=0,
        baseline_active_weeks=4,
        recent_active_weeks=0,
        sales_drop=1.0,
        trip_drop=1.0,
        active_week_drop=1.0,
        decline_score=1.0,
        eligible=True,
        flagged=True,
    )


def _tool(
    name: ToolName = ToolName.CUSTOMER_TREND,
    *,
    arguments: dict[str, JsonValue] | None = None,
) -> ToolDecision:
    return ToolDecision(
        investigation_question="Did visit frequency change?",
        selected_tool=name,
        arguments=arguments or {"household_id": "1"},
        decision_summary="Inspect a deterministic behavioral signal.",
    )


def _finish(
    *,
    evidence_ids: tuple[str, ...] = (TRIP_EVIDENCE_ID,),
    action: ActionId = ActionId.VISIT_FREQUENCY_REACTIVATION,
) -> FinishDecision:
    drivers = (
        (
            DriverClaim(
                summary="Reduced visit frequency is a plausible driver.",
                supporting_evidence_ids=evidence_ids,
            ),
        )
        if evidence_ids
        else ()
    )
    return FinishDecision(
        investigation_question="Is the evidence sufficient to finish?",
        decision_summary="Submit the grounded conclusion for verification.",
        final=FinishProposal(
            driver_summary=drivers,
            proposed_confidence=ConfidenceLevel.HIGH,
            supporting_evidence_ids=evidence_ids,
            counterevidence_ids=(),
            next_best_action_id=action,
            rationale="The recorded behavior supports a human-reviewed test.",
            alternative_explanations=(
                "The change may reflect activity outside the recorded retailer.",
            ),
            uncertainties=("The dataset does not record customer intent.",),
        ),
    )


def _run(
    tmp_path: Path,
    backend: ScriptedBackend,
    *,
    config: AgentConfig | None = None,
    registry: ToolRegistry | None = None,
    fault_injector: DemoFaultInjector | None = None,
    audit_writer: AuditJsonlWriter | None = None,
):
    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        return InvestigationRunner(
            backend=backend,
            registry=registry or ToolRegistry(),
            repository=repository,
            action_catalog=load_action_catalog(),
            config=config,
            fault_injector=fault_injector,
            audit_writer=audit_writer,
        ).run(_snapshot(), run_id=RUN_ID)


def test_frequency_path_executes_selected_tool_then_verified_finish(
    tmp_path: Path,
) -> None:
    backend = ScriptedBackend([_tool(), _finish()])

    outcome = _run(tmp_path, backend)

    assert outcome.state.run_status is RunStatus.COMPLETED
    assert outcome.verification is not None and outcome.verification.passed
    assert len(outcome.state.tool_history) == 1
    assert outcome.state.tool_history[0].tool_name is ToolName.CUSTOMER_TREND
    assert TRIP_EVIDENCE_ID in {
        item.evidence_id for item in outcome.state.evidence_ledger
    }
    assert outcome.state.remaining_tool_budget == 4
    assert outcome.state.model_usage.decisions == 2


def test_exact_duplicate_is_refused_without_second_execution(tmp_path: Path) -> None:
    backend = ScriptedBackend([_tool(), _tool(), _finish()])

    outcome = _run(tmp_path, backend)

    assert outcome.state.run_status is RunStatus.COMPLETED
    assert len(outcome.state.tool_history) == 2
    assert len(outcome.state.tool_history[0].attempts) == 1
    assert outcome.state.tool_history[1].attempts == ()
    assert outcome.state.tool_history[1].final_status is ToolStatus.INVALID_REQUEST
    assert outcome.state.remaining_tool_budget == 4


def test_invalid_household_argument_fails_closed_without_evidence(
    tmp_path: Path,
) -> None:
    backend = ScriptedBackend(
        [
            _tool(arguments={"household_id": "2"}),
            _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE),
        ]
    )

    outcome = _run(tmp_path, backend)

    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.state.evidence_ledger == ()
    assert outcome.state.tool_history[0].final_status is ToolStatus.INVALID_REQUEST
    assert ToolName.CUSTOMER_TREND in outcome.state.unavailable_tools


def test_verifier_allows_exactly_one_structured_repair(tmp_path: Path) -> None:
    invalid = _finish(evidence_ids=("missing",), action=ActionId.MONITOR)
    repaired = _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE)
    backend = ScriptedBackend([invalid, repaired])

    outcome = _run(tmp_path, backend)

    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.state.model_usage.decisions == 2
    assert backend.calls[1].allowed_tools == ()
    assert backend.calls[1].repair_issues


def test_model_turn_budget_stops_a_loop_and_returns_safe_fallback(
    tmp_path: Path,
) -> None:
    backend = ScriptedBackend([_tool(), _tool(ToolName.BASKET_BEHAVIOR)])
    config = AgentConfig(max_model_decisions=2)

    outcome = _run(tmp_path, backend, config=config)

    assert outcome.state.remaining_turn_budget == 0
    assert outcome.state.remaining_tool_budget == 3
    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.state.model_usage.decisions == 2


def test_retryable_failure_retries_once_then_marks_tool_unavailable(
    tmp_path: Path,
) -> None:
    calls = 0

    def always_retryable(
        parameters: CustomerTrendInput,
        context: ToolExecutionContext,
        repository: DataRepository,
    ) -> ToolResult:
        del parameters, repository
        nonlocal calls
        calls += 1
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.CUSTOMER_TREND,
            status=ToolStatus.RETRYABLE_ERROR,
            limitations=("Injected transient failure.",),
            retryable=True,
            provenance=ToolProvenance(
                normalized_parameters={"household_id": context.household_id}
            ),
        )

    spec = RegisteredTool(
        name=ToolName.CUSTOMER_TREND,
        input_model=CustomerTrendInput,
        handler=cast(Any, always_retryable),
        description="Requires household_id; test-only retryable handler.",
    )
    registry = ToolRegistry((spec,))
    backend = ScriptedBackend(
        [
            _tool(),
            _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE),
        ]
    )

    outcome = _run(tmp_path, backend, registry=registry)

    assert calls == 2
    assert len(outcome.state.tool_history[0].attempts) == 2
    assert outcome.state.remaining_tool_budget == 3
    assert ToolName.CUSTOMER_TREND in outcome.state.unavailable_tools
    assert outcome.state.evidence_ledger == ()
    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE


def test_timeout_once_retries_then_uses_real_promotion_evidence(
    tmp_path: Path,
) -> None:
    promotion_evidence_id = "ev_call-0000000000-02-promotion_response_001"
    finish = FinishDecision(
        investigation_question="Is promotion evidence sufficient to finish?",
        decision_summary="Submit the association for deterministic review.",
        final=FinishProposal(
            driver_summary=(
                DriverClaim(
                    summary="Promotion-associated purchasing is a plausible driver.",
                    supporting_evidence_ids=(promotion_evidence_id,),
                ),
            ),
            proposed_confidence=ConfidenceLevel.MEDIUM,
            supporting_evidence_ids=(promotion_evidence_id,),
            counterevidence_ids=(),
            next_best_action_id=ActionId.PROMOTION_VALUE_REENGAGEMENT,
            rationale="The recorded association supports a human-reviewed test.",
            alternative_explanations=(
                "Availability does not establish household exposure.",
            ),
            uncertainties=("The relationship is observational rather than causal.",),
        ),
    )
    backend = ScriptedBackend([_tool(ToolName.PROMOTION_RESPONSE), finish])
    injector = DemoFaultInjector.from_spec(
        "promotion_response:timeout-once", enabled=True
    )

    outcome = _run(tmp_path, backend, fault_injector=injector)

    assert outcome.state.run_status is RunStatus.COMPLETED
    assert [attempt.status for attempt in outcome.state.tool_history[0].attempts] == [
        ToolStatus.RETRYABLE_ERROR,
        ToolStatus.PARTIAL,
    ]
    assert any(
        "No recent transaction rows" in item
        for item in outcome.state.tool_history[0].limitations
    )
    assert promotion_evidence_id in {
        item.evidence_id for item in outcome.state.evidence_ledger
    }
    assert outcome.state.remaining_tool_budget == 3


def test_persistent_timeout_is_traced_and_other_evidence_finishes(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    trend_evidence_id = "ev_call-0000000000-03-customer_trend_002"
    backend = ScriptedBackend(
        [
            _tool(ToolName.PROMOTION_RESPONSE),
            _tool(ToolName.CUSTOMER_TREND),
            _finish(evidence_ids=(trend_evidence_id,)),
        ]
    )
    injector = DemoFaultInjector.from_spec(
        "promotion_response:timeout-always", enabled=True
    )

    with AuditJsonlWriter(trace_path) as writer:
        outcome = _run(
            tmp_path / "prepared",
            backend,
            fault_injector=injector,
            audit_writer=writer,
        )

    events = read_audit_events(trace_path)
    names = [event.event for event in events]
    promotion_history = outcome.state.tool_history[0]
    assert outcome.state.run_status is RunStatus.COMPLETED
    assert len(promotion_history.attempts) == 2
    assert all(
        attempt.status is ToolStatus.RETRYABLE_ERROR
        for attempt in promotion_history.attempts
    )
    assert ToolName.PROMOTION_RESPONSE in outcome.state.unavailable_tools
    assert not any(
        evidence.source_tool is ToolName.PROMOTION_RESPONSE
        for evidence in outcome.state.evidence_ledger
    )
    assert names.count(AuditEventName.RETRY_SCHEDULED) == 1
    assert names.count(AuditEventName.TOOL_FAILED) == 2
    assert names[-1] is AuditEventName.RUN_COMPLETED
    assert AuditEventName.VERIFICATION_PASSED in names
