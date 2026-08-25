"""Typed, deterministic boundaries shared by WhyBack report renderers."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

from whyback.agent.actions import ActionId, load_action_catalog
from whyback.agent.state import ConfidenceLevel, ResolvedConfidence, RunStatus
from whyback.agent.verifier import (
    required_context_counterevidence_ids,
    resolve_confidence_policy,
)
from whyback.immutability import frozen_mapping
from whyback.methodology import (
    ClaimType,
    ContextClassification,
    resolve_context_classifications,
)
from whyback.provenance import RunProvenance
from whyback.tools.contracts import EvidenceRecord, ToolName, ToolStatus

_CLAIM_ORDER = {
    ClaimType.DESCRIPTIVE: 0,
    ClaimType.ASSOCIATIONAL: 1,
    ClaimType.CAUSAL: 2,
}
_CONFIDENCE_ORDER = {
    ResolvedConfidence.INSUFFICIENT: 0,
    ResolvedConfidence.LOW: 1,
    ResolvedConfidence.MEDIUM: 2,
    ResolvedConfidence.HIGH: 3,
}


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
    text_value: str | None = None
    change: float | None = None
    unit: str | None = None
    maximum_claim_type: ClaimType = ClaimType.ASSOCIATIONAL
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
    claim_type: ClaimType
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1)
    counterevidence_ids: tuple[str, ...] = ()
    no_material_counterevidence_reason: str | None = Field(
        default=None,
        min_length=1,
    )
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_accounting(self) -> Self:
        if len(self.supporting_evidence_ids) != len(set(self.supporting_evidence_ids)):
            raise ValueError("Driver support references must be unique")
        if len(self.counterevidence_ids) != len(set(self.counterevidence_ids)):
            raise ValueError("Driver counterevidence references must be unique")
        if set(self.supporting_evidence_ids).intersection(self.counterevidence_ids):
            raise ValueError("Driver support and counterevidence cannot overlap")
        if (
            not self.counterevidence_ids
            and self.no_material_counterevidence_reason is None
        ):
            raise ValueError(
                "A driver must cite counterevidence or explain why none was material"
            )
        return self


class CohortComparisonReportData(BaseModel):
    """One target-excluded household distribution used for context."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cohort: Literal["eligible_population", "behavioral_peers"]
    available: bool
    cohort_count: int = Field(default=0, ge=0)
    median_change: float | None = None
    q25_change: float | None = None
    q75_change: float | None = None
    target_percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    declining_household_share: float | None = Field(default=None, ge=0.0, le=1.0)
    target_minus_median_change: float | None = None
    target_excluded: bool
    construction_method: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_distribution(self) -> Self:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Comparison evidence references must be unique")
        if not self.target_excluded:
            raise ValueError("Comparison context must exclude the target household")
        distribution = (
            self.median_change,
            self.q25_change,
            self.q75_change,
            self.target_percentile,
            self.declining_household_share,
            self.target_minus_median_change,
        )
        if self.available:
            if self.cohort_count < 1 or not self.evidence_ids:
                raise ValueError(
                    "Available comparison context requires a nonempty cohort"
                )
            if any(value is None for value in distribution):
                raise ValueError(
                    "Available comparison context requires full distribution"
                )
            assert self.q25_change is not None
            assert self.median_change is not None
            assert self.q75_change is not None
            if not self.q25_change <= self.median_change <= self.q75_change:
                raise ValueError("Comparison quartiles must contain the median")
        elif any(value is not None for value in distribution):
            raise ValueError(
                "Unavailable comparison context cannot publish distribution values"
            )
        if not self.evidence_ids and self.cohort_count != 0:
            raise ValueError("A comparison count without evidence must be zero")
        return self


