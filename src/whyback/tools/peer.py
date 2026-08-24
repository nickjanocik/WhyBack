"""Explainable deterministic behavioral peer comparison."""

from __future__ import annotations

import math
from typing import Any, cast

import numpy as np
from pydantic import JsonValue

from whyback.data.repository import DataRepository
from whyback.tools.common import EvidenceFactory, ToolTimer, make_provenance, query_hash
from whyback.tools.contracts import (
    PeerComparisonInput,
    ToolExecutionContext,
    ToolName,
    ToolResult,
    ToolStatus,
)

PEER_METHOD = (
    "Eligible households are robust-scaled on baseline log1p retailer sales value, "
    "trip count, median basket value, active weeks, and category concentration; "
    "nearest Euclidean peers are selected with household-ID tie breaking."
)


def _identifier_key(identifier: str) -> tuple[int, int | str]:
    return (0, int(identifier)) if identifier.isdigit() else (1, identifier)


def run_peer_comparison(
    parameters: PeerComparisonInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Compare the target change with nearest baseline behavioral peers."""

    timer = ToolTimer.start()
    if parameters.household_id != context.household_id:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.PEER_COMPARISON,
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
    window = context.window
    peer_sql = """
        WITH baseline AS (
            SELECT household_id,
                   SUM(retailer_sales_value)::DOUBLE AS baseline_sales,
                   COUNT(*)::BIGINT AS baseline_trips,
                   MEDIAN(retailer_sales_value)::DOUBLE AS median_basket,
                   COUNT(DISTINCT week)::BIGINT AS active_weeks
            FROM baskets
            WHERE week BETWEEN ? AND ?
            GROUP BY household_id
        ),
        recent AS (
            SELECT household_id,
                   SUM(retailer_sales_value)::DOUBLE AS recent_sales
            FROM baskets
            WHERE week BETWEEN ? AND ?
            GROUP BY household_id
        ),
        category_sales AS (
            SELECT t.household_id,
                   COALESCE(p.department, 'UNKNOWN') || ' / ' ||
                       COALESCE(p.product_category, 'UNKNOWN') AS category,
                   SUM(t.retailer_sales_value)::DOUBLE AS category_sales
            FROM transactions t
            LEFT JOIN products p USING (product_id)
            WHERE t.week BETWEEN ? AND ?
            GROUP BY t.household_id, category
        ),
        concentration AS (
            SELECT household_id,
                   SUM(POWER(category_sales / NULLIF(total_sales, 0), 2))::DOUBLE
                       AS category_concentration
            FROM (
                SELECT household_id, category_sales,
                       SUM(category_sales) OVER (PARTITION BY household_id)
                           AS total_sales
                FROM category_sales
            )
            GROUP BY household_id
        )
        SELECT b.household_id, b.baseline_sales, b.baseline_trips,
               b.median_basket, b.active_weeks,
               COALESCE(c.category_concentration, 0)::DOUBLE
                   AS category_concentration,
               COALESCE(r.recent_sales, 0)::DOUBLE AS recent_sales
        FROM baseline b
        LEFT JOIN recent r USING (household_id)
        LEFT JOIN concentration c USING (household_id)
        WHERE b.active_weeks >= 4 AND b.baseline_trips >= 6
              AND b.baseline_sales > 0
        ORDER BY b.household_id
    """
    sql_hash = query_hash(peer_sql)
    frame = repository.query(
        peer_sql,
        [
            window.baseline_start,
            window.baseline_end,
            window.recent_start,
            window.recent_end,
            window.baseline_start,
            window.baseline_end,
        ],
    )
    records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))
    target_index = next(
        (
            index
            for index, row in enumerate(records)
            if str(row["household_id"]) == context.household_id
        ),
        None,
    )
    if target_index is None:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.PEER_COMPARISON,
            status=ToolStatus.MISSING_DATA,
            limitations=(
                "The target does not meet the baseline eligibility contract for peers.",
            ),
            provenance=make_provenance(
                context,
                parameters,
                timer=timer,
                sql_hash=sql_hash,
                rows_examined=len(records),
            ),
        )
    if len(records) <= 1:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.PEER_COMPARISON,
            status=ToolStatus.MISSING_DATA,
            limitations=(
                "No eligible peer household remains after excluding the target.",
            ),
            provenance=make_provenance(
                context,
                parameters,
                timer=timer,
                sql_hash=sql_hash,
                rows_examined=len(records),
            ),
        )

    features = np.asarray(
        [
            [
                math.log1p(max(0.0, float(row["baseline_sales"]))),
                float(row["baseline_trips"]),
                float(row["median_basket"]),
                float(row["active_weeks"]),
                float(row["category_concentration"]),
            ]
            for row in records
        ],
        dtype=float,
    )
    feature_medians = np.median(features, axis=0)
    q25 = np.percentile(features, 25, axis=0)
    q75 = np.percentile(features, 75, axis=0)
    scales = q75 - q25
    scales[scales == 0] = 1.0
    scaled = (features - feature_medians) / scales
    distances = np.sqrt(np.square(scaled - scaled[target_index]).sum(axis=1))
    ranked = [
        (index, float(distance), str(records[index]["household_id"]))
        for index, distance in enumerate(distances)
        if index != target_index
    ]
    ranked.sort(key=lambda item: (item[1], _identifier_key(item[2])))
    selected = ranked[: parameters.peer_count]
    if not selected:
        raise AssertionError(
            "Target exclusion left an unexpectedly empty peer selection"
        )
    peer_ids = [item[2] for item in selected]
    if context.household_id in peer_ids:
        raise AssertionError("The target household appeared in its own peer cohort")

    def sales_change(row: dict[str, Any]) -> float:
        baseline = float(row["baseline_sales"])
        return (float(row["recent_sales"]) - baseline) / baseline

    peer_changes = np.asarray(
        [sales_change(records[index]) for index, _, _ in selected], dtype=float
    )
    target_change = sales_change(records[target_index])
    median_change = float(np.median(peer_changes))
    peer_q25 = float(np.percentile(peer_changes, 25))
    peer_q75 = float(np.percentile(peer_changes, 75))
    target_percentile = float(np.mean(peer_changes <= target_change) * 100.0)
    limitations: tuple[str, ...] = (
        "Peer similarity is descriptive, depends on the selected baseline "
        "features, and does not establish a causal benchmark.",
    )
    status = ToolStatus.OK
    if len(selected) < parameters.peer_count:
        status = ToolStatus.PARTIAL
        limitations += (
            f"Only {len(selected)} eligible peers were available instead of the "
            f"requested {parameters.peer_count}.",
        )

    evidence_factory = EvidenceFactory(context, ToolName.PEER_COMPARISON)
    evidence = (
        evidence_factory.add(
            "target_retailer_sales_change",
            value=target_change,
            unit="proportion",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "peer_median_retailer_sales_change",
            value=median_change,
            unit="proportion",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "peer_retailer_sales_change_q25",
            value=peer_q25,
            unit="proportion",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "peer_retailer_sales_change_q75",
            value=peer_q75,
            unit="proportion",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "target_retailer_sales_change_percentile",
            value=target_percentile,
            unit="percentile",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
    )
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.PEER_COMPARISON,
        status=status,
        model_summary=cast(
            dict[str, JsonValue],
            {
                "methodology": PEER_METHOD,
                "peer_count": len(selected),
                "target_retailer_sales_change": target_change,
                "peer_median_retailer_sales_change": median_change,
                "peer_change_q25": peer_q25,
                "peer_change_q75": peer_q75,
                "target_change_percentile": target_percentile,
                "peer_household_ids": peer_ids,
            },
        ),
        evidence=evidence,
        limitations=limitations,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_hash,
            rows_examined=len(records),
            diagnostics=cast(
                dict[str, JsonValue],
                {
                    "target_household_id": context.household_id,
                    "peer_household_ids": peer_ids,
                    "target_excluded": context.household_id not in peer_ids,
                    "feature_names": [
                        "log1p_baseline_retailer_sales_value",
                        "baseline_trip_count",
                        "baseline_median_basket_value",
                        "baseline_active_weeks",
                        "baseline_category_concentration",
                    ],
                    "zero_iqr_features": [
                        index for index, scale in enumerate(q75 - q25) if scale == 0
                    ],
                },
            ),
        ),
    )
