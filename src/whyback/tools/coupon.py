"""Deterministic campaign participation and coupon-response history."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from whyback.data.repository import DataRepository
from whyback.tools.common import EvidenceFactory, ToolTimer, make_provenance, query_hash
from whyback.tools.contracts import (
    CouponCampaignHistoryInput,
    ToolExecutionContext,
    ToolName,
    ToolResult,
    ToolStatus,
)

TYPE_A_LIMITATION = (
    "Type A participants received 16 coupons selected from a larger pool, but the "
    "household-specific delivered coupon identities are unavailable."
)


def _date_text(value: object) -> str:
    """Serialize date-like campaign fields while tolerating source scalar types."""

    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def run_coupon_campaign_history(
    parameters: CouponCampaignHistoryInput,
    context: ToolExecutionContext,
    repository: DataRepository,
) -> ToolResult:
    """Report known campaign/redemption facts without inventing Type A exposure."""

    timer = ToolTimer.start()
    if parameters.household_id != context.household_id:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.COUPON_CAMPAIGN_HISTORY,
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

    campaign_sql = """
        SELECT c.campaign_id, d.campaign_type, d.start_date, d.end_date,
               COUNT(DISTINCT cp.coupon_upc)::BIGINT AS campaign_coupon_count
        FROM campaigns c
        JOIN campaign_descriptions d USING (campaign_id)
        LEFT JOIN coupons cp USING (campaign_id)
        WHERE c.household_id = ?
        GROUP BY c.campaign_id, d.campaign_type, d.start_date, d.end_date
        ORDER BY d.start_date, c.campaign_id
    """
    redemption_sql = """
        SELECT r.household_id, r.campaign_id, r.coupon_upc, r.redemption_date
        FROM coupon_redemptions r
        JOIN (
            SELECT DISTINCT coupon_upc, campaign_id FROM coupons
        ) c USING (coupon_upc, campaign_id)
        WHERE r.household_id = ?
        ORDER BY r.redemption_date, r.campaign_id, r.coupon_upc
    """
    usage_sql = """
        SELECT
            CASE WHEN week BETWEEN ? AND ? THEN 'baseline' ELSE 'recent' END period,
            COUNT(DISTINCT basket_id)
                FILTER (WHERE coupon_discount > 0 OR coupon_match_discount > 0)::BIGINT
                AS coupon_baskets,
            COALESCE(SUM(coupon_discount + coupon_match_discount), 0)::DOUBLE
                AS recorded_coupon_discount,
            COUNT(*)::BIGINT AS transaction_lines
        FROM transactions
        WHERE household_id = ? AND week BETWEEN ? AND ?
        GROUP BY period
    """
    household_sql = "SELECT COUNT(*) FROM transactions WHERE household_id = ?"
    sql_hash = query_hash(campaign_sql, redemption_sql, usage_sql, household_sql)
    transaction_rows = int(repository.scalar(household_sql, [context.household_id]))
    if transaction_rows == 0:
        return ToolResult(
            tool_call_id=context.tool_call_id,
            tool_name=ToolName.COUPON_CAMPAIGN_HISTORY,
            status=ToolStatus.INVALID_REQUEST,
            limitations=("The household is unknown in prepared transactions.",),
            provenance=make_provenance(
                context,
                parameters,
                timer=timer,
                sql_hash=sql_hash,
                rows_examined=0,
            ),
        )

    campaigns = cast(
        list[dict[str, Any]],
        repository.query(campaign_sql, [context.household_id]).to_dict(
            orient="records"
        ),
    )
    redemptions = cast(
        list[dict[str, Any]],
        repository.query(redemption_sql, [context.household_id]).to_dict(
            orient="records"
        ),
    )
    window = context.window
    usage = cast(
        list[dict[str, Any]],
        repository.query(
            usage_sql,
            [
                window.baseline_start,
                window.baseline_end,
                context.household_id,
                window.baseline_start,
                window.recent_end,
            ],
        ).to_dict(orient="records"),
    )
    usage_by_period = {str(row["period"]): row for row in usage}

    def usage_value(period: str, field: str) -> float:
        """Read one coupon-usage measure and use zero for an absent period."""

        row = usage_by_period.get(period)
        return 0.0 if row is None else float(row[field])

    has_type_a = any(str(row["campaign_type"]) == "Type A" for row in campaigns)
    limitations: tuple[str, ...] = (TYPE_A_LIMITATION,) if has_type_a else ()
    evidence_factory = EvidenceFactory(context, ToolName.COUPON_CAMPAIGN_HISTORY)
    evidence = [
        evidence_factory.add(
            "campaign_participation_count",
            value=float(len(campaigns)),
            unit="campaigns",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "coupon_redemption_count",
            value=float(len(redemptions)),
            unit="redemptions",
            limitations=limitations,
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "transaction_coupon_baskets",
            baseline_value=usage_value("baseline", "coupon_baskets"),
            recent_value=usage_value("recent", "coupon_baskets"),
            change=(
                usage_value("recent", "coupon_baskets")
                - usage_value("baseline", "coupon_baskets")
            ),
            unit="baskets",
            sql_hash=sql_hash,
        ),
        evidence_factory.add(
            "recorded_coupon_discount",
            baseline_value=usage_value("baseline", "recorded_coupon_discount"),
            recent_value=usage_value("recent", "recorded_coupon_discount"),
            change=(
                usage_value("recent", "recorded_coupon_discount")
                - usage_value("baseline", "recorded_coupon_discount")
            ),
            unit="retailer_discount_value",
            sql_hash=sql_hash,
        ),
    ]
    campaign_summary: list[dict[str, object]] = []
    for row in campaigns:
        campaign_type = str(row["campaign_type"])
        delivered_known = campaign_type in {"Type B", "Type C"}
        campaign_summary.append(
            {
                "campaign_id": str(row["campaign_id"]),
                "campaign_type": campaign_type,
                "start_date": _date_text(row["start_date"]),
                "end_date": _date_text(row["end_date"]),
                "campaign_coupon_count": int(row["campaign_coupon_count"]),
                "delivered_coupon_set_known": delivered_known,
            }
        )
        evidence.append(
            evidence_factory.add(
                "campaign_participation",
                dimensions={
                    "campaign_id": str(row["campaign_id"]),
                    "campaign_type": campaign_type,
                },
                value=1.0,
                unit="participation",
                limitations=(TYPE_A_LIMITATION,) if campaign_type == "Type A" else (),
                sql_hash=sql_hash,
            )
        )
        if delivered_known:
            evidence.append(
                evidence_factory.add(
                    "known_delivered_campaign_coupon_count",
                    dimensions={
                        "campaign_id": str(row["campaign_id"]),
                        "campaign_type": campaign_type,
                    },
                    value=float(row["campaign_coupon_count"]),
                    unit="distinct_coupon_upcs",
                    sql_hash=sql_hash,
                )
            )

    return ToolResult(
        tool_call_id=context.tool_call_id,
        tool_name=ToolName.COUPON_CAMPAIGN_HISTORY,
        status=ToolStatus.PARTIAL if has_type_a else ToolStatus.OK,
        model_summary={
            "campaign_count": len(campaigns),
            "campaigns": cast(Any, campaign_summary),
            "redemption_count": len(redemptions),
            "redemptions": [
                {
                    "campaign_id": str(row["campaign_id"]),
                    "coupon_upc": str(row["coupon_upc"]),
                    "redemption_date": _date_text(row["redemption_date"]),
                }
                for row in redemptions
            ],
            "type_a_delivered_identities_available": False if has_type_a else None,
            "baseline_transaction_coupon_baskets": int(
                usage_value("baseline", "coupon_baskets")
            ),
            "recent_transaction_coupon_baskets": int(
                usage_value("recent", "coupon_baskets")
            ),
        },
        evidence=tuple(evidence),
        limitations=limitations,
        provenance=make_provenance(
            context,
            parameters,
            timer=timer,
            sql_hash=sql_hash,
            rows_examined=transaction_rows + len(campaigns) + len(redemptions),
            diagnostics={
                "redemption_join_keys": ["coupon_upc", "campaign_id"],
                "coupon_bridge_deduplicated": True,
                "type_a_present": has_type_a,
            },
        ),
    )
