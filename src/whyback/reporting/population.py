"""Deterministic, identifier-minimized population summaries for one demo batch."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Self, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whyback.agent.actions import ActionId
from whyback.config import DetectionConfig
from whyback.detection.decline import DeclineSnapshot, SensitivityRow
from whyback.reporting.models import ReportData

type CohortId = Literal["eligible", "flagged", "investigated"]
type MetricId = Literal[
    "decline_score",
    "sales_drop",
    "trip_drop",
    "active_week_drop",
    "baseline_retailer_sales_value",
    "recent_retailer_sales_value",
    "recorded_value_change",
]
type FactorType = Literal[
    "category",
    "cadence",
    "promotion_value",
    "multifactor",
    "monitoring",
    "insufficient_evidence",
    "failed",
]


class QuantilePoint(BaseModel):
    """One exact quantile in a cohort distribution."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    probability: float = Field(ge=0.0, le=1.0)
    value: float


class HistogramBin(BaseModel):
    """One common histogram interval and its cohort-specific count."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    lower: float
    upper: float
    count: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0)


class MetricDistribution(BaseModel):
    """Descriptive statistics for one metric within one cohort."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    metric: MetricId
    unit: Literal["share", "retailer_sales_value"]
    count: int = Field(ge=0)
    mean: float | None
    minimum: float | None
    q25: float | None
    median: float | None
    q75: float | None
    maximum: float | None
    deciles: tuple[QuantilePoint, ...]
    histogram: tuple[HistogramBin, ...]

    @model_validator(mode="after")
    def validate_distribution(self) -> Self:
        """Reconcile counts and require unavailable values to remain null."""

        if sum(item.count for item in self.histogram) != self.count:
            raise ValueError("Histogram bins must reconcile to the metric count")
        if any(item.upper <= item.lower for item in self.histogram):
            raise ValueError("Histogram bins must have increasing bounds")
        statistics = (
            self.mean,
            self.minimum,
            self.q25,
            self.median,
            self.q75,
            self.maximum,
        )
        if self.count == 0 and (
            any(item is not None for item in statistics) or self.deciles
        ):
            raise ValueError("An empty distribution cannot publish statistics")
        if self.count > 0 and (
            any(item is None for item in statistics) or len(self.deciles) != 9
        ):
            raise ValueError("A populated distribution requires complete statistics")
        if self.count > 0:
            ordered = cast(
                tuple[float, float, float, float, float],
                (
                    self.minimum,
                    self.q25,
                    self.median,
                    self.q75,
                    self.maximum,
                ),
            )
            if tuple(sorted(ordered)) != ordered:
                raise ValueError("Distribution quantiles must be ordered")
            if any(
                left.probability >= right.probability or left.value > right.value
                for left, right in zip(self.deciles, self.deciles[1:], strict=False)
            ):
                raise ValueError("Distribution deciles must be ordered")
        return self


class CohortSummary(BaseModel):
    """One explicitly defined nested household cohort."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cohort: CohortId
    definition: str = Field(min_length=1)
    household_count: int = Field(ge=0)
    aggregate_baseline_value: float
    aggregate_recent_value: float
    gross_recorded_decrease: float = Field(ge=0.0)
    metrics: tuple[MetricDistribution, ...]


class DensityCell(BaseModel):
    """One aggregate cell with no household identifiers."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    x_lower: float
    x_upper: float
    y_lower: float
    y_upper: float
    eligible_count: int = Field(ge=0)
    flagged_count: int = Field(ge=0)
    investigated_count: int = Field(ge=0)


class DensityGrid(BaseModel):
    """Common baseline-value by decline-score grid for all three cohorts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_metric: Literal["baseline_retailer_sales_value"] = "baseline_retailer_sales_value"
    y_metric: Literal["decline_score"] = "decline_score"
    x_scale: Literal["log1p"] = "log1p"
    x_edges: tuple[float, ...]
    y_edges: tuple[float, ...]
    cells: tuple[DensityCell, ...]


class MixRow(BaseModel):
    """One denominator-preserving executive mix entry."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    count: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0)


