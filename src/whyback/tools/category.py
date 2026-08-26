"""Deterministic department and product-category decomposition."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from pydantic import JsonValue

from whyback.config import SOURCE_COMMIT
from whyback.data.repository import DataRepository
from whyback.methodology import ClaimType, ContextClassification, classify_context
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
_CATEGORY_CONTEXT_LIMITATION = (
    "Category comparison is a target-excluded household-level descriptive benchmark "
    "among eligible households with meaningful baseline category activity. Broad "
    "contemporaneous movement does not establish seasonality or causation."
)

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
    """Target-household movement and share measures for one product category."""

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
        """Return this category's measures in the model-summary shape."""

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


@dataclass(frozen=True, slots=True)
class _CategoryContext:
    """Target-excluded population context for one selected loss category."""

    category: _CategoryRow
    comparison_count: int
    median_change: float | None
    declining_share: float | None
    target_minus_median_change: float | None
    classification: ContextClassification
    limitations: tuple[str, ...]

    def as_summary(self) -> JsonValue:
        """Return the category comparison and classification for model state."""

        return json_value(
            {
                "department": self.category.department,
                "product_category": self.category.product_category,
                "direction": "loss",
                "target_category_change": self.category.percentage_change,
                "comparison_household_count": self.comparison_count,
                "population_median_change": self.median_change,
                "population_declining_share": self.declining_share,
                "target_minus_population_median_change": (
                    self.target_minus_median_change
                ),
                "context_classification": self.classification.value,
                "target_excluded": True,
                "limitations": list(self.limitations),
            }
        )


def _category_context_sql(category_count: int) -> str:
    """Build parameterized SQL for the requested number of selected categories."""

    if category_count < 1:
        raise ValueError("Category context requires at least one selected category")
    selected_values = ", ".join("(?, ?)" for _ in range(category_count))
    return f"""
        WITH selected_categories(department, product_category) AS (
            VALUES {selected_values}
        ),
        eligible AS (
            SELECT household_id
            FROM household_week
            WHERE week BETWEEN ? AND ? AND household_id <> ?
            GROUP BY household_id
            HAVING COUNT(DISTINCT week) >= ?
               AND SUM(distinct_baskets) >= ?
               AND SUM(retailer_sales_value) > ?
        ),
        enriched AS (
            SELECT t.household_id,
                   t.week,
                   CAST(t.retailer_sales_value AS DECIMAL(38, 6)) AS sales_value,
                   COALESCE(
                       NULLIF(TRIM(CAST(p.department AS VARCHAR)), ''),
                       'UNKNOWN'
                   ) AS department,
                   COALESCE(
                       NULLIF(TRIM(CAST(p.product_category AS VARCHAR)), ''),
                       'UNKNOWN'
                   ) AS product_category
            FROM transactions t
            JOIN eligible e USING (household_id)
            LEFT JOIN products p ON p.product_id = t.product_id
            WHERE t.week BETWEEN ? AND ?
        ),
        category_activity AS (
            SELECT e.household_id,
                   e.department,
                   e.product_category,
                   COALESCE(SUM(e.sales_value) FILTER (
                       WHERE e.week BETWEEN ? AND ?
                   ), 0)::DOUBLE AS baseline_value,
                   COALESCE(SUM(e.sales_value) FILTER (
                       WHERE e.week BETWEEN ? AND ?
                   ), 0)::DOUBLE AS recent_value
            FROM enriched e
            JOIN selected_categories s
              ON s.department = e.department
             AND s.product_category = e.product_category
            GROUP BY e.household_id, e.department, e.product_category
        )
        SELECT household_id,
               department,
               product_category,
               baseline_value,
               recent_value
        FROM category_activity
        WHERE baseline_value >= ?
        ORDER BY department, product_category, household_id
    """


