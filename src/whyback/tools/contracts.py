"""Strict, shared analytical tool contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from whyback import __version__
from whyback.config import SOURCE_COMMIT
from whyback.immutability import frozen_mapping
from whyback.methodology import ClaimType, ContextPolicy


class ToolName(StrEnum):
    """Public names of the six analytical functions available to a model."""

    CUSTOMER_TREND = "customer_trend"
    CATEGORY_DECOMPOSITION = "category_decomposition"
    BASKET_BEHAVIOR = "basket_behavior"
    PROMOTION_RESPONSE = "promotion_response"
    COUPON_CAMPAIGN_HISTORY = "coupon_campaign_history"
    PEER_COMPARISON = "peer_comparison"


class ToolStatus(StrEnum):
    """Closed outcome vocabulary shared by every analytical tool."""

    OK = "ok"
    PARTIAL = "partial"
    MISSING_DATA = "missing_data"
    INVALID_REQUEST = "invalid_request"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"


class AnalysisWindow(BaseModel):
    """Inclusive analytical windows inherited from the detector."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    baseline_start: int = Field(ge=1, le=53)
    baseline_end: int = Field(ge=1, le=53)
    recent_start: int = Field(ge=1, le=53)
    recent_end: int = Field(ge=1, le=53)

    @model_validator(mode="after")
    def validate_order(self) -> AnalysisWindow:
        """Require positive, ordered, non-overlapping baseline and recent windows."""

        if not (
            self.baseline_start
            <= self.baseline_end
            < self.recent_start
            <= self.recent_end
        ):
            raise ValueError("Baseline and recent windows must be ordered and disjoint")
        return self


class HouseholdToolInput(BaseModel):
    """Common model-visible input for customer analytical tools."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    household_id: str = Field(min_length=1)


class CustomerTrendInput(HouseholdToolInput):
    """Request trend analysis for the active household."""

    pass


class CategoryDecompositionInput(HouseholdToolInput):
    """Request the largest category movements for the active household."""

    top_n: int = Field(default=8, ge=1, le=20)


class BasketBehaviorInput(HouseholdToolInput):
    """Request basket structure and visit-cadence analysis for the household."""

    pass


class PromotionResponseInput(HouseholdToolInput):
    """Request promotion-associated purchasing and category movements."""

    top_n_categories: int = Field(default=5, ge=1, le=10)


class CouponCampaignHistoryInput(HouseholdToolInput):
    """Request known campaign, redemption, and transaction-coupon history."""

    pass


class PeerComparisonInput(HouseholdToolInput):
    """Request population context and a bounded behavioral-peer cohort."""

    peer_count: int = Field(default=50, ge=5, le=100)


class ToolExecutionContext(BaseModel):
    """Application-owned values that the model cannot override."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID
    tool_call_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    window: AnalysisWindow
    source_commit: str = SOURCE_COMMIT
    source_hashes: dict[str, str] = Field(default_factory=dict)
    application_version: str = __version__
    context_policy: ContextPolicy = ContextPolicy()

    @model_validator(mode="after")
    def freeze_source_hashes(self) -> Self:
        """Freeze dataset hashes supplied by authoritative run context."""

        object.__setattr__(self, "source_hashes", frozen_mapping(self.source_hashes))
        return self


class EvidenceRecord(BaseModel):
    """One immutable deterministic value eligible for report grounding."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evidence_id: str = Field(min_length=1)
    run_id: UUID
    household_id: str = Field(min_length=1)
    source_tool: ToolName
    source_tool_call_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    dimensions: dict[str, str] = Field(default_factory=dict)
    baseline_value: float | None = None
    recent_value: float | None = None
    value: float | None = None
    text_value: str | None = Field(default=None, min_length=1)
    change: float | None = None
    unit: str | None = None
    maximum_claim_type: ClaimType = ClaimType.ASSOCIATIONAL
    limitations: tuple[str, ...] = ()
    query_hash: str | None = None

    @model_validator(mode="after")
    def require_computed_value(self) -> EvidenceRecord:
        """Require a computed value and freeze its identifying dimensions."""

        if all(
            value is None
            for value in (
                self.baseline_value,
                self.recent_value,
                self.value,
                self.text_value,
                self.change,
            )
        ):
            raise ValueError("Evidence must contain at least one computed value")
        object.__setattr__(self, "dimensions", frozen_mapping(self.dimensions))
        return self


class ToolProvenance(BaseModel):
    """Replay and integrity metadata for one deterministic invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    dataset_source_commit: str = SOURCE_COMMIT
    source_hashes: dict[str, str] = Field(default_factory=dict)
    normalized_parameters: dict[str, JsonValue]
    query_hash: str | None = None
    rows_examined: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    cache_hit: bool = False
    application_version: str = __version__
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_mappings(self) -> Self:
        """Freeze replay mappings after provenance validation completes."""

        for field in ("source_hashes", "normalized_parameters", "diagnostics"):
            object.__setattr__(self, field, frozen_mapping(getattr(self, field)))
        return self


SUCCESS_STATUSES = frozenset({ToolStatus.OK, ToolStatus.PARTIAL})


class ToolResult(BaseModel):
    """Common envelope returned by every analytical tool."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    tool_call_id: str = Field(min_length=1)
    tool_name: ToolName
    status: ToolStatus
    model_summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: tuple[EvidenceRecord, ...] = ()
    limitations: tuple[str, ...] = ()
    retryable: bool = False
    provenance: ToolProvenance

    @model_validator(mode="after")
    def validate_status_contract(self) -> ToolResult:
        """Enforce evidence, limitation, retry, and ownership rules for a result."""

        if self.status not in SUCCESS_STATUSES and self.evidence:
            raise ValueError(
                "Failed, missing, or invalid tool results cannot carry evidence"
            )
        if self.status is ToolStatus.PARTIAL and not self.limitations:
            raise ValueError("Partial tool results must state a limitation")
        if self.retryable != (self.status is ToolStatus.RETRYABLE_ERROR):
            raise ValueError("Only retryable_error may set retryable=true")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique within a tool result")
        for item in self.evidence:
            if item.source_tool is not self.tool_name:
                raise ValueError("Evidence source tool does not match the result")
            if item.source_tool_call_id != self.tool_call_id:
                raise ValueError("Evidence source call does not match the result")
        object.__setattr__(self, "model_summary", frozen_mapping(self.model_summary))
        return self


class ToolDefinition(BaseModel):
    """Provider-neutral strict function definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ToolName
    description: str
    input_schema: dict[str, Any]


ToolInput = (
    CustomerTrendInput
    | CategoryDecompositionInput
    | BasketBehaviorInput
    | PromotionResponseInput
    | CouponCampaignHistoryInput
    | PeerComparisonInput
)

Confidence = Literal["low", "medium", "high"]
