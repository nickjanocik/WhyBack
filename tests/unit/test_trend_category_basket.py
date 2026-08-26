"""Tests for WhyBack's trend category basket behavior."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pandas as pd
import pytest

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.methodology import ClaimType, ContextClassification, ContextPolicy
from whyback.tools.basket import basket_behavior
from whyback.tools.category import category_decomposition
from whyback.tools.contracts import (
    AnalysisWindow,
    BasketBehaviorInput,
    CategoryDecompositionInput,
    CustomerTrendInput,
    ToolExecutionContext,
    ToolStatus,
)
from whyback.tools.trend import customer_trend

RUN_ID = UUID("00000000-0000-0000-0000-000000000001")


def _context(tool_call_id: str) -> ToolExecutionContext:
    """Create the context value used by these tests."""

    return ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id=tool_call_id,
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=1,
            recent_start=2,
            recent_end=2,
        ),
    )


def test_customer_trend_uses_baskets_and_zero_fills_inactive_weeks(
    tmp_path: Path,
) -> None:
    """Verify that customer trend uses baskets and zero fills inactive weeks."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = customer_trend(
            CustomerTrendInput(household_id="1"), _context("trend"), repository
        )

    assert result.status is ToolStatus.PARTIAL
    baseline = result.model_summary["baseline"]
    recent = result.model_summary["recent"]
    weekly = result.model_summary["weekly_series"]
    assert isinstance(baseline, dict)
    assert isinstance(recent, dict)
    assert isinstance(weekly, list)
    assert baseline["retailer_sales_value"] == 8.0
    assert baseline["trips"] == 1
    assert baseline["median_retailer_sales_value_per_trip"] == 8.0
    assert recent["retailer_sales_value"] == 0.0
    assert [row["retailer_sales_value"] for row in weekly if isinstance(row, dict)] == [
        8.0,
        0.0,
    ]


