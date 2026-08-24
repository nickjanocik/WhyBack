"""Deterministic customer engagement trend analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pydantic import JsonValue

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
    slope,
)
from whyback.tools.contracts import (
    CustomerTrendInput,
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
    SELECT COUNT(*)::BIGINT AS household_rows,
           COUNT(*) FILTER (
               WHERE week BETWEEN ? AND ?
           )::BIGINT AS window_rows,
           COUNT(*) FILTER (
               WHERE week BETWEEN ? AND ?
           )::BIGINT AS baseline_rows,
           COUNT(*) FILTER (
               WHERE week BETWEEN ? AND ?
           )::BIGINT AS recent_rows,
           MAX(week) FILTER (WHERE week <= ?)::INTEGER AS baseline_last_week,
           MAX(week) FILTER (WHERE week <= ?)::INTEGER AS recent_last_week
    FROM transactions
    WHERE household_id = ?
"""

_WINDOW_AGGREGATES_SQL = """
    SELECT
        COALESCE(SUM(
            CASE WHEN week BETWEEN ? AND ?
                 THEN CAST(retailer_sales_value AS DECIMAL(38, 6)) ELSE 0 END
        ), 0)::DOUBLE AS baseline_sales,
        COALESCE(SUM(
            CASE WHEN week BETWEEN ? AND ?
                 THEN CAST(retailer_sales_value AS DECIMAL(38, 6)) ELSE 0 END
        ), 0)::DOUBLE AS recent_sales,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN basket_id END)::BIGINT
            AS baseline_trips,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN basket_id END)::BIGINT
            AS recent_trips,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN week END)::BIGINT
            AS baseline_active_weeks,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN week END)::BIGINT
            AS recent_active_weeks,
        COALESCE(SUM(
            CASE WHEN week BETWEEN ? AND ?
                 THEN CAST(quantity AS DECIMAL(38, 6)) ELSE 0 END
        ), 0)::DOUBLE AS baseline_quantity,
        COALESCE(SUM(
            CASE WHEN week BETWEEN ? AND ?
                 THEN CAST(quantity AS DECIMAL(38, 6)) ELSE 0 END
        ), 0)::DOUBLE AS recent_quantity,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN product_id END)::BIGINT
            AS baseline_products,
        COUNT(DISTINCT CASE WHEN week BETWEEN ? AND ? THEN product_id END)::BIGINT
            AS recent_products
    FROM transactions
    WHERE household_id = ? AND week BETWEEN ? AND ?
"""

_BASKET_VALUES_SQL = """
    SELECT week, basket_id, retailer_sales_value::DOUBLE AS retailer_sales_value
    FROM baskets
    WHERE household_id = ? AND week BETWEEN ? AND ?
    ORDER BY week, basket_id
"""

_WEEKLY_SERIES_SQL = """
    WITH requested_weeks AS (
        SELECT week
        FROM generate_series(?::INTEGER, ?::INTEGER) AS requested(week)
    )
    SELECT requested_weeks.week::INTEGER AS week,
           COALESCE(
               SUM(CAST(t.retailer_sales_value AS DECIMAL(38, 6))), 0
           )::DOUBLE AS retailer_sales_value,
           COUNT(DISTINCT t.basket_id)::BIGINT AS trips,
           COALESCE(SUM(CAST(t.quantity AS DECIMAL(38, 6))), 0)::DOUBLE
               AS recorded_quantity,
           COUNT(DISTINCT t.product_id)::BIGINT AS distinct_products
    FROM requested_weeks
    LEFT JOIN transactions t
      ON t.week = requested_weeks.week AND t.household_id = ?
    GROUP BY requested_weeks.week
    ORDER BY requested_weeks.week
"""


@dataclass(frozen=True, slots=True)
class _WindowMetrics:
    retailer_sales_value: float
    trips: int
    active_weeks: int
    average_retailer_sales_value_per_trip: float | None
    median_retailer_sales_value_per_trip: float | None
    recorded_quantity: float
    distinct_products: int
    recency_weeks: int | None
    weekly_retailer_sales_value_slope: float | None

    def as_summary(self) -> dict[str, JsonValue]:
        return {
            "retailer_sales_value": self.retailer_sales_value,
            "trips": self.trips,
            "active_weeks": self.active_weeks,
            "average_retailer_sales_value_per_trip": (
                self.average_retailer_sales_value_per_trip
            ),
            "median_retailer_sales_value_per_trip": (
                self.median_retailer_sales_value_per_trip
            ),
            "recorded_quantity": self.recorded_quantity,
            "distinct_products": self.distinct_products,
            "recency_weeks": self.recency_weeks,
            "weekly_retailer_sales_value_slope": (
                self.weekly_retailer_sales_value_slope
            ),
        }


