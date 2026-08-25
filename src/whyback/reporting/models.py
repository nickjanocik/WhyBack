"""Typed, deterministic boundaries shared by WhyBack report renderers."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from whyback.agent.actions import ActionId
from whyback.agent.state import ResolvedConfidence, RunStatus
from whyback.immutability import frozen_mapping
from whyback.provenance import RunProvenance
from whyback.tools.contracts import ToolName, ToolStatus


class DeclineReportData(BaseModel):
    """Run-owned deterministic detector evidence displayed in the summary."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evidence_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    source: Literal["decline_detector"] = "decline_detector"
    baseline_start_week: int = Field(ge=1, le=53)
    baseline_end_week: int = Field(ge=1, le=53)
    recent_start_week: int = Field(ge=1, le=53)
    recent_end_week: int = Field(ge=1, le=53)
    baseline_retailer_sales_value: float
    recent_retailer_sales_value: float
    baseline_distinct_baskets: int = Field(ge=0)
    recent_distinct_baskets: int = Field(ge=0)
    baseline_active_weeks: int = Field(ge=0)
    recent_active_weeks: int = Field(ge=0)
    sales_drop: float = Field(ge=0.0, le=1.0)
    trip_drop: float = Field(ge=0.0, le=1.0)
    active_week_drop: float = Field(ge=0.0, le=1.0)
    decline_score: float = Field(ge=0.0, le=1.0)
    eligible: bool
    flagged: bool
    partial_week_limitation: str | None = None


class InvestigationStepData(BaseModel):
    """One deterministic, compact row in the investigation path."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision_number: int = Field(ge=1)
    tool_name: ToolName
    tool_label: str = Field(min_length=1)
    investigation_question: str = Field(min_length=1)
    final_status: ToolStatus
    attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    total_latency_ms: float = Field(ge=0.0)
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class ReportEvidenceData(BaseModel):
    """One immutable evidence value with its report role and source status."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evidence_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    role: Literal["supporting", "counterevidence", "context"]
    source_tool: ToolName
    source_tool_call_id: str = Field(min_length=1)
    source_status: ToolStatus | None
    metric: str = Field(min_length=1)
    dimensions: dict[str, str] = Field(default_factory=dict)
    baseline_value: float | None = None
    recent_value: float | None = None
    value: float | None = None
    change: float | None = None
    unit: str | None = None
    limitations: tuple[str, ...] = ()
    query_hash: str | None = None

    @model_validator(mode="after")
    def freeze_dimensions(self) -> Self:
        object.__setattr__(self, "dimensions", frozen_mapping(self.dimensions))
        return self


class DriverReportData(BaseModel):
    """A verified qualitative driver and the IDs that ground it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1)


class ToolWarningData(BaseModel):
    """A visible failed, partial, or retried analytical step."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    tool_name: ToolName
    final_status: ToolStatus
    attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    attempt_statuses: tuple[ToolStatus, ...] = ()
    total_latency_ms: float = Field(ge=0.0)
    limitations: tuple[str, ...] = ()
    unavailable: bool = False


class ActionReportData(BaseModel):
    """The verifier-approved catalog choice and its measurement plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: ActionId
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    resolved_confidence: ResolvedConfidence
    confidence_cap_applied: bool
    recommended_success_metric: str = Field(min_length=1)
    suggested_experiment: str = Field(min_length=1)
    human_review_required: Literal[True]


class ReportData(BaseModel):
    """Stable JSON/report boundary built only from authoritative run state."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal[2] = 2
    product_name: Literal["WhyBack"] = "WhyBack"
    tagline: Literal["Find the why. Choose the way back."] = (
        "Find the why. Choose the way back."
    )
    investigator_name: Literal["WhyBack Investigator"] = "WhyBack Investigator"
    provenance: RunProvenance
    run_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    run_status: RunStatus
    decline: DeclineReportData
    investigation_path: tuple[InvestigationStepData, ...] = ()
    likely_drivers: tuple[DriverReportData, ...] = ()
    supporting_evidence: tuple[ReportEvidenceData, ...] = ()
    counterevidence: tuple[ReportEvidenceData, ...] = ()
    evidence_ledger: tuple[ReportEvidenceData, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    action: ActionReportData | None = None
    limitations: tuple[str, ...] = ()
    tool_warnings: tuple[ToolWarningData, ...] = ()
    verification_issues: tuple[str, ...] = ()
    failure_reason: str | None = None
    human_review_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_terminal_report(self) -> Self:
        if (
            self.decline.run_id != self.run_id
            or self.decline.household_id != self.household_id
        ):
            raise ValueError("Detector evidence must belong to its run and household")
        if self.run_status is RunStatus.RUNNING:
            raise ValueError("Published reports must have a terminal run status")
        if self.run_status is RunStatus.COMPLETED and (
            self.action is None
            or self.action.action_id is ActionId.INSUFFICIENT_EVIDENCE
        ):
            raise ValueError("A completed report requires a supported catalog action")
        if self.run_status is RunStatus.INSUFFICIENT_EVIDENCE and (
            self.action is None
            or self.action.action_id is not ActionId.INSUFFICIENT_EVIDENCE
        ):
            raise ValueError(
                "An insufficient-evidence report requires the governed fallback"
            )
        if self.run_status is RunStatus.FAILED and self.action is not None:
            raise ValueError("A failed report cannot publish an action")

        ledger = {item.evidence_id: item for item in self.evidence_ledger}
        if len(ledger) != len(self.evidence_ledger):
            raise ValueError("Report evidence IDs must be unique")
        for item in self.evidence_ledger:
            if item.run_id != self.run_id or item.household_id != self.household_id:
                raise ValueError("Report evidence must belong to its run and household")
        for role, records in (
            ("supporting", self.supporting_evidence),
            ("counterevidence", self.counterevidence),
        ):
            for record in records:
                if record.role != role or ledger.get(record.evidence_id) != record:
                    raise ValueError(
                        f"{role.title()} evidence must exactly match the ledger"
                    )
        supporting_ids = {item.evidence_id for item in self.supporting_evidence}
        for driver in self.likely_drivers:
            if not set(driver.supporting_evidence_ids).issubset(supporting_ids):
                raise ValueError(
                    "Driver citations must be accepted supporting evidence"
                )
        return self


class TraceEventData(BaseModel):
    """One sanitized trace event prepared for the static timeline."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    sequence: int = Field(ge=1)
    timestamp: str = Field(min_length=1)
    event: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool_name: str | None = None
    status: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    evidence_ids: tuple[str, ...] = ()
    retry_label: str | None = None
    verifier_label: str | None = None
    final_action: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_details(self) -> Self:
        object.__setattr__(self, "details", frozen_mapping(self.details))
        return self


class TraceViewData(BaseModel):
    """Deterministic boundary for a self-contained trace viewer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_name: Literal["WhyBack"] = "WhyBack"
    tagline: Literal["Find the why. Choose the way back."] = (
        "Find the why. Choose the way back."
    )
    run_id: str | None = None
    household_id: str | None = None
    event_count: int = Field(ge=0)
    decision_count: int = Field(ge=0)
    tool_attempt_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    verifier_status: str
    final_action: str | None = None
    events: tuple[TraceEventData, ...] = ()
