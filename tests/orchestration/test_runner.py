from __future__ import annotations

from pathlib import Path
from threading import Event, Lock
from typing import Any, cast
from uuid import UUID

import pytest
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
from whyback.methodology import ClaimType, ContextClassification
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
from whyback.tools.trend import customer_trend

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
                claim_type=ClaimType.ASSOCIATIONAL,
                supporting_evidence_ids=evidence_ids,
                no_material_counterevidence_reason=(
                    "No material counterevidence was identified."
                ),
                limitations=("The evidence is observational.",),
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


def test_context_confidence_adjustment_is_recorded_in_audit(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "context.trace.jsonl"
    backend = ScriptedBackend([_tool(), _finish()])
    with AuditJsonlWriter(trace_path) as writer:
        outcome = _run(tmp_path / "prepared", backend, audit_writer=writer)

    passed = next(
        event
        for event in read_audit_events(trace_path)
        if event.event is AuditEventName.VERIFICATION_PASSED
    )
    adjustments = passed.details["confidence_adjustments"]

    assert outcome.verification is not None and outcome.verification.final is not None
    assert isinstance(adjustments, list) and adjustments
    assert adjustments[0]["context_classification"] == (
        ContextClassification.INSUFFICIENT_CONTEXT.value
    )
    assert adjustments[0]["maximum_confidence"] == "medium"
    assert adjustments[0]["reason"]
    assert adjustments[0]["evidence_ids"] == []


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


def test_repair_cannot_upgrade_observational_evidence_to_causal(
    tmp_path: Path,
) -> None:
    valid_finish = _finish()
    assert valid_finish.final.driver_summary
    causal_driver = valid_finish.final.driver_summary[0].model_copy(
        update={"claim_type": ClaimType.CAUSAL}
    )
    causal_finish = valid_finish.model_copy(
        update={
            "final": valid_finish.final.model_copy(
                update={"driver_summary": (causal_driver,)}
            )
        }
    )
    backend = ScriptedBackend([_tool(), causal_finish, causal_finish])

    outcome = _run(tmp_path, backend)

    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.state.model_usage.decisions == 3
    assert any(
        "unsupported_causal_claim" in issue
        for issue in outcome.state.verification_issues
    )
    assert all(
        evidence.maximum_claim_type is not ClaimType.CAUSAL
        for evidence in outcome.state.evidence_ledger
    )


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


def test_real_timeout_uses_an_isolated_connection_before_retry(
    tmp_path: Path,
) -> None:
    release_first_attempt = Event()
    call_lock = Lock()
    calls = 0
    repository_ids: list[int] = []

    def block_once_then_run(
        parameters: CustomerTrendInput,
        context: ToolExecutionContext,
        repository: DataRepository,
    ) -> ToolResult:
        nonlocal calls
        with call_lock:
            calls += 1
            call_number = calls
            repository_ids.append(id(repository))
        if call_number == 1:
            release_first_attempt.wait(timeout=1.0)
            return ToolResult(
                tool_call_id=context.tool_call_id,
                tool_name=ToolName.CUSTOMER_TREND,
                status=ToolStatus.RETRYABLE_ERROR,
                limitations=("The blocked test attempt was released.",),
                retryable=True,
                provenance=ToolProvenance(
                    normalized_parameters={"household_id": context.household_id}
                ),
            )
        release_first_attempt.set()
        return customer_trend(parameters, context, repository)

    registry = ToolRegistry(
        (
            RegisteredTool(
                name=ToolName.CUSTOMER_TREND,
                input_model=CustomerTrendInput,
                handler=cast(Any, block_once_then_run),
                description="Requires household_id; blocks the first test attempt.",
            ),
        )
    )
    retry_evidence_id = "ev_call-0000000000-02-customer_trend_002"
    backend = ScriptedBackend([_tool(), _finish(evidence_ids=(retry_evidence_id,))])

    outcome = _run(
        tmp_path,
        backend,
        registry=registry,
        config=AgentConfig(tool_timeout_seconds=0.02),
    )

    assert outcome.state.run_status is RunStatus.COMPLETED
    assert [attempt.status for attempt in outcome.state.tool_history[0].attempts] == [
        ToolStatus.RETRYABLE_ERROR,
        ToolStatus.PARTIAL,
    ]
    assert calls == 2
    assert len(set(repository_ids)) == 2


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
                    claim_type=ClaimType.ASSOCIATIONAL,
                    supporting_evidence_ids=(promotion_evidence_id,),
                    no_material_counterevidence_reason=(
                        "No material counterevidence was identified."
                    ),
                    limitations=("The evidence is observational.",),
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


def test_tool_exception_secrets_are_redacted_before_state_storage(
    tmp_path: Path,
) -> None:
    secret = "sk-1234567890abcdefghijklmnop"

    def raises_secret(
        parameters: CustomerTrendInput,
        context: ToolExecutionContext,
        repository: DataRepository,
    ) -> ToolResult:
        del parameters, context, repository
        raise RuntimeError(f"provider rejected {secret}")

    registry = ToolRegistry(
        (
            RegisteredTool(
                name=ToolName.CUSTOMER_TREND,
                input_model=CustomerTrendInput,
                handler=cast(Any, raises_secret),
                description="Raises a secret-bearing test exception.",
            ),
        )
    )
    backend = ScriptedBackend(
        [_tool(), _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE)]
    )

    outcome = _run(tmp_path, backend, registry=registry)

    serialized = outcome.state.model_dump_json()
    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert secret not in serialized
    assert "[REDACTED]" in serialized


