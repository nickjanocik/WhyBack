"""Build and render reviewer-facing WhyBack investigation reports."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from whyback.agent.runner import InvestigationOutcome
from whyback.agent.verifier import VerifiedFinalDecision, is_report_safe_qualitative
from whyback.methodology import (
    ContextClassification,
    resolve_context_classifications,
)
from whyback.observability import REDACTED_VALUE, sanitize_public_text
from whyback.reporting.models import (
    ActionReportData,
    CategoryContextReportData,
    CohortComparisonReportData,
    ConfidenceAdjustmentReportData,
    DeclineReportData,
    DriverReportData,
    InterpretationLimitsReportData,
    InvestigationStepData,
    PopulationContextReportData,
    ReportData,
    ReportEvidenceData,
    ToolWarningData,
)
from whyback.tools.contracts import EvidenceRecord, ToolName, ToolStatus

_TEMPLATE_DIRECTORY: Final = Path(__file__).with_name("templates")
_NUMERICAL_CLAIM: Final = re.compile(
    r"(?<![A-Za-z0-9_])(?:[$€£]\s*)?\d+(?:[.,]\d+)*(?:\s*%)?"
)
_TOOL_LABELS: Final = {
    ToolName.CUSTOMER_TREND: "Customer trend",
    ToolName.CATEGORY_DECOMPOSITION: "Category decomposition",
    ToolName.BASKET_BEHAVIOR: "Basket behavior",
    ToolName.PROMOTION_RESPONSE: "Promotion response",
    ToolName.COUPON_CAMPAIGN_HISTORY: "Coupon campaign history",
    ToolName.PEER_COMPARISON: "Behavioral peer comparison",
}
_ELIGIBLE_POPULATION_METHOD: Final = (
    "Households meeting the declared baseline active-week, distinct-basket, and "
    "positive retailer-sales eligibility criteria; the target is excluded."
)
_BEHAVIORAL_PEER_METHOD: Final = (
    "Nearest target-excluded households after robust scaling of declared baseline "
    "behavioral features; demographics are not used."
)


@dataclass(frozen=True, slots=True)
class ReportBundlePaths:
    """Paths written by :func:`write_report_bundle`."""

    json: Path
    markdown: Path
    html: Path


def _deduplicate(values: list[str]) -> tuple[str, ...]:
    """Sanitize strings and retain each nonempty value only once in order."""

    return tuple(
        dict.fromkeys(sanitize_public_text(value) for value in values if value)
    )


def _qualitative(text: str, *, fallback: str) -> str:
    """Reject unsafe model prose at the final rendering boundary."""

    sanitized = sanitize_public_text(text)
    return (
        fallback
        if sanitized == REDACTED_VALUE
        or _NUMERICAL_CLAIM.search(sanitized)
        or not is_report_safe_qualitative(sanitized)
        else sanitized
    )


def _verified_final(outcome: InvestigationOutcome) -> VerifiedFinalDecision | None:
    """Return the final decision only when deterministic verification passed."""

    verification = outcome.verification
    if verification is None or not verification.passed:
        return None
    return verification.final


def _evidence_role(
    evidence_id: str,
    *,
    supporting_ids: frozenset[str],
    counterevidence_ids: frozenset[str],
) -> Literal["supporting", "counterevidence", "context"]:
    """Classify an evidence ID by its verified role in the final report."""

    if evidence_id in supporting_ids:
        return "supporting"
    if evidence_id in counterevidence_ids:
        return "counterevidence"
    return "context"


def _report_evidence(
    record: EvidenceRecord,
    *,
    call_statuses: dict[str, ToolStatus],
    supporting_ids: frozenset[str],
    counterevidence_ids: frozenset[str],
) -> ReportEvidenceData:
    """Convert a ledger record into its immutable, source-status-aware report form."""

    return ReportEvidenceData(
        evidence_id=record.evidence_id,
        run_id=str(record.run_id),
        household_id=record.household_id,
        role=_evidence_role(
            record.evidence_id,
            supporting_ids=supporting_ids,
            counterevidence_ids=counterevidence_ids,
        ),
        source_tool=record.source_tool,
        source_tool_call_id=record.source_tool_call_id,
        source_status=call_statuses.get(record.source_tool_call_id),
        metric=record.metric,
        dimensions=dict(sorted(record.dimensions.items())),
        baseline_value=record.baseline_value,
        recent_value=record.recent_value,
        value=record.value,
        text_value=record.text_value,
        change=record.change,
        unit=record.unit,
        maximum_claim_type=record.maximum_claim_type,
        limitations=tuple(sanitize_public_text(item) for item in record.limitations),
        query_hash=record.query_hash,
    )


def _first_metric(
    records: tuple[EvidenceRecord, ...], metric: str
) -> EvidenceRecord | None:
    """Return the first evidence record for a named metric, if one exists."""

    return next((record for record in records if record.metric == metric), None)


def _as_count(record: EvidenceRecord | None) -> int:
    """Convert a nonnegative count-valued evidence record to an integer."""

    if record is None or record.value is None:
        return 0
    return max(0, int(record.value))


def _cohort_comparison(
    records: tuple[EvidenceRecord, ...],
    *,
    cohort: Literal["eligible_population", "behavioral_peers"],
) -> CohortComparisonReportData:
    """Resolve one population or peer distribution from its bound evidence records."""

    if cohort == "eligible_population":
        names = {
            "count": "population_household_count",
            "median": "population_median_retailer_sales_change",
            "q25": "population_retailer_sales_change_q25",
            "q75": "population_retailer_sales_change_q75",
            "percentile": "target_population_retailer_sales_change_percentile",
            "share": "population_declining_household_share",
            "gap": "target_minus_population_median_change",
        }
        method = _ELIGIBLE_POPULATION_METHOD
    else:
        names = {
            "count": "peer_household_count",
            "median": "peer_median_retailer_sales_change",
            "q25": "peer_retailer_sales_change_q25",
            "q75": "peer_retailer_sales_change_q75",
            "percentile": "target_peer_retailer_sales_change_percentile",
            "share": "peer_declining_household_share",
            "gap": "target_minus_peer_median_change",
        }
        method = _BEHAVIORAL_PEER_METHOD
    selected = tuple(
        record for record in records if record.metric in frozenset(names.values())
    )
    by_metric = {record.metric: record for record in selected}
    count = _as_count(by_metric.get(names["count"]))
    median = by_metric.get(names["median"])
    q25 = by_metric.get(names["q25"])
    q75 = by_metric.get(names["q75"])
    percentile = by_metric.get(names["percentile"])
    share = by_metric.get(names["share"])
    gap = by_metric.get(names["gap"])
    available = (
        all(
            item is not None and item.value is not None
            for item in (median, q25, q75, percentile, share, gap)
        )
        and count > 0
    )
    limitations = _deduplicate(
        [item for record in selected for item in record.limitations]
    )
    target_excluded = all(
        record.dimensions.get("target_excluded", "").casefold() == "true"
        for record in selected
    )
    return CohortComparisonReportData(
        cohort=cohort,
        available=available,
        cohort_count=count,
        median_change=median.value if median is not None else None,
        q25_change=q25.value if q25 is not None else None,
        q75_change=q75.value if q75 is not None else None,
        target_percentile=(percentile.value if percentile is not None else None),
        declining_household_share=share.value if share is not None else None,
        target_minus_median_change=gap.value if gap is not None else None,
        target_excluded=target_excluded,
        construction_method=(
            selected[0].dimensions.get("cohort_definition", method)
            if selected
            else method
        ),
        evidence_ids=tuple(record.evidence_id for record in selected),
        limitations=(
            limitations
            if limitations
            else (
                ()
                if available
                else (
                    "Comparison context is unavailable or below its declared "
                    "cohort minimum.",
                )
            )
        ),
    )


def _category_context(
    records: tuple[EvidenceRecord, ...],
) -> tuple[CategoryContextReportData, ...]:
    """Assemble selected-category context rows from classification-linked evidence."""

    classification_records = tuple(
        record
        for record in records
        if record.metric == "category_context_classification"
    )
    category_keys = tuple(
        dict.fromkeys(
            (
                record.dimensions.get("department", "UNKNOWN"),
                record.dimensions.get("product_category", "UNKNOWN"),
            )
            for record in classification_records
        )
    )
    rows: list[CategoryContextReportData] = []
    for department, category in category_keys:
        scoped_classifications = tuple(
            record
            for record in classification_records
            if record.dimensions.get("department", "UNKNOWN") == department
            and record.dimensions.get("product_category", "UNKNOWN") == category
        )
        valid_classifications: list[ContextClassification] = []
        for record in scoped_classifications:
            try:
                valid_classifications.append(ContextClassification(record.text_value))
            except (TypeError, ValueError):
                continue
        classification = resolve_context_classifications(tuple(valid_classifications))
        classification_record = next(
            (
                record
                for record in scoped_classifications
                if record.text_value == classification.value
            ),
            None,
        )
        grouped = tuple(
            record
            for record in records
            if record.source_tool is ToolName.CATEGORY_DECOMPOSITION
            and classification_record is not None
            and record.source_tool_call_id == classification_record.source_tool_call_id
            and record.dimensions.get("department", "UNKNOWN") == department
            and record.dimensions.get("product_category", "UNKNOWN") == category
        )
        metrics = {record.metric: record for record in grouped}
        count_record = metrics.get("category_population_household_count")
        median_record = metrics.get("category_population_median_change")
        share_record = metrics.get("category_population_declining_share")
        gap_record = metrics.get("target_minus_category_population_median_change")
        target_record = metrics.get("category_percentage_change") or metrics.get(
            "target_category_change"
        )
        count = _as_count(count_record)
        available = (
            classification is not ContextClassification.INSUFFICIENT_CONTEXT
            and count > 0
            and all(
                item is not None and item.value is not None
                for item in (median_record, share_record, gap_record)
            )
        )
        rows.append(
            CategoryContextReportData(
                department=department,
                product_category=category,
                available=available,
                target_change=(
                    target_record.value if target_record is not None else None
                ),
                comparison_household_count=count,
                population_median_change=(
                    median_record.value if median_record is not None else None
                ),
                declining_household_share=(
                    share_record.value if share_record is not None else None
                ),
                target_minus_population_median_change=(
                    gap_record.value if gap_record is not None else None
                ),
                context_classification=classification,
                target_excluded=bool(grouped)
                and all(
                    record.dimensions.get("target_excluded", "").casefold() == "true"
                    for record in grouped
                    if record.metric.startswith("category_population_")
                    or record.metric.startswith("target_minus_category_")
                    or record.metric == "category_context_classification"
                ),
                evidence_ids=tuple(record.evidence_id for record in grouped),
                classification_evidence_id=(
                    classification_record.evidence_id
                    if classification_record is not None
                    else None
                ),
                classification_evidence_ids=tuple(
                    record.evidence_id for record in scoped_classifications
                ),
                limitations=_deduplicate(
                    [
                        item
                        for record in (*scoped_classifications, *grouped)
                        for item in record.limitations
                    ]
                ),
            )
        )
    return tuple(rows)


def build_population_context(
    records: tuple[EvidenceRecord, ...],
) -> PopulationContextReportData:
    """Build complete, ledger-bound population and category context."""
    classification_records = tuple(
        record for record in records if record.metric == "context_classification"
    )
    valid_classifications: list[ContextClassification] = []
    for record in classification_records:
        try:
            valid_classifications.append(ContextClassification(record.text_value))
        except (TypeError, ValueError):
            continue
    classification = resolve_context_classifications(tuple(valid_classifications))
    classification_record = next(
        (
            record
            for record in classification_records
            if record.text_value == classification.value
        ),
        None,
    )
    selected_call_records = tuple(
        record
        for record in records
        if classification_record is not None
        and record.source_tool is ToolName.PEER_COMPARISON
        and record.source_tool_call_id == classification_record.source_tool_call_id
    )
    target_record = _first_metric(selected_call_records, "target_retailer_sales_change")
    population = _cohort_comparison(selected_call_records, cohort="eligible_population")
    peers = _cohort_comparison(selected_call_records, cohort="behavioral_peers")
    related = tuple(
        record
        for record in records
        if record.source_tool
        in {ToolName.PEER_COMPARISON, ToolName.CATEGORY_DECOMPOSITION}
        and (
            record.metric == "context_classification"
            or record.metric.startswith("population_")
            or record.metric.startswith("peer_")
            or record.metric.startswith("target_population_")
            or record.metric.startswith("target_peer_")
            or record.metric.startswith("target_minus_")
            or record.metric.startswith("category_")
        )
    )
    limitations = _deduplicate(
        [item for record in related for item in record.limitations]
    )
    if classification is ContextClassification.INSUFFICIENT_CONTEXT and not limitations:
        limitations = (
            "Population context is unavailable or below its declared cohort minimum.",
        )
    return PopulationContextReportData(
        context_classification=classification,
        target_retailer_sales_change=(
            target_record.value if target_record is not None else None
        ),
        eligible_population=population,
        behavioral_peers=peers,
        category_context=_category_context(records),
        classification_evidence_id=(
            classification_record.evidence_id
            if classification_record is not None
            else None
        ),
        classification_evidence_ids=tuple(
            record.evidence_id for record in classification_records
        ),
        limitations=limitations,
    )


def build_interpretation_limits(
    records: tuple[EvidenceRecord, ...],
    classification: ContextClassification,
) -> InterpretationLimitsReportData:
    """Build the code-owned observable, unobserved, and causal boundaries."""
    tools = {record.source_tool for record in records}
    observed = [
        "Recorded retailer sales value, distinct baskets, and active weeks in the "
        "declared baseline and recent windows."
    ]
    if ToolName.CATEGORY_DECOMPOSITION in tools:
        observed.append(
            "Recorded category movement, including explicit UNKNOWN mappings and "
            "reconciled retailer-sales totals."
        )
    if ToolName.PEER_COMPARISON in tools:
        observed.append(
            "The household's relative position among target-excluded eligible "
            "households and behavioral peers."
        )
    if ToolName.PROMOTION_RESPONSE in tools:
        observed.append(
            "Purchasing associated with product/store/week promotion availability, "
            "not confirmed household attention."
        )
    if ToolName.COUPON_CAMPAIGN_HISTORY in tools:
        observed.append(
            "Recorded campaign participation, coupon redemption, and available "
            "delivery facts."
        )
    unobserved = [
        "Purchases at competitors, restaurants, and other online or offline channels.",
        "Relocation, travel, income or employment changes, household-composition "
        "changes, health, diet, and transportation access.",
        "Customer satisfaction, service experiences, stockouts, discontinuations, "
        "assortment changes, and competitor conditions.",
        "Customer intent and whether a particular household member noticed an "
        "advertisement or promotion.",
    ]
    if classification in {
        ContextClassification.BROAD_CONTEXT,
        ContextClassification.MIXED,
    }:
        unobserved.append(
            "The data cannot distinguish broad contemporaneous movement caused by "
            "holidays, prices, retailer conditions, economic effects, weather, or "
            "other common factors."
        )
    causal = [
        "The source is observational: current evidence supports descriptive and "
        "associational claims, not causal claims.",
        "Marketing treatment may be targeted from prior behavior, so campaign and "
        "purchasing associations can reflect selection into treatment.",
        "Whether a recommended action changes behavior must be learned through a "
        "valid prospective design such as the stated randomized holdout.",
    ]
    return InterpretationLimitsReportData(
        observed_scope=tuple(observed),
        unobserved_factors=tuple(unobserved),
        causal_limitations=tuple(causal),
    )


def build_report_data(outcome: InvestigationOutcome) -> ReportData:
    """Resolve a run into a stable report boundary without trusting numeric prose."""

    state = outcome.state
    snapshot = state.detector_snapshot
    final = _verified_final(outcome)
    supporting_ids = frozenset(final.supporting_evidence_ids if final else ())
    counterevidence_ids = frozenset(final.counterevidence_ids if final else ())
    population_context = build_population_context(tuple(state.evidence_ledger))
    call_statuses = {
        attempt.tool_call_id: attempt.status
        for history in state.tool_history
        for attempt in history.attempts
    }

    ledger = tuple(
        _report_evidence(
            record,
            call_statuses=call_statuses,
            supporting_ids=supporting_ids,
            counterevidence_ids=counterevidence_ids,
        )
        for record in state.evidence_ledger
    )
    by_id = {record.evidence_id: record for record in ledger}
    supporting = tuple(
        by_id[evidence_id]
        for evidence_id in (final.supporting_evidence_ids if final else ())
        if evidence_id in by_id
    )
    counterevidence = tuple(
        by_id[evidence_id]
        for evidence_id in (final.counterevidence_ids if final else ())
        if evidence_id in by_id
    )

    path: list[InvestigationStepData] = []
    warnings: list[ToolWarningData] = []
    limitations: list[str] = []
    if snapshot.partial_week_limitation:
        limitations.append(snapshot.partial_week_limitation)
    for history in state.tool_history:
        attempts = history.attempts
        retry_count = max(0, len(attempts) - 1)
        step_limitations = _deduplicate(
            [
                *history.limitations,
                *(item for attempt in attempts for item in attempt.limitations),
            ]
        )
        limitations.extend(step_limitations)
        fallback_question = f"Investigate {_TOOL_LABELS[history.tool_name].lower()}."
        path.append(
            InvestigationStepData(
                decision_number=history.decision_number,
                tool_name=history.tool_name,
                tool_label=_TOOL_LABELS[history.tool_name],
                investigation_question=_qualitative(
                    history.investigation_question,
                    fallback=fallback_question,
                ),
                final_status=history.final_status,
                attempt_count=len(attempts),
                retry_count=retry_count,
                total_latency_ms=sum(attempt.elapsed_ms for attempt in attempts),
                evidence_ids=history.evidence_ids,
                limitations=step_limitations,
            )
        )
        if history.final_status is not ToolStatus.OK or retry_count:
            unavailable = history.tool_name in state.unavailable_tools
            if unavailable:
                limitations.append(
                    f"{_TOOL_LABELS[history.tool_name]} is unavailable after its "
                    "bounded retry policy was exhausted."
                )
            warnings.append(
                ToolWarningData(
                    tool_name=history.tool_name,
                    final_status=history.final_status,
                    attempt_count=len(attempts),
                    retry_count=retry_count,
                    attempt_statuses=tuple(item.status for item in attempts),
                    total_latency_ms=sum(item.elapsed_ms for item in attempts),
                    limitations=step_limitations,
                    unavailable=unavailable,
                )
            )
    for record in ledger:
        limitations.extend(record.limitations)

    drivers: tuple[DriverReportData, ...] = ()
    alternatives: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    action: ActionReportData | None = None
    if final is not None:
        drivers = tuple(
            DriverReportData(
                summary=_qualitative(
                    driver.summary,
                    fallback="A grounded behavioral signal is a plausible driver.",
                ),
                claim_type=driver.claim_type,
                supporting_evidence_ids=driver.supporting_evidence_ids,
                counterevidence_ids=driver.counterevidence_ids,
                no_material_counterevidence_reason=(
                    _qualitative(
                        driver.no_material_counterevidence_reason,
                        fallback=(
                            "No material counterevidence was identified during the "
                            "bounded investigation."
                        ),
                    )
                    if driver.no_material_counterevidence_reason
                    else None
                ),
                limitations=tuple(
                    sanitize_public_text(item) for item in driver.limitations
                ),
            )
            for driver in final.drivers
        )
        alternatives = tuple(
            _qualitative(
                item,
                fallback=(
                    "An alternative explanation was retained without an "
                    "ungrounded numerical claim."
                ),
            )
            for item in final.alternative_explanations
        )
        uncertainties = tuple(
            _qualitative(
                item,
                fallback=(
                    "An uncertainty was retained without an ungrounded numerical claim."
                ),
            )
            for item in final.uncertainties
        )
        limitations.extend(final.propagated_limitations)
        limitations.extend(uncertainties)
        action = ActionReportData(
            action_id=final.next_best_action_id,
            description=_qualitative(
                final.action_description,
                fallback="Use the verifier-approved catalog action.",
            ),
            rationale=_qualitative(
                final.rationale,
                fallback="The rationale is grounded by the cited evidence records.",
            ),
            resolved_confidence=final.resolved_confidence,
            confidence_cap_applied=final.confidence_cap_applied,
            confidence_adjustments=tuple(
                ConfidenceAdjustmentReportData(
                    context_classification=item.context_classification,
                    maximum_confidence=item.maximum_confidence,
                    reason=sanitize_public_text(item.reason),
                    evidence_ids=item.evidence_ids,
                )
                for item in final.confidence_adjustments
            ),
            recommended_success_metric=final.recommended_success_metric,
            suggested_experiment=final.suggested_experiment,
            human_review_required=True,
        )
    if outcome.failure_reason:
        limitations.append(sanitize_public_text(outcome.failure_reason))
    limitations.extend(sanitize_public_text(item) for item in state.verification_issues)

    return ReportData(
        provenance=outcome.provenance,
        run_id=str(state.run_id),
        household_id=state.household_id,
        run_status=state.run_status,
        decline=DeclineReportData(
            evidence_id=f"detector_{state.run_id}",
            run_id=str(state.run_id),
            household_id=state.household_id,
            baseline_start_week=snapshot.baseline_start_week,
            baseline_end_week=snapshot.baseline_end_week,
            recent_start_week=snapshot.recent_start_week,
            recent_end_week=snapshot.recent_end_week,
            baseline_retailer_sales_value=snapshot.baseline_retailer_sales_value,
            recent_retailer_sales_value=snapshot.recent_retailer_sales_value,
            baseline_distinct_baskets=snapshot.baseline_distinct_baskets,
            recent_distinct_baskets=snapshot.recent_distinct_baskets,
            baseline_active_weeks=snapshot.baseline_active_weeks,
            recent_active_weeks=snapshot.recent_active_weeks,
            sales_drop=snapshot.sales_drop,
            trip_drop=snapshot.trip_drop,
            active_week_drop=snapshot.active_week_drop,
            decline_score=snapshot.decline_score,
            eligible=snapshot.eligible,
            flagged=snapshot.flagged,
            partial_week_limitation=snapshot.partial_week_limitation,
        ),
        population_context=population_context,
        investigation_path=tuple(path),
        likely_drivers=drivers,
        supporting_evidence=supporting,
        counterevidence=counterevidence,
        evidence_ledger=ledger,
        alternative_explanations=alternatives,
        uncertainties=uncertainties,
        interpretation_limits=build_interpretation_limits(
            tuple(state.evidence_ledger),
            population_context.context_classification,
        ),
        action=action,
        limitations=_deduplicate(limitations),
        tool_warnings=tuple(warnings),
        verification_issues=tuple(
            sanitize_public_text(item) for item in state.verification_issues
        ),
        failure_reason=(
            sanitize_public_text(outcome.failure_reason)
            if outcome.failure_reason
            else None
        ),
    )


def _markdown_escape(value: object) -> str:
    """Escape HTML and Markdown control characters in rendered report text."""

    text = html.escape(str(value), quote=False)
    for character in ("\\", "`", "*", "_", "[", "]", "|"):
        text = text.replace(character, f"\\{character}")
    return text


def _markdown_code(value: object) -> str:
    """Escape backticks without changing the identifier shown in a code span."""

    return str(value).replace("`", "&#96;")


def _format_number(value: float | int | None) -> str:
    """Format an optional numeric value compactly for a human-readable report."""

    if value is None:
        return "not available"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.6g}"


def _format_money(value: float | int | None) -> str:
    """Format an optional retailer sales value as currency."""

    return "not available" if value is None else f"${value:,.2f}"


def _format_percent(value: float | int | None) -> str:
    """Format an optional fractional value as a percentage."""

    return "not available" if value is None else f"{value * 100:,.1f}%"


def _humanize(value: object) -> str:
    """Turn an enum or snake-case value into a display label."""

    return str(getattr(value, "value", value)).replace("_", " ").title()


def _environment(*, autoescape: bool = False, trim_blocks: bool = True) -> Environment:
    """Create the strict Jinja environment and register report-safe filters."""

    environment = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIRECTORY),
        autoescape=autoescape,
        undefined=StrictUndefined,
        trim_blocks=trim_blocks,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    environment.filters.update(
        md=_markdown_escape,
        code=_markdown_code,
        number=_format_number,
        money=_format_money,
        percent=_format_percent,
        humanize=_humanize,
    )
    return environment


def render_report_json(report: ReportData) -> str:
    """Serialize the stable report boundary as deterministic, readable JSON."""

    return f"{json.dumps(report.model_dump(mode='json'), indent=2, sort_keys=True)}\n"


def render_report_markdown(report: ReportData) -> str:
    """Render a portable reviewer-facing Markdown report."""

    rendered = (
        _environment(trim_blocks=False)
        .get_template("report.md.j2")
        .render(report=report)
    )
    return f"{rendered.rstrip()}\n"


def render_report_html(report: ReportData) -> str:
    """Render a self-contained static HTML report safe for local opening."""

    return (
        _environment(autoescape=True)
        .get_template("report.html.j2")
        .render(report=report)
    )


def write_report_bundle(
    outcome: InvestigationOutcome,
    output_directory: Path,
    *,
    stem: str = "report",
) -> ReportBundlePaths:
    """Write matching JSON, Markdown, and HTML files for one investigation."""

    if not stem or Path(stem).name != stem:
        raise ValueError("Report stem must be a non-empty file name")
    output_directory.mkdir(parents=True, exist_ok=True)
    report = build_report_data(outcome)
    paths = ReportBundlePaths(
        json=output_directory / f"{stem}.json",
        markdown=output_directory / f"{stem}.md",
        html=output_directory / f"{stem}.html",
    )
    paths.json.write_text(render_report_json(report), encoding="utf-8")
    paths.markdown.write_text(render_report_markdown(report), encoding="utf-8")
    paths.html.write_text(render_report_html(report), encoding="utf-8")
    return paths
