from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pandas as pd

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
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
    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = run_promotion_response(
            PromotionResponseInput(household_id="1"), _context("1"), repository
        )

    assert result.status is ToolStatus.OK
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


def test_type_a_coupon_history_is_partial_without_fabricated_exposure(
    tmp_path: Path,
) -> None:
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