class IdentifiedFactor(BaseModel):
    """Structured, display-safe factor resolved from a verified report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor_type: FactorType
    label: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class InvestigatedHousehold(BaseModel):
    """The only population record permitted to carry a household identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    household_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    status: Literal["completed", "insufficient_evidence", "failed"]
    context_classification: str = Field(min_length=1)
    decline_score: float = Field(ge=0.0, le=1.0)
    sales_drop: float = Field(ge=0.0, le=1.0)
    trip_drop: float = Field(ge=0.0, le=1.0)
    active_week_drop: float = Field(ge=0.0, le=1.0)
    baseline_retailer_sales_value: float
    recent_retailer_sales_value: float
    recorded_value_change: float
    population_gap: float | None
    peer_gap: float | None
    identified_factor: IdentifiedFactor
    action_id: str | None
    action_label: str
    confidence: str
    warnings: tuple[str, ...]


class ExecutiveSummary(BaseModel):
    """Decision-facing totals without causal or recoverability semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    eligible_count: int = Field(ge=0)
    flagged_count: int = Field(ge=0)
    flagged_share: float = Field(ge=0.0, le=1.0)
    selected_count: int = Field(ge=0)
    investigated_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    insufficient_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    aggregate_baseline_value: float
    aggregate_recent_value: float
    recorded_value_change: float
    gross_recorded_decrease: float = Field(ge=0.0)
    verified_action_rate: float = Field(ge=0.0, le=1.0)
    action_mix: tuple[MixRow, ...]
    factor_mix: tuple[MixRow, ...]
    context_mix: tuple[MixRow, ...]


class AnalysisWindows(BaseModel):
    """Inclusive detector windows shared by every cohort comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_start_week: int
    baseline_end_week: int
    recent_start_week: int
    recent_end_week: int


class PopulationProvenance(BaseModel):
    """Collection-level provenance sufficient to interpret this artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_kind: str = Field(min_length=1)
    dataset_source_repository: str = Field(min_length=1)
    dataset_source_commit: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    source_manifest: str | None
    generated_at: datetime


class PopulationSummary(BaseModel):
    """Versioned collection-level population contract."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal[1] = 1
    availability: Literal["full"] = "full"
    missing_data_reasons: tuple[str, ...] = ()
    cohort_definitions: dict[CohortId, str]
    analysis_windows: AnalysisWindows
    detector_policy: DetectionConfig
    threshold_sensitivity: tuple[SensitivityRow, ...]
    data_quality_warnings: tuple[str, ...]
    cohorts: tuple[CohortSummary, ...]
    density_grid: DensityGrid
    investigated_households: tuple[InvestigatedHousehold, ...]
    executive: ExecutiveSummary
    provenance: PopulationProvenance

    @model_validator(mode="after")
    def validate_population(self) -> Self:
        """Enforce cohort nesting, unique metrics, and executive reconciliation."""

        by_id = {item.cohort: item for item in self.cohorts}
        if set(by_id) != {"eligible", "flagged", "investigated"}:
            raise ValueError("Population summary requires all three cohorts")
        if not (
            by_id["eligible"].household_count
            >= by_id["flagged"].household_count
            >= by_id["investigated"].household_count
        ):
            raise ValueError("Population cohorts must be explicitly nested")
        for cohort in self.cohorts:
            metric_ids = [item.metric for item in cohort.metrics]
            if len(metric_ids) != len(set(metric_ids)):
                raise ValueError("A cohort cannot repeat a metric")
            if any(item.count != cohort.household_count for item in cohort.metrics):
                raise ValueError("Metric counts must match their cohort")
        eligible_metrics = {item.metric: item for item in by_id["eligible"].metrics}
        for cohort in self.cohorts[1:]:
            for metric in cohort.metrics:
                reference = eligible_metrics.get(metric.metric)
                if reference is None or tuple(
                    (item.lower, item.upper) for item in metric.histogram
                ) != tuple((item.lower, item.upper) for item in reference.histogram):
                    raise ValueError("Cohort histograms must use common metric bins")
        if len(self.investigated_households) != self.executive.investigated_count:
            raise ValueError("Investigated rows must reconcile to executive totals")
        if self.executive.eligible_count != by_id["eligible"].household_count:
            raise ValueError("Eligible totals do not reconcile")
        if self.executive.flagged_count != by_id["flagged"].household_count:
            raise ValueError("Flagged totals do not reconcile")
        if self.executive.selected_count != by_id["investigated"].household_count:
            raise ValueError("Selected totals do not reconcile")
        if (
            self.executive.completed_count
            + self.executive.insufficient_count
            + self.executive.failed_count
            != self.executive.investigated_count
        ):
            raise ValueError("Investigated outcomes do not reconcile")
        if len({item.household_id for item in self.investigated_households}) != len(
            self.investigated_households
        ) or tuple(item.rank for item in self.investigated_households) != tuple(
            sorted(item.rank for item in self.investigated_households)
        ):
            raise ValueError("Investigated rows require unique IDs and ordered ranks")
        density_totals = (
            sum(item.eligible_count for item in self.density_grid.cells),
            sum(item.flagged_count for item in self.density_grid.cells),
            sum(item.investigated_count for item in self.density_grid.cells),
        )
        cohort_totals = tuple(
            by_id[cohort].household_count
            for cohort in ("eligible", "flagged", "investigated")
        )
        if density_totals != cohort_totals:
            raise ValueError("Density cells must reconcile to every cohort")
        if any(
            item.eligible_households != self.executive.eligible_count
            for item in self.threshold_sensitivity
        ):
            raise ValueError("Sensitivity rows must use the eligible denominator")
        configured = tuple(
            item
            for item in self.threshold_sensitivity
            if abs(item.threshold - self.detector_policy.decline_threshold) < 1e-12
        )
        if len(configured) != 1 or configured[0].flagged_households != (
            self.executive.flagged_count
        ):
            raise ValueError(
                "Configured sensitivity threshold must match flagged totals"
            )
        for mix in (
            self.executive.action_mix,
            self.executive.factor_mix,
            self.executive.context_mix,
        ):
            if sum(item.count for item in mix) != self.executive.investigated_count:
                raise ValueError(
                    "Executive mixes must retain every investigated outcome"
                )
        return self


