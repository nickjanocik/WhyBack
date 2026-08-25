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
from whyback.agent.verifier import VerifiedFinalDecision
from whyback.reporting.models import (
    ActionReportData,
    DeclineReportData,
    DriverReportData,
    InvestigationStepData,
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


@dataclass(frozen=True, slots=True)
class ReportBundlePaths:
    """Paths written by :func:`write_report_bundle`."""

    json: Path
    markdown: Path
    html: Path


def _deduplicate(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _qualitative(text: str, *, fallback: str) -> str:
    """Reject ungrounded numeric prose at the final rendering boundary."""

    return fallback if _NUMERICAL_CLAIM.search(text) else text


def _verified_final(outcome: InvestigationOutcome) -> VerifiedFinalDecision | None:
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
    return ReportEvidenceData(
        evidence_id=record.evidence_id,
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
        change=record.change,
        unit=record.unit,
        limitations=record.limitations,
        query_hash=record.query_hash,
    )


def build_report_data(outcome: InvestigationOutcome) -> ReportData:
    """Resolve a run into a stable report boundary without trusting numeric prose."""

    state = outcome.state
    snapshot = state.detector_snapshot
    final = _verified_final(outcome)
    supporting_ids = frozenset(final.supporting_evidence_ids if final else ())
    counterevidence_ids = frozenset(final.counterevidence_ids if final else ())
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
            warnings.append(
                ToolWarningData(
                    tool_name=history.tool_name,
                    final_status=history.final_status,
                    attempt_count=len(attempts),
                    retry_count=retry_count,
                    attempt_statuses=tuple(item.status for item in attempts),
                    total_latency_ms=sum(item.elapsed_ms for item in attempts),
                    limitations=step_limitations,
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
                supporting_evidence_ids=driver.supporting_evidence_ids,
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
            recommended_success_metric=final.recommended_success_metric,
            suggested_experiment=final.suggested_experiment,
            human_review_required=True,
        )
    if outcome.failure_reason:
        limitations.append(outcome.failure_reason)
    limitations.extend(state.verification_issues)

    return ReportData(
        run_id=str(state.run_id),
        household_id=state.household_id,
        run_status=state.run_status,
        decline=DeclineReportData(
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
        investigation_path=tuple(path),
        likely_drivers=drivers,
        supporting_evidence=supporting,
        counterevidence=counterevidence,
        evidence_ledger=ledger,
        alternative_explanations=alternatives,
        uncertainties=uncertainties,
        action=action,
        limitations=_deduplicate(limitations),
        tool_warnings=tuple(warnings),
        verification_issues=state.verification_issues,
        failure_reason=outcome.failure_reason,
    )


def _markdown_escape(value: object) -> str:
    text = html.escape(str(value), quote=False)
    for character in ("\\", "`", "*", "_", "[", "]", "|"):
        text = text.replace(character, f"\\{character}")
    return text


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "not available"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.6g}"


def _format_money(value: float | int | None) -> str:
    return "not available" if value is None else f"${value:,.2f}"


def _format_percent(value: float | int | None) -> str:
    return "not available" if value is None else f"{value * 100:,.1f}%"


def _humanize(value: object) -> str:
    return str(getattr(value, "value", value)).replace("_", " ").title()


def _environment(*, autoescape: bool = False) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIRECTORY),
        autoescape=autoescape,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    environment.filters.update(
        md=_markdown_escape,
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

    return _environment().get_template("report.md.j2").render(report=report)


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
