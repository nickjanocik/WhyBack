from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.evidence import EvidenceLedger, EvidenceLedgerError
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishProposal,
    InvestigationState,
    ResolvedConfidence,
    ToolAttemptRecord,
    ToolHistoryEntry,
)
from whyback.agent.verifier import FinalVerifier, VerificationIssueCode
from whyback.detection.decline import DeclineSnapshot
from whyback.tools.contracts import (
    EvidenceRecord,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)

RUN_ID = UUID("00000000-0000-0000-0000-000000000001")


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


def _evidence(
    evidence_id: str,
    *,
    tool: ToolName = ToolName.CUSTOMER_TREND,
    call_id: str = "call-trend",
    metric: str = "retailer_sales_value",
    household_id: str = "1",
    limitations: tuple[str, ...] = (),
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id=household_id,
        source_tool=tool,
        source_tool_call_id=call_id,
        metric=metric,
        baseline_value=8.0,
        recent_value=0.0,
        change=-8.0,
        unit="retailer_sales_value",
        limitations=limitations,
        query_hash="query",
    )


def _history(
    *,
    tool: ToolName = ToolName.CUSTOMER_TREND,
    call_id: str = "call-trend",
    status: ToolStatus = ToolStatus.OK,
    limitations: tuple[str, ...] = (),
    diagnostics: dict[str, object] | None = None,
) -> ToolHistoryEntry:
    return ToolHistoryEntry(
        decision_number=1,
        tool_name=tool,
        normalized_signature=f"signature-{tool.value}",
        investigation_question="What changed?",
        decision_summary="Inspect deterministic behavior.",
        normalized_arguments={"household_id": "1"},
        attempts=(
            ToolAttemptRecord(
                attempt=1,
                tool_call_id=call_id,
                status=status,
                retryable=status is ToolStatus.RETRYABLE_ERROR,
                limitations=limitations,
            ),
        ),
        final_status=status,
        provenance_diagnostics=diagnostics or {},  # type: ignore[arg-type]
        evidence_ids=("ev-1",) if status in {ToolStatus.OK, ToolStatus.PARTIAL} else (),
        limitations=limitations,
    )


def _state(
    records: tuple[EvidenceRecord, ...],
    histories: tuple[ToolHistoryEntry, ...],
) -> InvestigationState:
    return InvestigationState.start(_snapshot(), run_id=RUN_ID).model_copy(
        update={"evidence_ledger": records, "tool_history": histories}
    )


def _proposal(
    *,
    evidence_ids: tuple[str, ...] = ("ev-1",),
    action: ActionId = ActionId.MONITOR,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    summary: str = "The observed change warrants cautious monitoring.",
) -> FinishProposal:
    drivers = (
        (DriverClaim(summary=summary, supporting_evidence_ids=evidence_ids),)
        if evidence_ids
        else ()
    )
    return FinishProposal(
        driver_summary=drivers,
        proposed_confidence=confidence,
        supporting_evidence_ids=evidence_ids,
        counterevidence_ids=(),
        next_best_action_id=action.value,
        rationale="The recorded pattern supports human review.",
        alternative_explanations=(
            "The observed interval may reflect an unrecorded behavior shift.",
        ),
        uncertainties=("The data does not record a direct reason.",),
    )


def test_evidence_ledger_is_immutable_and_checks_ownership() -> None:
    record = _evidence("ev-1")
    result = ToolResult(
        tool_call_id="call-trend",
        tool_name=ToolName.CUSTOMER_TREND,
        status=ToolStatus.OK,
        evidence=(record,),
        provenance=ToolProvenance(normalized_parameters={"household_id": "1"}),
    )

    ledger = EvidenceLedger().add_tool_result(result, run_id=RUN_ID, household_id="1")

    assert ledger.records == (record,)
    with pytest.raises(ValidationError):
        ledger.records = ()  # type: ignore[misc]
    with pytest.raises(EvidenceLedgerError, match="another household"):
        EvidenceLedger().add_tool_result(
            result, run_id=RUN_ID, household_id="different"
        )
    with pytest.raises(EvidenceLedgerError, match="already exists"):
        ledger.add_tool_result(result, run_id=RUN_ID, household_id="1")


