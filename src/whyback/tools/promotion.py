"""Deterministic promotion-availability analysis."""

from __future__ import annotations

import math
from typing import Any, cast

from pydantic import JsonValue

from whyback.data.repository import DataRepository
from whyback.tools.common import (
    EvidenceFactory,
    ToolTimer,
    make_provenance,
    query_hash,
)
from whyback.tools.contracts import (
    PromotionResponseInput,
    ToolExecutionContext,
    ToolName,
    ToolResult,
    ToolStatus,
)

AVAILABILITY_LIMITATION = (
    "Promotion records indicate availability for a product at a store during a week; "
    "they do not establish that this household saw a display or mailer."
)
ASSOCIATION_LIMITATION = (
    "Observed promotion-associated purchasing is descriptive and does not establish "
    "that promotion availability caused the behavioral change."
)


def _invalid_customer_result(
    parameters: PromotionResponseInput,
    context: ToolExecutionContext,
    timer: ToolTimer,
) -> ToolResult:
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.PROMOTION_RESPONSE,
        status=ToolStatus.INVALID_REQUEST,
        limitations=(
            "The requested household does not match the active investigation.",
        ),
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=None,
            rows_examined=0,
        ),
    )


def run_promotion_response(
    parameters: PromotionResponseInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Compare purchasing with recorded promotion availability across windows."""

    timer = ToolTimer.start()
    if parameters.household_id != context.household_id:
        return _invalid_customer_result(parameters, context, timer)

    window = context.window
    raw_sql = """
        SELECT COUNT(*)::BIGINT AS line_count,
               COALESCE(SUM(retailer_sales_value), 0)::DOUBLE AS retailer_sales_value
        FROM transactions
        WHERE household_id = ? AND week BETWEEN ? AND ?
    """
    joined_sql = """
        SELECT
            CASE WHEN t.week BETWEEN ? AND ? THEN 'baseline' ELSE 'recent' END
                AS period,
            COUNT(*)::BIGINT AS line_count,
            COALESCE(SUM(t.retailer_sales_value), 0)::DOUBLE AS total_sales,
            COALESCE(SUM(t.retailer_sales_value)
                FILTER (WHERE p.product_id IS NOT NULL), 0)::DOUBLE
                AS promotion_sales,
            COALESCE(SUM(t.retailer_sales_value)
                FILTER (WHERE p.any_display), 0)::DOUBLE AS display_sales,
            COALESCE(SUM(t.retailer_sales_value)
                FILTER (WHERE p.any_mailer), 0)::DOUBLE AS mailer_sales,
            COUNT(*) FILTER (WHERE p.product_id IS NOT NULL)::BIGINT
                AS promotion_lines
        FROM transactions t
        LEFT JOIN promotion_state p USING (product_id, store_id, week)
        WHERE t.household_id = ? AND t.week BETWEEN ? AND ?
        GROUP BY period
        ORDER BY period
    """
    category_sql = """
        SELECT COALESCE(pr.department, 'UNKNOWN') AS department,
               COALESCE(pr.product_category, 'UNKNOWN') AS product_category,
               COALESCE(SUM(t.retailer_sales_value)
                   FILTER (WHERE t.week BETWEEN ? AND ?
                           AND p.product_id IS NOT NULL), 0)::DOUBLE
                   AS baseline_promotion_sales,
               COALESCE(SUM(t.retailer_sales_value)
                   FILTER (WHERE t.week BETWEEN ? AND ?
                           AND p.product_id IS NOT NULL), 0)::DOUBLE
                   AS recent_promotion_sales
        FROM transactions t
        LEFT JOIN promotion_state p USING (product_id, store_id, week)
        LEFT JOIN products pr USING (product_id)
        WHERE t.household_id = ? AND t.week BETWEEN ? AND ?
        GROUP BY department, product_category
    """
    sql_hash = query_hash(raw_sql, joined_sql, category_sql)
    raw = repository.query(
        raw_sql,
        [context.household_id, window.baseline_start, window.recent_end],
    )
    raw_record = cast(dict[str, Any], raw.to_dict(orient="records")[0])
    raw_count = int(raw_record["line_count"])
    raw_sales = float(raw_record["retailer_sales_value"])
    if raw_count == 0:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.PROMOTION_RESPONSE,
            status=ToolStatus.MISSING_DATA,
            limitations=(
                "No transaction rows exist for the household in either window.",
            ),
            provenance=make_provenance(
                context,
                parameters,
                timer=timer,
                sql_hash=sql_hash,
                rows_examined=0,
            ),
        )

    joined = repository.query(
        joined_sql,
        [
            window.baseline_start,
            window.baseline_end,
            context.household_id,
            window.baseline_start,
            window.recent_end,
        ],
    )
    joined_records = cast(list[dict[str, Any]], joined.to_dict(orient="records"))
    joined_count = sum(int(row["line_count"]) for row in joined_records)
    joined_sales = sum(float(row["total_sales"]) for row in joined_records)
    count_preserved = joined_count == raw_count
    sales_preserved = math.isclose(joined_sales, raw_sales, rel_tol=1e-9, abs_tol=1e-6)
    diagnostics: dict[str, JsonValue] = {
        "raw_transaction_rows": raw_count,
        "enriched_transaction_rows": joined_count,
        "raw_retailer_sales_value": raw_sales,
        "enriched_retailer_sales_value": joined_sales,
        "row_count_preserved": count_preserved,
        "retailer_sales_value_preserved": sales_preserved,
        "promotion_key": ["product_id", "store_id", "week"],
    }
    if not count_preserved or not sales_preserved:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.PROMOTION_RESPONSE,
            status=ToolStatus.FATAL_ERROR,
            limitations=(
                "Promotion enrichment failed its transaction non-multiplication "
                "invariant.",
            ),
            provenance=make_provenance(
                context,
                parameters,
                timer=timer,
                sql_hash=sql_hash,
                rows_examined=raw_count,
                diagnostics=diagnostics,
            ),
        )

    by_period = {str(row["period"]): row for row in joined_records}

    def metric(period: str, name: str) -> float:
        row = by_period.get(period)
        return 0.0 if row is None else float(row[name])

    baseline_total = metric("baseline", "total_sales")
    recent_total = metric("recent", "total_sales")
    baseline_promo = metric("baseline", "promotion_sales")
    recent_promo = metric("recent", "promotion_sales")
    baseline_share = baseline_promo / baseline_total if baseline_total else 0.0
    recent_share = recent_promo / recent_total if recent_total else 0.0
    category = repository.query(
        category_sql,
        [
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            context.household_id,
            window.baseline_start,
            window.recent_end,
        ],
    )
    category_records = cast(list[dict[str, Any]], category.to_dict(orient="records"))
    for row in category_records:
        row["change"] = float(row["recent_promotion_sales"]) - float(
            row["baseline_promotion_sales"]
        )
    category_records.sort(
        key=lambda row: (
            float(row["change"]),
            str(row["department"]),
            str(row["product_category"]),
        )
    )
    top_changes = category_records[: parameters.top_n_categories]

    evidence_factory = EvidenceFactory(context, ToolName.PROMOTION_RESPONSE)
    evidence = [
        evidence_factory.add(
            "promotion_associated_retailer_sales_value",
            baseline_value=baseline_promo,
            recent_value=recent_promo,
            change=recent_promo - baseline_promo,
            unit="retailer_sales_value",
            limitations=(AVAILABILITY_LIMITATION, ASSOCIATION_LIMITATION),
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "promotion_associated_share",
            baseline_value=baseline_share,
            recent_value=recent_share,
            change=recent_share - baseline_share,
            unit="proportion",
            limitations=(AVAILABILITY_LIMITATION, ASSOCIATION_LIMITATION),
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "display_associated_retailer_sales_value",
            baseline_value=metric("baseline", "display_sales"),
            recent_value=metric("recent", "display_sales"),
            change=(
                metric("recent", "display_sales") - metric("baseline", "display_sales")
            ),
            unit="retailer_sales_value",
            limitations=(AVAILABILITY_LIMITATION, ASSOCIATION_LIMITATION),
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "mailer_associated_retailer_sales_value",
            baseline_value=metric("baseline", "mailer_sales"),
            recent_value=metric("recent", "mailer_sales"),
            change=(
                metric("recent", "mailer_sales") - metric("baseline", "mailer_sales")
            ),
            unit="retailer_sales_value",
            limitations=(AVAILABILITY_LIMITATION, ASSOCIATION_LIMITATION),
            sql_hash=sql_hash,
        ),
    ]
    for row in top_changes:
        evidence.append(
            evidence_factory.add(
                "category_promotion_associated_retailer_sales_value",
                dimensions={
                    "department": str(row["department"]),
                    "category": str(row["product_category"]),
                },
                baseline_value=float(row["baseline_promotion_sales"]),
                recent_value=float(row["recent_promotion_sales"]),
                change=float(row["change"]),
                unit="retailer_sales_value",
                limitations=(AVAILABILITY_LIMITATION, ASSOCIATION_LIMITATION),
                sql_hash=sql_hash,
            )
        )
    matched_lines = sum(int(row["promotion_lines"]) for row in joined_records)
    window_limitations: tuple[str, ...] = tuple(
        f"No {period} transaction rows were observed; promotion-associated "
        "comparisons for that window are unavailable."
        for period in ("baseline", "recent")
        if period not in by_period
    )
    if matched_lines == 0:
        absence_limitation = (
            "No transaction line matched a recorded promotion key; this does not prove "
            "the household had no other marketing contact."
        )
        limitations = (
            AVAILABILITY_LIMITATION,
            ASSOCIATION_LIMITATION,
            absence_limitation,
            *window_limitations,
        )
    else:
        limitations = (
            AVAILABILITY_LIMITATION,
            ASSOCIATION_LIMITATION,
            *window_limitations,
        )
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.PROMOTION_RESPONSE,
        status=ToolStatus.PARTIAL if window_limitations else ToolStatus.OK,
        model_summary={
            "baseline_promotion_associated_retailer_sales_value": baseline_promo,
            "recent_promotion_associated_retailer_sales_value": recent_promo,
            "baseline_promotion_associated_share": baseline_share,
            "recent_promotion_associated_share": recent_share,
            "matched_transaction_lines": matched_lines,
            "top_category_losses": [
                {
                    "department": str(row["department"]),
                    "category": str(row["product_category"]),
                    "change": float(row["change"]),
                }
                for row in top_changes
            ],
        },
        evidence=tuple(evidence),
        limitations=limitations,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_hash,
            rows_examined=raw_count,
            diagnostics=diagnostics,
        ),
    )
