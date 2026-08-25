"""Deterministic department and product-category decomposition."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from pydantic import JsonValue

from whyback.config import SOURCE_COMMIT
from whyback.data.repository import DataRepository
from whyback.tools.common import (
    EvidenceFactory,
    ToolTimer,
    json_value,
    make_provenance,
    percentage_change,
    query_hash,
)
from whyback.tools.contracts import (
    CategoryDecompositionInput,
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
_RECONCILIATION_ABSOLUTE_TOLERANCE = 1e-6

_HOUSEHOLD_COUNTS_SQL = """
    SELECT COUNT(*)::BIGINT AS household_rows,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS window_rows,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS baseline_rows,
           COUNT(*) FILTER (WHERE week BETWEEN ? AND ?)::BIGINT AS recent_rows
    FROM transactions
    WHERE household_id = ?
"""

_CATEGORY_SQL = """
    WITH enriched AS (
        SELECT t.week,
               CAST(t.retailer_sales_value AS DECIMAL(38, 6)) AS sales_value,
               COALESCE(NULLIF(TRIM(CAST(p.department AS VARCHAR)), ''), 'UNKNOWN')
                   AS department,
               COALESCE(
                   NULLIF(TRIM(CAST(p.product_category AS VARCHAR)), ''),
                   'UNKNOWN'
               ) AS product_category
        FROM transactions t
        LEFT JOIN products p ON p.product_id = t.product_id
        WHERE t.household_id = ? AND t.week BETWEEN ? AND ?
    )
    SELECT department,
           product_category,
           COALESCE(SUM(sales_value) FILTER (
               WHERE week BETWEEN ? AND ?
           ), 0)::DOUBLE AS baseline_value,
           COALESCE(SUM(sales_value) FILTER (
               WHERE week BETWEEN ? AND ?
           ), 0)::DOUBLE AS recent_value
    FROM enriched
    GROUP BY department, product_category
    ORDER BY department, product_category
"""

_TOTALS_AND_MAPPING_SQL = """
    SELECT
        COALESCE(SUM(CAST(t.retailer_sales_value AS DECIMAL(38, 6))) FILTER (
            WHERE t.week BETWEEN ? AND ?
        ), 0)::DOUBLE AS baseline_total,
        COALESCE(SUM(CAST(t.retailer_sales_value AS DECIMAL(38, 6))) FILTER (
            WHERE t.week BETWEEN ? AND ?
        ), 0)::DOUBLE AS recent_total,
        COUNT(*)::BIGINT AS line_items,
        COUNT(*) FILTER (WHERE p.product_id IS NOT NULL)::BIGINT
            AS mapped_line_items,
        COUNT(DISTINCT t.product_id)::BIGINT AS distinct_products,
        COUNT(DISTINCT CASE WHEN p.product_id IS NOT NULL THEN t.product_id END)
            ::BIGINT AS mapped_distinct_products
    FROM transactions t
    LEFT JOIN products p ON p.product_id = t.product_id
    WHERE t.household_id = ? AND t.week BETWEEN ? AND ?
