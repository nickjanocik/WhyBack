"""Bounded, application-owned WhyBack investigation loop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from whyback import __version__
from whyback.agent.actions import ActionCatalog, ActionId
from whyback.agent.backend import ModelBackend, ModelBackendError
from whyback.agent.evidence import EvidenceLedger, EvidenceLedgerError
from whyback.agent.faults import DemoFaultInjector
from whyback.agent.prompts import PROMPT_HASH, PROMPT_VERSION
from whyback.agent.state import (
    ConfidenceLevel,
    FinishProposal,
    InvestigationState,
    ModelUsage,
    ResolvedConfidence,
    RunStatus,
    ToolAttemptRecord,
    ToolDecision,
    ToolHistoryEntry,
)
from whyback.agent.verifier import FinalVerifier, VerificationResult
from whyback.config import SOURCE_COMMIT, AgentConfig
from whyback.data.repository import DataRepository
from whyback.detection.decline import DeclineSnapshot
from whyback.observability import AuditEvent, AuditEventName, AuditJsonlWriter
from whyback.observability.events import utc_now
from whyback.tools.contracts import (
    SUCCESS_STATUSES,
    ToolExecutionContext,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)
from whyback.tools.registry import ToolRegistry


class InvestigationOutcome(BaseModel):
    """Final state and verification verdict returned to reporting boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: InvestigationState
    verification: VerificationResult | None = None
    failure_reason: str | None = None


def _stable_signature(name: ToolName, arguments: dict[str, JsonValue]) -> str:
    serialized = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{name.value}:{serialized}".encode()).hexdigest()


def make_tool_call_id(run_id: UUID, call_index: int, name: ToolName) -> str:
    """Return the stable call identifier used by traces and scripted plans."""

    if call_index < 1:
        raise ValueError("Tool call indexes start at one")
    return f"call-{run_id.hex[:10]}-{call_index:02d}-{name.value}"


def _append_unique[T](values: tuple[T, ...], item: T) -> tuple[T, ...]:
    return values if item in values else (*values, item)


def _tool_failure(
    *,
    context: ToolExecutionContext,
    name: ToolName,
    status: ToolStatus,
    limitation: str,
    parameters: dict[str, JsonValue],
) -> ToolResult:
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=name,
        status=status,
        limitations=(limitation,),
        retryable=status is ToolStatus.RETRYABLE_ERROR,
        provenance=ToolProvenance(
            dataset_source_commit=context.source_commit,
            source_hashes=context.source_hashes,
            normalized_parameters=parameters,
            rows_examined=0,
            application_version=context.application_version,
        ),
    )


