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
from whyback.methodology import (
    ClaimType,
    ContextClassification,
    ContextPolicy,
    classify_context,
)
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
    baseline_value: float = 8.0,
    recent_value: float = 0.0,
    value: float | None = None,
    dimensions: dict[str, str] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id=household_id,
        source_tool=tool,
        source_tool_call_id=call_id,
        metric=metric,
        dimensions=dimensions or {},
        baseline_value=baseline_value,
        recent_value=recent_value,
        value=value,
        change=recent_value - baseline_value,
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


def _context_evidence(
    classification: ContextClassification,
    *,
    evidence_id: str = "ev-context",
    call_id: str = "call-peer",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id="1",
        source_tool=ToolName.PEER_COMPARISON,
        source_tool_call_id=call_id,
        metric="context_classification",
        dimensions={"target_excluded": "true"},
        text_value=classification.value,
        unit="classification",
        query_hash="context-query",
    )


def _category_context_evidence(
    classification: ContextClassification,
    *,
    evidence_id: str = "ev-category-context",
    call_id: str = "call-category",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id="1",
        source_tool=ToolName.CATEGORY_DECOMPOSITION,
        source_tool_call_id=call_id,
        metric="category_context_classification",
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
            "target_excluded": "true",
        },
        text_value=classification.value,
        unit="classification",
        query_hash="category-context-query",
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
    counterevidence_ids: tuple[str, ...] = (),
    action: ActionId = ActionId.MONITOR,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    summary: str = "The observed change warrants cautious monitoring.",
) -> FinishProposal:
    drivers = (
        (
            DriverClaim(
                summary=summary,
                claim_type=ClaimType.ASSOCIATIONAL,
                supporting_evidence_ids=evidence_ids,
                counterevidence_ids=counterevidence_ids,
                no_material_counterevidence_reason=(
                    None
                    if counterevidence_ids
                    else "No material counterevidence was identified."
                ),
                limitations=("The evidence is observational.",),
            ),
        )
        if evidence_ids
        else ()
    )
    return FinishProposal(
        driver_summary=drivers,
        proposed_confidence=confidence,
        supporting_evidence_ids=evidence_ids,
        counterevidence_ids=counterevidence_ids,
        next_best_action_id=action,
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
    with pytest.raises(TypeError, match="immutable"):
        record.dimensions["tampered"] = "yes"
    with pytest.raises(EvidenceLedgerError, match="another household"):
        EvidenceLedger().add_tool_result(
            result, run_id=RUN_ID, household_id="different"
        )
    with pytest.raises(EvidenceLedgerError, match="already exists"):
        ledger.add_tool_result(result, run_id=RUN_ID, household_id="1")


def test_driver_claim_requires_claim_type_and_counterevidence_consideration() -> None:
    with pytest.raises(ValidationError, match="counterevidence"):
        DriverClaim(
            summary="A recorded pattern is associated with decline.",
            claim_type=ClaimType.ASSOCIATIONAL,
            supporting_evidence_ids=("ev-1",),
            limitations=("The evidence is observational.",),
        )


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
    assert limitation in verdict.final.propagated_limitations
    assert any(
        "missing context" in item.casefold()
        for item in verdict.final.propagated_limitations
    )
    assert verdict.final.confidence_adjustments[0].context_classification is (
        ContextClassification.INSUFFICIENT_CONTEXT
    )
    assert verdict.final.human_review_required


def test_high_confidence_requires_two_tools_without_limitations() -> None:
    trend = _evidence("ev-trend")
    peer = _evidence(
        "ev-peer",
        tool=ToolName.PEER_COMPARISON,
        call_id="call-peer",
        metric="target_retailer_sales_change_percentile",
        value=20.0,
    )
    context = _context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    state = _state(
        (trend, peer, context),
        (
            _history(),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )
    proposal = FinishProposal(
        driver_summary=(
            DriverClaim(
                summary="Multiple behavioral signals suggest an ambiguous decline.",
                claim_type=ClaimType.ASSOCIATIONAL,
                supporting_evidence_ids=("ev-trend", "ev-peer"),
                no_material_counterevidence_reason=(
                    "No material counterevidence was identified."
                ),
                limitations=("The evidence is observational.",),
            ),
        ),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=("ev-trend", "ev-peer"),
        counterevidence_ids=(),
        next_best_action_id=ActionId.PERSONALIZED_CHECK_IN,
        rationale="Independent behavioral families support a reviewed test.",
        alternative_explanations=("A narrower driver may emerge with more data.",),
        uncertainties=("The dataset does not record customer intent.",),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert verdict.passed
    assert verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.HIGH
    assert not verdict.final.confidence_cap_applied


def test_personalized_check_in_rejects_support_for_a_narrower_action() -> None:
    trend = _evidence("ev-trend", metric="distinct_trips")
    basket = _evidence(
        "ev-basket",
        tool=ToolName.BASKET_BEHAVIOR,
        call_id="call-basket",
        metric="basket_count",
    )
    state = _state(
        (trend, basket),
        (_history(), _history(tool=ToolName.BASKET_BEHAVIOR, call_id="call-basket")),
    )
    proposal = FinishProposal(
        driver_summary=(
            DriverClaim(
                summary="Recorded visit cadence is a plausible decline driver.",
                claim_type=ClaimType.ASSOCIATIONAL,
                supporting_evidence_ids=("ev-trend", "ev-basket"),
                no_material_counterevidence_reason=(
                    "No material counterevidence was identified."
                ),
                limitations=("The evidence is observational.",),
            ),
        ),
        proposed_confidence=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=("ev-trend", "ev-basket"),
        counterevidence_ids=(),
        next_best_action_id=ActionId.PERSONALIZED_CHECK_IN,
        rationale="Distinct computed measures support human review.",
        alternative_explanations=("Behavior may have shifted elsewhere.",),
        uncertainties=("Customer intent is not observed.",),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_CONTRAINDICATION in {
        issue.code for issue in verdict.issues
    }


def test_insufficient_action_rejects_a_satisfiable_ledger() -> None:
    state = _state(
        (_evidence("ev-1", metric="distinct_trips"),),
        (_history(),),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(evidence_ids=(), action=ActionId.INSUFFICIENT_EVIDENCE),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_CONTRAINDICATION in {
        issue.code for issue in verdict.issues
    }


def test_missing_context_keeps_monitor_available_despite_narrower_policy() -> None:
    state = _state(
        (_evidence("ev-1", metric="distinct_trips"),),
        (_history(),),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, _proposal())

    assert verdict.passed and verdict.final is not None
    assert verdict.final.next_best_action_id is ActionId.MONITOR
    assert verdict.final.resolved_confidence is ResolvedConfidence.MEDIUM
    assert verdict.final.confidence_adjustments[0].context_classification is (
        ContextClassification.INSUFFICIENT_CONTEXT
    )


def test_category_action_rejects_when_unknown_loss_dominates() -> None:
    known = _evidence(
        "ev-known",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    unknown = _evidence(
        "ev-unknown",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="unknown_group_retailer_sales_value",
        baseline_value=20.0,
        recent_value=5.0,
        dimensions={"direction": "loss"},
    )
    state = _state(
        (known, unknown),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={
                    "baseline_reconciled": True,
                    "recent_reconciled": True,
                },
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=("ev-known",),
            action=ActionId.CATEGORY_WINBACK,
        ),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_CONTRAINDICATION in {
        issue.code for issue in verdict.issues
    }


def test_broad_category_context_caps_category_driver_at_low() -> None:
    category = _evidence(
        "ev-category",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    category_context = _category_context_evidence(ContextClassification.BROAD_CONTEXT)
    overall_context = _context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    state = _state(
        (category, category_context, overall_context),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={
                    "baseline_reconciled": True,
                    "recent_reconciled": True,
                },
            ),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    omitted = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(evidence_ids=("ev-category",), action=ActionId.CATEGORY_WINBACK),
    )
    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=("ev-category",),
            counterevidence_ids=("ev-category-context",),
            action=ActionId.CATEGORY_WINBACK,
        ),
    )

    assert VerificationIssueCode.MATERIAL_COUNTEREVIDENCE_OMITTED in {
        issue.code for issue in omitted.issues
    }
    assert verdict.passed and verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.LOW
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is ContextClassification.BROAD_CONTEXT
    assert adjustment.evidence_ids == ("ev-category-context",)
    assert "not uniquely customer-specific" in adjustment.reason


def test_conflicting_category_context_uses_conservative_low_cap() -> None:
    category = _evidence(
        "ev-category",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    insufficient = _category_context_evidence(
        ContextClassification.INSUFFICIENT_CONTEXT,
        evidence_id="ev-category-insufficient",
    )
    broad = _category_context_evidence(
        ContextClassification.BROAD_CONTEXT,
        evidence_id="ev-category-broad",
        call_id="call-category-2",
    )
    overall = _context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    state = _state(
        (category, insufficient, broad, overall),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category-2",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=("ev-category",),
            counterevidence_ids=("ev-category-broad",),
            action=ActionId.CATEGORY_WINBACK,
        ),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.LOW
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is ContextClassification.BROAD_CONTEXT
    assert adjustment.evidence_ids == (
        "ev-category-insufficient",
        "ev-category-broad",
    )


def test_material_category_context_remains_citable_for_nine_categories() -> None:
    category_records = tuple(
        _evidence(
            f"ev-category-{index}",
            tool=ToolName.CATEGORY_DECOMPOSITION,
            call_id="call-category",
            metric="category_retailer_sales_value",
            baseline_value=10.0,
            recent_value=5.0,
            dimensions={
                "department": "GROCERY",
                "product_category": f"CATEGORY_{index}",
                "direction": "loss",
            },
        )
        for index in range(9)
    )
    context_records = tuple(
        _category_context_evidence(
            ContextClassification.BROAD_CONTEXT,
            evidence_id=f"ev-category-context-{index}",
        ).model_copy(
            update={
                "dimensions": {
                    "department": "GROCERY",
                    "product_category": f"CATEGORY_{index}",
                    "direction": "loss",
                    "target_excluded": "true",
                }
            }
        )
        for index in range(9)
    )
    support_ids = tuple(record.evidence_id for record in category_records)
    counter_ids = tuple(record.evidence_id for record in context_records)
    state = _state(
        (*category_records, *context_records),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=support_ids,
            counterevidence_ids=counter_ids,
            action=ActionId.CATEGORY_WINBACK,
        ),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.counterevidence_ids == counter_ids


def test_missing_category_context_caps_and_propagates_limitation() -> None:
    category = _evidence(
        "ev-category",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    overall_context = _context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    state = _state(
        (category, overall_context),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={
                    "baseline_reconciled": True,
                    "recent_reconciled": True,
                },
            ),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(evidence_ids=("ev-category",), action=ActionId.CATEGORY_WINBACK),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.MEDIUM
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is (
        ContextClassification.INSUFFICIENT_CONTEXT
    )
    assert any(
        "category-population context was unavailable" in item.casefold()
        for item in verdict.final.propagated_limitations
    )


def test_each_cited_category_requires_matching_context() -> None:
    soup = _evidence(
        "ev-soup",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    dairy = _evidence(
        "ev-dairy",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=12.0,
        recent_value=4.0,
        dimensions={
            "department": "DAIRY",
            "product_category": "MILK",
            "direction": "loss",
        },
    )
    soup_context = _category_context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    overall_context = _context_evidence(ContextClassification.CUSTOMER_SPECIFIC)
    state = _state(
        (soup, dairy, soup_context, overall_context),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=("ev-soup", "ev-dairy"),
            action=ActionId.CATEGORY_WINBACK,
        ),
    )

    assert verdict.passed and verdict.final is not None
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is (
        ContextClassification.INSUFFICIENT_CONTEXT
    )
    assert adjustment.evidence_ids == ()
    assert any(
        "category-population context was unavailable" in item.casefold()
        for item in verdict.final.propagated_limitations
    )


def test_visit_action_rejects_unavailable_sparse_interval_evidence() -> None:
    interval = _evidence(
        "ev-interval",
        tool=ToolName.BASKET_BEHAVIOR,
        call_id="call-basket",
        metric="mean_basket_interval_days",
        baseline_value=2.0,
        recent_value=8.0,
    )
    limitation = (
        "Basket intervals require at least two baskets; unavailable for recent."
    )
    state = _state(
        (interval,),
        (
            _history(
                tool=ToolName.BASKET_BEHAVIOR,
                call_id="call-basket",
                status=ToolStatus.PARTIAL,
                limitations=(limitation,),
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(
            evidence_ids=("ev-interval",),
            action=ActionId.VISIT_FREQUENCY_REACTIVATION,
        ),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_CONTRAINDICATION in {
        issue.code for issue in verdict.issues
    }


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


@pytest.mark.parametrize(
    "summary",
    (
        "Promotion availability drove the decline.",
        "The loss resulted from promotion changes.",
        "The loss resulted in the customer leaving.",
        "Fewer visits made the customer disengage.",
        "The decline happened because of fewer offers.",
        "This action will increase engagement.",
        "The household was exposed to the recorded promotion.",
        "An outside purchase explains the decline.",
        "The change was due to a category shift.",
        "The category triggered the decline.",
        "This action will boost engagement.",
        "The intervention is guaranteed to retain the customer.",
        "The customer got the promotion.",
        "The shopper viewed an offer.",
    ),
)
def test_verifier_rejects_adversarial_causal_and_exposure_claims(
    summary: str,
) -> None:
    state = _state((_evidence("ev-1"),), (_history(),))

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(summary=summary),
    )

    assert not verdict.passed
    assert VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM in {
        issue.code for issue in verdict.issues
    }


@pytest.mark.parametrize(
    ("summary", "expected_pass"),
    (
        ("This analysis cannot establish causality.", True),
        ("The recorded pattern did not cause the household's decline.", True),
        ("There is no evidence that reduced promotions caused the decline.", True),
        ("There is no evidence reduced promotions caused the decline.", True),
        ("There is no evidence but promotions caused the decline.", False),
        ("No evidence indicates promotions caused the decline.", True),
        ("Reduced promotions caused no decline.", True),
        ("It is unknown whether promotions caused the decline.", True),
        ("The recorded pattern caused the household's decline.", False),
        ("Reduced promotions prompted the customer to leave.", False),
        ("Reduced promotions forced the household to disengage.", False),
        ("Reduced promotions pushed the customer to leave.", False),
        ("Reduced promotions were the reason for the decline.", False),
        ("Reduced promotions are why the customer left.", False),
        ("The decline occurred as a consequence of reduced promotions.", False),
        ("Engagement fell as a result of fewer visits.", False),
        (
            "There is no evidence engagement fell as a result of fewer visits.",
            True,
        ),
        ("Reduced promotions brought about the decline.", False),
        ("Reduced promotions induced the decline.", False),
        ("Reduced promotions lead to disengagement.", False),
        ("Reduced promotions leads to disengagement.", False),
        ("Reduced promotions are leading to disengagement.", False),
        ("Reduced promotions created the decline.", False),
        ("Reduced promotions brought on the decline.", False),
        ("Reduced promotions gave rise to the decline.", False),
        ("Reduced promotions sparked the decline.", False),
        ("Reduced promotions account for the decline.", False),
        (
            "Which product categories account for the lost retailer sales value?",
            True,
        ),
        ("The decline arose from reduced promotions.", False),
        ("The decline originated from reduced promotions.", False),
    ),
)
def test_causal_defense_distinguishes_denials_from_assertions(
    summary: str,
    expected_pass: bool,
) -> None:
    verdict = FinalVerifier(load_action_catalog()).verify(
        _state((_evidence("ev-1"),), (_history(),)),
        _proposal(summary=summary),
    )

    assert verdict.passed is expected_pass
    if not expected_pass:
        assert VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM in {
            issue.code for issue in verdict.issues
        }


def test_claim_type_cannot_exceed_evidence_support() -> None:
    record = _evidence("ev-1").model_copy(
        update={"maximum_claim_type": ClaimType.DESCRIPTIVE}
    )
    proposal = _proposal()
    associational = proposal.driver_summary[0]
    causal = associational.model_copy(update={"claim_type": ClaimType.CAUSAL})

    associational_verdict = FinalVerifier(load_action_catalog()).verify(
        _state((record,), (_history(),)),
        proposal,
    )
    causal_verdict = FinalVerifier(load_action_catalog()).verify(
        _state((_evidence("ev-1"),), (_history(),)),
        proposal.model_copy(update={"driver_summary": (causal,)}),
    )

    assert VerificationIssueCode.CLAIM_STRENGTH_EXCEEDED in {
        issue.code for issue in associational_verdict.issues
    }
    assert VerificationIssueCode.UNSUPPORTED_CAUSAL_CLAIM in {
        issue.code for issue in causal_verdict.issues
    }


def test_descriptive_claim_with_observational_evidence_passes() -> None:
    proposal = _proposal()
    descriptive = proposal.driver_summary[0].model_copy(
        update={"claim_type": ClaimType.DESCRIPTIVE}
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        _state((_evidence("ev-1"),), (_history(),)),
        proposal.model_copy(update={"driver_summary": (descriptive,)}),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.drivers[0].claim_type is ClaimType.DESCRIPTIVE


def test_code_owned_driver_accepts_full_bounded_support_and_counter_sets() -> None:
    support = tuple(
        _evidence(
            f"ev-support-{index}",
            tool=ToolName.CATEGORY_DECOMPOSITION,
            call_id="call-category",
            metric="category_retailer_sales_value",
            baseline_value=10.0 + index,
            recent_value=5.0,
            dimensions={
                "department": "GROCERY",
                "product_category": f"CATEGORY_{index}",
                "direction": "loss",
            },
        )
        for index in range(7)
    )
    counters = tuple(
        _category_context_evidence(
            ContextClassification.BROAD_CONTEXT,
            evidence_id=f"ev-counter-{index}",
            call_id="call-category",
        ).model_copy(
            update={
                "dimensions": {
                    "department": "GROCERY",
                    "product_category": f"CATEGORY_{index}",
                    "direction": "loss",
                    "target_excluded": "true",
                }
            }
        )
        for index in range(7)
    )
    support_ids = tuple(record.evidence_id for record in support)
    counter_ids = tuple(record.evidence_id for record in counters)
    driver = DriverClaim(
        summary="Recorded category losses are plausible contributors.",
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=support_ids,
        counterevidence_ids=counter_ids,
        limitations=("The evidence is observational.",),
    )
    proposal = FinishProposal(
        driver_summary=(driver,),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=support_ids,
        counterevidence_ids=counter_ids,
        next_best_action_id=ActionId.CATEGORY_WINBACK,
        rationale="Recorded category losses support a human-reviewed test.",
        alternative_explanations=("Outside-retailer behavior remains unknown.",),
        uncertainties=("Customer intent is not recorded.",),
    )
    state = _state(
        (*support, *counters),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert verdict.passed and verdict.final is not None
    assert verdict.final.drivers[0].supporting_evidence_ids == support_ids
    assert verdict.final.drivers[0].counterevidence_ids == counter_ids


def test_verifier_rejects_unrelated_counterevidence() -> None:
    support = _evidence("ev-1")
    unrelated = _evidence(
        "ev-unrelated-counter",
        metric="unrelated_metric",
        baseline_value=1.0,
        recent_value=2.0,
    )
    driver = DriverClaim(
        summary="The observed decline warrants cautious monitoring.",
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=(support.evidence_id,),
        counterevidence_ids=(unrelated.evidence_id,),
        limitations=("The evidence is observational.",),
    )
    proposal = FinishProposal(
        driver_summary=(driver,),
        proposed_confidence=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=(support.evidence_id,),
        counterevidence_ids=(unrelated.evidence_id,),
        next_best_action_id=ActionId.MONITOR,
        rationale="The recorded pattern supports human review.",
        alternative_explanations=("Outside-retailer behavior remains unknown.",),
        uncertainties=("Customer intent is not recorded.",),
    )
    state = _state((support, unrelated), (_history(),))

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert VerificationIssueCode.IRRELEVANT_COUNTEREVIDENCE in {
        issue.code for issue in verdict.issues
    }


def test_verifier_does_not_treat_malformed_adverse_record_as_counterevidence() -> None:
    support = _evidence(
        "ev-category-support",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    malformed = _evidence(
        "ev-category-malformed-counter",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=9.0,
        recent_value=4.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
        },
    )
    driver = DriverClaim(
        summary="A recorded category loss is a plausible contributor.",
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=(support.evidence_id,),
        counterevidence_ids=(malformed.evidence_id,),
        limitations=("The evidence is observational.",),
    )
    proposal = FinishProposal(
        driver_summary=(driver,),
        proposed_confidence=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=(support.evidence_id,),
        counterevidence_ids=(malformed.evidence_id,),
        next_best_action_id=ActionId.CATEGORY_WINBACK,
        rationale="The recorded pattern supports human review.",
        alternative_explanations=("Outside-retailer behavior remains unknown.",),
        uncertainties=("Customer intent is not recorded.",),
    )
    state = _state(
        (support, malformed),
        (
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert VerificationIssueCode.IRRELEVANT_COUNTEREVIDENCE in {
        issue.code for issue in verdict.issues
    }


def test_resolved_driver_keeps_only_its_own_counterevidence() -> None:
    cadence = _evidence(
        "ev-cadence",
        metric="distinct_trips",
        baseline_value=5.0,
        recent_value=2.0,
    )
    category = _evidence(
        "ev-category-other",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        baseline_value=10.0,
        recent_value=5.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "SOUP",
            "direction": "loss",
        },
    )
    category_counter = _evidence(
        "ev-category-counter",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_percentage_change",
        baseline_value=1.0,
        recent_value=2.0,
        dimensions={
            "department": "GROCERY",
            "product_category": "BAKERY",
            "direction": "gain",
        },
    )
    cadence_driver = DriverClaim(
        summary="Recorded visit cadence is a plausible contributor.",
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=("ev-cadence",),
        no_material_counterevidence_reason=(
            "No material cadence counterevidence was identified."
        ),
        limitations=("The evidence is observational.",),
    )
    category_driver = DriverClaim(
        summary="Recorded category movement is a plausible contributor.",
        claim_type=ClaimType.ASSOCIATIONAL,
        supporting_evidence_ids=("ev-category-other",),
        counterevidence_ids=("ev-category-counter",),
        limitations=("The evidence is observational.",),
    )
    proposal = FinishProposal(
        driver_summary=(cadence_driver, category_driver),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=("ev-cadence", "ev-category-other"),
        counterevidence_ids=("ev-category-counter",),
        next_best_action_id=ActionId.VISIT_FREQUENCY_REACTIVATION,
        rationale="Recorded visit cadence supports a human-reviewed test.",
        alternative_explanations=("Outside-retailer activity remains unknown.",),
        uncertainties=("Customer intent is not recorded.",),
    )
    state = _state(
        (cadence, category, category_counter),
        (
            _history(),
            _history(
                tool=ToolName.CATEGORY_DECOMPOSITION,
                call_id="call-category",
                diagnostics={"baseline_reconciled": True, "recent_reconciled": True},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert verdict.passed and verdict.final is not None
    assert verdict.final.supporting_evidence_ids == ("ev-cadence",)
    assert verdict.final.counterevidence_ids == ()
    assert verdict.final.drivers[0].counterevidence_ids == ()
    assert verdict.final.drivers[0].no_material_counterevidence_reason is not None


def test_resolved_driver_never_upgrades_descriptive_context_evidence() -> None:
    peer = _evidence(
        "ev-1",
        tool=ToolName.PEER_COMPARISON,
        call_id="call-peer",
        metric="target_retailer_sales_change",
        value=-0.50,
    ).model_copy(update={"maximum_claim_type": ClaimType.DESCRIPTIVE})
    context = _context_evidence(ContextClassification.BROAD_CONTEXT)
    proposal = _proposal(counterevidence_ids=("ev-context",))
    descriptive = proposal.driver_summary[0].model_copy(
        update={"claim_type": ClaimType.DESCRIPTIVE}
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        _state(
            (peer, context),
            (
                _history(
                    tool=ToolName.PEER_COMPARISON,
                    call_id="call-peer",
                    diagnostics={
                        "target_excluded": True,
                        "peer_household_ids": ["2"],
                    },
                ),
            ),
        ),
        proposal.model_copy(update={"driver_summary": (descriptive,)}),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.drivers[0].claim_type is ClaimType.DESCRIPTIVE
    assert "underlying reason remains unknown" in verdict.final.drivers[0].summary


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    (
        (
            {
                "target_change": -0.45,
                "population_median_change": -0.10,
                "population_declining_share": 0.30,
                "peer_median_change": -0.15,
                "peer_declining_share": 0.40,
                "population_count": 40,
                "peer_count": 10,
            },
            ContextClassification.CUSTOMER_SPECIFIC,
        ),
        (
            {
                "target_change": -0.25,
                "population_median_change": -0.20,
                "population_declining_share": 0.75,
                "peer_median_change": -0.18,
                "peer_declining_share": 0.70,
                "population_count": 40,
                "peer_count": 10,
            },
            ContextClassification.BROAD_CONTEXT,
        ),
        (
            {
                "target_change": -0.25,
                "population_median_change": -0.10,
                "population_declining_share": 0.70,
                "peer_median_change": -0.20,
                "peer_declining_share": 0.70,
                "population_count": 40,
                "peer_count": 10,
            },
            ContextClassification.MIXED,
        ),
        (
            {
                "target_change": -0.45,
                "population_median_change": -0.20,
                "population_declining_share": 0.70,
                "peer_median_change": -0.20,
                "peer_declining_share": 0.40,
                "population_count": 40,
                "peer_count": 10,
            },
            ContextClassification.MIXED,
        ),
        (
            {
                "target_change": -0.25,
                "population_median_change": -0.20,
                "population_declining_share": 0.75,
                "peer_median_change": -0.18,
                "peer_declining_share": 0.70,
                "population_count": 19,
                "peer_count": 10,
            },
            ContextClassification.INSUFFICIENT_CONTEXT,
        ),
    ),
)
def test_context_classification_uses_central_signed_change_policy(
    kwargs: dict[str, float | int],
    expected: ContextClassification,
) -> None:
    assert classify_context(**kwargs, policy=ContextPolicy()) is expected  # type: ignore[arg-type]


def test_verifier_rejects_omitted_material_broad_context() -> None:
    context = _context_evidence(ContextClassification.BROAD_CONTEXT)
    state = _state(
        (_evidence("ev-1"), context),
        (
            _history(),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, _proposal())

    assert not verdict.passed
    assert VerificationIssueCode.MATERIAL_COUNTEREVIDENCE_OMITTED in {
        issue.code for issue in verdict.issues
    }


def test_broad_context_caps_customer_specific_confidence_at_low() -> None:
    context = _context_evidence(ContextClassification.BROAD_CONTEXT)
    state = _state(
        (_evidence("ev-1"), context),
        (
            _history(),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(counterevidence_ids=("ev-context",)),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.LOW
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is ContextClassification.BROAD_CONTEXT
    assert adjustment.maximum_confidence is ResolvedConfidence.LOW
    assert adjustment.evidence_ids == ("ev-context",)


def test_conflicting_context_records_resolve_conservatively() -> None:
    customer_specific = _context_evidence(
        ContextClassification.CUSTOMER_SPECIFIC,
        evidence_id="ev-context-customer",
    )
    broad = _context_evidence(
        ContextClassification.BROAD_CONTEXT,
        evidence_id="ev-context-broad",
    )
    state = _state(
        (_evidence("ev-1"), customer_specific, broad),
        (
            _history(),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(counterevidence_ids=("ev-context-broad",)),
    )

    assert verdict.passed and verdict.final is not None
    assert verdict.final.resolved_confidence is ResolvedConfidence.LOW
    adjustment = verdict.final.confidence_adjustments[0]
    assert adjustment.context_classification is ContextClassification.BROAD_CONTEXT
    assert adjustment.evidence_ids == (
        "ev-context-customer",
        "ev-context-broad",
    )


def test_context_classification_requires_expected_tool_and_exclusion_proof() -> None:
    invalid_context = _context_evidence(ContextClassification.BROAD_CONTEXT).model_copy(
        update={"source_tool": ToolName.CUSTOMER_TREND}
    )
    state = _state(
        (_evidence("ev-1"), invalid_context),
        (
            _history(),
            _history(
                tool=ToolName.PEER_COMPARISON,
                call_id="call-peer",
                diagnostics={"target_excluded": True, "peer_household_ids": ["2"]},
            ),
        ),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(state, _proposal())

    assert not verdict.passed
    assert VerificationIssueCode.INVALID_CONTEXT_EVIDENCE in {
        issue.code for issue in verdict.issues
    }


def test_visit_action_rejects_stable_or_increasing_cadence() -> None:
    increasing = _evidence(
        "ev-1",
        metric="distinct_trips",
        baseline_value=5.0,
        recent_value=6.0,
    )
    verdict = FinalVerifier(load_action_catalog()).verify(
        _state((increasing,), (_history(),)),
        _proposal(action=ActionId.VISIT_FREQUENCY_REACTIVATION),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_PREREQUISITE in {
        issue.code for issue in verdict.issues
    }


def test_category_action_rejects_an_unknown_or_growing_category() -> None:
    unknown_loss = _evidence(
        "ev-1",
        tool=ToolName.CATEGORY_DECOMPOSITION,
        call_id="call-category",
        metric="category_retailer_sales_value",
        dimensions={
            "department": "UNKNOWN",
            "product_category": "UNKNOWN",
            "direction": "loss",
        },
    )
    verdict = FinalVerifier(load_action_catalog()).verify(
        _state(
            (unknown_loss,),
            (
                _history(
                    tool=ToolName.CATEGORY_DECOMPOSITION,
                    call_id="call-category",
                    diagnostics={
                        "baseline_reconciled": True,
                        "recent_reconciled": True,
                    },
                ),
            ),
        ),
        _proposal(action=ActionId.CATEGORY_WINBACK),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_PREREQUISITE in {
        issue.code for issue in verdict.issues
    }


def test_promotion_action_rejects_increasing_associated_value() -> None:
    increasing = _evidence(
        "ev-1",
        tool=ToolName.PROMOTION_RESPONSE,
        call_id="call-promotion",
        metric="promotion_associated_share",
        baseline_value=0.2,
        recent_value=0.4,
    )
    verdict = FinalVerifier(load_action_catalog()).verify(
        _state(
            (increasing,),
            (
                _history(
                    tool=ToolName.PROMOTION_RESPONSE,
                    call_id="call-promotion",
                    diagnostics={
                        "row_count_preserved": True,
                        "retailer_sales_value_preserved": True,
                    },
                ),
            ),
        ),
        _proposal(action=ActionId.PROMOTION_VALUE_REENGAGEMENT),
    )

    assert not verdict.passed
    assert VerificationIssueCode.ACTION_PREREQUISITE in {
        issue.code for issue in verdict.issues
    }


def test_verifier_publishes_catalog_grounded_driver_language() -> None:
    state = _state((_evidence("ev-1"),), (_history(),))
    proposal = _proposal(summary="A health crisis is a plausible driver.")

    verdict = FinalVerifier(load_action_catalog()).verify(state, proposal)

    assert verdict.passed and verdict.final is not None
    assert "health" not in verdict.final.drivers[0].summary.casefold()
    assert "recorded decline signal" in verdict.final.drivers[0].summary.casefold()
    assert verdict.final.alternative_explanations == (
        "Recorded evidence does not distinguish the observed signal from "
        "unobserved activity outside this retailer.",
    )
    assert "health" not in " ".join(verdict.final.alternative_explanations).casefold()


@pytest.mark.parametrize(
    "summary",
    (
        "Retailer sales fell fifty percent.",
        "There were two visits.",
        "Retailer sales fell by half.",
    ),
)
def test_verifier_rejects_spelled_out_quantitative_claims(summary: str) -> None:
    state = _state((_evidence("ev-1"),), (_history(),))

    verdict = FinalVerifier(load_action_catalog()).verify(
        state,
        _proposal(summary=summary),
    )

    assert not verdict.passed
    assert VerificationIssueCode.UNSUPPORTED_NUMERICAL_CLAIM in {
        issue.code for issue in verdict.issues
    }


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
