"""Tests for WhyBack's agent invariants behavior."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import JsonValue

from tests.fixtures.source_frames import minimal_source_frames
from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.runner import InvestigationRunner
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.state import (
    ConfidenceLevel,
    DriverClaim,
    FinishDecision,
    FinishProposal,
    InvestigationState,
    ToolAttemptRecord,
    ToolDecision,
    ToolHistoryEntry,
)
from whyback.agent.verifier import FinalVerifier, VerificationIssueCode
from whyback.config import AgentConfig
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.detection.decline import DeclineSnapshot
from whyback.methodology import ClaimType
from whyback.tools.basket import basket_behavior
from whyback.tools.category import category_decomposition
from whyback.tools.contracts import (
    SUCCESS_STATUSES,
    AnalysisWindow,
    BasketBehaviorInput,
    CategoryDecompositionInput,
    CustomerTrendInput,
    EvidenceRecord,
    PeerComparisonInput,
    PromotionResponseInput,
    ToolExecutionContext,
    ToolName,
    ToolStatus,
)
from whyback.tools.peer import run_peer_comparison
from whyback.tools.promotion import run_promotion_response
from whyback.tools.registry import ToolRegistry
from whyback.tools.trend import customer_trend

RUN_ID = UUID("00000000-0000-0000-0000-000000000123")
ANALYSIS_WINDOW = AnalysisWindow(
    baseline_start=1,
    baseline_end=1,
    recent_start=2,
    recent_end=2,
)


@contextmanager
def _repository(
    frames: dict[str, pd.DataFrame],
) -> Generator[DataRepository, None, None]:
    """Create an in-memory analytical repository for this test."""

    with TemporaryDirectory(prefix="whyback-property-") as directory:
        prepared_dir = Path(directory)
        prepare_frames_for_tests(frames, prepared_dir)
        with DataRepository(prepared_dir) as repository:
            yield repository


def _context(
    call_id: str,
    *,
    household_id: str = "1",
    window: AnalysisWindow = ANALYSIS_WINDOW,
) -> ToolExecutionContext:
    """Create the context value used by these tests."""

    return ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id=call_id,
        household_id=household_id,
        window=window,
    )


def _snapshot() -> DeclineSnapshot:
    """Create a deterministic decline snapshot for this test."""

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


def _tool_decision(tool_name: ToolName) -> ToolDecision:
    """Create a typed analytical-tool decision for this test."""

    return ToolDecision(
        investigation_question="Which deterministic signal should be checked?",
        selected_tool=tool_name,
        arguments={"household_id": "1"},
        decision_summary="Inspect one application-calculated signal.",
    )


def _insufficient_finish() -> FinishDecision:
    """Create an explicit insufficient-evidence finish decision."""

    return FinishDecision(
        investigation_question="Is there sufficient evidence to act?",
        decision_summary="Finish safely without selecting a customer action.",
        final=FinishProposal(
            driver_summary=(),
            proposed_confidence=ConfidenceLevel.LOW,
            supporting_evidence_ids=(),
            counterevidence_ids=(),
            next_best_action_id=ActionId.INSUFFICIENT_EVIDENCE,
            rationale="The available evidence does not support a customer action.",
            alternative_explanations=(
                "The observed interval may not represent a durable change.",
            ),
            uncertainties=("The data does not record customer intent.",),
        ),
    )


def _verification_state(
    record: EvidenceRecord,
    history: ToolHistoryEntry,
) -> InvestigationState:
    """Create investigation state suitable for verifier property tests."""

    return InvestigationState.start(_snapshot(), run_id=RUN_ID).model_copy(
        update={"evidence_ledger": (record,), "tool_history": (history,)}
    )


def _monitor_proposal(*evidence_ids: str) -> FinishProposal:
    """Create a monitor action proposal grounded in test evidence."""

    return FinishProposal(
        driver_summary=(
            DriverClaim(
                summary="The observed pattern warrants cautious monitoring.",
                claim_type=ClaimType.ASSOCIATIONAL,
                supporting_evidence_ids=tuple(evidence_ids),
                no_material_counterevidence_reason=(
                    "No material counterevidence was identified."
                ),
                limitations=("The evidence is observational.",),
            ),
        ),
        proposed_confidence=ConfidenceLevel.HIGH,
        supporting_evidence_ids=tuple(evidence_ids),
        counterevidence_ids=(),
        next_best_action_id=ActionId.MONITOR,
        rationale="The recorded behavior supports human review.",
        alternative_explanations=(
            "The interval may reflect activity outside the recorded retailer.",
        ),
        uncertainties=("The data does not record a direct reason.",),
    )


@settings(max_examples=8, deadline=None)
@given(
    baseline_values=st.lists(
        st.integers(min_value=1, max_value=500), min_size=1, max_size=5
    ),
    recent_values=st.lists(
        st.integers(min_value=1, max_value=500), min_size=1, max_size=5
    ),
)
def test_category_totals_reconcile_for_varied_window_values(
    baseline_values: list[int], recent_values: list[int]
) -> None:
    """Verify that category totals reconcile for varied window values."""

    frames = minimal_source_frames()
    rows: list[dict[str, object]] = []
    for week, values in ((1, baseline_values), (2, recent_values)):
        for index, value in enumerate(values):
            rows.append(
                {
                    "household_id": "1",
                    "store_id": "10",
                    "basket_id": f"{week}-{index}",
                    "product_id": "1000" if index % 2 == 0 else "2000",
                    "quantity": 1.0,
                    "sales_value": float(value),
                    "retail_disc": 0.0,
                    "coupon_disc": 0.0,
                    "coupon_match_disc": 0.0,
                    "week": week,
                    "transaction_timestamp": f"2017-01-{week * 10 + index + 1:02d}",
                }
            )
    frames["transactions"] = pd.DataFrame(rows)

    with _repository(frames) as repository:
        result = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=20),
            _context("category-property"),
            repository,
        )

    reconciliation = cast(dict[str, JsonValue], result.model_summary["reconciliation"])
    assert reconciliation["baseline_transaction_total"] == sum(baseline_values)
    assert reconciliation["baseline_category_total"] == sum(baseline_values)
    assert reconciliation["recent_transaction_total"] == sum(recent_values)
    assert reconciliation["recent_category_total"] == sum(recent_values)
    assert reconciliation["baseline_delta"] == pytest.approx(0.0)
    assert reconciliation["recent_delta"] == pytest.approx(0.0)
    assert reconciliation["baseline_reconciled"] is True
    assert reconciliation["recent_reconciled"] is True


@settings(max_examples=8, deadline=None)
@given(
    duplicate_count=st.integers(min_value=1, max_value=12),
    promoted_sales=st.integers(min_value=1, max_value=500),
)
def test_promotion_duplicates_never_multiply_economic_values(
    duplicate_count: int, promoted_sales: int
) -> None:
    """Verify that promotion duplicates never multiply economic values."""

    frames = minimal_source_frames()
    frames["transactions"].loc[0, "sales_value"] = float(promoted_sales)
    promotion = frames["promotions"].iloc[[0]].copy()
    frames["promotions"] = pd.concat(
        [
            promotion.assign(display_location=str(index + 1))
            for index in range(duplicate_count)
        ],
        ignore_index=True,
    )

    with _repository(frames) as repository:
        result = run_promotion_response(
            PromotionResponseInput(household_id="1"),
            _context("promotion-property"),
            repository,
        )

    assert result.status in SUCCESS_STATUSES
    diagnostics = result.provenance.diagnostics
    assert diagnostics["raw_transaction_rows"] == 2
    assert diagnostics["enriched_transaction_rows"] == 2
    assert diagnostics["row_count_preserved"] is True
    assert diagnostics["raw_retailer_sales_value"] == pytest.approx(
        promoted_sales + 3.0
    )
    assert diagnostics["enriched_retailer_sales_value"] == pytest.approx(
        promoted_sales + 3.0
    )
    assert diagnostics["retailer_sales_value_preserved"] is True
    promotion_evidence = next(
        record
        for record in result.evidence
        if record.metric == "promotion_associated_retailer_sales_value"
    )
    assert promotion_evidence.baseline_value == pytest.approx(promoted_sales)


def _peer_frames() -> dict[str, pd.DataFrame]:
    """Create source frames for target-excluded peer comparisons."""

    frames = minimal_source_frames()
    rows: list[dict[str, object]] = []
    for household in range(1, 8):
        basket_number = 0
        for week in range(1, 5):
            for visit in range(2):
                basket_number += 1
                rows.append(
                    {
                        "household_id": str(household),
                        "store_id": "10",
                        "basket_id": f"{household}-b-{basket_number}",
                        "product_id": "1000",
                        "quantity": 1.0,
                        "sales_value": float(10 + household),
                        "retail_disc": 0.0,
                        "coupon_disc": 0.0,
                        "coupon_match_disc": 0.0,
                        "week": week,
                        "transaction_timestamp": (
                            f"2017-01-{week * 2 + visit:02d}T10:00:00"
                        ),
                    }
                )
        for week in range(5, 9):
            rows.append(
                {
                    "household_id": str(household),
                    "store_id": "10",
                    "basket_id": f"{household}-r-{week}",
                    "product_id": "1000",
                    "quantity": 1.0,
                    "sales_value": float((10 + household) * household / 7),
                    "retail_disc": 0.0,
                    "coupon_disc": 0.0,
                    "coupon_match_disc": 0.0,
                    "week": week,
                    "transaction_timestamp": f"2017-02-{week:02d}T10:00:00",
                }
            )
    frames["transactions"] = pd.DataFrame(rows)
    return frames


@settings(max_examples=7, deadline=None)
@given(target_household=st.integers(min_value=1, max_value=7))
def test_peer_selection_excludes_every_possible_target(target_household: int) -> None:
    """Verify that peer selection excludes every possible target."""

    target = str(target_household)
    window = AnalysisWindow(
        baseline_start=1,
        baseline_end=4,
        recent_start=5,
        recent_end=8,
    )
    with _repository(_peer_frames()) as repository:
        result = run_peer_comparison(
            PeerComparisonInput(household_id=target, peer_count=5),
            _context("peer-property", household_id=target, window=window),
            repository,
        )

    assert result.status in SUCCESS_STATUSES
    peer_ids = cast(list[JsonValue], result.model_summary["peer_household_ids"])
    diagnostic_ids = cast(
        list[JsonValue], result.provenance.diagnostics["peer_household_ids"]
    )
    assert target not in peer_ids
    assert target not in diagnostic_ids
    assert result.provenance.diagnostics["target_excluded"] is True


@settings(max_examples=6, deadline=None)
@given(
    extra_values=st.lists(
        st.integers(min_value=1, max_value=1_000), min_size=1, max_size=6
    )
)
def test_unrelated_households_cannot_change_target_direct_metrics(
    extra_values: list[int],
) -> None:
    """Verify that unrelated households cannot change target direct metrics."""

    base_frames = minimal_source_frames()
    enriched_frames = minimal_source_frames()
    extra_rows = []
    for index, value in enumerate(extra_values):
        extra_rows.append(
            {
                "household_id": "unrelated",
                "store_id": "99",
                "basket_id": f"unrelated-{index}",
                "product_id": "1000",
                "quantity": 1.0,
                "sales_value": float(value),
                "retail_disc": 0.0,
                "coupon_disc": 0.0,
                "coupon_match_disc": 0.0,
                "week": 1 if index % 2 == 0 else 2,
                "transaction_timestamp": f"2017-03-{index + 1:02d}T10:00:00",
            }
        )
    enriched_frames["transactions"] = pd.concat(
        [enriched_frames["transactions"], pd.DataFrame(extra_rows)],
        ignore_index=True,
    )

    def direct_summaries(
        frames: dict[str, pd.DataFrame],
    ) -> tuple[dict[str, JsonValue], ...]:
        """Run the direct metrics and return their comparable summaries."""

        with _repository(frames) as repository:
            return (
                customer_trend(
                    CustomerTrendInput(household_id="1"),
                    _context("trend-isolation"),
                    repository,
                ).model_summary,
                category_decomposition(
                    CategoryDecompositionInput(household_id="1"),
                    _context("category-isolation"),
                    repository,
                ).model_summary,
                basket_behavior(
                    BasketBehaviorInput(household_id="1"),
                    _context("basket-isolation"),
                    repository,
                ).model_summary,
            )

    assert direct_summaries(enriched_frames) == direct_summaries(base_frames)


@pytest.mark.parametrize(
    "tool_name",
    [
        ToolName.CUSTOMER_TREND,
        ToolName.CATEGORY_DECOMPOSITION,
        ToolName.BASKET_BEHAVIOR,
        ToolName.PROMOTION_RESPONSE,
    ],
)
def test_missing_and_one_sided_windows_have_explicit_statuses(
    tool_name: ToolName,
) -> None:
    """Verify that missing and one sided windows have explicit statuses."""

    registry = ToolRegistry()
    no_rows_window = AnalysisWindow(
        baseline_start=3,
        baseline_end=3,
        recent_start=4,
        recent_end=4,
    )
    with _repository(minimal_source_frames()) as repository:
        missing = registry.execute(
            tool_name,
            {"household_id": "1"},
            _context("missing-window", window=no_rows_window),
            repository,
        )
        one_sided = registry.execute(
            tool_name,
            {"household_id": "1"},
            _context("one-sided-window"),
            repository,
        )

    assert missing.status is ToolStatus.MISSING_DATA
    assert not missing.evidence
    assert missing.limitations
    assert one_sided.status is ToolStatus.PARTIAL
    assert any("recent" in limitation.lower() for limitation in one_sided.limitations)


def test_evidence_identifiers_are_unique_across_successful_tool_calls() -> None:
    """Verify that evidence identifiers are unique across successful tool calls."""

    with _repository(minimal_source_frames()) as repository:
        results = (
            customer_trend(
                CustomerTrendInput(household_id="1"),
                _context("cross-call-trend"),
                repository,
            ),
            category_decomposition(
                CategoryDecompositionInput(household_id="1"),
                _context("cross-call-category"),
                repository,
            ),
            basket_behavior(
                BasketBehaviorInput(household_id="1"),
                _context("cross-call-basket"),
                repository,
            ),
            run_promotion_response(
                PromotionResponseInput(household_id="1"),
                _context("cross-call-promotion"),
                repository,
            ),
        )

    assert all(result.status in SUCCESS_STATUSES for result in results)
    evidence = [record for result in results for record in result.evidence]
    identifiers = [record.evidence_id for record in evidence]
    source_calls = {record.source_tool_call_id for record in evidence}
    assert len(source_calls) == len(results)
    assert len(identifiers) == len(set(identifiers))


@settings(max_examples=12, deadline=None)
@given(
    budget=st.integers(min_value=1, max_value=5),
    selected_tools=st.lists(st.sampled_from(list(ToolName)), min_size=1, max_size=9),
)
def test_budgets_never_go_negative_and_duplicate_signatures_execute_once(
    budget: int,
    selected_tools: list[ToolName],
) -> None:
    """Verify that budgets never go negative and duplicate signatures execute once."""

    decisions = [
        _tool_decision(ToolName.CUSTOMER_TREND),
        *(_tool_decision(name) for name in selected_tools),
        _insufficient_finish(),
    ]
    backend = ScriptedBackend(decisions)
    config = AgentConfig(
        max_tool_executions=budget,
        max_model_decisions=len(decisions),
    )
    with _repository(minimal_source_frames()) as repository:
        outcome = InvestigationRunner(
            backend=backend,
            registry=ToolRegistry(),
            repository=repository,
            action_catalog=load_action_catalog(),
            config=config,
        ).run(_snapshot(), run_id=RUN_ID)

    actual_attempts = sum(
        len(history.attempts) for history in outcome.state.tool_history
    )
    attempts_per_signature: dict[str, int] = {}
    for history in outcome.state.tool_history:
        attempts_per_signature[history.normalized_signature] = (
            attempts_per_signature.get(history.normalized_signature, 0)
            + len(history.attempts)
        )
    evidence_ids = [record.evidence_id for record in outcome.state.evidence_ledger]

    assert 0 <= outcome.state.remaining_tool_budget <= budget
    assert 0 <= outcome.state.remaining_turn_budget <= len(decisions)
    assert actual_attempts <= budget
    assert outcome.state.remaining_tool_budget == budget - actual_attempts
    assert all(count <= 1 for count in attempts_per_signature.values())
    assert len(evidence_ids) == len(set(evidence_ids))


@settings(max_examples=12, deadline=None)
@given(
    unknown_suffix=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=20,
    ),
    failed_status=st.sampled_from(
        [
            ToolStatus.MISSING_DATA,
            ToolStatus.INVALID_REQUEST,
            ToolStatus.RETRYABLE_ERROR,
            ToolStatus.FATAL_ERROR,
        ]
    ),
)
def test_verifier_rejects_unknown_and_failed_source_evidence(
    unknown_suffix: str,
    failed_status: ToolStatus,
) -> None:
    """Verify that verifier rejects unknown and failed source evidence."""

    evidence_id = "ev-failed"
    record = EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id="1",
        source_tool=ToolName.CUSTOMER_TREND,
        source_tool_call_id="failed-call",
        metric="retailer_sales_value",
        baseline_value=8.0,
        recent_value=0.0,
        change=-8.0,
        unit="retailer_sales_value",
    )
    history = ToolHistoryEntry(
        decision_number=1,
        tool_name=ToolName.CUSTOMER_TREND,
        normalized_signature="failed-signature",
        investigation_question="What changed?",
        decision_summary="Inspect a deterministic signal.",
        normalized_arguments={"household_id": "1"},
        attempts=(
            ToolAttemptRecord(
                attempt=1,
                tool_call_id="failed-call",
                status=failed_status,
                retryable=failed_status is ToolStatus.RETRYABLE_ERROR,
            ),
        ),
        final_status=failed_status,
        limitations=("The analytical call failed.",),
    )
    unknown_id = f"unknown-{unknown_suffix}"
    verdict = FinalVerifier(load_action_catalog()).verify(
        _verification_state(record, history),
        _monitor_proposal(evidence_id, unknown_id),
    )

    codes = {issue.code for issue in verdict.issues}
    assert not verdict.passed
    assert VerificationIssueCode.UNKNOWN_EVIDENCE in codes
    assert VerificationIssueCode.INVALID_EVIDENCE_SOURCE in codes


@settings(max_examples=12, deadline=None)
@given(
    limitations=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
            min_size=1,
            max_size=24,
        ),
        min_size=1,
        max_size=4,
        unique=True,
    )
)
def test_valid_partial_limitations_are_propagated_without_loss(
    limitations: list[str],
) -> None:
    """Verify that valid partial limitations are propagated without loss."""

    evidence_id = "ev-partial"
    record = EvidenceRecord(
        evidence_id=evidence_id,
        run_id=RUN_ID,
        household_id="1",
        source_tool=ToolName.CUSTOMER_TREND,
        source_tool_call_id="partial-call",
        metric="retailer_sales_value",
        baseline_value=8.0,
        recent_value=0.0,
        change=-8.0,
        unit="retailer_sales_value",
        limitations=tuple(limitations[:1]),
    )
    history = ToolHistoryEntry(
        decision_number=1,
        tool_name=ToolName.CUSTOMER_TREND,
        normalized_signature="partial-signature",
        investigation_question="What changed?",
        decision_summary="Inspect a deterministic signal.",
        normalized_arguments={"household_id": "1"},
        attempts=(
            ToolAttemptRecord(
                attempt=1,
                tool_call_id="partial-call",
                status=ToolStatus.PARTIAL,
                limitations=tuple(limitations),
            ),
        ),
        final_status=ToolStatus.PARTIAL,
        evidence_ids=(evidence_id,),
        limitations=tuple(limitations),
    )

    verdict = FinalVerifier(load_action_catalog()).verify(
        _verification_state(record, history), _monitor_proposal(evidence_id)
    )

    assert verdict.passed
    assert verdict.final is not None
    assert verdict.final.propagated_limitations[: len(limitations)] == tuple(
        limitations
    )
    assert all(
        limitation in verdict.final.propagated_limitations for limitation in limitations
    )
    assert verdict.final.confidence_cap_applied