def test_category_decomposition_retains_unknown_and_reconciles(tmp_path: Path) -> None:
    """Verify that category decomposition retains unknown and reconciles."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=5),
            _context("category"),
            repository,
        )

    assert result.status is ToolStatus.PARTIAL
    reconciliation = result.model_summary["reconciliation"]
    unknown = result.model_summary["unknown_group"]
    losses = result.model_summary["top_losses"]
    assert isinstance(reconciliation, dict)
    assert isinstance(unknown, dict)
    assert isinstance(losses, list)
    assert reconciliation["baseline_reconciled"] is True
    assert reconciliation["recent_reconciled"] is True
    assert reconciliation["baseline_transaction_total"] == 8.0
    assert unknown["baseline_retailer_sales_value"] == 3.0
    assert any(
        isinstance(row, dict) and row["product_category"] == "UNKNOWN" for row in losses
    )


def test_basket_behavior_aggregates_multiline_basket_before_metrics(
    tmp_path: Path,
) -> None:
    """Verify that basket behavior aggregates multiline basket before metrics."""

    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = basket_behavior(
            BasketBehaviorInput(household_id="1"), _context("basket"), repository
        )

    assert result.status is ToolStatus.PARTIAL
    baseline = result.model_summary["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["basket_count"] == 1
    assert baseline["mean_basket_retailer_sales_value"] == 8.0
    assert baseline["median_basket_retailer_sales_value"] == 8.0
    assert baseline["mean_distinct_products_per_basket"] == 2.0
    assert baseline["mean_distinct_categories_per_basket"] == 2.0


def test_trend_direct_metrics_ignore_transaction_row_order(tmp_path: Path) -> None:
    """Verify that trend direct metrics ignore transaction row order."""

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = minimal_source_frames()
    second = minimal_source_frames()
    second["transactions"] = second["transactions"].sample(frac=1.0, random_state=42)
    prepare_frames_for_tests(first, first_dir)
    prepare_frames_for_tests(second, second_dir)

    with DataRepository(first_dir) as first_repository:
        first_result = customer_trend(
            CustomerTrendInput(household_id="1"),
            _context("first"),
            first_repository,
        )
    with DataRepository(second_dir) as second_repository:
        second_result = customer_trend(
            CustomerTrendInput(household_id="1"),
            _context("second"),
            second_repository,
        )

    assert first_result.model_summary == second_result.model_summary


def _category_population_frames() -> dict[str, pd.DataFrame]:
    """Create source frames for category-population comparisons."""

    frames = minimal_source_frames()
    rows: list[dict[str, object]] = []
    for household in range(1, 8):
        baseline_product = "2000" if household == 7 else "1000"
        basket_number = 0
        for week in range(1, 5):
            for visit in range(2):
                basket_number += 1
                rows.append(
                    {
                        "household_id": str(household),
                        "store_id": "10",
                        "basket_id": f"{household}b{basket_number}",
                        "product_id": baseline_product,
                        "quantity": 1.0,
                        "sales_value": 10.0,
                        "retail_disc": 0.0,
                        "coupon_disc": 0.0,
                        "coupon_match_disc": 0.0,
                        "week": week,
                        "transaction_timestamp": (
                            f"2017-01-{week * 2 + visit:02d}T10:00:00"
                        ),
                    }
                )
        recent_value = 4.0 if household == 1 else 22.0
        for week in range(5, 9):
            rows.append(
                {
                    "household_id": str(household),
                    "store_id": "10",
                    "basket_id": f"{household}r{week}",
                    "product_id": "1000",
                    "quantity": 1.0,
                    "sales_value": recent_value,
                    "retail_disc": 0.0,
                    "coupon_disc": 0.0,
                    "coupon_match_disc": 0.0,
                    "week": week,
                    "transaction_timestamp": f"2017-02-{week:02d}T10:00:00",
                }
            )
    frames["transactions"] = pd.DataFrame(rows)
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


def _category_population_context(
    call_id: str,
    *,
    minimum_category_households: int = 5,
    meaningful_category_baseline_retailer_sales_value: float = 1.0,
) -> ToolExecutionContext:
    """Create tool context with a target-excluded category population."""

    return ToolExecutionContext(
        run_id=RUN_ID,
        tool_call_id=call_id,
        household_id="1",
        window=AnalysisWindow(
            baseline_start=1,
            baseline_end=4,
            recent_start=5,
            recent_end=8,
        ),
        context_policy=ContextPolicy(
            minimum_category_households=minimum_category_households,
            meaningful_category_baseline_retailer_sales_value=(
                meaningful_category_baseline_retailer_sales_value
            ),
        ),
    )


def test_category_context_is_target_excluded_and_exact(tmp_path: Path) -> None:
    """Verify that category context is target excluded and exact."""

    prepare_frames_for_tests(_category_population_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=1),
            _category_population_context("category-context"),
            repository,
        )

    assert result.status is ToolStatus.OK
    evidence = {item.metric: item for item in result.evidence}
    category_value = evidence["category_retailer_sales_value"]
    assert category_value.baseline_value == 80
    assert category_value.recent_value == 16
    assert category_value.change == -64
    assert evidence["category_population_household_count"].value == 5
    assert evidence["category_population_median_change"].value == pytest.approx(0.1)
    assert evidence["category_population_declining_share"].value == 0
    assert evidence["target_minus_category_population_median_change"].value == (
        pytest.approx(-0.9)
    )
    classification = evidence["category_context_classification"]
    assert classification.text_value == ContextClassification.CUSTOMER_SPECIFIC.value
    assert classification.maximum_claim_type is ClaimType.ASSOCIATIONAL
    assert classification.dimensions["department"] == "GROCERY"
    assert classification.dimensions["product_category"] == "SOUP"
    assert classification.dimensions["direction"] == "loss"
    assert classification.dimensions["target_excluded"] == "true"
    assert classification.dimensions["change_sign_convention"] == "lower_is_worse"
    assert (
        evidence["category_population_median_change"].maximum_claim_type
        is ClaimType.DESCRIPTIVE
    )
    assert result.provenance.diagnostics["category_context_target_excluded"] is True
    assert result.provenance.diagnostics["category_context_comparison_group_rows"] == 5
    reconciliation = result.model_summary["reconciliation"]
    assert isinstance(reconciliation, dict)
    assert reconciliation["baseline_transaction_total"] == 80
    assert reconciliation["recent_transaction_total"] == 16
    assert reconciliation["baseline_reconciled"] is True
    assert reconciliation["recent_reconciled"] is True


def test_category_context_suppresses_undersized_population(tmp_path: Path) -> None:
    """Verify that category context suppresses undersized population."""

    prepare_frames_for_tests(_category_population_frames(), tmp_path)
    with DataRepository(tmp_path) as repository:
        result = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=1),
            _category_population_context(
                "category-small", minimum_category_households=6
            ),
            repository,
        )

    assert result.status is ToolStatus.PARTIAL
    evidence = {item.metric: item for item in result.evidence}
    assert evidence["category_retailer_sales_value"].baseline_value == 80
    assert evidence["category_population_household_count"].value == 5
    assert evidence["category_context_classification"].text_value == (
        ContextClassification.INSUFFICIENT_CONTEXT.value
    )
    assert "category_population_median_change" not in evidence
    assert "category_population_declining_share" not in evidence
    assert "target_minus_category_population_median_change" not in evidence
    assert any("policy requires at least 6" in item for item in result.limitations)


def test_category_context_excludes_subthreshold_baseline_shoppers(
    tmp_path: Path,
) -> None:
    """Verify that category context excludes subthreshold baseline shoppers."""

    frames = _category_population_frames()
    tiny_soup_purchase = {
        **frames["transactions"].iloc[0].to_dict(),
        "household_id": "7",
        "basket_id": "7-tiny-soup-baseline",
        "product_id": "1000",
        "sales_value": 0.5,
        "week": 1,
        "transaction_timestamp": "2017-01-03T11:00:00",
    }
    frames["transactions"] = pd.concat(
        [frames["transactions"], pd.DataFrame([tiny_soup_purchase])],
        ignore_index=True,
    )
    prepare_frames_for_tests(frames, tmp_path)

    with DataRepository(tmp_path) as repository:
        default_threshold = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=1),
            _category_population_context("category-threshold-default"),
            repository,
        )
        lower_threshold = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=1),
            _category_population_context(
                "category-threshold-lower",
                meaningful_category_baseline_retailer_sales_value=0.1,
            ),
            repository,
        )

    default_evidence = {item.metric: item for item in default_threshold.evidence}
    lower_evidence = {item.metric: item for item in lower_threshold.evidence}
    assert default_evidence["category_population_household_count"].value == 5
    assert lower_evidence["category_population_household_count"].value == 6


def test_category_context_classifies_broad_contemporaneous_decline(
    tmp_path: Path,
) -> None:
    """Verify that category context classifies broad contemporaneous decline."""

    frames = _category_population_frames()
    transactions = frames["transactions"]
    soup_recent = (transactions["week"] >= 5) & (
        transactions["household_id"].isin([str(value) for value in range(1, 7)])
    )
    transactions.loc[soup_recent, "sales_value"] = 18.0
    prepare_frames_for_tests(frames, tmp_path)
    with DataRepository(tmp_path) as repository:
        result = category_decomposition(
            CategoryDecompositionInput(household_id="1", top_n=1),
            _category_population_context("category-broad"),
            repository,
        )

    evidence = {item.metric: item for item in result.evidence}
    assert evidence["category_population_median_change"].value == pytest.approx(-0.1)
    assert evidence["category_population_declining_share"].value == 1
    assert evidence["category_context_classification"].text_value == (
        ContextClassification.BROAD_CONTEXT.value
    )


def test_category_context_is_invariant_to_transaction_row_order(tmp_path: Path) -> None:
    """Verify that category context is invariant to transaction row order."""

    first_dir = tmp_path / "first-category"
    second_dir = tmp_path / "second-category"
    first = _category_population_frames()
    second = _category_population_frames()
    second["transactions"] = second["transactions"].sample(frac=1.0, random_state=27)
    prepare_frames_for_tests(first, first_dir)
    prepare_frames_for_tests(second, second_dir)

    def run(prepared_dir: Path, call_id: str):
        """Run the local scenario and return its deterministic result."""

        with DataRepository(prepared_dir) as repository:
            return category_decomposition(
                CategoryDecompositionInput(household_id="1", top_n=1),
                _category_population_context(call_id),
                repository,
            )

    first_result = run(first_dir, "category-first")
    second_result = run(second_dir, "category-second")
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