_COHORT_DEFINITIONS: dict[CohortId, str] = {
    "eligible": (
        "All households meeting the declared baseline activity, basket, and "
        "retailer-sales eligibility policy in this analysis window."
    ),
    "flagged": (
        "Eligible households at or above the configured decline-score threshold."
    ),
    "investigated": (
        "The ranked batch selected from the flagged cohort for household-level "
        "investigation."
    ),
}

_METRICS: tuple[MetricId, ...] = (
    "decline_score",
    "sales_drop",
    "trip_drop",
    "active_week_drop",
    "baseline_retailer_sales_value",
    "recent_retailer_sales_value",
    "recorded_value_change",
)


def _metric_value(snapshot: DeclineSnapshot, metric: MetricId) -> float:
    """Resolve one declared metric without exposing an identifier."""

    if metric == "recorded_value_change":
        return (
            snapshot.recent_retailer_sales_value
            - snapshot.baseline_retailer_sales_value
        )
    return float(getattr(snapshot, metric))


def _edges(
    values: Sequence[float], metric: MetricId, bins: int = 16
) -> tuple[float, ...]:
    """Build stable shared edges with useful resolution for bounded and value data."""

    if metric in {
        "decline_score",
        "sales_drop",
        "trip_drop",
        "active_week_drop",
    }:
        return tuple(float(value) for value in np.linspace(0.0, 1.0, bins + 1))
    if not values:
        return tuple(float(value) for value in np.linspace(0.0, 1.0, bins + 1))
    minimum = min(values)
    maximum = max(values)
    if metric != "recorded_value_change" and minimum >= 0:
        edges = tuple(
            float(value)
            for value in np.expm1(np.linspace(0.0, np.log1p(maximum or 1.0), bins + 1))
        )
    else:
        if minimum == maximum:
            padding = max(1.0, abs(minimum) * 0.01)
            minimum -= padding
            maximum += padding
        edges = tuple(float(value) for value in np.linspace(minimum, maximum, bins + 1))

    # expm1(log1p(maximum)) can round one representable float below the source
    # maximum. np.histogram then silently drops that household. Make the outer
    # bounds explicitly inclusive while preserving the shared internal bins.
    return (
        min(edges[0], float(np.nextafter(min(values), -np.inf))),
        *edges[1:-1],
        max(edges[-1], float(np.nextafter(max(values), np.inf))),
    )