def _failed_result(
    parameters: CustomerTrendInput,
    context: ToolExecutionContext,
    *,
    timer: ToolTimer,
    status: ToolStatus,
    reason: str,
    sql_hash: str | None,
    rows_examined: int = 0,
    household_known: bool | None = None,
) -> ToolResult:
    summary: dict[str, JsonValue] = {"reason": reason}
    if household_known is not None:
        summary["household_known"] = household_known
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.CUSTOMER_TREND,
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


def _comparison(baseline: float | int | None, recent: float | int | None) -> JsonValue:
    absolute_change: float | None = None
    relative_change: float | None = None
    if baseline is not None and recent is not None:
        absolute_change = float(recent) - float(baseline)
        relative_change = percentage_change(float(baseline), float(recent))
    return json_value(
        {
            "baseline": baseline,
            "recent": recent,
            "absolute_change": absolute_change,
            "relative_change": relative_change,
        }
    )


def _window_has_partial_week(start: int, end: int) -> bool:
    return start <= 1 <= end or start <= 53 <= end


def customer_trend(
    parameters: CustomerTrendInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Compute zero-filled weekly and baseline/recent engagement measures."""

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
            window.baseline_end,
            window.recent_end,
            parameters.household_id,
        ],
    )
    counts = cast(dict[str, Any], count_frame.iloc[0].to_dict())
    household_rows = int(counts["household_rows"])
    window_rows = int(counts["window_rows"])
    baseline_rows = int(counts["baseline_rows"])
    recent_rows = int(counts["recent_rows"])
    count_hash = query_hash(_HOUSEHOLD_COUNTS_SQL)
    if household_rows == 0:
        return _failed_result(
            parameters,
            context,
            timer=timer,
            status=ToolStatus.MISSING_DATA,
            reason="Household is not present in the transaction data.",
            sql_hash=count_hash,
            household_known=False,
        )
    if window_rows == 0:
        return _failed_result(
            parameters,
            context,
            timer=timer,
            status=ToolStatus.MISSING_DATA,
            reason="Household has no transactions in the requested analysis window.",
            sql_hash=count_hash,
            household_known=True,
        )

    aggregate_frame = repository.query(
        _WINDOW_AGGREGATES_SQL,
        [
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            parameters.household_id,
            window.baseline_start,
            window.recent_end,
        ],
    )
    aggregates = cast(dict[str, Any], aggregate_frame.iloc[0].to_dict())
    basket_frame = repository.query(
        _BASKET_VALUES_SQL,
        [parameters.household_id, window.baseline_start, window.recent_end],
    )
    basket_records = cast(list[dict[str, Any]], basket_frame.to_dict(orient="records"))
    weekly_frame = repository.query(
        _WEEKLY_SERIES_SQL,
        [window.baseline_start, window.recent_end, parameters.household_id],
    )
    weekly_records = cast(list[dict[str, Any]], weekly_frame.to_dict(orient="records"))

    baseline_basket_values = [
        float(row["retailer_sales_value"])
        for row in basket_records
        if window.baseline_start <= int(row["week"]) <= window.baseline_end
    ]
    recent_basket_values = [
        float(row["retailer_sales_value"])
        for row in basket_records
        if window.recent_start <= int(row["week"]) <= window.recent_end
    ]
    baseline_week_values = [
        float(row["retailer_sales_value"])
        for row in weekly_records
        if window.baseline_start <= int(row["week"]) <= window.baseline_end
    ]
    recent_week_values = [
        float(row["retailer_sales_value"])
        for row in weekly_records
        if window.recent_start <= int(row["week"]) <= window.recent_end
    ]

    baseline_trips = int(aggregates["baseline_trips"])
    recent_trips = int(aggregates["recent_trips"])
    baseline_sales = float(aggregates["baseline_sales"])
    recent_sales = float(aggregates["recent_sales"])
    baseline_last_week_value = counts["baseline_last_week"]
    recent_last_week_value = counts["recent_last_week"]
    baseline = _WindowMetrics(
        retailer_sales_value=baseline_sales,
        trips=baseline_trips,
        active_weeks=int(aggregates["baseline_active_weeks"]),
        average_retailer_sales_value_per_trip=(
            baseline_sales / baseline_trips if baseline_trips else None
        ),
        median_retailer_sales_value_per_trip=median(baseline_basket_values),
        recorded_quantity=float(aggregates["baseline_quantity"]),
        distinct_products=int(aggregates["baseline_products"]),
        recency_weeks=(
            window.baseline_end - int(baseline_last_week_value)
            if baseline_last_week_value is not None
            else None
        ),
        weekly_retailer_sales_value_slope=slope(baseline_week_values),
    )
    recent = _WindowMetrics(
        retailer_sales_value=recent_sales,
        trips=recent_trips,
        active_weeks=int(aggregates["recent_active_weeks"]),
        average_retailer_sales_value_per_trip=(
            recent_sales / recent_trips if recent_trips else None
        ),
        median_retailer_sales_value_per_trip=median(recent_basket_values),
        recorded_quantity=float(aggregates["recent_quantity"]),
        distinct_products=int(aggregates["recent_products"]),
        recency_weeks=(
            window.recent_end - int(recent_last_week_value)
            if recent_last_week_value is not None
            else None
        ),
        weekly_retailer_sales_value_slope=slope(recent_week_values),
    )

    limitations = [QUANTITY_LIMITATION]
    status = ToolStatus.OK
    if baseline_rows == 0 or recent_rows == 0:
        empty_period = "baseline" if baseline_rows == 0 else "recent"
        limitations.append(
            f"No {empty_period} transactions were observed; per-trip statistics "
            "for that period are unavailable."
        )
        status = ToolStatus.PARTIAL
    if _window_has_partial_week(window.baseline_start, window.baseline_end) or (
        _window_has_partial_week(window.recent_start, window.recent_end)
    ):
        limitations.append(_PARTIAL_WEEK_LIMITATION)

    evidence_factory = EvidenceFactory(context, ToolName.CUSTOMER_TREND)
    sql_digest = query_hash(
        _HOUSEHOLD_COUNTS_SQL,
        _WINDOW_AGGREGATES_SQL,
        _BASKET_VALUES_SQL,
        _WEEKLY_SERIES_SQL,
    )
    evidence: list[EvidenceRecord] = []
    metric_values: tuple[
        tuple[str, float | int | None, float | int | None, str, tuple[str, ...]],
        ...,
    ] = (
        (
            "retailer_sales_value",
            baseline.retailer_sales_value,
            recent.retailer_sales_value,
            "retailer_sales_value",
            (),
        ),
        ("distinct_trips", baseline.trips, recent.trips, "count", ()),
        ("active_weeks", baseline.active_weeks, recent.active_weeks, "weeks", ()),
        (
            "average_retailer_sales_value_per_trip",
            baseline.average_retailer_sales_value_per_trip,
            recent.average_retailer_sales_value_per_trip,
            "retailer_sales_value_per_trip",
            (),
        ),
        (
            "median_retailer_sales_value_per_trip",
            baseline.median_retailer_sales_value_per_trip,
            recent.median_retailer_sales_value_per_trip,
            "retailer_sales_value_per_trip",
            (),
        ),
        (
            "recorded_quantity",
            baseline.recorded_quantity,
            recent.recorded_quantity,
            "recorded_quantity",
            (QUANTITY_LIMITATION,),
        ),
        (
            "distinct_products",
            baseline.distinct_products,
            recent.distinct_products,
            "count",
            (),
        ),
        (
            "recency_weeks",
            baseline.recency_weeks,
            recent.recency_weeks,
            "weeks",
            (),
        ),
        (
            "weekly_retailer_sales_value_slope",
            baseline.weekly_retailer_sales_value_slope,
            recent.weekly_retailer_sales_value_slope,
            "retailer_sales_value_per_week",
            (),
        ),
    )
    for metric, baseline_value, recent_value, unit, metric_limitations in metric_values:
        change = (
            float(recent_value) - float(baseline_value)
            if baseline_value is not None and recent_value is not None
            else None
        )
        if baseline_value is not None or recent_value is not None:
            evidence.append(
                evidence_factory.add(
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

    weekly_summary: list[JsonValue] = []
    for row in weekly_records:
        week = int(row["week"])
        weekly_sales = float(row["retailer_sales_value"])
        weekly_summary.append(
            json_value(
                {
                    "week": week,
                    "retailer_sales_value": weekly_sales,
                    "trips": int(row["trips"]),
                    "recorded_quantity": float(row["recorded_quantity"]),
                    "distinct_products": int(row["distinct_products"]),
                }
            )
        )
        evidence.append(
            evidence_factory.add(
                "weekly_retailer_sales_value",
                dimensions={"week": str(week)},
                value=weekly_sales,
                unit="retailer_sales_value",
                sql_hash=sql_digest,
            )
        )

    full_slope = slope([float(row["retailer_sales_value"]) for row in weekly_records])
    if full_slope is not None:
        evidence.append(
            evidence_factory.add(
                "full_window_weekly_retailer_sales_value_slope",
                value=full_slope,
                unit="retailer_sales_value_per_week",
                sql_hash=sql_digest,
            )
        )
    changes: dict[str, JsonValue] = {
        metric: _comparison(baseline_value, recent_value)
        for metric, baseline_value, recent_value, _, _ in metric_values
    }
    model_summary: dict[str, JsonValue] = {
        "baseline": json_value(baseline.as_summary()),
        "recent": json_value(recent.as_summary()),
        "changes": json_value(changes),
        "weekly_series": weekly_summary,
        "full_window_weekly_retailer_sales_value_slope": full_slope,
    }
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.CUSTOMER_TREND,
        status=status,
        model_summary=model_summary,
        evidence=tuple(evidence),
        limitations=tuple(limitations),
        retryable=False,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_digest,
            rows_examined=window_rows,
            diagnostics={
                "baseline_transaction_rows": baseline_rows,
                "recent_transaction_rows": recent_rows,
                "zero_filled_week_count": len(weekly_records),
            },
        ),
    )
