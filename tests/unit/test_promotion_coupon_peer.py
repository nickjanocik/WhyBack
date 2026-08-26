"""Tests for WhyBack's promotion coupon peer behavior."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pandas as pd
import pytest

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.methodology import ClaimType, ContextClassification, ContextPolicy
from whyback.tools.contracts import (
    AnalysisWindow,
    CouponCampaignHistoryInput,
    PeerComparisonInput,
    PromotionResponseInput,
    ToolExecutionContext,
    ToolStatus,
)
from whyback.tools.coupon import TYPE_A_LIMITATION, run_coupon_campaign_history
from whyback.tools.peer import run_peer_comparison
from whyback.tools.promotion import run_promotion_response

RUN_ID = UUID("00000000-0000-0000-0000-000000000001")


def _context(household_id: str, call_id: str = "call") -> ToolExecutionContext:
    """Create the context value used by these tests."""

    return ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id=call_id,
        household_id=household_id,
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=1,
            recent_start=2,
            recent_end=2,
        ),
    )


def test_promotion_enrichment_is_nonmultiplicative(tmp_path: Path) -> None:
    """Verify that promotion enrichment is nonmultiplicative."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = run_promotion_response(
            PromotionResponseInput(household_id="1"), _context("1"), repository
        )

    assert result.status is ToolStatus.PARTIAL
    assert result.provenance.diagnostics["raw_transaction_rows"] == 2
    assert result.provenance.diagnostics["enriched_transaction_rows"] == 2
    assert result.provenance.diagnostics["retailer_sales_value_preserved"] is True
    promotion_evidence = next(
        evidence
        for evidence in result.evidence
        if evidence.metric == "promotion_associated_retailer_sales_value"
    )
    assert promotion_evidence.baseline_value == 5.0
    assert promotion_evidence.recent_value == 0.0
    assert "do not establish" in " ".join(result.limitations).lower()
    assert any("No recent transaction rows" in item for item in result.limitations)