def _distribution(
    snapshots: Sequence[DeclineSnapshot], metric: MetricId, edges: tuple[float, ...]
) -> MetricDistribution:
    """Calculate deterministic descriptive statistics and common-bin counts."""

    values = np.asarray(
        [_metric_value(item, metric) for item in snapshots], dtype=float
    )
    counts, _ = np.histogram(values, bins=np.asarray(edges))
    total = len(values)
    histogram = tuple(
        HistogramBin(
            lower=edges[index],
            upper=edges[index + 1],
            count=int(count),
            share=float(count / total) if total else 0.0,
        )
        for index, count in enumerate(counts.tolist())
    )
    unit: Literal["share", "retailer_sales_value"] = (
        "share"
        if metric in {"decline_score", "sales_drop", "trip_drop", "active_week_drop"}
        else "retailer_sales_value"
    )
    if total == 0:
        return MetricDistribution(
            metric=metric,
            unit=unit,
            count=0,
            mean=None,
            minimum=None,
            q25=None,
            median=None,
            q75=None,
            maximum=None,
            deciles=(),
            histogram=histogram,
        )
    quartiles = np.quantile(values, (0.25, 0.5, 0.75))
    return MetricDistribution(
        metric=metric,
        unit=unit,
        count=total,
        mean=float(np.mean(values)),
        minimum=float(np.min(values)),
        q25=float(quartiles[0]),
        median=float(quartiles[1]),
        q75=float(quartiles[2]),
        maximum=float(np.max(values)),
        deciles=tuple(
            QuantilePoint(
                probability=probability, value=float(np.quantile(values, probability))
            )
            for probability in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
        ),
        histogram=histogram,
    )


def _cohort(
    cohort: CohortId,
    snapshots: Sequence[DeclineSnapshot],
    common_edges: dict[MetricId, tuple[float, ...]],
) -> CohortSummary:
    """Aggregate one nested cohort using collection-wide histogram edges."""

    baseline = sum(item.baseline_retailer_sales_value for item in snapshots)
    recent = sum(item.recent_retailer_sales_value for item in snapshots)
    return CohortSummary(
        cohort=cohort,
        definition=_COHORT_DEFINITIONS[cohort],
        household_count=len(snapshots),
        aggregate_baseline_value=baseline,
        aggregate_recent_value=recent,
        gross_recorded_decrease=sum(
            max(
                0.0,
                item.baseline_retailer_sales_value - item.recent_retailer_sales_value,
            )
            for item in snapshots
        ),
        metrics=tuple(
            _distribution(snapshots, metric, common_edges[metric])
            for metric in _METRICS
        ),
    )


def _dominant_drop(snapshot: DeclineSnapshot) -> tuple[str, float]:
    """Return the largest declared detector component for a descriptive label."""

    values = (
        ("sales", snapshot.sales_drop),
        ("trip", snapshot.trip_drop),
        ("active-week", snapshot.active_week_drop),
    )
    return max(values, key=lambda item: item[1])


def _factor(report: ReportData, snapshot: DeclineSnapshot) -> IdentifiedFactor:
    """Map governed outcomes to a stable factor taxonomy and differentiated label."""

    if report.run_status.value == "failed" or report.action is None:
        return IdentifiedFactor(
            factor_type="failed",
            label=f"Failed investigation · {snapshot.decline_score:.0%} decline score",
            detail=report.failure_reason or "No governed conclusion was published.",
        )
    action_id = report.action.action_id
    if action_id is ActionId.INSUFFICIENT_EVIDENCE:
        signal, value = _dominant_drop(snapshot)
        return IdentifiedFactor(
            factor_type="insufficient_evidence",
            label=f"Unresolved {signal} signal · {value:.0%} drop",
            detail="No supported differentiating factor cleared verification.",
        )
    mapping: dict[ActionId, tuple[FactorType, str]] = {
        ActionId.CATEGORY_WINBACK: ("category", "Category-specific decline"),
        ActionId.VISIT_FREQUENCY_REACTIVATION: (
            "cadence",
            f"Visit cadence · {snapshot.trip_drop:.0%} trip drop",
        ),
        ActionId.PROMOTION_VALUE_REENGAGEMENT: (
            "promotion_value",
            f"Promotion/value · {snapshot.sales_drop:.0%} sales drop",
        ),
        ActionId.PERSONALIZED_CHECK_IN: (
            "multifactor",
            (
                f"Multifactor · sales {snapshot.sales_drop:.0%}, "
                f"trips {snapshot.trip_drop:.0%}"
            ),
        ),
        ActionId.MONITOR: (
            "monitoring",
            f"Monitoring · {snapshot.decline_score:.0%} decline score",
        ),
    }
    factor_type, fallback = mapping[action_id]
    label = fallback
    if action_id is ActionId.CATEGORY_WINBACK:
        supporting_ids = {
            evidence_id
            for driver in report.likely_drivers
            for evidence_id in driver.supporting_evidence_ids
        }
        for evidence in report.supporting_evidence:
            if evidence.evidence_id not in supporting_ids:
                continue
            category = evidence.dimensions.get("product_category")
            department = evidence.dimensions.get("department")
            if category and department:
                label = f"{department} / {category}"
                break
            if category or department:
                label = category or department or fallback
                break
    detail = (
        report.likely_drivers[0].summary
        if report.likely_drivers
        else report.action.rationale
    )
    return IdentifiedFactor(factor_type=factor_type, label=label, detail=detail)