def _category_context_dimensions(
    context: ToolExecutionContext, row: _CategoryRow
) -> dict[str, str]:
    """Describe the category cohort, windows, and sign convention on evidence."""

    window = context.window
    return {
        "department": row.department,
        "product_category": row.product_category,
        "direction": "loss",
        "comparison_scope": "category_population",
        "cohort_definition": (
            "eligible target-excluded households with meaningful baseline category "
            "retailer sales value"
        ),
        "target_excluded": "true",
        "baseline_window": f"{window.baseline_start}-{window.baseline_end}",
        "recent_window": f"{window.recent_start}-{window.recent_end}",
        "change_definition": "(recent-baseline)/baseline",
        "change_sign_convention": "lower_is_worse",
    }


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
    """Build a typed, evidence-free category failure with replay provenance."""

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
    """Return whether an official-data window includes short week 1 or 53."""

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

    policy = context.context_policy
    context_sql: str | None = None
    context_records: list[dict[str, Any]] = []
    category_contexts: list[_CategoryContext] = []
    context_limitations: list[str] = []
    if losses:
        context_sql = _category_context_sql(len(losses))
        selected_parameters: list[object] = [
            value for row in losses for value in (row.department, row.product_category)
        ]
        context_frame = repository.query(
            context_sql,
            [
                *selected_parameters,
                window.baseline_start,
                window.baseline_end,
                context.household_id,
                policy.minimum_baseline_active_weeks,
                policy.minimum_baseline_distinct_baskets,
                policy.minimum_baseline_retailer_sales_value,
                window.baseline_start,
                window.recent_end,
                window.baseline_start,
                window.baseline_end,
                window.recent_start,
                window.recent_end,
                policy.meaningful_category_baseline_retailer_sales_value,
            ],
        )
        context_records = cast(
            list[dict[str, Any]], context_frame.to_dict(orient="records")
        )
        if any(
            str(record["household_id"]) == context.household_id
            for record in context_records
        ):
            raise AssertionError(
                "The target household appeared in a category comparison cohort"
            )
        records_by_category: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for record in context_records:
            key = (str(record["department"]), str(record["product_category"]))
            records_by_category.setdefault(key, []).append(record)

        category_policy = policy.model_copy(
            update={
                "minimum_population_households": policy.minimum_category_households,
                "minimum_peer_households": policy.minimum_category_households,
            }
        )
        for row in losses:
            comparison_records = records_by_category.get(
                (row.department, row.product_category), []
            )
            comparison_count = len(comparison_records)
            sufficient = (
                comparison_count >= policy.minimum_category_households
                and row.percentage_change is not None
            )
            changes = np.asarray(
                [
                    (float(record["recent_value"]) - float(record["baseline_value"]))
                    / float(record["baseline_value"])
                    for record in comparison_records
                ],
                dtype=float,
            )
            median_change = float(np.median(changes)) if sufficient else None
            declining_share = float(np.mean(changes < 0.0)) if sufficient else None
            target_minus_median = (
                row.percentage_change - median_change
                if row.percentage_change is not None and median_change is not None
                else None
            )
            classification = classify_context(
                target_change=row.percentage_change,
                population_median_change=median_change,
                population_declining_share=declining_share,
                peer_median_change=median_change,
                peer_declining_share=declining_share,
                population_count=comparison_count,
                peer_count=comparison_count,
                policy=category_policy,
            )
            category_limitations = [_CATEGORY_CONTEXT_LIMITATION]
            if not sufficient:
                limitation = (
                    f"Category {row.department} / {row.product_category} has "
                    f"{comparison_count} eligible target-excluded households with "
                    "meaningful baseline activity; policy requires at least "
                    f"{policy.minimum_category_households}, so category population "
                    "distribution statistics are unavailable."
                )
                category_limitations.append(limitation)
                context_limitations.append(limitation)
            category_contexts.append(
                _CategoryContext(
                    category=row,
                    comparison_count=comparison_count,
                    median_change=median_change,
                    declining_share=declining_share,
                    target_minus_median_change=target_minus_median,
                    classification=classification,
                    limitations=tuple(category_limitations),
                )
            )

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
    if category_contexts:
        limitations.append(_CATEGORY_CONTEXT_LIMITATION)
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
    if context_limitations:
        limitations.extend(context_limitations)
        status = ToolStatus.PARTIAL

    sql_queries = [_HOUSEHOLD_COUNTS_SQL, _CATEGORY_SQL, _TOTALS_AND_MAPPING_SQL]
    if context_sql is not None:
        sql_queries.append(context_sql)
    sql_digest = query_hash(*sql_queries)
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

    for category_context in category_contexts:
        dimensions = _category_context_dimensions(context, category_context.category)
        evidence.append(
            evidence_factory.add(
                "category_population_household_count",
                dimensions=dimensions,
                value=float(category_context.comparison_count),
                unit="households",
                limitations=category_context.limitations,
                sql_hash=sql_digest,
                maximum_claim_type=ClaimType.DESCRIPTIVE,
            )
        )
        if category_context.median_change is not None:
            evidence.extend(
                [
                    evidence_factory.add(
                        "category_population_median_change",
                        dimensions=dimensions,
                        value=category_context.median_change,
                        unit="proportion",
                        limitations=category_context.limitations,
                        sql_hash=sql_digest,
                        maximum_claim_type=ClaimType.DESCRIPTIVE,
                    ),
                    evidence_factory.add(
                        "category_population_declining_share",
                        dimensions=dimensions,
                        value=category_context.declining_share,
                        unit="proportion",
                        limitations=category_context.limitations,
                        sql_hash=sql_digest,
                        maximum_claim_type=ClaimType.DESCRIPTIVE,
                    ),
                    evidence_factory.add(
                        "target_minus_category_population_median_change",
                        dimensions=dimensions,
                        value=category_context.target_minus_median_change,
                        unit="proportion",
                        limitations=category_context.limitations,
                        sql_hash=sql_digest,
                        maximum_claim_type=ClaimType.DESCRIPTIVE,
                    ),
                ]
            )
        evidence.append(
            evidence_factory.add(
                "category_context_classification",
                dimensions=dimensions,
                text_value=category_context.classification.value,
                unit="classification",
                limitations=category_context.limitations,
                sql_hash=sql_digest,
                maximum_claim_type=ClaimType.ASSOCIATIONAL,
            )
        )

    model_summary: dict[str, JsonValue] = {
        "baseline_total_retailer_sales_value": baseline_total,
        "recent_total_retailer_sales_value": recent_total,
        "net_change": recent_total - baseline_total,
        "gross_lost_retailer_sales_value": gross_loss,
        "top_losses": [row.as_summary() for row in losses],
        "top_gains": [row.as_summary() for row in gains],
        "category_context": [item.as_summary() for item in category_contexts],
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
            rows_examined=window_rows + len(context_records),
            diagnostics={
                "category_group_count": len(category_rows),
                "baseline_reconciled": baseline_reconciled,
                "recent_reconciled": recent_reconciled,
                "baseline_reconciliation_delta": baseline_delta,
                "recent_reconciliation_delta": recent_delta,
                "category_context_target_excluded": True,
                "category_context_comparison_group_rows": len(context_records),
                "category_context_policy": policy.model_dump(mode="json"),
                "category_context": [
                    {
                        "department": item.category.department,
                        "product_category": item.category.product_category,
                        "comparison_household_count": item.comparison_count,
                        "target_excluded": True,
                        "context_classification": item.classification.value,
                    }
                    for item in category_contexts
                ],
            },
        ),
    )