def test_type_a_coupon_history_is_partial_without_fabricated_exposure(
    tmp_path: Path,
) -> None:
    """Verify that type a coupon history is partial without fabricated exposure."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = run_coupon_campaign_history(
            CouponCampaignHistoryInput(household_id="1"),
            _context("1", "coupon-call"),
            repository,
        )

    assert result.status is ToolStatus.PARTIAL
    assert TYPE_A_LIMITATION in result.limitations
    assert result.model_summary["redemption_count"] == 1
    assert result.model_summary["type_a_delivered_identities_available"] is False
    assert not any(
        evidence.metric == "known_delivered_campaign_coupon_count"
        and evidence.dimensions.get("campaign_type") == "Type A"
        for evidence in result.evidence
    )


def _peer_frames() -> dict[str, pd.DataFrame]:
    """Create source frames for target-excluded peer comparisons."""

    frames = minimal_source_frames()
    transaction_rows: list[dict[str, object]] = []
    for household in range(1, 8):
        basket_number = 0
        for week in range(1, 5):
            for visit in range(2):
                basket_number += 1
                transaction_rows.append(
                    {
                        "household_id": str(household),
                        "store_id": "10",
                        "basket_id": f"{household}0{basket_number}",
                        "product_id": "1000",
                        "quantity": 1.0,
                        "sales_value": float(8 + household),
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
            transaction_rows.append(
                {
                    "household_id": str(household),
                    "store_id": "10",
                    "basket_id": f"{household}9{week}",
                    "product_id": "1000",
                    "quantity": 1.0,
                    "sales_value": float((8 + household) * household / 7),
                    "retail_disc": 0.0,
                    "coupon_disc": 0.0,
                    "coupon_match_disc": 0.0,
                    "week": week,
                    "transaction_timestamp": f"2017-02-{week:02d}T10:00:00",
                }
            )
    frames["transactions"] = pd.DataFrame(transaction_rows)
    frames["promotions"] = pd.DataFrame(
        [
            {
                "product_id": "1000",
                "store_id": "10",
                "display_location": "0",
                "mailer_location": "A",
                "week": 1,
            }
        ]
    )
    return frames


def test_peer_comparison_excludes_target_and_is_deterministic(tmp_path: Path) -> None:
    """Verify that peer comparison excludes target and is deterministic."""

    prepare_frames_for_tests(_peer_frames(), tmp_path)
    context = ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id="peer-call",
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=4,
            recent_start=5,
            recent_end=8,
        ),
        context_policy=ContextPolicy(
            minimum_population_households=5,
            minimum_peer_households=5,
        ),
    )
    with DataRepository(tmp_path) as repository:
        result = run_peer_comparison(
            PeerComparisonInput(household_id="1", peer_count=5),
            context,
            repository,
        )

    assert result.status is ToolStatus.OK
    peer_ids = result.model_summary["peer_household_ids"]
    assert isinstance(peer_ids, list)
    assert "1" not in peer_ids
    assert len(peer_ids) == 5
    assert result.provenance.diagnostics["target_excluded"] is True
    assert result.provenance.diagnostics["population_target_excluded"] is True
    assert result.provenance.diagnostics["robust_scaling_fit_target_excluded"] is True

    evidence = {item.metric: item for item in result.evidence}
    assert evidence["target_retailer_sales_change"].value == pytest.approx(-13 / 14)
    assert evidence["population_household_count"].value == 6
    assert evidence["population_median_retailer_sales_change"].value == pytest.approx(
        -9.5 / 14
    )
    assert evidence["population_retailer_sales_change_q25"].value == pytest.approx(
        -10.75 / 14
    )
    assert evidence["population_retailer_sales_change_q75"].value == pytest.approx(
        -8.25 / 14
    )
    assert evidence["target_population_retailer_sales_change_percentile"].value == 0
    assert evidence["population_declining_household_share"].value == 1
    assert evidence["target_minus_population_median_change"].value == pytest.approx(
        -3.5 / 14
    )
    assert evidence["peer_household_count"].value == 5
    assert evidence["peer_median_retailer_sales_change"].value == pytest.approx(
        -10 / 14
    )
    assert evidence["peer_retailer_sales_change_q25"].value == pytest.approx(-11 / 14)
    assert evidence["peer_retailer_sales_change_q75"].value == pytest.approx(-9 / 14)
    assert evidence["target_peer_retailer_sales_change_percentile"].value == 0
    assert evidence["peer_declining_household_share"].value == 1
    assert evidence["target_minus_peer_median_change"].value == pytest.approx(-3 / 14)
    classification = evidence["context_classification"]
    assert classification.text_value == ContextClassification.MIXED.value
    assert classification.maximum_claim_type is ClaimType.ASSOCIATIONAL
    assert classification.dimensions["target_excluded"] == "true"
    assert classification.dimensions["change_sign_convention"] == "lower_is_worse"
    assert (
        evidence["population_median_retailer_sales_change"].maximum_claim_type
        is ClaimType.DESCRIPTIVE
    )


def test_peer_comparison_suppresses_undersized_distributions(tmp_path: Path) -> None:
    """Verify that peer comparison suppresses undersized distributions."""

    prepare_frames_for_tests(_peer_frames(), tmp_path)
    context = ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id="peer-small",
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=4,
            recent_start=5,
            recent_end=8,
        ),
        context_policy=ContextPolicy(
            minimum_population_households=7,
            minimum_peer_households=6,
        ),
    )
    with DataRepository(tmp_path) as repository:
        result = run_peer_comparison(
            PeerComparisonInput(household_id="1", peer_count=5),
            context,
            repository,
        )

    assert result.status is ToolStatus.PARTIAL
    evidence = {item.metric: item for item in result.evidence}
    assert evidence["population_household_count"].value == 6
    assert evidence["peer_household_count"].value == 5
    assert evidence["context_classification"].text_value == (
        ContextClassification.INSUFFICIENT_CONTEXT.value
    )
    assert "population_median_retailer_sales_change" not in evidence
    assert "peer_median_retailer_sales_change" not in evidence
    assert any("policy requires at least 7" in item for item in result.limitations)
    assert any("policy requires at least 6" in item for item in result.limitations)


def test_peer_context_is_invariant_to_transaction_row_order(tmp_path: Path) -> None:
    """Verify that peer context is invariant to transaction row order."""

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = _peer_frames()
    second = _peer_frames()
    second["transactions"] = second["transactions"].sample(frac=1.0, random_state=42)
    prepare_frames_for_tests(first, first_dir)
    prepare_frames_for_tests(second, second_dir)
    policy = ContextPolicy(
        minimum_population_households=5,
        minimum_peer_households=5,
    )

    def run(prepared_dir: Path, call_id: str):
        """Run the local scenario and return its deterministic result."""

        context = ToolExecutionContext(
            run_id=RUN_ID,
            tool_call_id=call_id,
            household_id="1",
            window=AnalysisWindow(
                baseline_start=1,
                baseline_end=4,
                recent_start=5,
                recent_end=8,
            ),
            context_policy=policy,
        )
        with DataRepository(prepared_dir) as repository:
            return run_peer_comparison(
                PeerComparisonInput(household_id="1", peer_count=5),
                context,
                repository,
            )

    first_result = run(first_dir, "first-order")
    second_result = run(second_dir, "second-order")
    first_evidence = [
        (item.metric, item.value, item.text_value, dict(item.dimensions))
        for item in first_result.evidence
    ]
    second_evidence = [
        (item.metric, item.value, item.text_value, dict(item.dimensions))
        for item in second_result.evidence
    ]
    assert first_result.model_summary == second_result.model_summary
    assert first_evidence == second_evidence