class InvestigationRunner:
    """Enforce one-action turns, budgets, duplicate refusal, retries, and repair."""

    def __init__(
        self,
        *,
        backend: ModelBackend,
        registry: ToolRegistry,
        repository: DataRepository,
        action_catalog: ActionCatalog,
        config: AgentConfig | None = None,
        source_hashes: dict[str, str] | None = None,
        fault_injector: DemoFaultInjector | None = None,
        audit_writer: AuditJsonlWriter | None = None,
        event_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._backend = backend
        self._registry = registry
        self._repository = repository
        self._catalog = action_catalog
        self._verifier = FinalVerifier(action_catalog)
        self._config = config or AgentConfig()
        self._source_hashes = source_hashes or {}
        self._fault_injector = fault_injector
        self._audit_writer = audit_writer
        self._event_clock = event_clock or utc_now

    def _emit(
        self,
        state: InvestigationState,
        event: AuditEventName,
        details: dict[str, object] | None = None,
    ) -> None:
        if self._audit_writer is None:
            return
        self._audit_writer.append(
            AuditEvent(
                timestamp=self._event_clock(),
                event=event,
                run_id=state.run_id,
                household_id=state.household_id,
                details=cast(dict[str, JsonValue], details or {}),
            )
        )

    def run(
        self,
        detector_snapshot: DeclineSnapshot,
        *,
        run_id: UUID | None = None,
    ) -> InvestigationOutcome:
        state = InvestigationState.start(
            detector_snapshot,
            max_tool_executions=self._config.max_tool_executions,
            max_model_decisions=self._config.max_model_decisions,
            run_id=run_id,
        ).model_copy(
            update={
                "open_questions": (
                    "Which observed behavioral changes best explain the decline?",
                    "What evidence argues against the leading explanation?",
                )
            }
        )
        self._emit(
            state,
            AuditEventName.RUN_STARTED,
            {
                "model": self._backend.model_name,
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "dataset_source_commit": SOURCE_COMMIT,
                "application_version": __version__,
                "remaining_tool_budget": state.remaining_tool_budget,
                "remaining_turn_budget": state.remaining_turn_budget,
                "demo_fault": (
                    self._fault_injector.scenario.value
                    if self._fault_injector is not None
                    else None
                ),
                "decline_score": state.detector_snapshot.decline_score,
            },
        )
        repair_pending = False
        repair_attempted = False

        while state.remaining_turn_budget > 0:
            if repair_pending or state.remaining_tool_budget == 0:
                definitions = ()
            else:
                allowed = tuple(
                    name
                    for name in self._registry.names
                    if name not in state.unavailable_tools
                )
                definitions = self._registry.definitions(allowed)
            repair_issues = state.verification_issues if repair_pending else ()
            self._emit(
                state,
                AuditEventName.MODEL_DECISION_REQUESTED,
                {
                    "model": self._backend.model_name,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_hash": PROMPT_HASH,
                    "allowed_tools": [item.name.value for item in definitions],
                    "finish_available": True,
                    "repair_requested": repair_pending,
                    "remaining_tool_budget": state.remaining_tool_budget,
                    "remaining_turn_budget": state.remaining_turn_budget,
                },
            )
            try:
                backend_decision = self._backend.decide_next_step(
                    state,
                    definitions,
                    repair_issues=repair_issues,
                )
            except ModelBackendError as error:
                failed_usage = state.model_usage.plus(ModelUsage(decisions=1))
                failed_state = state.model_copy(
                    update={
                        "remaining_turn_budget": state.remaining_turn_budget - 1,
                        "model_usage": failed_usage,
                        "run_status": RunStatus.FAILED,
                        "verification_issues": (str(error),),
                    }
                )
                self._emit(
                    failed_state,
                    AuditEventName.RUN_COMPLETED,
                    {
                        "status": failed_state.run_status.value,
                        "failure_type": type(error).__name__,
                        "message": str(error),
                    },
                )
                return InvestigationOutcome(
                    state=failed_state,
                    failure_reason=str(error),
                )

            reported = backend_decision.usage
            usage = ModelUsage(
                decisions=1,
                input_tokens=reported.input_tokens,
                output_tokens=reported.output_tokens,
                total_tokens=reported.total_tokens,
                latency_ms=reported.latency_ms,
            )
            state = state.model_copy(
                update={
                    "remaining_turn_budget": state.remaining_turn_budget - 1,
                    "model_usage": state.model_usage.plus(usage),
                }
            )
            decision = backend_decision.decision
            self._emit(
                state,
                AuditEventName.MODEL_DECISION_RECEIVED,
                {
                    "provider_call_id": backend_decision.provider_call_id,
                    "model": backend_decision.model,
                    "decision_kind": decision.kind,
                    "investigation_question": decision.investigation_question,
                    "decision_summary": decision.decision_summary,
                    "selected_tool": (
                        decision.selected_tool.value
                        if isinstance(decision, ToolDecision)
                        else None
                    ),
                    "input_tokens": reported.input_tokens,
                    "output_tokens": reported.output_tokens,
                    "latency_ms": reported.latency_ms,
                },
            )
            if isinstance(decision, ToolDecision):
                self._emit(
                    state,
                    AuditEventName.TOOL_REQUESTED,
                    {
                        "tool_name": decision.selected_tool.value,
                        "arguments": decision.arguments,
                        "investigation_question": decision.investigation_question,
                    },
                )
                if repair_pending:
                    return self._fallback(
                        state,
                        "The single structured repair returned an analytical "
                        "tool call.",
                    )
                state = self._handle_tool_decision(state, decision)
                continue

            self._emit(
                state,
                AuditEventName.FINISH_REQUESTED,
                {
                    "next_best_action_id": decision.final.next_best_action_id,
                    "proposed_confidence": decision.final.proposed_confidence.value,
                    "supporting_evidence_ids": list(
                        decision.final.supporting_evidence_ids
                    ),
                    "counterevidence_ids": list(decision.final.counterevidence_ids),
                },
            )
            self._emit(
                state,
                AuditEventName.VERIFICATION_STARTED,
                {
                    "repair_attempted": repair_attempted,
                    "referenced_evidence_count": len(
                        decision.final.supporting_evidence_ids
                    )
                    + len(decision.final.counterevidence_ids),
                },
            )
            verification = self._verifier.verify(state, decision.final)
            if verification.passed:
                assert verification.final is not None
                completed = state.model_copy(
                    update={
                        "run_status": (
                            RunStatus.INSUFFICIENT_EVIDENCE
                            if verification.final.next_best_action_id
                            is ActionId.INSUFFICIENT_EVIDENCE
                            else RunStatus.COMPLETED
                        ),
                        "final_proposal": decision.final,
                        "resolved_confidence": verification.final.resolved_confidence,
                        "verification_issues": (),
                    }
                )
                self._emit(
                    completed,
                    AuditEventName.VERIFICATION_PASSED,
                    {
                        "next_best_action_id": (
                            verification.final.next_best_action_id.value
                        ),
                        "resolved_confidence": (
                            verification.final.resolved_confidence.value
                        ),
                        "confidence_cap_applied": (
                            verification.final.confidence_cap_applied
                        ),
                    },
                )
                self._emit(
                    completed,
                    AuditEventName.RUN_COMPLETED,
                    {
                        "status": completed.run_status.value,
                        "next_best_action_id": (
                            verification.final.next_best_action_id.value
                        ),
                        "human_review_required": True,
                    },
                )
                return InvestigationOutcome(
                    state=completed,
                    verification=verification,
                )
            self._emit(
                state,
                AuditEventName.VERIFICATION_REJECTED,
                {
                    "issues": [
                        {"code": issue.code.value, "message": issue.message}
                        for issue in verification.issues
                    ],
                    "repair_available": (
                        not repair_attempted and state.remaining_turn_budget > 0
                    ),
                },
            )
            if not repair_attempted and state.remaining_turn_budget > 0:
                repair_attempted = True
                repair_pending = True
                state = state.model_copy(
                    update={
                        "verification_issues": tuple(
                            f"{issue.code.value}: {issue.message}"
                            for issue in verification.issues
                        )
                    }
                )
                continue
            return self._fallback(
                state,
                "Final verification failed after the permitted repair attempt.",
                prior_verification=verification,
            )

        return self._fallback(state, "The model-decision budget was exhausted.")

    def _handle_tool_decision(
        self, state: InvestigationState, decision: ToolDecision
    ) -> InvestigationState:
        decision_number = state.model_usage.decisions
        if state.remaining_tool_budget == 0:
            return state.model_copy(
                update={
                    "open_questions": (*state.open_questions, "Tool budget exhausted."),
                }
            )

        validated: BaseModel | None = None
        normalized: dict[str, JsonValue]
        try:
            validated, signature = self._registry.normalize_arguments(
                decision.selected_tool, decision.arguments
            )
            normalized = cast(dict[str, JsonValue], validated.model_dump(mode="json"))
        except (KeyError, ValidationError):
            normalized = dict(decision.arguments)
            signature = _stable_signature(decision.selected_tool, normalized)

        if signature in state.requested_signatures:
            history = ToolHistoryEntry(
                decision_number=decision_number,
                tool_name=decision.selected_tool,
                normalized_signature=signature,
                investigation_question=decision.investigation_question,
                decision_summary=decision.decision_summary,
                normalized_arguments=normalized,
                attempts=(),
                final_status=ToolStatus.INVALID_REQUEST,
                limitations=(
                    "Exact duplicate tool and normalized arguments were refused.",
                ),
            )
            refused_state = state.model_copy(
                update={
                    "tool_history": (*state.tool_history, history),
                    "failed_or_partial_tools": _append_unique(
                        state.failed_or_partial_tools, decision.selected_tool
                    ),
                    "open_questions": (
                        *state.open_questions,
                        "Choose a different analytical question or finish.",
                    ),
                }
            )
            self._emit(
                refused_state,
                AuditEventName.TOOL_FAILED,
                {
                    "tool_name": decision.selected_tool.value,
                    "status": ToolStatus.INVALID_REQUEST.value,
                    "duplicate_refused": True,
                    "normalized_signature": signature,
                    "limitations": list(history.limitations),
                },
            )
            return refused_state

        state = state.model_copy(
            update={
                "requested_signatures": (*state.requested_signatures, signature),
            }
        )
        attempts: list[ToolAttemptRecord] = []
        final_result: ToolResult | None = None
        max_attempts = 1 + self._config.max_retryable_retries
        while len(attempts) < max_attempts and state.remaining_tool_budget > 0:
            attempt_number = len(attempts) + 1
            call_index = (
                sum(len(item.attempts) for item in state.tool_history) + attempt_number
            )
            call_id = make_tool_call_id(
                state.run_id, call_index, decision.selected_tool
            )
            context = ToolExecutionContext(
                run_id=state.run_id,
                tool_call_id=call_id,
                household_id=state.household_id,
                window=state.window,
                source_commit=SOURCE_COMMIT,
                source_hashes=self._source_hashes,
                application_version=__version__,
            )
            self._emit(
                state,
                AuditEventName.TOOL_STARTED,
                {
                    "tool_name": decision.selected_tool.value,
                    "tool_call_id": call_id,
                    "attempt": attempt_number,
                    "normalized_arguments": normalized,
                    "remaining_tool_budget": state.remaining_tool_budget,
                },
            )
            if validated is not None and (
                str(getattr(validated, "household_id", "")) != state.household_id
            ):
                result = _tool_failure(
                    context=context,
                    name=decision.selected_tool,
                    status=ToolStatus.INVALID_REQUEST,
                    limitation=(
                        "Tool household_id must match the active investigation "
                        "household."
                    ),
                    parameters=normalized,
                )
            elif self._fault_injector is not None:
                result = self._fault_injector.intercept(
                    name=decision.selected_tool,
                    attempt=attempt_number,
                    context=context,
                    normalized_parameters=normalized,
                ) or self._execute_with_timeout(
                    decision.selected_tool,
                    decision.arguments,
                    context,
                    normalized,
                )
            else:
                result = self._execute_with_timeout(
                    decision.selected_tool,
                    decision.arguments,
                    context,
                    normalized,
                )
            attempts.append(
                ToolAttemptRecord(
                    attempt=attempt_number,
                    tool_call_id=result.tool_call_id,
                    status=result.status,
                    retryable=result.retryable,
                    elapsed_ms=result.provenance.elapsed_ms,
                    limitations=result.limitations,
                )
            )
            state = state.model_copy(
                update={"remaining_tool_budget": state.remaining_tool_budget - 1}
            )
            final_result = result
            event_name = (
                AuditEventName.TOOL_COMPLETED
                if result.status is ToolStatus.OK
                else (
                    AuditEventName.TOOL_PARTIAL
                    if result.status is ToolStatus.PARTIAL
                    else AuditEventName.TOOL_FAILED
                )
            )
            self._emit(
                state,
                event_name,
                {
                    "tool_name": result.tool_name.value,
                    "tool_call_id": result.tool_call_id,
                    "attempt": attempt_number,
                    "status": result.status.value,
                    "retryable": result.retryable,
                    "latency_ms": result.provenance.elapsed_ms,
                    "rows_examined": result.provenance.rows_examined,
                    "query_hash": result.provenance.query_hash,
                    "evidence_ids": [item.evidence_id for item in result.evidence],
                    "limitations": list(result.limitations),
                    "diagnostics": result.provenance.diagnostics,
                    "tool_result": result.model_dump(mode="json"),
                },
            )
            will_retry = (
                result.retryable
                and len(attempts) < max_attempts
                and state.remaining_tool_budget > 0
            )
            if will_retry:
                self._emit(
                    state,
                    AuditEventName.RETRY_SCHEDULED,
                    {
                        "tool_name": result.tool_name.value,
                        "after_tool_call_id": result.tool_call_id,
                        "next_attempt": attempt_number + 1,
                        "remaining_tool_budget": state.remaining_tool_budget,
                    },
                )
            if not result.retryable:
                break

        assert final_result is not None
        ledger = EvidenceLedger(records=state.evidence_ledger)
        try:
            updated_ledger = ledger.add_tool_result(
                final_result,
                run_id=state.run_id,
                household_id=state.household_id,
            )
            for evidence in final_result.evidence:
                self._emit(
                    state,
                    AuditEventName.EVIDENCE_ADDED,
                    {
                        "evidence_id": evidence.evidence_id,
                        "source_tool": evidence.source_tool.value,
                        "source_tool_call_id": evidence.source_tool_call_id,
                        "metric": evidence.metric,
                        "limitations": list(evidence.limitations),
                    },
                )
        except EvidenceLedgerError as error:
            final_result = _tool_failure(
                context=ToolExecutionContext(
                    run_id=state.run_id,
                    tool_call_id=final_result.tool_call_id,
                    household_id=state.household_id,
                    window=state.window,
                    source_hashes=self._source_hashes,
                ),
                name=decision.selected_tool,
                status=ToolStatus.FATAL_ERROR,
                limitation=f"Evidence ledger rejected tool output: {error}",
                parameters=normalized,
            )
            updated_ledger = ledger

        history = ToolHistoryEntry(
            decision_number=decision_number,
            tool_name=decision.selected_tool,
            normalized_signature=signature,
            investigation_question=decision.investigation_question,
            decision_summary=decision.decision_summary,
            normalized_arguments=normalized,
            attempts=tuple(attempts),
            final_status=final_result.status,
            model_summary=final_result.model_summary,
            provenance_diagnostics=final_result.provenance.diagnostics,
            evidence_ids=tuple(item.evidence_id for item in final_result.evidence),
            limitations=final_result.limitations,
        )
        failed_or_partial = state.failed_or_partial_tools
        unavailable = state.unavailable_tools
        if final_result.status is not ToolStatus.OK:
            failed_or_partial = _append_unique(
                failed_or_partial, decision.selected_tool
            )
        if final_result.status not in SUCCESS_STATUSES:
            unavailable = _append_unique(unavailable, decision.selected_tool)
        return state.model_copy(
            update={
                "tool_history": (*state.tool_history, history),
                "evidence_ledger": updated_ledger.records,
                "failed_or_partial_tools": failed_or_partial,
                "unavailable_tools": unavailable,
            }
        )

    def _execute_with_timeout(
        self,
        name: ToolName,
        arguments: dict[str, JsonValue],
        context: ToolExecutionContext,
        normalized: dict[str, JsonValue],
    ) -> ToolResult:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whyback-tool")
        future = executor.submit(
            self._registry.execute,
            name,
            arguments,
            context,
            self._repository,
        )
        timed_out = False
        try:
            return future.result(timeout=self._config.tool_timeout_seconds)
        except FutureTimeoutError:
            timed_out = True
            future.cancel()
            return _tool_failure(
                context=context,
                name=name,
                status=ToolStatus.RETRYABLE_ERROR,
                limitation=(
                    "Tool exceeded the configured "
                    f"{self._config.tool_timeout_seconds:g}-second timeout."
                ),
                parameters=normalized,
            )
        except Exception as error:
            return _tool_failure(
                context=context,
                name=name,
                status=ToolStatus.FATAL_ERROR,
                limitation=f"Tool raised {type(error).__name__}: {error}",
                parameters=normalized,
            )
        finally:
            executor.shutdown(wait=not timed_out, cancel_futures=True)

    def _fallback(
        self,
        state: InvestigationState,
        reason: str,
        *,
        prior_verification: VerificationResult | None = None,
    ) -> InvestigationOutcome:
        proposal = FinishProposal(
            driver_summary=(),
            proposed_confidence=ConfidenceLevel.LOW,
            supporting_evidence_ids=(),
            counterevidence_ids=(),
            next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE,
            rationale="Available evidence does not support a customer action.",
            alternative_explanations=(
                "The observed decline may reflect behavior outside the recorded data.",
            ),
            uncertainties=(reason,),
        )
        self._emit(
            state,
            AuditEventName.VERIFICATION_STARTED,
            {
                "deterministic_fallback": True,
                "reason": reason,
                "referenced_evidence_count": 0,
            },
        )
        fallback_verification = self._verifier.verify(state, proposal)
        issues = tuple(
            dict.fromkeys(
                (
                    *(state.verification_issues),
                    *(
                        f"{item.code.value}: {item.message}"
                        for item in (
                            prior_verification.issues
                            if prior_verification is not None
                            else ()
                        )
                    ),
                    reason,
                )
            )
        )
        if fallback_verification.passed:
            final_state = state.model_copy(
                update={
                    "run_status": RunStatus.INSUFFICIENT_EVIDENCE,
                    "final_proposal": proposal,
                    "resolved_confidence": ResolvedConfidence.INSUFFICIENT,
                    "verification_issues": issues,
                }
            )
            self._emit(
                final_state,
                AuditEventName.VERIFICATION_PASSED,
                {
                    "deterministic_fallback": True,
                    "next_best_action_id": ActionId.INSUFFICIENT_EVIDENCE.value,
                    "resolved_confidence": ResolvedConfidence.INSUFFICIENT.value,
                    "confidence_cap_applied": True,
                },
            )
            self._emit(
                final_state,
                AuditEventName.RUN_COMPLETED,
                {
                    "status": final_state.run_status.value,
                    "next_best_action_id": ActionId.INSUFFICIENT_EVIDENCE.value,
                    "human_review_required": True,
                    "fallback_reason": reason,
                },
            )
            return InvestigationOutcome(
                state=final_state,
                verification=fallback_verification,
                failure_reason=reason,
            )
        final_state = state.model_copy(
            update={
                "run_status": RunStatus.FAILED,
                "final_proposal": proposal,
                "verification_issues": (
                    *issues,
                    *(
                        f"{item.code.value}: {item.message}"
                        for item in fallback_verification.issues
                    ),
                ),
            }
        )
        self._emit(
            final_state,
            AuditEventName.VERIFICATION_REJECTED,
            {
                "deterministic_fallback": True,
                "issues": [
                    {"code": item.code.value, "message": item.message}
                    for item in fallback_verification.issues
                ],
                "repair_available": False,
            },
        )
        self._emit(
            final_state,
            AuditEventName.RUN_COMPLETED,
            {
                "status": final_state.run_status.value,
                "failure_type": "fallback_verification_failed",
                "fallback_reason": reason,
            },
        )
        return InvestigationOutcome(
            state=final_state,
            verification=fallback_verification,
            failure_reason=reason,
        )
