"""Typed, application-owned investigation state and model decisions."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self, cast
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    field_validator,
    model_validator,
)

from whyback.agent.actions import ActionId
from whyback.detection.decline import DeclineSnapshot
from whyback.immutability import frozen_mapping
from whyback.tools.contracts import AnalysisWindow, EvidenceRecord, ToolName, ToolStatus


class RunStatus(StrEnum):
    """Externally visible lifecycle states for one investigation."""

    RUNNING = "running"
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class ConfidenceLevel(StrEnum):
    """Confidence values a model may propose."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResolvedConfidence(StrEnum):
    """Confidence after deterministic verification and capping."""

    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelUsage(BaseModel):
    """Aggregate, provider-neutral model usage for a run."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decisions: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)

    def plus(self, other: ModelUsage) -> ModelUsage:
        """Return a new aggregate without mutating either usage record."""

        return ModelUsage(
            decisions=self.decisions + other.decisions,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
        )


class ToolAttemptRecord(BaseModel):
    """One actual dispatch attempt, including bounded retries."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    attempt: int = Field(ge=1, le=2)
    tool_call_id: str = Field(min_length=1)
    status: ToolStatus
    retryable: bool = False
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    limitations: tuple[str, ...] = ()


class ToolHistoryEntry(BaseModel):
    """Compact history for a single model-requested analytical action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_number: int = Field(ge=1)
    tool_name: ToolName
    normalized_signature: str = Field(min_length=1)
    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    normalized_arguments: dict[str, JsonValue]
    attempts: tuple[ToolAttemptRecord, ...]
    final_status: ToolStatus
    model_summary: dict[str, JsonValue] = Field(default_factory=dict)
    provenance_diagnostics: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def freeze_history_mappings(self) -> Self:
        for field in (
            "normalized_arguments",
            "model_summary",
            "provenance_diagnostics",
        ):
            object.__setattr__(self, field, frozen_mapping(getattr(self, field)))
        return self


class DriverClaim(BaseModel):
    """One qualitative driver mapped to its deterministic support."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=1, max_length=400)
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=6)

    @field_validator("supporting_evidence_ids")
    @classmethod
    def unique_support(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Driver evidence references must be unique")
        return value


class FinishProposal(BaseModel):
    """Qualitative model proposal whose evidence references are verified in code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    driver_summary: tuple[DriverClaim, ...] = Field(max_length=4)
    proposed_confidence: ConfidenceLevel
    supporting_evidence_ids: tuple[str, ...] = Field(max_length=12)
    counterevidence_ids: tuple[str, ...] = Field(max_length=8)
    next_best_action_id: ActionId
    rationale: str = Field(min_length=1, max_length=800)
    alternative_explanations: tuple[str, ...] = Field(min_length=1, max_length=4)
    uncertainties: tuple[str, ...] = Field(min_length=1, max_length=6)

    @field_validator("supporting_evidence_ids", "counterevidence_ids")
    @classmethod
    def unique_evidence_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("Evidence references must be unique")
        return value


class ToolDecision(BaseModel):
    """A fresh model decision to execute exactly one analytical tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["tool"] = "tool"
    investigation_question: str = Field(min_length=1, max_length=300)
    selected_tool: ToolName
    arguments: dict[str, JsonValue]
    decision_summary: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def freeze_arguments(self) -> Self:
        object.__setattr__(self, "arguments", frozen_mapping(self.arguments))
        return self


class FinishDecision(BaseModel):
    """A fresh model decision to ask deterministic code to finish."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["finish"] = "finish"
    investigation_question: str = Field(min_length=1, max_length=300)
    decision_summary: str = Field(min_length=1, max_length=500)
    final: FinishProposal


ModelDecision = Annotated[ToolDecision | FinishDecision, Field(discriminator="kind")]
MODEL_DECISION_ADAPTER = TypeAdapter(ModelDecision)


class InvestigationState(BaseModel):
    """Immutable source of truth supplied compactly to each fresh model call."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    run_id: UUID
    household_id: str = Field(min_length=1)
    detector_snapshot: DeclineSnapshot
    window: AnalysisWindow
    tool_history: tuple[ToolHistoryEntry, ...] = ()
    evidence_ledger: tuple[EvidenceRecord, ...] = ()
    open_questions: tuple[str, ...] = ()
    failed_or_partial_tools: tuple[ToolName, ...] = ()
    unavailable_tools: tuple[ToolName, ...] = ()
    requested_signatures: tuple[str, ...] = ()
    remaining_tool_budget: int = Field(ge=0)
    remaining_turn_budget: int = Field(ge=0)
    model_usage: ModelUsage = ModelUsage()
    run_status: RunStatus = RunStatus.RUNNING
    final_proposal: FinishProposal | None = None
    resolved_confidence: ResolvedConfidence | None = None
    verification_issues: tuple[str, ...] = ()

    @classmethod
    def start(
        cls,
        detector_snapshot: DeclineSnapshot,
        *,
        max_tool_executions: int = 5,
        max_model_decisions: int = 6,
        run_id: UUID | None = None,
    ) -> InvestigationState:
        if max_tool_executions < 1 or max_model_decisions < 1:
            raise ValueError("Investigation budgets must be positive")
        return cls(
            run_id=run_id or uuid4(),
            household_id=detector_snapshot.household_id,
            detector_snapshot=detector_snapshot,
            window=AnalysisWindow(
                baseline_start=detector_snapshot.baseline_start_week,
                baseline_end=detector_snapshot.baseline_end_week,
                recent_start=detector_snapshot.recent_start_week,
                recent_end=detector_snapshot.recent_end_week,
            ),
            remaining_tool_budget=max_tool_executions,
            remaining_turn_budget=max_model_decisions,
        )

    def compact_model_context(self) -> dict[str, JsonValue]:
        """Return bounded evidence and state, never an accumulated transcript."""

        evidence = [
            {
                "evidence_id": item.evidence_id,
                "source_tool": item.source_tool.value,
                "metric": item.metric,
                "dimensions": item.dimensions,
                "baseline_value": item.baseline_value,
                "recent_value": item.recent_value,
                "value": item.value,
                "change": item.change,
                "unit": item.unit,
                "limitations": list(item.limitations),
            }
            for item in self.evidence_ledger
        ]
        history = [
            {
                "tool_name": item.tool_name.value,
                "investigation_question": item.investigation_question,
                "status": item.final_status.value,
                "summary": item.model_summary,
                "evidence_ids": list(item.evidence_ids),
                "limitations": list(item.limitations),
            }
            for item in self.tool_history
        ]
        return cast(
            dict[str, JsonValue],
            {
                "run_id": str(self.run_id),
                "household_id": self.household_id,
                "decline_snapshot": self.detector_snapshot.model_dump(mode="json"),
                "completed_tools": history,
                "evidence_summary": evidence,
                "open_questions": list(self.open_questions),
                "failed_or_partial_tools": [
                    item.value for item in self.failed_or_partial_tools
                ],
                "unavailable_tools": [item.value for item in self.unavailable_tools],
                "remaining_tool_budget": self.remaining_tool_budget,
                "remaining_turn_budget": self.remaining_turn_budget,
                "verification_issues": list(self.verification_issues),
            },
        )
