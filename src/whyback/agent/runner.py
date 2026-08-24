"""Bounded, application-owned WhyBack investigation loop."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from whyback import __version__
from whyback.agent.actions import ActionCatalog, ActionId
from whyback.agent.backend import ModelBackend, ModelBackendError
from whyback.agent.evidence import EvidenceLedger, EvidenceLedgerError
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
    ) -> None:
        self._backend = backend
        self._registry = registry
        self._repository = repository
        self._catalog = action_catalog
        self._verifier = FinalVerifier(action_catalog)
        self._config = config or AgentConfig()
        self._source_hashes = source_hashes or {}

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
            if isinstance(decision, ToolDecision):
                if repair_pending:
                    return self._fallback(
                        state,
                        "The single structured repair returned an analytical "
                        "tool call.",
                    )
                state = self._handle_tool_decision(state, decision)
                continue

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
                return InvestigationOutcome(
                    state=completed,
                    verification=verification,
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
            return state.model_copy(
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
            call_id = (
                f"call-{state.run_id.hex[:10]}-{call_index:02d}-"
                f"{decision.selected_tool.value}"
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
            next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE.value,
            rationale="Available evidence does not support a customer action.",
            alternative_explanations=(
                "The observed decline may reflect behavior outside the recorded data.",
            ),
            uncertainties=(reason,),
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
        return InvestigationOutcome(
            state=final_state,
            verification=fallback_verification,
            failure_reason=reason,
        )