class CategoryContextReportData(BaseModel):
    """Contemporaneous household context for one selected loss category."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    department: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    available: bool
    target_change: float | None = None
    comparison_household_count: int = Field(default=0, ge=0)
    population_median_change: float | None = None
    declining_household_share: float | None = Field(default=None, ge=0.0, le=1.0)
    target_minus_population_median_change: float | None = None
    context_classification: ContextClassification
    target_excluded: bool
    evidence_ids: tuple[str, ...] = ()
    classification_evidence_id: str | None = None
    classification_evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_category_context(self) -> Self:
        for values in (self.evidence_ids, self.classification_evidence_ids):
            if len(values) != len(set(values)):
                raise ValueError("Category context evidence references must be unique")
        if not self.target_excluded:
            raise ValueError("Category comparison context must exclude the target")
        if (
            self.classification_evidence_id is not None
            and self.classification_evidence_id not in self.classification_evidence_ids
        ):
            raise ValueError(
                "Primary category classification evidence must be in the full set"
            )
        distribution = (
            self.population_median_change,
            self.declining_household_share,
            self.target_minus_population_median_change,
        )
        if self.available:
            if (
                self.context_classification
                is ContextClassification.INSUFFICIENT_CONTEXT
                or self.comparison_household_count < 1
                or self.target_change is None
                or not self.evidence_ids
                or any(value is None for value in distribution)
            ):
                raise ValueError(
                    "Available category context requires a complete comparison"
                )
        elif any(value is not None for value in distribution):
            raise ValueError(
                "Unavailable category context cannot publish distribution values"
            )
        return self


class PopulationContextReportData(BaseModel):
    """Target, eligible-population, peer, and category comparison boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    context_classification: ContextClassification
    target_retailer_sales_change: float | None
    eligible_population: CohortComparisonReportData
    behavioral_peers: CohortComparisonReportData
    category_context: tuple[CategoryContextReportData, ...]
    classification_evidence_id: str | None
    classification_evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]