def _investigated_rows(
    selected: Sequence[DeclineSnapshot], reports: Sequence[ReportData]
) -> tuple[InvestigatedHousehold, ...]:
    """Join only selected report owners to detector ranks."""

    rank = {item.household_id: index + 1 for index, item in enumerate(selected)}
    snapshots = {item.household_id: item for item in selected}
    rows: list[InvestigatedHousehold] = []
    for report in reports:
        if report.run_status.value == "running":
            raise ValueError("Population artifacts cannot contain running reports")
        snapshot = snapshots.get(report.household_id)
        if snapshot is None:
            continue
        population = report.population_context.eligible_population
        peers = report.population_context.behavioral_peers
        warnings = tuple(
            dict.fromkeys(
                (
                    *report.limitations,
                    *report.verification_issues,
                    *(
                        limitation
                        for warning in report.tool_warnings
                        for limitation in warning.limitations
                    ),
                    *((report.failure_reason,) if report.failure_reason else ()),
                )
            )
        )
        action_id = report.action.action_id.value if report.action is not None else None
        rows.append(
            InvestigatedHousehold(
                household_id=report.household_id,
                rank=rank[report.household_id],
                status=report.run_status.value,
                context_classification=report.population_context.context_classification.value,
                decline_score=snapshot.decline_score,
                sales_drop=snapshot.sales_drop,
                trip_drop=snapshot.trip_drop,
                active_week_drop=snapshot.active_week_drop,
                baseline_retailer_sales_value=snapshot.baseline_retailer_sales_value,
                recent_retailer_sales_value=snapshot.recent_retailer_sales_value,
                recorded_value_change=(
                    snapshot.recent_retailer_sales_value
                    - snapshot.baseline_retailer_sales_value
                ),
                population_gap=population.target_minus_median_change,
                peer_gap=peers.target_minus_median_change,
                identified_factor=_factor(report, snapshot),
                action_id=action_id,
                action_label=(
                    report.action.description
                    if report.action is not None
                    else "No recommendation published"
                ),
                confidence=(
                    report.action.resolved_confidence.value
                    if report.action is not None
                    else "unavailable"
                ),
                warnings=warnings,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.rank))


def _mix(values: Sequence[tuple[str, str]], denominator: int) -> tuple[MixRow, ...]:
    """Count a categorical mix while retaining zero-free, stable ordering."""

    labels = dict(values)
    counts = Counter(key for key, _ in values)
    return tuple(
        MixRow(
            key=key,
            label=labels[key],
            count=count,
            share=count / denominator if denominator else 0.0,
        )
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )


def _density_grid(
    eligible: Sequence[DeclineSnapshot],
    flagged: Sequence[DeclineSnapshot],
    investigated: Sequence[DeclineSnapshot],
) -> DensityGrid:
    """Create a count-only grid whose cells cannot disclose unselected households."""

    baseline_values = [item.baseline_retailer_sales_value for item in eligible]
    x_edges = _edges(baseline_values, "baseline_retailer_sales_value", bins=12)
    y_edges = _edges(
        [item.decline_score for item in eligible], "decline_score", bins=10
    )

    def counts(items: Sequence[DeclineSnapshot]) -> np.ndarray:
        """Count one cohort into the shared two-dimensional density bins."""

        points = np.asarray(
            [
                (item.baseline_retailer_sales_value, item.decline_score)
                for item in items
            ],
            dtype=float,
        )
        if points.size == 0:
            return np.zeros((len(x_edges) - 1, len(y_edges) - 1), dtype=int)
        result, _, _ = np.histogram2d(
            points[:, 0], points[:, 1], bins=(np.asarray(x_edges), np.asarray(y_edges))
        )
        return result.astype(int)

    eligible_counts = counts(eligible)
    flagged_counts = counts(flagged)
    investigated_counts = counts(investigated)
    cells = tuple(
        DensityCell(
            x_lower=x_edges[x],
            x_upper=x_edges[x + 1],
            y_lower=y_edges[y],
            y_upper=y_edges[y + 1],
            eligible_count=int(eligible_counts[x, y]),
            flagged_count=int(flagged_counts[x, y]),
            investigated_count=int(investigated_counts[x, y]),
        )
        for y in range(len(y_edges) - 1)
        for x in range(len(x_edges) - 1)
        if eligible_counts[x, y] or flagged_counts[x, y] or investigated_counts[x, y]
    )
    return DensityGrid(x_edges=x_edges, y_edges=y_edges, cells=cells)