def test_verifier_caps_high_confidence_and_propagates_partial_limitation() -> None:
    limitation = "The recent window has no observed transactions."
    record = _evidence("ev-1")
    state = _state(
        (record,),
        (
            _history(
                status=ToolStatus.PARTIAL,
                limitations=(limitation,),
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, _proposal())

    assert verdict.passed
    assert verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.MEDIUM
    assert verdict.final.confidence_cap_applied
    assert verdict.final.propagated_limitations == (limitation,)
    assert verdict.final.human_review_required


def test_high_confidence_requires_two_tools_without_limitations() -> None:
    trend = _evidence("ev-trend")
    basket = _evidence(
        "ev-basket",
        tool=ToolName.BASKET_BEHAVIOR,
        call_id="call-basket",
        metric="basket_count",
    )
    state = _state(
        (trend, basket),
        (
            _history(),
            _history(tool=ToolName.BASKET_BEHAVIOR, call_id="call-basket"),
        ),
    )
    proposal = FinishProposal(
        driver_summary=(
            DriverClaim(
                summary="Multiple behavioral signals suggest an ambiguous decline.",
                supporting_evidence_ids=("ev-trend", "ev-basket"),
            ),
        ),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=("ev-trend", "ev-basket"),
        counterevidence_ids=(),
        next_best_action_id=ActionId.PERSONALIZED_CHECK_IN.value,
        rationale="Independent behavioral families support a reviewed test.",
        alternative_explanations=("A narrower driver may emerge with more data.",),
        uncertainties=("The dataset does not record customer intent.",),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert verdict.passed
    assert verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.HIGH
    assert not verdict.final.confidence_cap_applied


@pytest.mark.parametrize(
    ("proposal", "code"),
    [
        (
            _proposal(evidence_ids=("missing",)),
            VerificationIssueCode.UNKNOWN_EVIDENCE,
        ),
        (
            _proposal(summary="Retailer sales value fell 50 percent."),
            VerificationIssueCode.UNSUPPORTED_NUMERICAL_CLAIM,
        ),
        (
            _proposal(summary="The category caused the decline."),
            VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM,
        ),
        (
            _proposal(action=ActionId.CATEGORY_WINBACK),
            VerificationIssueCode.ACTION_PREREQUISITE,
        ),
    ],
)
def test_verifier_rejects_unsupported_claims(
    proposal: FinishProposal, code: VerificationIssueCode
) -> None:
    state = _state((_evidence("ev-1"),), (_history(),))

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert not verdict.passed
    assert code in {issue.code for issue in verdict.issues}


def test_verifier_rejects_wrong_owner_and_failed_source() -> None:
    wrong_owner = _state(
        (_evidence("ev-1", household_id="other"),),
        (_history(status=ToolStatus.FATAL_ERROR),),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(wrong_owner, _proposal())
    codes = {issue.code for issue in verdict.issues}

    assert VerificationIssueCode.WRONG_EVIDENCE_OWNER in codes
    assert VerificationIssueCode.INVALID_EVIDENCE_SOURCE in codes


@pytest.mark.parametrize(
    ("history", "code"),
    [
        (
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={
                    "target_excluded": False,
                    "peer_household_ids": ["1"],
                },
            ),
            VerificationIssueCode.PEER_SELF_COMPARISON,
        ),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={
                    "baseline_reconciled": True,
                    "recent_reconciled": False,
                },
            ),
            VerificationIssueCode.CATEGORY_RECONCILIATION,
        ),
        (
            _history(
                tool=ToolName.PROMOTION_RESPONSE,
                call_id="call-promotion",
                diagnostics={
                    "row_count_preserved": True,
                    "retailer_sales_value_preserved": False,
                },
            ),
            VerificationIssueCode.PROMOTION_MULTIPLICATION,
        ),
    ],
)
def test_verifier_rechecks_analytical_invariants(
    history: ToolHistoryEntry, code: VerificationIssueCode
) -> None:
    state = _state(
        (_evidence("ev-1"),),
        (_history(), history),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, _proposal())

    assert not verdict.passed
    assert code in {issue.code for issue in verdict.issues}


def test_insufficient_evidence_is_a_valid_no_action_fallback() -> None:
    proposal = _proposal(
        evidence_ids=(),
        action=ActionId.INSUFFICIENT_EVIDENCE,
        confidence=ConfidenceLevel.LOW,
    )

    verdict = FinalVerifier(load_action_catalog()).verify(_state((), ()), proposal)

    assert verdict.passed
    assert verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.INSUFFICIENT
