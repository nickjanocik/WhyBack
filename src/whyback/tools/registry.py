"""Single deterministic registry shared by the investigator and optional adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, JsonValue, ValidationError

from whyback.data.repository import DataRepository
from whyback.tools.basket import basket_behavior
from whyback.tools.category import category_decomposition
from whyback.tools.contracts import (
    BasketBehaviorInput,
    CategoryDecompositionInput,
    CouponCampaignHistoryInput,
    CustomerTrendInput,
    PeerComparisonInput,
    PromotionResponseInput,
    ToolDefinition,
    ToolExecutionContext,
    ToolName,
    ToolProvenance,
    ToolResult,
    ToolStatus,
)
from whyback.tools.coupon import run_coupon_campaign_history
from whyback.tools.peer import run_peer_comparison
from whyback.tools.promotion import run_promotion_response
from whyback.tools.trend import customer_trend

ToolHandler = Callable[[Any, ToolExecutionContext, DataRepository], ToolResult]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """One analytical handler paired with its input contract and model description."""

    name: ToolName
    input_model: type[BaseModel]
    handler: ToolHandler
    description: str

    def definition(self) -> ToolDefinition:
        """Expose this registered handler as a provider-neutral function schema."""

        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
        )


TOOL_SPECS: tuple[RegisteredTool, ...] = (
    RegisteredTool(
        ToolName.CUSTOMER_TREND,
        CustomerTrendInput,
        cast(ToolHandler, customer_trend),
        "Use to distinguish frequency, value, recency, and weekly trajectory changes. "
        "Requires the active household_id. Returns deterministic baseline/recent "
        "metrics and a zero-filled weekly series. Recorded quantity has a fuel-scale "
        "limitation. Returns an explicit status when window data is unavailable.",
    ),
    RegisteredTool(
        ToolName.CATEGORY_DECOMPOSITION,
        CategoryDecompositionInput,
        cast(ToolHandler, category_decomposition),
        "Use to identify departments/categories contributing to retailer sales value "
        "losses, gains, and share shifts. Requires household_id; top_n is optional. "
        "Selected loss categories include target-excluded context among eligible "
        "households with meaningful baseline activity. Unmapped products remain "
        "UNKNOWN and totals must reconcile. Do not use this tool to infer product "
        "preference causes.",
    ),
    RegisteredTool(
        ToolName.BASKET_BEHAVIOR,
        BasketBehaviorInput,
        cast(ToolHandler, basket_behavior),
        "Use to distinguish fewer visits from smaller or structurally different "
        "baskets and changed cadence/store behavior. Requires household_id. Metrics "
        "are calculated at distinct-basket grain; sparse windows are surfaced rather "
        "than imputed.",
    ),
    RegisteredTool(
        ToolName.PROMOTION_RESPONSE,
        PromotionResponseInput,
        cast(ToolHandler, run_promotion_response),
        "Use to compare purchasing associated with recorded product/store/week "
        "promotion availability. Requires household_id; top_n_categories is optional. "
        "It never establishes household exposure or causation and fails closed if the "
        "enrichment changes transaction count or retailer sales value.",
    ),
    RegisteredTool(
        ToolName.COUPON_CAMPAIGN_HISTORY,
        CouponCampaignHistoryInput,
        cast(ToolHandler, run_coupon_campaign_history),
        "Use to inspect known campaign participation, observed redemption events, and "
        "transaction coupon usage. Requires household_id. Type A delivered coupon "
        "identities are unavailable, so affected results are partial and never infer "
        "ignored category offers.",
    ),
    RegisteredTool(
        ToolName.PEER_COMPARISON,
        PeerComparisonInput,
        cast(ToolHandler, run_peer_comparison),
        "Use to compare the target with the full eligible household population and "
        "behavioral peers. Requires household_id; peer_count defaults to 50. The "
        "target is excluded from both distributions; peers use robust-scaled baseline "
        "behavior without demographics. Context is descriptive rather than causal.",
    ),
)


class ToolRegistry:
    """Validate, dispatch, describe, and normalize the six analytical tools."""

    def __init__(self, tools: Sequence[RegisteredTool] = TOOL_SPECS) -> None:
        """Index a unique set of tools by their public analytical names."""

        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("Tool names must be unique")

    @property
    def names(self) -> tuple[ToolName, ...]:
        """Return registered tool names in their stable declaration order."""

        return tuple(self._tools)

    def definitions(
        self, allowed: Sequence[ToolName] | None = None
    ) -> tuple[ToolDefinition, ...]:
        """Return strict schemas for all tools or only an allowed subset."""

        permitted = set(allowed) if allowed is not None else set(self._tools)
        return tuple(
            tool.definition() for name, tool in self._tools.items() if name in permitted
        )

    def normalize_arguments(
        self, name: ToolName, arguments: Mapping[str, Any]
    ) -> tuple[BaseModel, str]:
        """Validate arguments and hash their canonical JSON for duplicate checks."""

        tool = self._tools[name]
        validated = tool.input_model.model_validate(dict(arguments))
        payload = validated.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(f"{name.value}:{serialized}".encode()).hexdigest()
        return validated, key

    def execute(
        self,
        name: ToolName,
        arguments: Mapping[str, Any],
        context: ToolExecutionContext,
        repository: DataRepository,
    ) -> ToolResult:
        """Validate model arguments, dispatch the handler, or return a typed refusal."""

        try:
            parameters, _ = self.normalize_arguments(name, arguments)
        except (KeyError, ValidationError):
            return ToolResult(
                tool_call_id=context.tool_call_id,
                tool_name=name,
                status=ToolStatus.INVALID_REQUEST,
                model_summary={
                    "validation_error": (
                        "Arguments did not match the strict tool schema."
                    )
                },
                limitations=("Tool arguments failed strict schema validation.",),
                provenance=ToolProvenance(
                    dataset_source_commit=context.source_commit,
                    source_hashes=context.source_hashes,
                    normalized_parameters=cast(
                        dict[str, JsonValue], {"validation_failed": True}
                    ),
                    rows_examined=0,
                    application_version=context.application_version,
                ),
            )
        return self._tools[name].handler(parameters, context, repository)


def build_tool_registry() -> ToolRegistry:
    """Construct the standard registry containing all six analytical tools."""

    return ToolRegistry()


def compact_tool_result(result: ToolResult) -> dict[str, JsonValue]:
    """Create bounded model context while full values remain in the trace."""

    evidence = [
        {
            "evidence_id": item.evidence_id,
            "metric": item.metric,
            "dimensions": item.dimensions,
            "baseline_value": item.baseline_value,
            "recent_value": item.recent_value,
            "value": item.value,
            "change": item.change,
            "unit": item.unit,
            "limitations": list(item.limitations),
        }
        for item in result.evidence
    ]
    return cast(
        dict[str, JsonValue],
        {
            "tool_call_id": result.tool_call_id,
            "tool_name": result.tool_name.value,
            "status": result.status.value,
            "model_summary": result.model_summary,
            "evidence": evidence,
            "limitations": list(result.limitations),
        },
    )
