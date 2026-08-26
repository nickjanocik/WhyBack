"""Deterministic basket structure and visit-cadence analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

import pandas as pd
from pydantic import JsonValue

from whyback.config import SOURCE_COMMIT
from whyback.data.repository import DataRepository
from whyback.tools.common import (
    QUANTITY_LIMITATION,
    EvidenceFactory,
    ToolTimer,
    json_value,
    make_provenance,
    median,
    percentage_change,
    query_hash,
)
from whyback.tools.contracts import (
    BasketBehaviorInput,
    EvidenceRecord,
    ToolExecutionContext,
    ToolName,
    ToolResult,
    ToolStatus,
)

_PARTIAL_WEEK_LIMITATION = (
    "Source weeks 1 and 53 are partial calendar weeks, so comparisons including "
    "either week may not be like-for-like."
)

_HOUSEHOLD_COUNTS_SQL = """
    SELECT COUNT(*)::BIGINT AS household_baskets,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS window_baskets,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS baseline_baskets,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS recent_baskets
    FROM baskets
    WHERE household_id = ?
"""

_BASKETS_SQL = """
    SELECT CAST(basket_id AS VARCHAR) AS basket_id,
           CAST(store_id AS VARCHAR) AS store_id,
           week::INTEGER AS week,
           transaction_timestamp,
           retailer_sales_value::DOUBLE AS retailer_sales_value,
           units::DOUBLE AS recorded_quantity,
           distinct_products::BIGINT AS distinct_products,
           distinct_categories::BIGINT AS distinct_categories
    FROM baskets
    WHERE household_id = ? AND week BETWEEN ? AND ?
    ORDER BY transaction_timestamp, basket_id