def test_repository_fork_failure_becomes_a_typed_terminal_tool_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_path = tmp_path / "trace.jsonl"

    def fail_fork(_repository: DataRepository) -> DataRepository:
        raise RuntimeError("connection setup failed")

    monkeypatch.setattr(DataRepository, "fork", fail_fork)
    backend = ScriptedBackend(
        [_tool(), _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE)]
    )
    with AuditJsonlWriter(trace_path) as writer:
        outcome = _run(tmp_path / "prepared", backend, audit_writer=writer)

    events = read_audit_events(trace_path)
    assert outcome.state.run_status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.state.tool_history[0].final_status is ToolStatus.FATAL_ERROR
    assert events[-1].event is AuditEventName.RUN_COMPLETED


def test_invalid_tool_arguments_are_not_written_raw_to_the_trace(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    backend = ScriptedBackend(
        [
            _tool(arguments={"household_id": "1", "thought_process": "private"}),
            _finish(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE),
        ]
    )
    with AuditJsonlWriter(trace_path) as writer:
        _run(tmp_path / "prepared", backend, audit_writer=writer)

    requested = next(
        event
        for event in read_audit_events(trace_path)
        if event.event is AuditEventName.TOOL_REQUESTED
    )
    assert requested.details["arguments_valid"] is False
    assert requested.details["normalized_arguments"] == {}
    assert "private" not in trace_path.read_text(encoding="utf-8")


def test_causal_model_decision_prose_is_not_stored_or_traced(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    unsafe_tool_decision = ToolDecision(
        investigation_question="The decline stemmed from fewer visits.",
        selected_tool=ToolName.CUSTOMER_TREND,
        arguments={"household_id": "1"},
        decision_summary="The customer was exposed to the offer.",
    )
    backend = ScriptedBackend([unsafe_tool_decision, _finish()])

    with AuditJsonlWriter(trace_path) as writer:
        outcome = _run(tmp_path / "prepared", backend, audit_writer=writer)

    history = outcome.state.tool_history[0]
    assert history.investigation_question == (
        "Investigate the next permitted evidence source."
    )
    assert history.decision_summary == "Choose one bounded, evidence-seeking next step."
    serialized_trace = trace_path.read_text(encoding="utf-8")
    assert "stemmed from" not in serialized_trace
    assert "was exposed" not in serialized_trace
