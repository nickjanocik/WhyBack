"""Explainable deterministic population and behavioral-peer comparison."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from pydantic import JsonValue

from whyback.data.repository import DataRepository
from whyback.methodology import ClaimType, classify_context
from whyback.tools.common import (
    EvidenceFactory,
    ToolTimer,
    json_value,
    make_provenance,
    query_hash,
)
from whyback.tools.contracts import (
    PeerComparisonInput,
    ToolExecutionContext,
    ToolName,
    ToolResult,
    ToolStatus,
)

POPULATION_METHOD = (
    "The target is compared with the household-level distribution of signed "
    "retailer-sales changes among all other households meeting the declared baseline "
    "eligibility policy. The target is excluded, and lower change means a more severe "
    "decline."
)
PEER_METHOD = (
    "Eligible target-excluded households are robust-scaled on baseline log1p retailer "
    "sales value, trip count, median basket value, active weeks, and category "
    "concentration. Scaling is fit on comparison households only; nearest Euclidean "
    "peers are selected with household-ID tie breaking."
)
_POPULATION_LIMITATION = (
    "Eligible-population context is a household-level descriptive benchmark, excludes "
    "the target, and does not identify seasonality or a cause of change."
)
_PEER_LIMITATION = (
    "Peer similarity is descriptive, depends on the selected baseline features, "
    "excludes the target, and does not establish a causal control group."
)


@dataclass(frozen=True, slots=True)
class _Distribution:
    """Summary statistics comparing the target change with one household cohort."""

    count: int
    median: float
    q25: float
    q75: float
    target_percentile: float
    declining_share: float
    target_minus_median: float


def _identifier_key(identifier: str) -> tuple[int, int | str]:
    """Sort numeric household IDs numerically before stable text identifiers."""

    return (0, int(identifier)) if identifier.isdigit() else (1, identifier)


def _sales_change(row: dict[str, Any]) -> float:
    """Calculate signed retailer-sales change from an eligible household row."""

    baseline = float(row["baseline_sales"])
    return (float(row["recent_sales"]) - baseline) / baseline


def _distribution(values: np.ndarray, target_change: float) -> _Distribution:
    """Summarize a nonempty cohort and locate the target within its changes."""

    if not values.size:
        raise ValueError("A comparison distribution cannot be empty")
    median_change = float(np.median(values))
    return _Distribution(
        count=int(values.size),
        median=median_change,
        q25=float(np.percentile(values, 25)),
        q75=float(np.percentile(values, 75)),
        target_percentile=float(np.mean(values <= target_change) * 100.0),
        declining_share=float(np.mean(values < 0.0)),
        target_minus_median=target_change - median_change,
    )


def _dimensions(
    context: ToolExecutionContext,
    *,
    scope: str,
    definition: str,
) -> dict[str, str]:
    """Describe a target-excluded comparison cohort and its change convention."""

    window = context.window
    return {
        "comparison_scope": scope,
        "cohort_definition": definition,
        "target_excluded": "true",
        "baseline_window": f"{window.baseline_start}-{window.baseline_end}",
        "recent_window": f"{window.recent_start}-{window.recent_end}",
        "change_definition": "(recent-baseline)/baseline",
        "change_sign_convention": "lower_is_worse",
        "quartile_method": "linear",
        "target_percentile_definition": (
            "share_of_comparison_changes_less_than_or_equal_to_target"
        ),
    }


def run_peer_comparison(
    parameters: PeerComparisonInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Compare target change with target-excluded population and behavioral peers."""

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
    policy = context.context_policy
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
        WHERE b.active_weeks >= ? AND b.baseline_trips >= ?
              AND b.baseline_sales > ?
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
            policy.minimum_baseline_active_weeks,
            policy.minimum_baseline_distinct_baskets,
            policy.minimum_baseline_retailer_sales_value,
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

    target_change = _sales_change(records[target_index])
    comparison_indices = [
        index for index in range(len(records)) if index != target_index
    ]
    comparison_ids = [
        str(records[index]["household_id"]) for index in comparison_indices
    ]
    if context.household_id in comparison_ids:
        raise AssertionError(
            "The target household appeared in the comparison population"
        )
    population_changes = np.asarray(
        [_sales_change(records[index]) for index in comparison_indices], dtype=float
    )

    selected: list[tuple[int, float, str]] = []
    zero_iqr_features: list[int] = []
    if comparison_indices:
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
        fit_features = features[comparison_indices]
        feature_medians = np.median(fit_features, axis=0)
        feature_q25 = np.percentile(fit_features, 25, axis=0)
        feature_q75 = np.percentile(fit_features, 75, axis=0)
        raw_scales = feature_q75 - feature_q25
        zero_iqr_features = [
            index for index, scale in enumerate(raw_scales) if scale == 0
        ]
        scales = raw_scales.copy()
        scales[scales == 0] = 1.0
        target_scaled = (features[target_index] - feature_medians) / scales
        comparison_scaled = (fit_features - feature_medians) / scales
        distances = np.sqrt(np.square(comparison_scaled - target_scaled).sum(axis=1))
        selected = [
            (record_index, float(distance), str(records[record_index]["household_id"]))
            for record_index, distance in zip(
                comparison_indices, distances, strict=True
            )
        ]
        selected.sort(key=lambda item: (item[1], _identifier_key(item[2])))
        selected = selected[: parameters.peer_count]

    peer_ids = [item[2] for item in selected]
    if context.household_id in peer_ids:
        raise AssertionError("The target household appeared in its own peer cohort")
    peer_changes = np.asarray(
        [_sales_change(records[index]) for index, _, _ in selected], dtype=float
    )

    population_sufficient = (
        len(comparison_indices) >= policy.minimum_population_households
    )
    peers_sufficient = len(selected) >= policy.minimum_peer_households
    population_distribution = (
        _distribution(population_changes, target_change)
        if population_sufficient
        else None
    )
    peer_distribution = (
        _distribution(peer_changes, target_change) if peers_sufficient else None
    )
    classification = classify_context(
        target_change=target_change,
        population_median_change=(
            population_distribution.median if population_distribution else None
        ),
        population_declining_share=(
            population_distribution.declining_share if population_distribution else None
        ),
        peer_median_change=(peer_distribution.median if peer_distribution else None),
        peer_declining_share=(
            peer_distribution.declining_share if peer_distribution else None
        ),
        population_count=len(comparison_indices),
        peer_count=len(selected),
        policy=policy,
    )

    limitations: list[str] = [_POPULATION_LIMITATION, _PEER_LIMITATION]
    status = ToolStatus.OK
    if not population_sufficient:
        status = ToolStatus.PARTIAL
        limitations.append(
            "Eligible comparison population has "
            f"{len(comparison_indices)} target-excluded households; policy requires "
            f"at least {policy.minimum_population_households}, so population "
            "distribution statistics are unavailable."
        )
    if not peers_sufficient:
        status = ToolStatus.PARTIAL
        limitations.append(
            f"Behavioral peer cohort has {len(selected)} target-excluded households; "
            f"policy requires at least {policy.minimum_peer_households}, so peer "
            "distribution statistics are unavailable."
        )
    elif len(selected) < parameters.peer_count:
        status = ToolStatus.PARTIAL
        limitations.append(
            f"Only {len(selected)} eligible peers were available instead of the "
            f"requested {parameters.peer_count}."
        )
    limitation_tuple = tuple(limitations)

    population_dimensions = _dimensions(
        context,
        scope="eligible_population",
        definition=POPULATION_METHOD,
    )
    peer_dimensions = _dimensions(
        context,
        scope="behavioral_peers",
        definition=PEER_METHOD,
    )
    combined_dimensions = {
        **population_dimensions,
        "comparison_scope": "eligible_population_and_behavioral_peers",
        "peer_cohort_definition": PEER_METHOD,
    }
    evidence_factory = EvidenceFactory(context, ToolName.PEER_COMPARISON)
    evidence = [
        evidence_factory.add(
            "target_retailer_sales_change",
            value=target_change,
            unit="proportion",
            limitations=limitation_tuple,
            sql_hash=sql_hash,
            maximum_claim_type=ClaimType.DESCRIPTIVE,
        ),
        evidence_factory.add(
            "population_household_count",
            dimensions=population_dimensions,
            value=float(len(comparison_indices)),
            unit="households",
            limitations=limitation_tuple,
            sql_hash=sql_hash,
            maximum_claim_type=ClaimType.DESCRIPTIVE,
        ),
        evidence_factory.add(
            "peer_household_count",
            dimensions=peer_dimensions,
            value=float(len(selected)),
            unit="households",
            limitations=limitation_tuple,
            sql_hash=sql_hash,
            maximum_claim_type=ClaimType.DESCRIPTIVE,
        ),
    ]

    def add_distribution_evidence(
        *, scope: str, distribution: _Distribution, dimensions: dict[str, str]
    ) -> None:
        """Append the complete evidence set for one available comparison cohort."""

        prefix = "population" if scope == "population" else "peer"
        evidence.extend(
            [
                evidence_factory.add(
                    f"{prefix}_median_retailer_sales_change",
                    dimensions=dimensions,
                    value=distribution.median,
                    unit="proportion",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
                evidence_factory.add(
                    f"{prefix}_retailer_sales_change_q25",
                    dimensions=dimensions,
                    value=distribution.q25,
                    unit="proportion",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
                evidence_factory.add(
                    f"{prefix}_retailer_sales_change_q75",
                    dimensions=dimensions,
                    value=distribution.q75,
                    unit="proportion",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
                evidence_factory.add(
                    f"target_{prefix}_retailer_sales_change_percentile",
                    dimensions=dimensions,
                    value=distribution.target_percentile,
                    unit="percentile",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
                evidence_factory.add(
                    f"{prefix}_declining_household_share",
                    dimensions=dimensions,
                    value=distribution.declining_share,
                    unit="proportion",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
                evidence_factory.add(
                    f"target_minus_{prefix}_median_change",
                    dimensions=dimensions,
                    value=distribution.target_minus_median,
                    unit="proportion",
                    limitations=limitation_tuple,
                    sql_hash=sql_hash,
                    maximum_claim_type=ClaimType.DESCRIPTIVE,
                ),
            ]
        )

    if population_distribution is not None:
        add_distribution_evidence(
            scope="population",
            distribution=population_distribution,
            dimensions=population_dimensions,
        )
    if peer_distribution is not None:
        add_distribution_evidence(
            scope="peer",
            distribution=peer_distribution,
            dimensions=peer_dimensions,
        )
        # Compatibility metric retained for the existing action catalog.
        evidence.append(
            evidence_factory.add(
                "target_retailer_sales_change_percentile",
                dimensions=peer_dimensions,
                value=peer_distribution.target_percentile,
                unit="percentile",
                limitations=limitation_tuple,
                sql_hash=sql_hash,
                maximum_claim_type=ClaimType.DESCRIPTIVE,
            )
        )
    evidence.append(
        evidence_factory.add(
            "context_classification",
            dimensions=combined_dimensions,
            text_value=classification.value,
            unit="classification",
            limitations=limitation_tuple,
            sql_hash=sql_hash,
            maximum_claim_type=ClaimType.ASSOCIATIONAL,
        )
    )

    population_summary: dict[str, JsonValue] = {
        "methodology": POPULATION_METHOD,
        "household_count": len(comparison_indices),
        "target_excluded": True,
        "median_retailer_sales_change": (
            population_distribution.median if population_distribution else None
        ),
        "retailer_sales_change_q25": (
            population_distribution.q25 if population_distribution else None
        ),
        "retailer_sales_change_q75": (
            population_distribution.q75 if population_distribution else None
        ),
        "target_change_percentile": (
            population_distribution.target_percentile
            if population_distribution
            else None
        ),
        "declining_household_share": (
            population_distribution.declining_share if population_distribution else None
        ),
        "target_minus_median_change": (
            population_distribution.target_minus_median
            if population_distribution
            else None
        ),
    }
    peer_summary: dict[str, JsonValue] = {
        "methodology": PEER_METHOD,
        "household_count": len(selected),
        "target_excluded": True,
        "median_retailer_sales_change": (
            peer_distribution.median if peer_distribution else None
        ),
        "retailer_sales_change_q25": (
            peer_distribution.q25 if peer_distribution else None
        ),
        "retailer_sales_change_q75": (
            peer_distribution.q75 if peer_distribution else None
        ),
        "target_change_percentile": (
            peer_distribution.target_percentile if peer_distribution else None
        ),
        "declining_household_share": (
            peer_distribution.declining_share if peer_distribution else None
        ),
        "target_minus_median_change": (
            peer_distribution.target_minus_median if peer_distribution else None
        ),
        "peer_household_ids": json_value(peer_ids),
    }
    model_summary = cast(
        dict[str, JsonValue],
        {
            "methodology": PEER_METHOD,
            "population_methodology": POPULATION_METHOD,
            "target_retailer_sales_change": target_change,
            "context_classification": classification.value,
            "population_context": population_summary,
            "peer_context": peer_summary,
            # Stable compatibility fields retained for existing consumers.
            "peer_count": len(selected),
            "peer_median_retailer_sales_change": (
                peer_distribution.median if peer_distribution else None
            ),
            "peer_change_q25": peer_distribution.q25 if peer_distribution else None,
            "peer_change_q75": peer_distribution.q75 if peer_distribution else None,
            "target_change_percentile": (
                peer_distribution.target_percentile if peer_distribution else None
            ),
            "peer_household_ids": peer_ids,
        },
    )
    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.PEER_COMPARISON,
        status=status,
        model_summary=model_summary,
        evidence=tuple(evidence),
        limitations=limitation_tuple,
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
                    "population_target_excluded": (
                        context.household_id not in comparison_ids
                    ),
                    "population_household_count": len(comparison_indices),
                    "peer_household_count": len(selected),
                    "robust_scaling_fit_target_excluded": True,
                    "context_classification": classification.value,
                    "context_policy": policy.model_dump(mode="json"),
                    "baseline_eligibility_policy": {
                        "minimum_baseline_active_weeks": (
                            policy.minimum_baseline_active_weeks
                        ),
                        "minimum_baseline_distinct_baskets": (
                            policy.minimum_baseline_distinct_baskets
                        ),
                        "minimum_baseline_retailer_sales_value": (
                            policy.minimum_baseline_retailer_sales_value
                        ),
                    },
                    "baseline_window": [window.baseline_start, window.baseline_end],
                    "recent_window": [window.recent_start, window.recent_end],
                    "change_sign_convention": "lower_is_worse",
                    "feature_names": [
                        "log1p_baseline_retailer_sales_value",
                        "baseline_trip_count",
                        "baseline_median_basket_value",
                        "baseline_active_weeks",
                        "baseline_category_concentration",
                    ],
                    "zero_iqr_features": zero_iqr_features,
                },
            ),
        ),
    )
