from __future__ import annotations

from pathlib import Path
from uuid import UUID

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
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