def build_population_summary(
    *,
    candidates: Sequence[DeclineSnapshot],
    selected: Sequence[DeclineSnapshot],
    reports: Sequence[ReportData],
    detector_policy: DetectionConfig,
    threshold_sensitivity: Sequence[SensitivityRow],
    dataset_kind: str,
    dataset_source_repository: str,
    dataset_source_commit: str,
    backend: str,
    source_manifest: str | None,
) -> PopulationSummary:
    """Build the full population artifact entirely from validated Python data."""

    eligible = tuple(item for item in candidates if item.eligible)
    flagged = tuple(item for item in eligible if item.flagged)
    selected_tuple = tuple(selected)
    if any(item not in flagged for item in selected_tuple):
        raise ValueError(
            "Every investigated household must belong to the flagged cohort"
        )
    if not eligible:
        raise ValueError(
            "A population summary requires at least one eligible household"
        )
    common_edges: dict[MetricId, tuple[float, ...]] = {
        metric: _edges([_metric_value(item, metric) for item in eligible], metric)
        for metric in _METRICS
    }
    rows = _investigated_rows(selected_tuple, reports)
    completed = sum(item.status == "completed" for item in rows)
    insufficient = sum(item.status == "insufficient_evidence" for item in rows)
    failed = sum(item.status == "failed" for item in rows)
    baseline = sum(item.baseline_retailer_sales_value for item in eligible)
    recent = sum(item.recent_retailer_sales_value for item in eligible)
    first = eligible[0]
    partial_warnings = tuple(
        dict.fromkeys(
            item.partial_week_limitation
            for item in eligible
            if item.partial_week_limitation
        )
    )
    action_values = [
        (item.action_id or "NO_PUBLISHED_RECOMMENDATION", item.action_label)
        for item in rows
    ]
    factor_values = [
        (
            f"{item.identified_factor.factor_type}:{item.identified_factor.label}",
            item.identified_factor.label,
        )
        for item in rows
    ]
    context_values = [
        (
            item.context_classification,
            item.context_classification.replace("_", " ").title(),
        )
        for item in rows
    ]
    generated_at = reports[0].provenance.generated_at if reports else datetime.now(UTC)
    return PopulationSummary(
        cohort_definitions=_COHORT_DEFINITIONS,
        analysis_windows=AnalysisWindows(
            baseline_start_week=first.baseline_start_week,
            baseline_end_week=first.baseline_end_week,
            recent_start_week=first.recent_start_week,
            recent_end_week=first.recent_end_week,
        ),
        detector_policy=detector_policy,
        threshold_sensitivity=tuple(threshold_sensitivity),
        data_quality_warnings=partial_warnings,
        cohorts=(
            _cohort("eligible", eligible, common_edges),
            _cohort("flagged", flagged, common_edges),
            _cohort("investigated", selected_tuple, common_edges),
        ),
        density_grid=_density_grid(eligible, flagged, selected_tuple),
        investigated_households=rows,
        executive=ExecutiveSummary(
            eligible_count=len(eligible),
            flagged_count=len(flagged),
            flagged_share=len(flagged) / len(eligible),
            selected_count=len(selected_tuple),
            investigated_count=len(rows),
            completed_count=completed,
            insufficient_count=insufficient,
            failed_count=failed,
            aggregate_baseline_value=baseline,
            aggregate_recent_value=recent,
            recorded_value_change=recent - baseline,
            gross_recorded_decrease=sum(
                max(
                    0.0,
                    item.baseline_retailer_sales_value
                    - item.recent_retailer_sales_value,
                )
                for item in eligible
            ),
            verified_action_rate=completed / len(rows) if rows else 0.0,
            action_mix=_mix(action_values, len(rows)),
            factor_mix=_mix(factor_values, len(rows)),
            context_mix=_mix(context_values, len(rows)),
        ),
        provenance=PopulationProvenance(
            dataset_kind=dataset_kind,
            dataset_source_repository=dataset_source_repository,
            dataset_source_commit=dataset_source_commit,
            backend=backend,
            source_manifest=source_manifest,
            generated_at=generated_at,
        ),
    )