"""


@dataclass(frozen=True, slots=True)
class _CategoryRow:
    department: str
    product_category: str
    baseline_value: float
    recent_value: float
    absolute_change: float
    percentage_change: float | None
    baseline_share: float | None
    recent_share: float | None
    share_shift: float | None
    loss_contribution_share: float | None

    def as_summary(self) -> JsonValue:
        return json_value(
            {
                "department": self.department,
                "product_category": self.product_category,
                "baseline_retailer_sales_value": self.baseline_value,
                "recent_retailer_sales_value": self.recent_value,
                "absolute_change": self.absolute_change,
                "percentage_change": self.percentage_change,
                "baseline_share": self.baseline_share,
                "recent_share": self.recent_share,
                "share_shift": self.share_shift,
                "loss_contribution_share": self.loss_contribution_share,
            }
        )


def _failed_result(
    parameters: CategoryDecompositionInput,
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
        tool_name=ToolName.CATEGORY_DECOMPOSITION,
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
    return context.source_commit == SOURCE_COMMIT and (
        start <= 1 <= end or start <= 53 <= end
    )


def category_decomposition(
    parameters: CategoryDecompositionInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Attribute retailer-sales changes without dropping unmapped products."""

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

    category_frame = repository.query(
        _CATEGORY_SQL,
        [
            parameters.household_id,
            window.baseline_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
        ],
    )
    raw_categories = cast(
        list[dict[str, Any]], category_frame.to_dict(orient="records")
    )
    totals_frame = repository.query(
        _TOTALS_AND_MAPPING_SQL,
        [
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            parameters.household_id,
            window.baseline_start,
            window.recent_end,
        ],
    )
    totals = cast(dict[str, Any], totals_frame.iloc[0].to_dict())
    baseline_total = float(totals["baseline_total"])
    recent_total = float(totals["recent_total"])
    baseline_category_total = sum(
        float(row["baseline_value"]) for row in raw_categories
    )
    recent_category_total = sum(float(row["recent_value"]) for row in raw_categories)
    baseline_delta = baseline_category_total - baseline_total
    recent_delta = recent_category_total - recent_total
    baseline_reconciled = math.isclose(
        baseline_category_total,
        baseline_total,
        rel_tol=1e-12,
        abs_tol=_RECONCILIATION_ABSOLUTE_TOLERANCE,
    )
    recent_reconciled = math.isclose(
        recent_category_total,
        recent_total,
        rel_tol=1e-12,
        abs_tol=_RECONCILIATION_ABSOLUTE_TOLERANCE,
    )
    if not baseline_reconciled or not recent_reconciled:
        raise RuntimeError(
            "Category decomposition failed separate-window retailer-sales "
            f"reconciliation: baseline_delta={baseline_delta}, "
            f"recent_delta={recent_delta}"
        )

    gross_loss = sum(
        -min(0.0, float(row["recent_value"]) - float(row["baseline_value"]))
        for row in raw_categories
    )
    category_rows: list[_CategoryRow] = []
    for row in raw_categories:
        baseline_value = float(row["baseline_value"])
        recent_value = float(row["recent_value"])
        absolute_change = recent_value - baseline_value
        baseline_share = (
            baseline_value / baseline_total if baseline_total != 0 else None
        )
        recent_share = recent_value / recent_total if recent_total != 0 else None
        category_rows.append(
            _CategoryRow(
                department=str(row["department"]),
                product_category=str(row["product_category"]),
                baseline_value=baseline_value,
                recent_value=recent_value,
                absolute_change=absolute_change,
                percentage_change=percentage_change(baseline_value, recent_value),
                baseline_share=baseline_share,
                recent_share=recent_share,
                share_shift=(
                    recent_share - baseline_share
                    if baseline_share is not None and recent_share is not None
                    else None
                ),
                loss_contribution_share=(
                    -absolute_change / gross_loss
                    if absolute_change < 0 and gross_loss > 0
                    else None
                ),
            )
        )

    losses = sorted(
        (row for row in category_rows if row.absolute_change < 0),
        key=lambda row: (
            row.absolute_change,
            row.department,
            row.product_category,
        ),
    )[: parameters.top_n]
    gains = sorted(
        (row for row in category_rows if row.absolute_change > 0),
        key=lambda row: (
            -row.absolute_change,
            row.department,
            row.product_category,
        ),
    )[: parameters.top_n]

    line_items = int(totals["line_items"])
    mapped_line_items = int(totals["mapped_line_items"])
    distinct_products = int(totals["distinct_products"])
    mapped_distinct_products = int(totals["mapped_distinct_products"])
    line_mapping_coverage = mapped_line_items / line_items if line_items else None
    product_mapping_coverage = (
        mapped_distinct_products / distinct_products if distinct_products else None
    )
    unknown_baseline = sum(
        row.baseline_value
        for row in category_rows
        if row.department == "UNKNOWN" or row.product_category == "UNKNOWN"
    )
    unknown_recent = sum(
        row.recent_value
        for row in category_rows
        if row.department == "UNKNOWN" or row.product_category == "UNKNOWN"
    )

    limitations: list[str] = []
    status = ToolStatus.OK
    if baseline_rows == 0 or recent_rows == 0:
        empty_period = "baseline" if baseline_rows == 0 else "recent"
        limitations.append(
            f"No {empty_period} transactions were observed; changes from that "
            "period cannot be fully compared."
        )
        status = ToolStatus.PARTIAL
    if mapped_line_items < line_items:
        limitations.append(
            "Some transaction products lack a product-table match and are retained "
            "in the explicit UNKNOWN group."
        )
    if _window_has_partial_week(
        context, window.baseline_start, window.baseline_end
    ) or (_window_has_partial_week(context, window.recent_start, window.recent_end)):
        limitations.append(_PARTIAL_WEEK_LIMITATION)

    sql_digest = query_hash(
        _HOUSEHOLD_COUNTS_SQL, _CATEGORY_SQL, _TOTALS_AND_MAPPING_SQL
    )
    evidence_factory = EvidenceFactory(context, ToolName.CATEGORY_DECOMPOSITION)
    evidence: list[EvidenceRecord] = [
        evidence_factory.add(
            "retailer_sales_value",
            baseline_value=baseline_total,
            recent_value=recent_total,
            change=recent_total - baseline_total,
            unit="retailer_sales_value",
            sql_hash=sql_digest,
        ),
        evidence_factory.add(
            "product_mapping_line_item_coverage",
            value=line_mapping_coverage,
            unit="ratio",
            sql_hash=sql_digest,
        ),
        evidence_factory.add(
            "product_mapping_distinct_product_coverage",
            value=product_mapping_coverage,
            unit="ratio",
            sql_hash=sql_digest,
        ),
        evidence_factory.add(
            "unknown_group_retailer_sales_value",
            baseline_value=unknown_baseline,
            recent_value=unknown_recent,
            change=unknown_recent - unknown_baseline,
            unit="retailer_sales_value",
            sql_hash=sql_digest,
        ),
    ]
    selected_rows: list[tuple[str, _CategoryRow]] = [
        *(("loss", row) for row in losses),
        *(("gain", row) for row in gains),
    ]
    for direction, row in selected_rows:
        dimensions = {
            "department": row.department,
            "product_category": row.product_category,
            "direction": direction,
        }
        evidence.append(
            evidence_factory.add(
                "category_retailer_sales_value",
                dimensions=dimensions,
                baseline_value=row.baseline_value,
                recent_value=row.recent_value,
                change=row.absolute_change,
                unit="retailer_sales_value",
                sql_hash=sql_digest,
            )
        )
        if row.percentage_change is not None:
            evidence.append(
                evidence_factory.add(
                    "category_percentage_change",
                    dimensions=dimensions,
                    value=row.percentage_change,
                    unit="ratio",
                    sql_hash=sql_digest,
                )
            )
        if row.baseline_share is not None or row.recent_share is not None:
            evidence.append(
                evidence_factory.add(
                    "category_share_shift",
                    dimensions=dimensions,
                    baseline_value=row.baseline_share,
                    recent_value=row.recent_share,
                    change=row.share_shift,
                    unit="share",
                    sql_hash=sql_digest,
                )
            )
        if row.loss_contribution_share is not None:
            evidence.append(
                evidence_factory.add(
                    "contribution_to_lost_retailer_sales_value",
                    dimensions=dimensions,
                    value=row.loss_contribution_share,
                    unit="share",
                    sql_hash=sql_digest,
                )
            )

    model_summary: dict[str, JsonValue] = {
        "baseline_total_retailer_sales_value": baseline_total,
        "recent_total_retailer_sales_value": recent_total,
        "net_change": recent_total - baseline_total,
        "gross_lost_retailer_sales_value": gross_loss,
        "top_losses": [row.as_summary() for row in losses],
        "top_gains": [row.as_summary() for row in gains],
        "mapping_coverage": json_value(
            {
                "line_item_coverage": line_mapping_coverage,
                "mapped_line_items": mapped_line_items,
                "total_line_items": line_items,
                "distinct_product_coverage": product_mapping_coverage,
                "mapped_distinct_products": mapped_distinct_products,
                "total_distinct_products": distinct_products,
            }
        ),
        "unknown_group": json_value(
            {
                "baseline_retailer_sales_value": unknown_baseline,
                "recent_retailer_sales_value": unknown_recent,
            }
        ),
        "reconciliation": json_value(
            {
                "baseline_transaction_total": baseline_total,
                "baseline_category_total": baseline_category_total,
                "baseline_delta": baseline_delta,
                "baseline_reconciled": baseline_reconciled,
                "recent_transaction_total": recent_total,
                "recent_category_total": recent_category_total,
                "recent_delta": recent_delta,
                "recent_reconciled": recent_reconciled,
            }
        ),
    }
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.CATEGORY_DECOMPOSITION,
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
                "category_group_count": len(category_rows),
                "baseline_reconciled": baseline_reconciled,
                "recent_reconciled": recent_reconciled,
                "baseline_reconciliation_delta": baseline_delta,
                "recent_reconciliation_delta": recent_delta,
            },
        ),
    )