class InterpretationLimitsReportData(BaseModel):
    """Code-owned boundary for observable scope and omitted factors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_scope: tuple[str, ...] = Field(min_length=1)
    unobserved_factors: tuple[str, ...] = Field(min_length=1)
    causal_limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if any(
            not item.strip()
            for values in (
                self.observed_scope,
                self.unobserved_factors,
                self.causal_limitations,
            )
            for item in values
        ):
            raise ValueError("Interpretation-limit entries cannot be blank")
        return self


class ConfidenceAdjustmentReportData(BaseModel):
    """One deterministic, evidence-linked confidence adjustment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context_classification: ContextClassification
    maximum_confidence: ResolvedConfidence
    reason: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_ids(self) -> Self:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Confidence adjustment evidence IDs must be unique")
        return self


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
    confidence_adjustments: tuple[ConfidenceAdjustmentReportData, ...] = ()
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
    population_context: PopulationContextReportData
    investigation_path: tuple[InvestigationStepData, ...] = ()
    likely_drivers: tuple[DriverReportData, ...] = ()
    supporting_evidence: tuple[ReportEvidenceData, ...] = ()
    counterevidence: tuple[ReportEvidenceData, ...] = ()
    evidence_ledger: tuple[ReportEvidenceData, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    interpretation_limits: InterpretationLimitsReportData
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
        supporting_by_id = {item.evidence_id: item for item in self.supporting_evidence}
        supporting_ids = set(supporting_by_id)
        counterevidence_ids = {item.evidence_id for item in self.counterevidence}
        for driver in self.likely_drivers:
            if not set(driver.supporting_evidence_ids).issubset(supporting_ids):
                raise ValueError(
                    "Driver citations must be accepted supporting evidence"
                )
            if not set(driver.counterevidence_ids).issubset(counterevidence_ids):
                raise ValueError(
                    "Driver counterevidence must be accepted counterevidence"
                )
            if any(
                _CLAIM_ORDER[driver.claim_type]
                > _CLAIM_ORDER[supporting_by_id[evidence_id].maximum_claim_type]
                for evidence_id in driver.supporting_evidence_ids
            ):
                raise ValueError("Driver claim type exceeds its evidence support level")
        if self.action is not None:
            try:
                evidence_records = {
                    item.evidence_id: EvidenceRecord.model_validate(
                        item.model_dump(exclude={"role", "source_status"})
                    )
                    for item in self.evidence_ledger
                }
            except ValidationError as error:
                raise ValueError(
                    "Report ledger cannot reconstruct deterministic evidence"
                ) from error
            action_definition = load_action_catalog().get(self.action.action_id)
            full_evidence_records = tuple(evidence_records.values())
            for driver in self.likely_drivers:
                driver_support = tuple(
                    evidence_records[evidence_id]
                    for evidence_id in driver.supporting_evidence_ids
                )
                required_context_ids = set(
                    required_context_counterevidence_ids(
                        action_definition,
                        driver_support,
                        full_evidence_records,
                    )
                )
                if not required_context_ids.issubset(driver.counterevidence_ids):
                    raise ValueError(
                        "Driver omits material broad or mixed counterevidence"
                    )

            confidence_limitations = tuple(
                dict.fromkeys(
                    (
                        *(
                            limitation
                            for item in (
                                *self.supporting_evidence,
                                *self.counterevidence,
                            )
                            for limitation in item.limitations
                        ),
                        *(
                            "A cited evidence source returned a partial result."
                            for item in (
                                *self.supporting_evidence,
                                *self.counterevidence,
                            )
                            if item.source_status is ToolStatus.PARTIAL
                        ),
                        *(
                            "An analytical tool is unavailable."
                            for warning in self.tool_warnings
                            if warning.unavailable
                        ),
                    )
                )
            )
            report_support_records = tuple(
                evidence_records[item.evidence_id] for item in self.supporting_evidence
            )
            confidence_policy = resolve_confidence_policy(
                action=action_definition,
                proposed_confidence=ConfidenceLevel.HIGH,
                proposal_supporting_records=report_support_records,
                resolved_supporting_records=report_support_records,
                full_ledger_records=full_evidence_records,
                support_limitations=confidence_limitations,
            )
            if confidence_policy.issues:
                raise ValueError(
                    "Report evidence violates deterministic confidence policy"
                )
            expected_adjustments = tuple(
                item.model_dump(mode="json")
                for item in confidence_policy.confidence_adjustments
            )
            actual_adjustments = tuple(
                item.model_dump(mode="json")
                for item in self.action.confidence_adjustments
            )
            if actual_adjustments != expected_adjustments:
                raise ValueError(
                    "Confidence adjustments do not match deterministic evidence policy"
                )
            if (
                _CONFIDENCE_ORDER[self.action.resolved_confidence]
                > _CONFIDENCE_ORDER[confidence_policy.resolved_confidence]
            ):
                raise ValueError(
                    "Resolved confidence exceeds the deterministic evidence cap"
                )
            for adjustment in self.action.confidence_adjustments:
                if not set(adjustment.evidence_ids).issubset(ledger):
                    raise ValueError(
                        "Confidence adjustment cites evidence outside the ledger"
                    )
                adjustment_records = tuple(
                    ledger[evidence_id] for evidence_id in adjustment.evidence_ids
                )
                adjustment_metrics = {record.metric for record in adjustment_records}
                if (
                    not adjustment_metrics.issubset(
                        {
                            "context_classification",
                            "category_context_classification",
                        }
                    )
                    or len(adjustment_metrics) > 1
                ):
                    raise ValueError(
                        "Confidence adjustments must cite one classification scope"
                    )
                classifications: list[ContextClassification] = []
                for record in adjustment_records:
                    try:
                        classifications.append(ContextClassification(record.text_value))
                    except (TypeError, ValueError) as error:
                        raise ValueError(
                            "Confidence adjustment cites an invalid classification"
                        ) from error
                if adjustment_records and (
                    resolve_context_classifications(tuple(classifications))
                    is not adjustment.context_classification
                ):
                    raise ValueError(
                        "Confidence adjustment must use the conservative evidence "
                        "classification"
                    )
                if (
                    adjustment.context_classification
                    is not ContextClassification.INSUFFICIENT_CONTEXT
                    and not adjustment_records
                ):
                    raise ValueError(
                        "A non-missing confidence adjustment requires evidence"
                    )
                expected_maximum = (
                    ResolvedConfidence.LOW
                    if adjustment.context_classification
                    is ContextClassification.BROAD_CONTEXT
                    else ResolvedConfidence.MEDIUM
                )
                if (
                    adjustment.context_classification
                    is ContextClassification.CUSTOMER_SPECIFIC
                    or adjustment.maximum_confidence is not expected_maximum
                ):
                    raise ValueError(
                        "Confidence adjustment does not match deterministic policy"
                    )
                if (
                    _CONFIDENCE_ORDER[self.action.resolved_confidence]
                    > _CONFIDENCE_ORDER[adjustment.maximum_confidence]
                ):
                    raise ValueError(
                        "Resolved confidence exceeds a deterministic adjustment"
                    )
        self._validate_population_context(ledger)
        if (
            self.action is not None
            and self.population_context.context_classification
            is not ContextClassification.CUSTOMER_SPECIFIC
            and not any(
                adjustment.context_classification
                is self.population_context.context_classification
                and adjustment.evidence_ids
                == self.population_context.classification_evidence_ids
                for adjustment in self.action.confidence_adjustments
            )
        ):
            raise ValueError(
                "Non-specific population context requires its confidence adjustment"
            )
        return self

    def _validate_population_context(
        self, ledger: dict[str, ReportEvidenceData]
    ) -> None:
        """Bind every structured comparison value back to ledger evidence."""

        context = self.population_context

        def selected(ids: tuple[str, ...]) -> tuple[ReportEvidenceData, ...]:
            if not set(ids).issubset(ledger):
                raise ValueError("Population context cites evidence outside the ledger")
            return tuple(ledger[item] for item in ids)

        if len(context.classification_evidence_ids) != len(
            set(context.classification_evidence_ids)
        ):
            raise ValueError("Population classification evidence must be unique")
        if context.classification_evidence_id is not None:
            record = ledger.get(context.classification_evidence_id)
            if (
                record is None
                or record.metric != "context_classification"
                or record.source_tool is not ToolName.PEER_COMPARISON
                or record.text_value != context.context_classification.value
            ):
                raise ValueError(
                    "Population classification must match its ledger evidence"
                )
        if not set(context.classification_evidence_ids).issubset(ledger):
            raise ValueError(
                "Population classification cites evidence outside the ledger"
            )
        expected_population_classifications = tuple(
            item.evidence_id
            for item in ledger.values()
            if item.metric == "context_classification"
        )
        if context.classification_evidence_ids != expected_population_classifications:
            raise ValueError(
                "Population context must include every ledger classification"
            )
        if any(
            ledger[evidence_id].metric != "context_classification"
            or ledger[evidence_id].source_tool is not ToolName.PEER_COMPARISON
            for evidence_id in context.classification_evidence_ids
        ):
            raise ValueError(
                "Population classification evidence must use the context metric"
            )
        if (
            context.classification_evidence_id is not None
            and context.classification_evidence_id
            not in context.classification_evidence_ids
        ):
            raise ValueError(
                "Primary population classification evidence must be in the full set"
            )
        valid_classifications: list[ContextClassification] = []
        for evidence_id in context.classification_evidence_ids:
            try:
                valid_classifications.append(
                    ContextClassification(ledger[evidence_id].text_value)
                )
            except (TypeError, ValueError):
                continue
        if (
            resolve_context_classifications(tuple(valid_classifications))
            is not context.context_classification
        ):
            raise ValueError(
                "Population context must use the conservative classification"
            )
        if valid_classifications and context.classification_evidence_id is None:
            raise ValueError(
                "Population context requires primary classification evidence"
            )

        primary = (
            ledger[context.classification_evidence_id]
            if context.classification_evidence_id is not None
            else None
        )
        primary_call_id = primary.source_tool_call_id if primary is not None else None
        target_records = tuple(
            item
            for item in ledger.values()
            if item.metric == "target_retailer_sales_change"
            and item.source_tool is ToolName.PEER_COMPARISON
            and item.source_tool_call_id == primary_call_id
        )
        if context.target_retailer_sales_change is not None and not any(
            item.value == context.target_retailer_sales_change
            for item in target_records
        ):
            raise ValueError("Target comparison change must match ledger evidence")
        if primary_call_id is None and context.target_retailer_sales_change is not None:
            raise ValueError(
                "Target comparison change requires classification evidence"
            )

        for comparison in (
            context.eligible_population,
            context.behavioral_peers,
        ):
            selected_records = selected(comparison.evidence_ids)
            if len({item.metric for item in selected_records}) != len(selected_records):
                raise ValueError("Comparison context cannot cite duplicate metrics")
            if any(
                item.source_tool is not ToolName.PEER_COMPARISON
                or item.source_tool_call_id != primary_call_id
                for item in selected_records
            ):
                raise ValueError(
                    "Comparison values must come from the primary classification call"
                )
            metrics = {item.metric: item for item in selected_records}
            prefix = (
                "population" if comparison.cohort == "eligible_population" else "peer"
            )
            expected: tuple[tuple[str, float | int | None], ...] = (
                (
                    f"{prefix}_household_count",
                    comparison.cohort_count if comparison.evidence_ids else None,
                ),
                (
                    f"{prefix}_median_retailer_sales_change",
                    comparison.median_change,
                ),
                (f"{prefix}_retailer_sales_change_q25", comparison.q25_change),
                (f"{prefix}_retailer_sales_change_q75", comparison.q75_change),
                (
                    f"target_{prefix}_retailer_sales_change_percentile",
                    comparison.target_percentile,
                ),
                (
                    f"{prefix}_declining_household_share",
                    comparison.declining_household_share,
                ),
                (
                    f"target_minus_{prefix}_median_change",
                    comparison.target_minus_median_change,
                ),
            )
            for metric, value in expected:
                if value is None:
                    continue
                record = metrics.get(metric)
                if record is None or record.value != float(value):
                    raise ValueError(
                        f"{comparison.cohort} value must match ledger metric {metric}"
                    )
            if comparison.evidence_ids and any(
                item.dimensions.get("target_excluded") != "true"
                for item in selected_records
            ):
                raise ValueError("Comparison context must prove target exclusion")

        category_keys = [
            (item.department, item.product_category)
            for item in context.category_context
        ]
        if len(category_keys) != len(set(category_keys)):
            raise ValueError("Category context rows must be unique")
        expected_category_classifications = {
            item.evidence_id
            for item in ledger.values()
            if item.metric == "category_context_classification"
        }
        reported_category_classifications = {
            evidence_id
            for item in context.category_context
            for evidence_id in item.classification_evidence_ids
        }
        if reported_category_classifications != expected_category_classifications:
            raise ValueError(
                "Category context must include every ledger classification"
            )
        for category in context.category_context:
            classification_records = selected(category.classification_evidence_ids)
            if any(
                item.metric != "category_context_classification"
                or item.source_tool is not ToolName.CATEGORY_DECOMPOSITION
                or item.dimensions.get("department", "UNKNOWN") != category.department
                or item.dimensions.get("product_category", "UNKNOWN")
                != category.product_category
                for item in classification_records
            ):
                raise ValueError("Category classification evidence has the wrong scope")
            category_classifications: list[ContextClassification] = []
            for record in classification_records:
                try:
                    category_classifications.append(
                        ContextClassification(record.text_value)
                    )
                except (TypeError, ValueError):
                    continue
            if (
                resolve_context_classifications(tuple(category_classifications))
                is not category.context_classification
            ):
                raise ValueError(
                    "Category context must use the conservative classification"
                )
            if category.classification_evidence_id is not None and (
                category.classification_evidence_id
                not in category.classification_evidence_ids
                or ledger[category.classification_evidence_id].text_value
                != category.context_classification.value
            ):
                raise ValueError(
                    "Primary category classification must match its context"
                )
            if category_classifications and category.classification_evidence_id is None:
                raise ValueError(
                    "Category context requires primary classification evidence"
                )
            category_primary = (
                ledger[category.classification_evidence_id]
                if category.classification_evidence_id is not None
                else None
            )
            category_call_id = (
                category_primary.source_tool_call_id
                if category_primary is not None
                else None
            )
            selected_records = selected(category.evidence_ids)
            if len({item.metric for item in selected_records}) != len(selected_records):
                raise ValueError("Category context cannot cite duplicate metrics")
            if any(
                item.source_tool is not ToolName.CATEGORY_DECOMPOSITION
                or item.source_tool_call_id != category_call_id
                or item.dimensions.get("department", "UNKNOWN") != category.department
                or item.dimensions.get("product_category", "UNKNOWN")
                != category.product_category
                for item in selected_records
            ):
                raise ValueError(
                    "Category values must come from the primary classification call"
                )
            metrics = {item.metric: item for item in selected_records}
            expected_category = {
                "category_percentage_change": category.target_change,
                "category_population_household_count": float(
                    category.comparison_household_count
                ),
                "category_population_median_change": (
                    category.population_median_change
                ),
                "category_population_declining_share": (
                    category.declining_household_share
                ),
                "target_minus_category_population_median_change": (
                    category.target_minus_population_median_change
                ),
            }
            for metric, value in expected_category.items():
                if value is None:
                    continue
                record = metrics.get(metric)
                if record is None or record.value != value:
                    raise ValueError(
                        f"Category context must match ledger metric {metric}"
                    )
            classification = metrics.get("category_context_classification")
            if (
                classification is None
                or classification.text_value != category.context_classification.value
            ):
                raise ValueError("Category classification must match ledger evidence")
            if selected_records and any(
                item.dimensions.get("target_excluded") != "true"
                for item in selected_records
                if item.metric.startswith("category_population_")
                or item.metric.startswith("target_minus_category_")
                or item.metric == "category_context_classification"
            ):
                raise ValueError("Category context must prove target exclusion")


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