"""


@dataclass(frozen=True, slots=True)
class _Basket:
    """One distinct checkout with the fields needed for basket analysis."""

    basket_id: str
    store_id: str
    week: int
    timestamp: pd.Timestamp
    retailer_sales_value: float
    recorded_quantity: float
    distinct_products: int
    distinct_categories: int


@dataclass(frozen=True, slots=True)
class _BasketMetrics:
    """Window-level basket size, cadence, product, and store measures."""

    basket_count: int
    active_weeks: int
    baskets_per_calendar_week: float
    mean_basket_retailer_sales_value: float | None
    median_basket_retailer_sales_value: float | None
    mean_recorded_quantity_per_basket: float | None
    median_recorded_quantity_per_basket: float | None
    mean_distinct_products_per_basket: float | None
    mean_distinct_categories_per_basket: float | None
    mean_basket_interval_days: float | None
    median_basket_interval_days: float | None
    primary_store_id: str | None
    primary_store_share: float | None
    stores_visited: int
    consecutive_store_switch_rate: float | None

    def as_summary(self) -> dict[str, JsonValue]:
        """Return the basket measures in the compact model-summary shape."""

        return {
            "basket_count": self.basket_count,
            "active_weeks": self.active_weeks,
            "baskets_per_calendar_week": self.baskets_per_calendar_week,
            "mean_basket_retailer_sales_value": (self.mean_basket_retailer_sales_value),
            "median_basket_retailer_sales_value": (
                self.median_basket_retailer_sales_value
            ),
            "mean_recorded_quantity_per_basket": (
                self.mean_recorded_quantity_per_basket
            ),
            "median_recorded_quantity_per_basket": (
                self.median_recorded_quantity_per_basket
            ),
            "mean_distinct_products_per_basket": (
                self.mean_distinct_products_per_basket
            ),
            "mean_distinct_categories_per_basket": (
                self.mean_distinct_categories_per_basket
            ),
            "mean_basket_interval_days": self.mean_basket_interval_days,
            "median_basket_interval_days": self.median_basket_interval_days,
            "primary_store_id": self.primary_store_id,
            "primary_store_share": self.primary_store_share,
            "stores_visited": self.stores_visited,
            "consecutive_store_switch_rate": self.consecutive_store_switch_rate,
        }


def _mean(values: list[float]) -> float | None:
    """Return the arithmetic mean, or none when no observations exist."""

    return sum(values) / len(values) if values else None


def _calculate_metrics(
    baskets: list[_Basket], *, window_week_count: int
) -> _BasketMetrics:
    """Aggregate distinct baskets into size, cadence, and store behavior metrics."""

    value = [basket.retailer_sales_value for basket in baskets]
    quantity = [basket.recorded_quantity for basket in baskets]
    products = [float(basket.distinct_products) for basket in baskets]
    categories = [float(basket.distinct_categories) for basket in baskets]
    intervals = [
        (current.timestamp - previous.timestamp).total_seconds() / 86_400
        for previous, current in pairwise(baskets)
    ]
    store_counts = Counter(basket.store_id for basket in baskets)
    primary_store = (
        sorted(store_counts, key=lambda store: (-store_counts[store], store))[0]
        if store_counts
        else None
    )
    switch_rate = (
        sum(
            current.store_id != previous.store_id
            for previous, current in pairwise(baskets)
        )
        / (len(baskets) - 1)
        if len(baskets) >= 2
        else None
    )
    return _BasketMetrics(
        basket_count=len(baskets),
        active_weeks=len({basket.week for basket in baskets}),
        baskets_per_calendar_week=len(baskets) / window_week_count,
        mean_basket_retailer_sales_value=_mean(value),
        median_basket_retailer_sales_value=median(value),
        mean_recorded_quantity_per_basket=_mean(quantity),
        median_recorded_quantity_per_basket=median(quantity),
        mean_distinct_products_per_basket=_mean(products),
        mean_distinct_categories_per_basket=_mean(categories),
        mean_basket_interval_days=_mean(intervals),
        median_basket_interval_days=median(intervals),
        primary_store_id=primary_store,
        primary_store_share=(
            store_counts[primary_store] / len(baskets)
            if primary_store is not None
            else None
        ),
        stores_visited=len(store_counts),
        consecutive_store_switch_rate=switch_rate,
    )


def _failed_result(
    parameters: BasketBehaviorInput,
    context: ToolExecutionContext,
    *,
    timer: ToolTimer,
    status: ToolStatus,
    reason: str,
    sql_hash: str | None,
    rows_examined: int = 0,
    household_known: bool | None = None,
) -> ToolResult:
    """Build a typed, evidence-free basket failure with replay provenance."""

    summary: dict[str, JsonValue] = {"reason": reason}
    if household_known is not None:
        summary["household_known"] = household_known
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.BASKET_BEHAVIOR,
        status=status,
        model_summary=summary,
        limitations=(reason,),
        retryable=False,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_hash,
            rows_examined=rows_examined,
            diagnostics={"failure_reason": reason},
        ),
    )


def _window_has_partial_week(
    context: ToolExecutionContext, start: int, end: int
) -> bool:
    """Return whether an official-data window includes short week 1 or 53."""

    return context.source_commit == SOURCE_COMMIT and (
        start <= 1 <= end or start <= 53 <= end
    )


def _comparison(baseline: float | int | None, recent: float | int | None) -> JsonValue:
    """Describe absolute and relative movement between two optional values."""

    change: float | None = None
    relative: float | None = None
    if baseline is not None and recent is not None:
        change = float(recent) - float(baseline)
        relative = percentage_change(float(baseline), float(recent))
    return json_value(
        {
            "baseline": baseline,
            "recent": recent,
            "absolute_change": change,
            "relative_change": relative,
        }
    )


def basket_behavior(
    parameters: BasketBehaviorInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Compare basket-level structure, cadence, and observed store switching."""

    timer = ToolTimer.start()
    if parameters.household_id != context.household_id:
        return _failed_result(
            parameters,
            context,
            timer=timer,
            status=ToolStatus.INVALID_REQUEST,
            reason="Input household does not match the application-owned context.",
            sql_hash=None,
        )

    window = context.window
    count_frame = repository.query(
        _HOUSEHOLD_COUNTS_SQL,
        [
            window.baseline_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            parameters.household_id,
        ],
    )
    counts = cast(dict[str, Any], count_frame.iloc[0].to_dict())
    household_baskets = int(counts["household_baskets"])
    window_baskets = int(counts["window_baskets"])
    baseline_count = int(counts["baseline_baskets"])
    recent_count = int(counts["recent_baskets"])
    count_hash = query_hash(_HOUSEHOLD_COUNTS_SQL)
    if household_baskets == 0:
        return _failed_result(
            parameters,
            context,
            timer=timer,
            status=ToolStatus.MISSING_DATA,
            reason="Household is not present in the basket data.",
            sql_hash=count_hash,
            household_known=False,
        )
    if window_baskets == 0:
        return _failed_result(
            parameters,
            context,
            timer=timer,
            status=ToolStatus.MISSING_DATA,
            reason="Household has no baskets in the requested analysis window.",
            sql_hash=count_hash,
            household_known=True,
        )

    frame = repository.query(
        _BASKETS_SQL,
        [parameters.household_id, window.baseline_start, window.recent_end],
    )
    records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))
    all_baskets = [
        _Basket(
            basket_id=str(row["basket_id"]),
            store_id=str(row["store_id"]),
            week=int(row["week"]),
            timestamp=cast(pd.Timestamp, pd.Timestamp(row["transaction_timestamp"])),
            retailer_sales_value=float(row["retailer_sales_value"]),
            recorded_quantity=float(row["recorded_quantity"]),
            distinct_products=int(row["distinct_products"]),
            distinct_categories=int(row["distinct_categories"]),
        )
        for row in records
    ]
    baseline_baskets = [
        basket
        for basket in all_baskets
        if window.baseline_start <= basket.week <= window.baseline_end
    ]
    recent_baskets = [
        basket
        for basket in all_baskets
        if window.recent_start <= basket.week <= window.recent_end
    ]
    baseline = _calculate_metrics(
        baseline_baskets,
        window_week_count=window.baseline_end - window.baseline_start + 1,
    )
    recent = _calculate_metrics(
        recent_baskets,
        window_week_count=window.recent_end - window.recent_start + 1,
    )

    baseline_stores = {basket.store_id for basket in baseline_baskets}
    recent_new_store_share = (
        sum(basket.store_id not in baseline_stores for basket in recent_baskets)
        / len(recent_baskets)
        if recent_baskets
        else None
    )
    primary_store_changed = (
        baseline.primary_store_id != recent.primary_store_id
        if baseline.primary_store_id is not None and recent.primary_store_id is not None
        else None
    )

    limitations = [QUANTITY_LIMITATION]
    status = ToolStatus.OK
    if baseline_count == 0 or recent_count == 0:
        empty_period = "baseline" if baseline_count == 0 else "recent"
        limitations.append(
            f"No {empty_period} baskets were observed; basket structure and cadence "
            "for that period are unavailable."
        )
        status = ToolStatus.PARTIAL
    elif baseline_count < 2 or recent_count < 2:
        sparse_periods = [
            period
            for period, count in (
                ("baseline", baseline_count),
                ("recent", recent_count),
            )
            if count < 2
        ]
        limitations.append(
            "Basket intervals and consecutive store switching require at least two "
            f"baskets; unavailable for {', '.join(sparse_periods)}."
        )
        status = ToolStatus.PARTIAL
    if _window_has_partial_week(
        context, window.baseline_start, window.baseline_end
    ) or (_window_has_partial_week(context, window.recent_start, window.recent_end)):
        limitations.append(_PARTIAL_WEEK_LIMITATION)

    metric_values: tuple[
        tuple[str, float | int | None, float | int | None, str, tuple[str, ...]],
        ...,
    ] = (
        ("basket_count", baseline.basket_count, recent.basket_count, "count", ()),
        ("active_weeks", baseline.active_weeks, recent.active_weeks, "weeks", ()),
        (
            "baskets_per_calendar_week",
            baseline.baskets_per_calendar_week,
            recent.baskets_per_calendar_week,
            "baskets_per_week",
            (),
        ),
        (
            "mean_basket_retailer_sales_value",
            baseline.mean_basket_retailer_sales_value,
            recent.mean_basket_retailer_sales_value,
            "retailer_sales_value_per_basket",
            (),
        ),
        (
            "median_basket_retailer_sales_value",
            baseline.median_basket_retailer_sales_value,
            recent.median_basket_retailer_sales_value,
            "retailer_sales_value_per_basket",
            (),
        ),
        (
            "mean_recorded_quantity_per_basket",
            baseline.mean_recorded_quantity_per_basket,
            recent.mean_recorded_quantity_per_basket,
            "recorded_quantity_per_basket",
            (QUANTITY_LIMITATION,),
        ),
        (
            "median_recorded_quantity_per_basket",
            baseline.median_recorded_quantity_per_basket,
            recent.median_recorded_quantity_per_basket,
            "recorded_quantity_per_basket",
            (QUANTITY_LIMITATION,),
        ),
        (
            "mean_distinct_products_per_basket",
            baseline.mean_distinct_products_per_basket,
            recent.mean_distinct_products_per_basket,
            "products_per_basket",
            (),
        ),
        (
            "mean_distinct_categories_per_basket",
            baseline.mean_distinct_categories_per_basket,
            recent.mean_distinct_categories_per_basket,
            "categories_per_basket",
            (),
        ),
        (
            "mean_basket_interval_days",
            baseline.mean_basket_interval_days,
            recent.mean_basket_interval_days,
            "days",
            (),
        ),
        (
            "median_basket_interval_days",
            baseline.median_basket_interval_days,
            recent.median_basket_interval_days,
            "days",
            (),
        ),
        (
            "primary_store_share",
            baseline.primary_store_share,
            recent.primary_store_share,
            "share",
            (),
        ),
        (
            "stores_visited",
            baseline.stores_visited,
            recent.stores_visited,
            "count",
            (),
        ),
        (
            "consecutive_store_switch_rate",
            baseline.consecutive_store_switch_rate,
            recent.consecutive_store_switch_rate,
            "share",
            (),
        ),
    )
    sql_digest = query_hash(_HOUSEHOLD_COUNTS_SQL, _BASKETS_SQL)
    factory = EvidenceFactory(context, ToolName.BASKET_BEHAVIOR)
    evidence: list[EvidenceRecord] = []
    changes: dict[str, JsonValue] = {}
    for metric, baseline_value, recent_value, unit, metric_limitations in metric_values:
        change = (
            float(recent_value) - float(baseline_value)
            if baseline_value is not None and recent_value is not None
            else None
        )
        if baseline_value is not None or recent_value is not None:
            evidence.append(
                factory.add(
                    metric,
                    baseline_value=(
                        float(baseline_value) if baseline_value is not None else None
                    ),
                    recent_value=(
                        float(recent_value) if recent_value is not None else None
                    ),
                    change=change,
                    unit=unit,
                    limitations=metric_limitations,
                    sql_hash=sql_digest,
                )
            )
        changes[metric] = _comparison(baseline_value, recent_value)
    if primary_store_changed is not None:
        evidence.append(
            factory.add(
                "primary_store_changed",
                dimensions={
                    "baseline_primary_store": (
                        baseline.primary_store_id or "UNAVAILABLE"
                    ),
                    "recent_primary_store": recent.primary_store_id or "UNAVAILABLE",
                },
                value=float(primary_store_changed),
                unit="boolean_indicator",
                sql_hash=sql_digest,
            )
        )
    if recent_new_store_share is not None:
        evidence.append(
            factory.add(
                "recent_baskets_at_new_store_share",
                value=recent_new_store_share,
                unit="share",
                sql_hash=sql_digest,
            )
        )

    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.BASKET_BEHAVIOR,
        status=status,
        model_summary={
            "baseline": json_value(baseline.as_summary()),
            "recent": json_value(recent.as_summary()),
            "changes": json_value(changes),
            "store_switching": json_value(
                {
                    "primary_store_changed": primary_store_changed,
                    "baseline_primary_store_id": baseline.primary_store_id,
                    "recent_primary_store_id": recent.primary_store_id,
                    "recent_baskets_at_new_store_share": recent_new_store_share,
                }
            ),
        },
        evidence=tuple(evidence),
        limitations=tuple(limitations),
        retryable=False,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_digest,
            rows_examined=window_baskets,
            diagnostics={
                "baseline_baskets": baseline_count,
                "recent_baskets": recent_count,
            },
        ),
    )
