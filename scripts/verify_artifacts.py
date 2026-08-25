"""Fail-closed verification for reviewer-facing WhyBack artifacts.

The verifier deliberately checks portable files without running an investigation.
It validates strict report and audit schemas, evidence references, execution-mode
labels, and every file digest declared by an artifact manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from whyback.agent.actions import ActionCatalogError, ActionId, load_action_catalog
from whyback.agent.state import ConfidenceLevel
from whyback.agent.verifier import (
    is_relevant_counterevidence,
    is_report_safe_qualitative,
    required_context_counterevidence_ids,
    resolve_confidence_policy,
)
from whyback.data.download import SOURCE_FILES
from whyback.data.manifest import DataManifest, preparation_code_sha256
from whyback.detection.decline import DeclineSnapshot
from whyback.methodology import ClaimType
from whyback.observability import (
    AuditEvent,
    AuditEventName,
    read_audit_events,
    sanitize_public_text,
)
from whyback.reporting import (
    build_interpretation_limits,
    build_population_context,
    render_report_html,
    render_report_markdown,
    render_trace_html,
)
from whyback.reporting.models import (
    DriverReportData,
    InvestigationStepData,
    ReportData,
    ReportEvidenceData,
    ToolWarningData,
)
from whyback.tools.contracts import (
    SUCCESS_STATUSES,
    EvidenceRecord,
    ToolName,
    ToolResult,
    ToolStatus,
)

ExecutionMode = Literal["scripted", "live", "skipped"]
ArtifactIdentity = tuple[str, str]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPORT_NAMES = frozenset({"report.json", "customer_report.json"})
_BRANDING = (
    "WhyBack",
    "Find the why. Choose the way back.",
    "WhyBack Investigator",
)
_TOOL_LABELS = {
    "customer_trend": "Customer trend",
    "category_decomposition": "Category decomposition",
    "basket_behavior": "Basket behavior",
    "promotion_response": "Promotion response",
    "coupon_campaign_history": "Coupon campaign history",
    "peer_comparison": "Behavioral peer comparison",
}
_DRIVER_TEMPLATES = {
    ActionId.CATEGORY_WINBACK: (
        "A recorded mapped category-level loss is a plausible contributor to the "
        "observed engagement decline."
    ),
    ActionId.VISIT_FREQUENCY_REACTIVATION: (
        "Reduced recorded visit cadence is a plausible contributor to the observed "
        "engagement decline."
    ),
    ActionId.PROMOTION_VALUE_REENGAGEMENT: (
        "A decline in recorded promotion-associated or coupon activity is a "
        "plausible contributor to the observed engagement decline."
    ),
    ActionId.PERSONALIZED_CHECK_IN: (
        "Multiple distinct computed behavioral measures support a multifactor "
        "engagement-decline hypothesis."
    ),
    ActionId.MONITOR: (
        "The recorded decline signal supports monitored reassessment while its "
        "underlying reason remains uncertain."
    ),
}
_DESCRIPTIVE_DRIVER_TEMPLATES = {
    ActionId.CATEGORY_WINBACK: (
        "A recorded mapped category-level loss is present in the observed decline."
    ),
    ActionId.VISIT_FREQUENCY_REACTIVATION: (
        "Recorded visit cadence declined during the observed period."
    ),
    ActionId.PROMOTION_VALUE_REENGAGEMENT: (
        "Recorded promotion-associated or coupon activity declined during the "
        "observed period."
    ),
    ActionId.PERSONALIZED_CHECK_IN: (
        "Multiple distinct computed behavioral measures changed during the observed "
        "period."
    ),
    ActionId.MONITOR: (
        "A recorded decline signal is present and warrants monitored reassessment; "
        "its underlying reason remains unknown."
    ),
}
_CLAIM_ORDER = {
    ClaimType.DESCRIPTIVE: 0,
    ClaimType.ASSOCIATIONAL: 1,
    ClaimType.CAUSAL: 2,
}
_VERIFIED_ALTERNATIVES = (
    "Recorded evidence does not distinguish the observed signal from unobserved "
    "activity outside this retailer.",
)
_VERIFIED_UNCERTAINTIES = (
    "Customer intent and activity outside the recorded retailer data are not observed.",
)
_OBSERVATIONAL_DRIVER_LIMITATION = (
    "The observational evidence supports an association, not a causal explanation "
    "of the household's behavior."
)


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    """One stable artifact-verification failure."""

    path: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ArtifactVerificationResult:
    """Complete verification result; callers decide how to render it."""

    root: str
    checked_files: tuple[str, ...]
    execution_modes: tuple[ExecutionMode, ...]
    issues: tuple[VerificationIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    def as_json(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "root": self.root,
            "passed": self.passed,
            "checked_files": list(self.checked_files),
            "execution_modes": list(self.execution_modes),
            "issues": [
                {"path": item.path, "code": item.code, "message": item.message}
                for item in self.issues
            ],
        }


@dataclass(frozen=True, slots=True)
class TraceValidation:
    """Validated trace facts used for cross-artifact reconciliation."""

    mode: ExecutionMode | None
    identity: ArtifactIdentity | None
    events: tuple[AuditEvent, ...]
    tool_results: tuple[ToolResult, ...]
    evidence: tuple[tuple[EvidenceRecord, ToolStatus], ...]
    evidence_added_ids: tuple[str, ...]
    issues: tuple[VerificationIssue, ...]


@dataclass(frozen=True, slots=True)
class ManifestValidation:
    """Validated artifact-manifest metadata and its declared file set."""

    modes: frozenset[ExecutionMode]
    declared_files: frozenset[Path]
    is_artifact_manifest: bool
    data: Mapping[str, object] | None
    issues: tuple[VerificationIssue, ...]


@dataclass(frozen=True, slots=True)
class ProposedDriverTrace:
    """One model-proposed driver reconstructed from a finish audit event."""

    claim_type: ClaimType
    supporting_evidence_ids: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinishRequestTrace:
    """Confidence and evidence accounting from one structured finish request."""

    next_best_action_id: ActionId
    proposed_confidence: ConfidenceLevel
    supporting_evidence_ids: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]
    drivers: tuple[ProposedDriverTrace, ...]


def sha256_file(path: Path) -> str:
    """Hash one file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _issue(path: Path, root: Path, code: str, message: str) -> VerificationIssue:
    return VerificationIssue(_relative(path, root), code, message)


def _load_json(path: Path, root: Path) -> tuple[object | None, list[VerificationIssue]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [
            _issue(path, root, "malformed_json", f"JSON could not be parsed: {error}")
        ]


def _looks_like_report(path: Path, value: object) -> bool:
    if path.name in _REPORT_NAMES or path.name.endswith("_customer_report.json"):
        return True
    return isinstance(value, Mapping) and {
        "product_name",
        "evidence_ledger",
        "human_review_required",
    }.issubset(value)


def _validate_report(
    path: Path, root: Path, value: object
) -> tuple[ReportData | None, list[VerificationIssue]]:
    issues: list[VerificationIssue] = []
    try:
        report = ReportData.model_validate(value)
    except ValidationError as error:
        return None, [
            _issue(
                path,
                root,
                "malformed_report",
                f"Report failed its strict schema: {error}",
            )
        ]

    if (
        report.product_name,
        report.tagline,
        report.investigator_name,
    ) != _BRANDING:
        issues.append(
            _issue(path, root, "branding_mismatch", "WhyBack branding is not exact")
        )
    if report.human_review_required is not True or (
        report.action is not None and report.action.human_review_required is not True
    ):
        issues.append(
            _issue(
                path,
                root,
                "human_review_missing",
                "Reports and actions must explicitly require human review",
            )
        )

    ledger_ids = [item.evidence_id for item in report.evidence_ledger]
    ledger_set = set(ledger_ids)
    if len(ledger_ids) != len(ledger_set):
        issues.append(
            _issue(
                path,
                root,
                "duplicate_evidence_id",
                "The evidence ledger contains duplicate identifiers",
            )
        )

    references: list[tuple[str, str]] = []
    for driver in report.likely_drivers:
        references.extend(
            (evidence_id, "likely driver")
            for evidence_id in driver.supporting_evidence_ids
        )
    for step in report.investigation_path:
        references.extend(
            (evidence_id, "investigation path") for evidence_id in step.evidence_ids
        )
    for role, records in (
        ("supporting evidence", report.supporting_evidence),
        ("counterevidence", report.counterevidence),
    ):
        for record in records:
            references.append((record.evidence_id, role))
            if record.source_status not in SUCCESS_STATUSES:
                issues.append(
                    _issue(
                        path,
                        root,
                        "failed_evidence_reference",
                        f"{record.evidence_id} cites non-success status "
                        f"{record.source_status}",
                    )
                )
    for evidence_id, source in references:
        if evidence_id not in ledger_set:
            issues.append(
                _issue(
                    path,
                    root,
                    "unknown_evidence_reference",
                    f"{source} references {evidence_id!r}, which is not in the ledger",
                )
            )
    return report, issues


def _validate_exact_render(
    path: Path,
    root: Path,
    expected: str,
    *,
    missing_code: str,
    mismatch_code: str,
    label: str,
) -> list[VerificationIssue]:
    if not path.is_file():
        return [_issue(path, root, missing_code, f"The matching {label} is absent")]
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [_issue(path, root, mismatch_code, f"{label} is unreadable: {error}")]
    if actual == expected:
        return []
    return [
        _issue(
            path,
            root,
            mismatch_code,
            f"{label} is not the exact deterministic rerender of its source data",
        )
    ]


def _trace_execution_mode(events: Sequence[AuditEvent]) -> ExecutionMode | None:
    if not events:
        return None
    model = events[0].details.get("model")
    if not isinstance(model, str):
        return None
    return "scripted" if model.startswith("scripted/") else "live"


def _model_execution_for_backend(backend: object, execution_mode: object) -> str | None:
    """Map a manifest mode to current or preserved historical provenance."""

    if execution_mode == "scripted" and backend == "scripted":
        return "scripted_control"
    if execution_mode == "live" and backend == "gemini":
        return "live_gemini"
    if execution_mode == "live" and backend == "openai":
        return "live_openai"
    return None


def _integer_detail(event: AuditEvent, key: str) -> int | None:
    value = event.details.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string_detail(event: AuditEvent, key: str) -> str | None:
    value = event.details.get(key)
    return value if isinstance(value, str) and value else None


def _tool_result_from_event(
    path: Path,
    root: Path,
    event: AuditEvent,
) -> tuple[ToolResult | None, list[VerificationIssue]]:
    raw_result = event.details.get("tool_result")
    if not isinstance(raw_result, Mapping):
        return None, [
            _issue(
                path,
                root,
                "tool_result_missing",
                f"{event.event.value} must contain its complete ToolResult envelope",
            )
        ]
    try:
        result = ToolResult.model_validate(raw_result)
    except ValidationError as error:
        return None, [
            _issue(
                path,
                root,
                "malformed_tool_result",
                f"Embedded ToolResult failed its strict schema: {error}",
            )
        ]

    issues: list[VerificationIssue] = []
    expected_event = {
        ToolStatus.OK: AuditEventName.TOOL_COMPLETED,
        ToolStatus.PARTIAL: AuditEventName.TOOL_PARTIAL,
    }.get(result.status, AuditEventName.TOOL_FAILED)
    comparisons: tuple[tuple[str, object, object], ...] = (
        ("tool_call_id", event.details.get("tool_call_id"), result.tool_call_id),
        ("tool_name", event.details.get("tool_name"), result.tool_name.value),
        ("status", event.details.get("status"), result.status.value),
        ("retryable", event.details.get("retryable"), result.retryable),
        (
            "evidence_ids",
            event.details.get("evidence_ids"),
            [item.evidence_id for item in result.evidence],
        ),
        ("latency_ms", event.details.get("latency_ms"), result.provenance.elapsed_ms),
        (
            "rows_examined",
            event.details.get("rows_examined"),
            result.provenance.rows_examined,
        ),
        ("query_hash", event.details.get("query_hash"), result.provenance.query_hash),
        ("limitations", event.details.get("limitations"), list(result.limitations)),
        (
            "diagnostics",
            event.details.get("diagnostics"),
            dict(result.provenance.diagnostics),
        ),
    )
    if event.event is not expected_event:
        issues.append(
            _issue(
                path,
                root,
                "tool_result_event_mismatch",
                f"Status {result.status.value!r} cannot be emitted as "
                f"{event.event.value!r}",
            )
        )
    for field, outer, embedded in comparisons:
        if outer != embedded:
            issues.append(
                _issue(
                    path,
                    root,
                    "tool_result_event_mismatch",
                    f"Outer event field {field!r} does not match ToolResult",
                )
            )
    return result, issues


def _evidence_added_matches(event: AuditEvent, evidence: EvidenceRecord) -> bool:
    return all(
        (
            event.details.get("evidence_id") == evidence.evidence_id,
            event.details.get("source_tool") == evidence.source_tool.value,
            event.details.get("source_tool_call_id") == evidence.source_tool_call_id,
            event.details.get("metric") == evidence.metric,
            event.details.get("limitations") == list(evidence.limitations),
        )
    )


def _validate_trace(
    path: Path,
    root: Path,
) -> TraceValidation:
    try:
        events = read_audit_events(path)
    except (OSError, ValueError) as error:
        return TraceValidation(
            None,
            None,
            (),
            (),
            (),
            (),
            (
                _issue(
                    path,
                    root,
                    "malformed_trace",
                    f"Trace validation failed: {error}",
                ),
            ),
        )
    if not events:
        return TraceValidation(
            None,
            None,
            (),
            (),
            (),
            (),
            (_issue(path, root, "empty_trace", "Trace has no events"),),
        )

    issues: list[VerificationIssue] = []
    run_ids = {str(event.run_id) for event in events}
    households = {event.household_id for event in events}
    identity: ArtifactIdentity | None = None
    if len(run_ids) != 1 or len(households) != 1:
        issues.append(
            _issue(
                path,
                root,
                "mixed_trace_identity",
                "One trace must contain exactly one run and household",
            )
        )
    else:
        identity = (next(iter(run_ids)), next(iter(households)))

    starts = [event for event in events if event.event is AuditEventName.RUN_STARTED]
    completions = [
        event for event in events if event.event is AuditEventName.RUN_COMPLETED
    ]
    if len(starts) != 1 or events[0].event is not AuditEventName.RUN_STARTED:
        issues.append(
            _issue(
                path,
                root,
                "trace_start_missing",
                "Trace must contain exactly one run_started event in first position",
            )
        )
    if len(completions) != 1 or events[-1].event is not AuditEventName.RUN_COMPLETED:
        issues.append(
            _issue(
                path,
                root,
                "trace_completion_missing",
                "Trace must contain exactly one run_completed event in last position",
            )
        )
    if any(
        current.timestamp < previous.timestamp for previous, current in pairwise(events)
    ):
        issues.append(
            _issue(
                path,
                root,
                "trace_time_reversal",
                "Trace timestamps are not monotonically nondecreasing",
            )
        )

    initial_tool_budget = _integer_detail(events[0], "remaining_tool_budget")
    initial_turn_budget = _integer_detail(events[0], "remaining_turn_budget")
    if initial_tool_budget is None or initial_tool_budget < 1:
        issues.append(
            _issue(
                path,
                root,
                "trace_budget_invalid",
                "run_started must record a positive remaining_tool_budget",
            )
        )
    if initial_turn_budget is None or initial_turn_budget < 1:
        issues.append(
            _issue(
                path,
                root,
                "trace_budget_invalid",
                "run_started must record a positive remaining_turn_budget",
            )
        )
    required_start_strings = (
        "model",
        "prompt_version",
        "prompt_hash",
        "dataset_kind",
        "dataset_source_repository",
        "dataset_source_commit",
        "application_version",
        "timing_mode",
    )
    missing_start = [
        key
        for key in required_start_strings
        if _string_detail(events[0], key) in {None, "unspecified"}
    ]
    if (
        missing_start
        or events[0].details.get("dataset_kind")
        not in {"synthetic", "official_complete_journey"}
        or _SHA256.fullmatch(str(events[0].details.get("prompt_hash", ""))) is None
        or events[0].details.get("timing_mode") != "actual_utc_and_monotonic"
    ):
        issues.append(
            _issue(
                path,
                root,
                "run_provenance_incomplete",
                "run_started must record known data, model, application, prompt, "
                "and timing provenance",
            )
        )
    raw_detector_snapshot = events[0].details.get("detector_snapshot")
    detector_snapshot: DeclineSnapshot | None = None
    try:
        detector_snapshot = DeclineSnapshot.model_validate(raw_detector_snapshot)
    except ValidationError:
        issues.append(
            _issue(
                path,
                root,
                "detector_snapshot_missing",
                "run_started must record a complete typed detector snapshot",
            )
        )
    decline_score = events[0].details.get("decline_score")
    if detector_snapshot is not None and (
        detector_snapshot.household_id != events[0].household_id
        or decline_score != detector_snapshot.decline_score
    ):
        issues.append(
            _issue(
                path,
                root,
                "detector_snapshot_identity_mismatch",
                "The detector snapshot owner and decline score must match run_started",
            )
        )
    remaining_tools = initial_tool_budget or 0
    remaining_turns = initial_turn_budget or 0
    model_request_pending = False
    expected_followup: AuditEventName | None = None
    pending_tool: str | None = None
    active_call: tuple[str, str, int] | None = None
    previous_retry_call_id: str | None = None
    expected_evidence: list[EvidenceRecord] = []
    evidence_added_ids: list[str] = []
    reconstructed: list[tuple[EvidenceRecord, ToolStatus]] = []
    tool_results: list[ToolResult] = []
    tool_call_ids: set[str] = set()
    received_decisions = 0
    started_attempts = 0
    retry_count = 0
    verification_pending = False
    verification_passed = False
    last_verdict: AuditEvent | None = None
    finish_decision_pending = False
    finish_request_pending = False
    verification_is_fallback = False

    for index, event in enumerate(events[1:-1], start=2):
        name = event.event
        public_model_fields = (
            ("investigation_question", "decision_summary")
            if name is AuditEventName.MODEL_DECISION_RECEIVED
            else (
                ("investigation_question",)
                if name is AuditEventName.TOOL_REQUESTED
                else ()
            )
        )
        for field in public_model_fields:
            value = event.details.get(field)
            if value is not None and (
                not isinstance(value, str)
                or not is_report_safe_qualitative(sanitize_public_text(value))
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "unsafe_trace_prose",
                        f"Trace event {index} contains unsafe public model prose in "
                        f"{field!r}",
                    )
                )
        if expected_evidence and name is not AuditEventName.EVIDENCE_ADDED:
            issues.append(
                _issue(
                    path,
                    root,
                    "trace_evidence_lifecycle_invalid",
                    "Successful evidence was not followed by one evidence_added "
                    "event per record",
                )
            )
            expected_evidence.clear()

        duplicate_refusal = (
            name is AuditEventName.TOOL_FAILED
            and event.details.get("duplicate_refused") is True
        )
        if (
            expected_followup is not None
            and name is not expected_followup
            and not (
                expected_followup is AuditEventName.TOOL_STARTED and duplicate_refusal
            )
        ):
            issues.append(
                _issue(
                    path,
                    root,
                    "trace_lifecycle_invalid",
                    f"Event {index} is {name.value!r}; expected "
                    f"{expected_followup.value!r}",
                )
            )
        if expected_followup is not None:
            expected_followup = None
        if active_call is not None and name not in {
            AuditEventName.TOOL_COMPLETED,
            AuditEventName.TOOL_PARTIAL,
            AuditEventName.TOOL_FAILED,
        }:
            issues.append(
                _issue(
                    path,
                    root,
                    "trace_lifecycle_invalid",
                    f"Tool call {active_call[0]!r} has no immediate terminal event",
                )
            )

        if name is AuditEventName.RUN_STARTED or name is AuditEventName.RUN_COMPLETED:
            continue
        if name is AuditEventName.MODEL_DECISION_REQUESTED:
            if (
                model_request_pending
                or pending_tool is not None
                or active_call is not None
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "A model decision was requested while prior work was pending",
                    )
                )
            if (
                _integer_detail(event, "remaining_tool_budget") != remaining_tools
                or _integer_detail(event, "remaining_turn_budget") != remaining_turns
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_budget_invalid",
                        "Model request budgets do not reconcile with prior events",
                    )
                )
            model_request_pending = True
            expected_followup = AuditEventName.MODEL_DECISION_RECEIVED
            continue
        if name is AuditEventName.MODEL_DECISION_RECEIVED:
            if not model_request_pending or remaining_turns < 1:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "A model decision was received without an available request",
                    )
                )
            else:
                remaining_turns -= 1
            model_request_pending = False
            received_decisions += 1
            decision_kind = _string_detail(event, "decision_kind")
            if decision_kind == "tool":
                finish_decision_pending = False
                pending_tool = _string_detail(event, "selected_tool")
                if pending_tool is None:
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_lifecycle_invalid",
                            "A tool decision must select one tool",
                        )
                    )
                expected_followup = AuditEventName.TOOL_REQUESTED
            elif decision_kind == "finish":
                finish_decision_pending = True
                expected_followup = AuditEventName.FINISH_REQUESTED
            else:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "Model decisions must be typed as tool or finish",
                    )
                )
            continue
        if name is AuditEventName.TOOL_REQUESTED:
            tool_name = _string_detail(event, "tool_name")
            if pending_tool is None or tool_name != pending_tool:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "tool_requested does not match its model decision",
                    )
                )
            expected_followup = AuditEventName.TOOL_STARTED
            continue
        if name is AuditEventName.TOOL_STARTED:
            call_id = _string_detail(event, "tool_call_id")
            tool_name = _string_detail(event, "tool_name")
            attempt = _integer_detail(event, "attempt")
            expected_attempt = 2 if previous_retry_call_id is not None else 1
            if (
                pending_tool is None
                or tool_name != pending_tool
                or call_id is None
                or attempt != expected_attempt
                or active_call is not None
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_attempt_invalid",
                        "Tool attempts must start at one and only retry once as two",
                    )
                )
            if call_id is not None:
                if call_id in tool_call_ids:
                    issues.append(
                        _issue(
                            path,
                            root,
                            "duplicate_tool_call_id",
                            f"Tool call ID {call_id!r} was reused",
                        )
                    )
                tool_call_ids.add(call_id)
            if (
                remaining_tools < 1
                or _integer_detail(event, "remaining_tool_budget") != remaining_tools
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_budget_invalid",
                        "Tool-start budget does not reconcile with prior attempts",
                    )
                )
            active_call = (call_id or "", tool_name or "", attempt or 0)
            previous_retry_call_id = None
            started_attempts += 1
            continue
        if name in {
            AuditEventName.TOOL_COMPLETED,
            AuditEventName.TOOL_PARTIAL,
            AuditEventName.TOOL_FAILED,
        }:
            if duplicate_refusal:
                if pending_tool != _string_detail(event, "tool_name"):
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_lifecycle_invalid",
                            "Duplicate refusal does not match its tool request",
                        )
                    )
                if event.details.get("status") != ToolStatus.INVALID_REQUEST.value:
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_lifecycle_invalid",
                            "Duplicate refusals must have invalid_request status",
                        )
                    )
                pending_tool = None
                continue

            result, result_issues = _tool_result_from_event(path, root, event)
            issues.extend(result_issues)
            call_id = _string_detail(event, "tool_call_id")
            tool_name = _string_detail(event, "tool_name")
            attempt = _integer_detail(event, "attempt")
            if active_call != (call_id or "", tool_name or "", attempt or 0):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_attempt_invalid",
                        "Tool terminal event does not match its started attempt",
                    )
                )
            active_call = None
            if remaining_tools > 0:
                remaining_tools -= 1
            if result is None:
                pending_tool = None
                continue
            tool_results.append(result)
            for evidence in result.evidence:
                if (
                    identity is not None
                    and (str(evidence.run_id), evidence.household_id) != identity
                ):
                    issues.append(
                        _issue(
                            path,
                            root,
                            "tool_result_owner_mismatch",
                            f"Evidence {evidence.evidence_id!r} belongs to another run",
                        )
                    )
            if result.status in SUCCESS_STATUSES:
                reconstructed.extend((item, result.status) for item in result.evidence)
                expected_evidence.extend(result.evidence)
            will_retry = result.retryable and attempt == 1 and remaining_tools > 0
            if will_retry:
                previous_retry_call_id = result.tool_call_id
                expected_followup = AuditEventName.RETRY_SCHEDULED
            else:
                if result.retryable and attempt not in {1, 2}:
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_retry_invalid",
                            "Retryable terminal event has an invalid attempt number",
                        )
                    )
                pending_tool = None
                previous_retry_call_id = None
            continue
        if name is AuditEventName.RETRY_SCHEDULED:
            retry_count += 1
            if (
                previous_retry_call_id is None
                or _string_detail(event, "after_tool_call_id") != previous_retry_call_id
                or _integer_detail(event, "next_attempt") != 2
                or _string_detail(event, "tool_name") != pending_tool
                or _integer_detail(event, "remaining_tool_budget") != remaining_tools
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_retry_invalid",
                        "Retry event does not reconcile with the retryable first "
                        "attempt",
                    )
                )
            expected_followup = AuditEventName.TOOL_STARTED
            continue
        if name is AuditEventName.EVIDENCE_ADDED:
            evidence_id = _string_detail(event, "evidence_id")
            if not expected_evidence:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_evidence_lifecycle_invalid",
                        "evidence_added has no successful ToolResult record",
                    )
                )
            else:
                expected = expected_evidence.pop(0)
                if not _evidence_added_matches(event, expected):
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_evidence_lifecycle_invalid",
                            "evidence_added does not exactly match its ToolResult "
                            "record",
                        )
                    )
            if evidence_id is not None:
                evidence_added_ids.append(evidence_id)
            continue
        if name is AuditEventName.FINISH_REQUESTED:
            if not finish_decision_pending:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "finish_requested has no matching finish model decision",
                    )
                )
            finish_decision_pending = False
            finish_request_pending = True
            expected_followup = AuditEventName.VERIFICATION_STARTED
            continue
        if name is AuditEventName.VERIFICATION_STARTED:
            if verification_pending:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "Verification was started before the prior verdict",
                    )
                )
            is_fallback = event.details.get("deterministic_fallback") is True
            if not finish_request_pending and not is_fallback:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "Verification must follow finish_requested or identify the "
                        "deterministic fallback",
                    )
                )
            finish_request_pending = False
            verification_is_fallback = is_fallback
            verification_pending = True
            continue
        if name in {
            AuditEventName.VERIFICATION_PASSED,
            AuditEventName.VERIFICATION_REJECTED,
        }:
            if not verification_pending:
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "Verification verdict has no matching start event",
                    )
                )
            verification_pending = False
            verification_passed = name is AuditEventName.VERIFICATION_PASSED
            last_verdict = event
            if verification_is_fallback != (
                event.details.get("deterministic_fallback") is True
            ):
                issues.append(
                    _issue(
                        path,
                        root,
                        "trace_lifecycle_invalid",
                        "Fallback identity must be preserved through its verdict",
                    )
                )
            if verification_passed:
                supporting = event.details.get("supporting_evidence_ids")
                counter = event.details.get("counterevidence_ids")
                if (
                    not isinstance(supporting, list)
                    or any(not isinstance(item, str) for item in supporting)
                    or len(supporting) != len(set(supporting))
                    or not isinstance(counter, list)
                    or any(not isinstance(item, str) for item in counter)
                    or len(counter) != len(set(counter))
                    or bool(set(supporting) & set(counter))
                    or _string_detail(event, "next_best_action_id") is None
                    or _string_detail(event, "resolved_confidence")
                    not in {"insufficient", "low", "medium", "high"}
                    or not isinstance(event.details.get("confidence_cap_applied"), bool)
                ):
                    issues.append(
                        _issue(
                            path,
                            root,
                            "verification_verdict_invalid",
                            "Passing verification must record resolved evidence, "
                            "action, confidence, and confidence-cap fields",
                        )
                    )
                expected_followup = AuditEventName.RUN_COMPLETED
            continue

    completion = events[-1]
    completion_status = _string_detail(completion, "status")
    if expected_followup is not None and not (
        expected_followup is AuditEventName.RUN_COMPLETED
        or (
            expected_followup is AuditEventName.MODEL_DECISION_RECEIVED
            and completion_status == "failed"
        )
    ):
        issues.append(
            _issue(
                path,
                root,
                "trace_lifecycle_invalid",
                f"Trace completed while awaiting {expected_followup.value!r}",
            )
        )
    if completion_status not in {"completed", "insufficient_evidence", "failed"}:
        issues.append(
            _issue(
                path,
                root,
                "trace_completion_invalid",
                "run_completed must record a terminal status",
            )
        )
    if expected_evidence:
        issues.append(
            _issue(
                path,
                root,
                "trace_evidence_lifecycle_invalid",
                "Trace ended before all successful evidence was added",
            )
        )
    if (
        active_call is not None
        or pending_tool is not None
        or verification_pending
        or finish_decision_pending
        or finish_request_pending
    ):
        issues.append(
            _issue(
                path,
                root,
                "trace_lifecycle_invalid",
                "Trace completed with analytical or verification work pending",
            )
        )
    if model_request_pending and completion_status != "failed":
        issues.append(
            _issue(
                path,
                root,
                "trace_lifecycle_invalid",
                "Only a failed run may end after an unanswered model request",
            )
        )
    if completion_status in {"completed", "insufficient_evidence"} and (
        last_verdict is None
        or last_verdict.event is not AuditEventName.VERIFICATION_PASSED
    ):
        issues.append(
            _issue(
                path,
                root,
                "trace_terminal_verdict_mismatch",
                "Completed and insufficient-evidence runs require a final passing "
                "verification verdict",
            )
        )
    if completion_status == "failed" and verification_passed:
        issues.append(
            _issue(
                path,
                root,
                "trace_terminal_verdict_mismatch",
                "A failed run cannot follow a passing verification verdict",
            )
        )
    if (
        last_verdict is not None
        and last_verdict.event is AuditEventName.VERIFICATION_PASSED
    ):
        verdict_action = last_verdict.details.get("next_best_action_id")
        completion_action = completion.details.get("next_best_action_id")
        if (
            verdict_action != completion_action
            or completion.details.get("human_review_required") is not True
            or (
                completion_status == "insufficient_evidence"
                and completion_action != "INSUFFICIENT_EVIDENCE"
            )
            or (
                completion_status == "completed"
                and completion_action in {None, "INSUFFICIENT_EVIDENCE"}
            )
        ):
            issues.append(
                _issue(
                    path,
                    root,
                    "trace_terminal_verdict_mismatch",
                    "run_completed does not preserve the passing verifier action",
                )
            )
        if last_verdict.details.get("deterministic_fallback") is True and (
            completion_status != "insufficient_evidence"
            or completion_action != "INSUFFICIENT_EVIDENCE"
            or not isinstance(completion.details.get("fallback_reason"), str)
        ):
            issues.append(
                _issue(
                    path,
                    root,
                    "trace_terminal_verdict_mismatch",
                    "Deterministic fallback must preserve its status, action, and "
                    "reason through completion",
                )
            )
    if initial_tool_budget is not None and started_attempts > initial_tool_budget:
        issues.append(
            _issue(path, root, "trace_budget_invalid", "Tool budget was exceeded")
        )
    if initial_turn_budget is not None and received_decisions > initial_turn_budget:
        issues.append(
            _issue(path, root, "trace_budget_invalid", "Turn budget was exceeded")
        )
    if retry_count > started_attempts // 2 + started_attempts % 2:
        issues.append(
            _issue(
                path,
                root,
                "trace_retry_invalid",
                "Trace contains more retry events than bounded attempt groups",
            )
        )

    evidence_ids = [item.evidence_id for item, _ in reconstructed]
    if len(evidence_ids) != len(set(evidence_ids)):
        issues.append(
            _issue(
                path,
                root,
                "duplicate_trace_evidence_id",
                "Successful ToolResult envelopes reuse an evidence identifier",
            )
        )
    if evidence_ids != evidence_added_ids:
        issues.append(
            _issue(
                path,
                root,
                "trace_evidence_lifecycle_invalid",
                "evidence_added events do not exactly reproduce ToolResult evidence",
            )
        )

    mode = _trace_execution_mode(events)
    if mode is None:
        issues.append(
            _issue(
                path,
                root,
                "trace_model_missing",
                "run_started must identify the scripted or live model",
            )
        )
    if mode == "live":
        model = events[0].details.get("model")
        provider_ids = [
            event.details.get("provider_call_id")
            for event in events
            if event.event is AuditEventName.MODEL_DECISION_RECEIVED
        ]
        if (
            not isinstance(model, str)
            or model.startswith("scripted/")
            or not provider_ids
            or any(
                not isinstance(value, str) or not value.strip()
                for value in provider_ids
            )
        ):
            issues.append(
                _issue(
                    path,
                    root,
                    "unsubstantiated_live_trace",
                    "A live trace needs non-scripted provider call identifiers",
                )
            )
    return TraceValidation(
        mode=mode,
        identity=identity,
        events=events,
        tool_results=tuple(tool_results),
        evidence=tuple(reconstructed),
        evidence_added_ids=tuple(evidence_added_ids),
        issues=tuple(issues),
    )


def _mode(value: object) -> ExecutionMode | None:
    return (
        cast(ExecutionMode, value) if value in {"scripted", "live", "skipped"} else None
    )


def _manifest_records(value: Mapping[str, object]) -> object | None:
    if "artifacts" in value:
        return value["artifacts"]
    if "files" in value:
        return value["files"]
    return None


def _safe_manifest_path(root: Path, manifest: Path, relative: str) -> Path | None:
    candidate = (manifest.parent / relative).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        return None
    return candidate


def _validate_hash_record(
    manifest: Path,
    root: Path,
    relative_path: object,
    expected_hash: object,
) -> list[VerificationIssue]:
    if not isinstance(relative_path, str) or not relative_path:
        return [
            _issue(
                manifest,
                root,
                "malformed_manifest",
                "A file record has no non-empty relative path",
            )
        ]
    if not isinstance(expected_hash, str) or _SHA256.fullmatch(expected_hash) is None:
        return [
            _issue(
                manifest,
                root,
                "malformed_manifest",
                f"File {relative_path!r} has no lowercase SHA-256 digest",
            )
        ]
    target = _safe_manifest_path(root, manifest, relative_path)
    if target is None:
        return [
            _issue(
                manifest,
                root,
                "unsafe_manifest_path",
                f"File path {relative_path!r} escapes the artifact root",
            )
        ]
    if not target.is_file():
        return [
            _issue(
                manifest,
                root,
                "missing_manifest_file",
                f"Declared file {relative_path!r} is absent",
            )
        ]
    actual = sha256_file(target)
    if actual != expected_hash:
        return [
            _issue(
                manifest,
                root,
                "file_hash_mismatch",
                f"Declared file {relative_path!r} hashes to {actual}, "
                f"not {expected_hash}",
            )
        ]
    return []


def _validate_manifest(path: Path, root: Path, value: object) -> ManifestValidation:
    if not isinstance(value, Mapping):
        return ManifestValidation(
            frozenset(),
            frozenset(),
            False,
            None,
            (
                _issue(
                    path,
                    root,
                    "malformed_manifest",
                    "Manifest root must be an object",
                ),
            ),
        )
    data = cast(Mapping[str, object], value)
    modes: set[ExecutionMode] = set()
    issues: list[VerificationIssue] = []
    declared_files: set[Path] = set()
    root_mode = _mode(data.get("execution_mode"))
    if "execution_mode" in data and root_mode is None:
        issues.append(
            _issue(
                path,
                root,
                "malformed_execution_mode",
                "execution_mode must be scripted, live, or skipped",
            )
        )
    if root_mode is not None:
        modes.add(root_mode)
        if root_mode == "skipped" and not isinstance(data.get("reason"), str):
            issues.append(
                _issue(
                    path,
                    root,
                    "skip_reason_missing",
                    "A skipped execution must record a reason",
                )
            )

    records = _manifest_records(data)
    is_data_manifest = {"source_commit", "sources", "prepared"}.issubset(data)
    is_status = isinstance(data.get("status"), str)
    if records is None and not is_data_manifest and not is_status:
        issues.append(
            _issue(
                path,
                root,
                "malformed_manifest",
                "Manifest has no recognized artifact, data, or status records",
            )
        )
        return ManifestValidation(
            frozenset(modes),
            frozenset(),
            False,
            data,
            tuple(issues),
        )

    if isinstance(records, Mapping):
        for relative_path, expected_hash in records.items():
            issues.extend(
                _validate_hash_record(path, root, relative_path, expected_hash)
            )
            if isinstance(relative_path, str):
                target = _safe_manifest_path(root, path, relative_path)
                if target is not None:
                    declared_files.add(target)
    elif isinstance(records, list):
        for index, raw_record in enumerate(records):
            if not isinstance(raw_record, Mapping):
                issues.append(
                    _issue(
                        path,
                        root,
                        "malformed_manifest",
                        f"Artifact record {index} is not an object",
                    )
                )
                continue
            record = cast(Mapping[str, object], raw_record)
            record_mode = _mode(record.get("execution_mode"))
            if "execution_mode" in record and record_mode is None:
                issues.append(
                    _issue(
                        path,
                        root,
                        "malformed_execution_mode",
                        f"Artifact record {index} has an invalid execution mode",
                    )
                )
            if record_mode is not None:
                modes.add(record_mode)
            relative_path = record.get("path") or record.get("filename")
            issues.extend(
                _validate_hash_record(
                    path,
                    root,
                    relative_path,
                    record.get("sha256"),
                )
            )
            if isinstance(relative_path, str):
                target = _safe_manifest_path(root, path, relative_path)
                if target is not None:
                    if target in declared_files:
                        issues.append(
                            _issue(
                                path,
                                root,
                                "duplicate_manifest_file",
                                f"Manifest declares {relative_path!r} more than once",
                            )
                        )
                    declared_files.add(target)
    elif records is not None:
        issues.append(
            _issue(
                path,
                root,
                "malformed_manifest",
                "Artifact files must be an object or a list of records",
            )
        )

    if not is_data_manifest and (records is not None or is_status) and not modes:
        issues.append(
            _issue(
                path,
                root,
                "execution_mode_missing",
                "Artifact and status manifests must label scripted, live, or skipped",
            )
        )

    if is_data_manifest:
        for group in (data.get("sources"), data.get("prepared")):
            if not isinstance(group, list):
                issues.append(
                    _issue(
                        path,
                        root,
                        "malformed_manifest",
                        "Data manifest source and prepared groups must be lists",
                    )
                )
                break
            for entry in group:
                if (
                    not isinstance(entry, Mapping)
                    or _SHA256.fullmatch(str(entry.get("sha256", ""))) is None
                ):
                    issues.append(
                        _issue(
                            path,
                            root,
                            "malformed_manifest",
                            "Data manifest entries must include lowercase "
                            "SHA-256 digests",
                        )
                    )
                    break
    is_artifact_manifest = records is not None and not is_data_manifest
    if is_artifact_manifest:
        expected_files = {
            candidate.resolve()
            for candidate in path.parent.rglob("*")
            if candidate.is_file()
            and not candidate.is_symlink()
            and candidate.resolve() != path.resolve()
        }
        for missing in sorted(
            expected_files - declared_files,
            key=lambda item: _relative(item, root),
        ):
            issues.append(
                _issue(
                    missing,
                    root,
                    "unhashed_artifact_file",
                    "Artifact file is not covered by its containing manifest",
                )
            )
        if path.resolve() in declared_files:
            issues.append(
                _issue(
                    path,
                    root,
                    "manifest_self_reference",
                    "An artifact manifest cannot hash itself",
                )
            )

    return ManifestValidation(
        modes=frozenset(modes),
        declared_files=frozenset(declared_files),
        is_artifact_manifest=is_artifact_manifest,
        data=data,
        issues=tuple(issues),
    )


def _accepted_evidence_ids(
    events: Sequence[AuditEvent],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    for event in reversed(events):
        if event.event is not AuditEventName.VERIFICATION_PASSED:
            continue

        def identifiers(raw: object) -> tuple[str, ...]:
            if not isinstance(raw, list):
                return ()
            return tuple(item for item in raw if isinstance(item, str))

        return identifiers(event.details.get("supporting_evidence_ids")), identifiers(
            event.details.get("counterevidence_ids")
        )
    return (), ()


def _finish_request(events: Sequence[AuditEvent]) -> FinishRequestTrace | None:
    """Recover typed confidence and evidence accounting from the last finish."""

    for event in reversed(events):
        if event.event is not AuditEventName.FINISH_REQUESTED:
            continue
        try:
            action_id = ActionId(event.details.get("next_best_action_id"))
            proposed_confidence = ConfidenceLevel(
                event.details.get("proposed_confidence")
            )
        except (TypeError, ValueError):
            return None
        raw_proposal_support = event.details.get("supporting_evidence_ids")
        raw_proposal_counter = event.details.get("counterevidence_ids")
        raw_claim_types = event.details.get("driver_claim_types")
        raw_supporting = event.details.get("driver_supporting_evidence_ids")
        raw_counterevidence = event.details.get("driver_counterevidence_ids")
        if not all(
            isinstance(item, list)
            for item in (
                raw_proposal_support,
                raw_proposal_counter,
                raw_claim_types,
                raw_supporting,
                raw_counterevidence,
            )
        ):
            return None
        assert isinstance(raw_proposal_support, list)
        assert isinstance(raw_proposal_counter, list)
        assert isinstance(raw_claim_types, list)
        assert isinstance(raw_supporting, list)
        assert isinstance(raw_counterevidence, list)
        if any(
            not isinstance(item, str)
            for item in (*raw_proposal_support, *raw_proposal_counter)
        ):
            return None
        proposal_support = tuple(cast(str, item) for item in raw_proposal_support)
        proposal_counter = tuple(cast(str, item) for item in raw_proposal_counter)
        if (
            len(proposal_support) != len(set(proposal_support))
            or len(proposal_counter) != len(set(proposal_counter))
            or set(proposal_support).intersection(proposal_counter)
        ):
            return None
        if not (
            len(raw_claim_types) == len(raw_supporting) == len(raw_counterevidence)
        ):
            return None
        drivers: list[ProposedDriverTrace] = []
        for raw_claim_type, support, counters in zip(
            raw_claim_types,
            raw_supporting,
            raw_counterevidence,
            strict=True,
        ):
            try:
                claim_type = ClaimType(raw_claim_type)
            except (TypeError, ValueError):
                return None
            if (
                not isinstance(support, list)
                or not isinstance(counters, list)
                or any(not isinstance(item, str) for item in (*support, *counters))
            ):
                return None
            drivers.append(
                ProposedDriverTrace(
                    claim_type=claim_type,
                    supporting_evidence_ids=tuple(cast(str, item) for item in support),
                    counterevidence_ids=tuple(cast(str, item) for item in counters),
                )
            )
        if any(
            len(driver.supporting_evidence_ids)
            != len(set(driver.supporting_evidence_ids))
            or len(driver.counterevidence_ids) != len(set(driver.counterevidence_ids))
            or set(driver.supporting_evidence_ids).intersection(
                driver.counterevidence_ids
            )
            or not set(driver.supporting_evidence_ids).issubset(proposal_support)
            or not set(driver.counterevidence_ids).issubset(proposal_counter)
            for driver in drivers
        ):
            return None
        if {
            evidence_id
            for driver in drivers
            for evidence_id in driver.supporting_evidence_ids
        } != set(proposal_support) or {
            evidence_id
            for driver in drivers
            for evidence_id in driver.counterevidence_ids
        } != set(proposal_counter):
            return None
        return FinishRequestTrace(
            next_best_action_id=action_id,
            proposed_confidence=proposed_confidence,
            supporting_evidence_ids=proposal_support,
            counterevidence_ids=proposal_counter,
            drivers=tuple(drivers),
        )
    return None


def _deduplicate_public_text(values: Sequence[str]) -> tuple[str, ...]:
    """Return report-rendered text in deterministic first-seen order."""

    return tuple(
        dict.fromkeys(sanitize_public_text(value) for value in values if value)
    )


def _verification_issue_strings(event: AuditEvent) -> tuple[str, ...]:
    """Recover the public issue strings emitted by one verifier rejection."""

    raw_issues = event.details.get("issues")
    if not isinstance(raw_issues, list):
        return ()
    issues: list[str] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, Mapping):
            continue
        code = raw_issue.get("code")
        message = raw_issue.get("message")
        if isinstance(code, str) and isinstance(message, str):
            issues.append(f"{code}: {message}")
    return tuple(issues)


def _terminal_trace_reason(events: Sequence[AuditEvent]) -> str | None:
    if not events:
        return None
    completion = events[-1]
    raw_reason = completion.details.get("fallback_reason")
    if raw_reason is None:
        raw_reason = completion.details.get("message")
    return raw_reason if isinstance(raw_reason, str) else None


def _expected_report_verification_issues(
    events: Sequence[AuditEvent],
) -> tuple[str, ...]:
    """Reconstruct terminal state.verification_issues from lifecycle events."""

    if not events:
        return ()
    completion_status = events[-1].details.get("status")
    fallback_started = any(
        event.event is AuditEventName.VERIFICATION_STARTED
        and event.details.get("deterministic_fallback") is True
        for event in events
    )
    if not fallback_started:
        # An ordinary pass clears earlier repair issues. A direct backend failure
        # replaces them with only its public terminal error.
        reason = _terminal_trace_reason(events)
        return (reason,) if completion_status == "failed" and reason is not None else ()

    ordinary_rejections = tuple(
        issue
        for event in events
        if event.event is AuditEventName.VERIFICATION_REJECTED
        and event.details.get("deterministic_fallback") is not True
        for issue in _verification_issue_strings(event)
    )
    fallback_rejections = tuple(
        issue
        for event in events
        if event.event is AuditEventName.VERIFICATION_REJECTED
        and event.details.get("deterministic_fallback") is True
        for issue in _verification_issue_strings(event)
    )
    reason = _terminal_trace_reason(events)
    return _deduplicate_public_text(
        (
            *ordinary_rejections,
            *((reason,) if reason is not None else ()),
            *fallback_rejections,
        )
    )


def _expected_report_evidence(
    record: EvidenceRecord,
    status: ToolStatus,
    *,
    supporting_ids: frozenset[str],
    counterevidence_ids: frozenset[str],
) -> ReportEvidenceData:
    role = (
        "supporting"
        if record.evidence_id in supporting_ids
        else (
            "counterevidence"
            if record.evidence_id in counterevidence_ids
            else "context"
        )
    )
    return ReportEvidenceData.model_validate(
        {
            **record.model_dump(mode="json"),
            "role": role,
            "source_status": status.value,
        }
    )


def _expected_investigation_records(
    events: Sequence[AuditEvent],
) -> tuple[tuple[InvestigationStepData, ...], tuple[ToolWarningData, ...]]:
    steps: list[InvestigationStepData] = []
    warnings: list[ToolWarningData] = []
    decision_number = 0
    for index, event in enumerate(events):
        if event.event is AuditEventName.MODEL_DECISION_RECEIVED:
            decision_number += 1
            continue
        if event.event is not AuditEventName.TOOL_REQUESTED:
            continue
        tool_name = _string_detail(event, "tool_name")
        question = _string_detail(event, "investigation_question")
        if tool_name not in _TOOL_LABELS or question is None:
            continue
        safe_question = sanitize_public_text(question)
        if not is_report_safe_qualitative(safe_question):
            safe_question = f"Investigate {_TOOL_LABELS[tool_name].lower()}."
        end = next(
            (
                offset
                for offset in range(index + 1, len(events))
                if events[offset].event
                in {
                    AuditEventName.MODEL_DECISION_REQUESTED,
                    AuditEventName.RUN_COMPLETED,
                }
            ),
            len(events),
        )
        segment = events[index + 1 : end]
        results: list[ToolResult] = []
        duplicate_refusal: AuditEvent | None = None
        for candidate in segment:
            if candidate.event not in {
                AuditEventName.TOOL_COMPLETED,
                AuditEventName.TOOL_PARTIAL,
                AuditEventName.TOOL_FAILED,
            }:
                continue
            if candidate.details.get("duplicate_refused") is True:
                duplicate_refusal = candidate
                continue
            raw = candidate.details.get("tool_result")
            if not isinstance(raw, Mapping):
                continue
            try:
                results.append(ToolResult.model_validate(raw))
            except ValidationError:
                continue

        attempt_count = sum(
            candidate.event is AuditEventName.TOOL_STARTED for candidate in segment
        )
        retry_count = sum(
            candidate.event is AuditEventName.RETRY_SCHEDULED for candidate in segment
        )
        if results:
            final_status = results[-1].status
            evidence_ids = tuple(item.evidence_id for item in results[-1].evidence)
            limitations = tuple(
                dict.fromkeys(
                    (
                        *results[-1].limitations,
                        *(item for result in results for item in result.limitations),
                    )
                )
            )
            statuses = tuple(result.status for result in results)
            total_latency = sum(result.provenance.elapsed_ms for result in results)
            unavailable = final_status not in SUCCESS_STATUSES
        elif duplicate_refusal is not None:
            final_status = ToolStatus.INVALID_REQUEST
            evidence_ids = ()
            raw_limitations = duplicate_refusal.details.get("limitations")
            limitations = (
                tuple(item for item in raw_limitations if isinstance(item, str))
                if isinstance(raw_limitations, list)
                else ()
            )
            statuses = ()
            total_latency = 0.0
            unavailable = False
        else:
            continue
        normalized_tool = ToolName(tool_name)
        step = InvestigationStepData(
            decision_number=decision_number,
            tool_name=normalized_tool,
            tool_label=_TOOL_LABELS[tool_name],
            investigation_question=safe_question,
            final_status=final_status,
            attempt_count=attempt_count,
            retry_count=retry_count,
            total_latency_ms=total_latency,
            evidence_ids=evidence_ids,
            limitations=limitations,
        )
        steps.append(step)
        if final_status is not ToolStatus.OK or retry_count:
            warnings.append(
                ToolWarningData(
                    tool_name=normalized_tool,
                    final_status=final_status,
                    attempt_count=attempt_count,
                    retry_count=retry_count,
                    attempt_statuses=statuses,
                    total_latency_ms=total_latency,
                    limitations=limitations,
                    unavailable=unavailable,
                )
            )
    return tuple(steps), tuple(warnings)


def _validate_report_trace_pair(
    report_path: Path,
    trace_path: Path,
    root: Path,
    report: ReportData,
    trace: TraceValidation,
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    confidence_policy = None
    expected_steps, expected_warnings = _expected_investigation_records(trace.events)
    if report.investigation_path != expected_steps:
        issues.append(
            _issue(
                report_path,
                root,
                "report_investigation_path_mismatch",
                "Report investigation path does not exactly reproduce trace attempts",
            )
        )
    if report.tool_warnings != expected_warnings:
        issues.append(
            _issue(
                report_path,
                root,
                "report_tool_warning_mismatch",
                "Report warnings do not exactly preserve failed, partial, and "
                "retried tool attempts",
            )
        )
    expected_verification_issues = _expected_report_verification_issues(trace.events)
    if report.verification_issues != expected_verification_issues:
        issues.append(
            _issue(
                report_path,
                root,
                "report_verification_issue_mismatch",
                "Report verification issues are not the exact trace reconstruction",
            )
        )
    qualitative_claims = (
        *(driver.summary for driver in report.likely_drivers),
        *(step.investigation_question for step in report.investigation_path),
        *report.alternative_explanations,
        *report.uncertainties,
        *report.interpretation_limits.observed_scope,
        *report.interpretation_limits.unobserved_factors,
        *report.interpretation_limits.causal_limitations,
        *((report.action.rationale,) if report.action is not None else ()),
    )
    if any(not is_report_safe_qualitative(item) for item in qualitative_claims):
        issues.append(
            _issue(
                report_path,
                root,
                "unsafe_report_prose",
                "Report prose contains a forbidden numerical, causal, or exposure "
                "claim",
            )
        )
    supporting_ids, counterevidence_ids = _accepted_evidence_ids(trace.events)
    if set(supporting_ids) & set(counterevidence_ids):
        issues.append(
            _issue(
                trace_path,
                root,
                "trace_evidence_role_conflict",
                "Accepted support and counterevidence identifiers overlap",
            )
        )
    expected_ledger = tuple(
        _expected_report_evidence(
            record,
            status,
            supporting_ids=frozenset(supporting_ids),
            counterevidence_ids=frozenset(counterevidence_ids),
        )
        for record, status in trace.evidence
    )
    expected_by_id = {item.evidence_id: item for item in expected_ledger}
    trace_records = tuple(record for record, _ in trace.evidence)
    try:
        expected_population_context = build_population_context(trace_records)
        expected_interpretation_limits = build_interpretation_limits(
            trace_records,
            expected_population_context.context_classification,
        )
    except ValidationError as error:
        issues.append(
            _issue(
                trace_path,
                root,
                "invalid_methodology_context",
                f"Trace evidence cannot produce report-safe context: {error}",
            )
        )
    else:
        if report.population_context != expected_population_context:
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_population_context_mismatch",
                    "Report population context is not the exact trace reconstruction",
                )
            )
        if report.interpretation_limits != expected_interpretation_limits:
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_interpretation_limits_mismatch",
                    "Report interpretation limits are not the code-owned "
                    "reconstruction",
                )
            )
    expected_supporting = tuple(
        expected_by_id[evidence_id]
        for evidence_id in supporting_ids
        if evidence_id in expected_by_id
    )
    expected_counter = tuple(
        expected_by_id[evidence_id]
        for evidence_id in counterevidence_ids
        if evidence_id in expected_by_id
    )
    if (
        set(supporting_ids) - expected_by_id.keys()
        or set(counterevidence_ids) - expected_by_id.keys()
    ):
        issues.append(
            _issue(
                trace_path,
                root,
                "trace_evidence_mismatch",
                "Passing verification cites evidence absent from successful "
                "ToolResults",
            )
        )
    if report.evidence_ledger != expected_ledger:
        issues.append(
            _issue(
                report_path,
                root,
                "report_ledger_mismatch",
                "Report ledger is not the exact reconstruction of trace ToolResults",
            )
        )
    if report.supporting_evidence != expected_supporting:
        issues.append(
            _issue(
                report_path,
                root,
                "report_supporting_evidence_mismatch",
                "Report supporting evidence does not match the accepted finish",
            )
        )
    if report.counterevidence != expected_counter:
        issues.append(
            _issue(
                report_path,
                root,
                "report_counterevidence_mismatch",
                "Report counterevidence does not match the accepted finish",
            )
        )
    if report.action is not None:
        action_definition = load_action_catalog().get(report.action.action_id)
        trace_records_by_id = {record.evidence_id: record for record in trace_records}
        supporting_trace_records = tuple(
            trace_records_by_id[evidence_id]
            for evidence_id in supporting_ids
            if evidence_id in trace_records_by_id
        )
        driver_supporting = tuple(
            record
            for record in supporting_trace_records
            if any(
                record.source_tool in rule.source_tools
                and record.metric in rule.metrics
                and any(predicate.matches(record) for predicate in rule.predicates)
                for rule in action_definition.evidence_prerequisites
            )
        )
        driver_supporting_ids = tuple(
            record.evidence_id for record in driver_supporting
        )
        finish_request = _finish_request(trace.events)
        proposed_drivers = (
            finish_request.drivers if finish_request is not None else None
        )
        if report.action.action_id is not ActionId.INSUFFICIENT_EVIDENCE and (
            finish_request is None
            or finish_request.next_best_action_id is not report.action.action_id
        ):
            issues.append(
                _issue(
                    trace_path,
                    root,
                    "trace_driver_provenance_missing",
                    "A supported action requires complete, matching finish provenance",
                )
            )
        contributing_drivers = tuple(
            driver
            for driver in proposed_drivers or ()
            if set(driver_supporting_ids).intersection(driver.supporting_evidence_ids)
        )
        resolved_counterevidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for driver in contributing_drivers
                for evidence_id in driver.counterevidence_ids
            )
        )
        if any(
            counter_id in trace_records_by_id
            and not is_relevant_counterevidence(
                action_definition,
                trace_records_by_id[counter_id],
                tuple(
                    trace_records_by_id[evidence_id]
                    for evidence_id in driver.supporting_evidence_ids
                    if evidence_id in trace_records_by_id
                ),
            )
            for driver in contributing_drivers
            for counter_id in driver.counterevidence_ids
        ):
            issues.append(
                _issue(
                    trace_path,
                    root,
                    "trace_irrelevant_counterevidence",
                    "A resolved driver labels unrelated evidence as counterevidence",
                )
            )
        if any(
            set(
                required_context_counterevidence_ids(
                    action_definition,
                    tuple(
                        trace_records_by_id[evidence_id]
                        for evidence_id in driver.supporting_evidence_ids
                        if evidence_id in trace_records_by_id
                    ),
                    trace_records,
                )
            ).difference(driver.counterevidence_ids)
            for driver in contributing_drivers
        ):
            issues.append(
                _issue(
                    trace_path,
                    root,
                    "trace_material_counterevidence_omitted",
                    "A resolved driver omits material broad or mixed context",
                )
            )
        if report.action.action_id is not ActionId.INSUFFICIENT_EVIDENCE and (
            driver_supporting_ids != supporting_ids
            or resolved_counterevidence_ids != counterevidence_ids
            or not contributing_drivers
        ):
            issues.append(
                _issue(
                    trace_path,
                    root,
                    "trace_resolved_driver_mismatch",
                    "Passing evidence roles do not match per-driver action resolution",
                )
            )
        expected_claim_type = (
            min(
                (
                    *(item.maximum_claim_type for item in driver_supporting),
                    *(item.claim_type for item in contributing_drivers),
                ),
                key=_CLAIM_ORDER.__getitem__,
            )
            if driver_supporting or contributing_drivers
            else ClaimType.ASSOCIATIONAL
        )
        templates = (
            _DESCRIPTIVE_DRIVER_TEMPLATES
            if expected_claim_type is ClaimType.DESCRIPTIVE
            else _DRIVER_TEMPLATES
        )
        driver_template = templates.get(report.action.action_id)
        expected_drivers = (
            (
                DriverReportData(
                    summary=driver_template,
                    claim_type=expected_claim_type,
                    supporting_evidence_ids=driver_supporting_ids,
                    counterevidence_ids=resolved_counterevidence_ids,
                    no_material_counterevidence_reason=(
                        None
                        if resolved_counterevidence_ids
                        else (
                            "No material counterevidence was cited from the "
                            "available ledger."
                        )
                    ),
                    limitations=tuple(
                        dict.fromkeys(
                            (
                                _OBSERVATIONAL_DRIVER_LIMITATION,
                                *(
                                    limitation
                                    for record in driver_supporting
                                    for limitation in record.limitations
                                ),
                            )
                        )
                    ),
                ),
            )
            if driver_template is not None and driver_supporting_ids
            else ()
        )
        if (
            report.likely_drivers != expected_drivers
            or report.alternative_explanations != _VERIFIED_ALTERNATIVES
            or report.uncertainties != _VERIFIED_UNCERTAINTIES
        ):
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_verified_prose_mismatch",
                    "Drivers, alternatives, and uncertainties must match "
                    "verifier-owned templates",
                )
            )

        policy_proposed_confidence: ConfidenceLevel | None
        policy_proposal_support_ids: tuple[str, ...]
        policy_referenced_ids: tuple[str, ...]
        if report.action.action_id is ActionId.INSUFFICIENT_EVIDENCE:
            policy_proposed_confidence = ConfidenceLevel.LOW
            policy_proposal_support_ids = ()
            policy_referenced_ids = ()
        elif (
            finish_request is not None
            and finish_request.next_best_action_id is report.action.action_id
        ):
            policy_proposed_confidence = finish_request.proposed_confidence
            policy_proposal_support_ids = finish_request.supporting_evidence_ids
            policy_referenced_ids = (
                *finish_request.supporting_evidence_ids,
                *finish_request.counterevidence_ids,
            )
        else:
            policy_proposed_confidence = None
            policy_proposal_support_ids = ()
            policy_referenced_ids = ()

        if policy_proposed_confidence is not None:
            missing_policy_records = set(policy_referenced_ids).difference(
                trace_records_by_id
            )
            if missing_policy_records:
                issues.append(
                    _issue(
                        trace_path,
                        root,
                        "trace_confidence_provenance_missing",
                        "Confidence policy references evidence absent from successful "
                        "ToolResults",
                    )
                )
            results_by_call = {
                result.tool_call_id: result for result in trace.tool_results
            }
            policy_limitations: list[str] = []
            for evidence_id in policy_referenced_ids:
                record = trace_records_by_id.get(evidence_id)
                if record is None:
                    continue
                policy_limitations.extend(record.limitations)
                result = results_by_call.get(record.source_tool_call_id)
                if result is not None and result.status is ToolStatus.PARTIAL:
                    policy_limitations.extend(result.limitations)
            for warning in expected_warnings:
                if not warning.unavailable:
                    continue
                policy_limitations.append(
                    f"{warning.tool_name.value} is unavailable after its bounded "
                    "retry policy was exhausted."
                )
                policy_limitations.extend(warning.limitations)
            confidence_policy = resolve_confidence_policy(
                action=action_definition,
                proposed_confidence=policy_proposed_confidence,
                proposal_supporting_records=tuple(
                    trace_records_by_id[evidence_id]
                    for evidence_id in policy_proposal_support_ids
                    if evidence_id in trace_records_by_id
                ),
                resolved_supporting_records=driver_supporting,
                full_ledger_records=trace_records,
                support_limitations=tuple(dict.fromkeys(policy_limitations)),
            )
            if confidence_policy.issues:
                issues.append(
                    _issue(
                        trace_path,
                        root,
                        "trace_confidence_policy_invalid",
                        "Trace evidence violates deterministic confidence policy",
                    )
                )
            expected_policy_adjustments = [
                item.model_dump(mode="json")
                for item in confidence_policy.confidence_adjustments
            ]
            actual_report_adjustments = [
                item.model_dump(mode="json")
                for item in report.action.confidence_adjustments
            ]
            if (
                report.action.resolved_confidence
                is not confidence_policy.resolved_confidence
                or report.action.confidence_cap_applied
                is not confidence_policy.confidence_cap_applied
                or actual_report_adjustments != expected_policy_adjustments
            ):
                issues.append(
                    _issue(
                        report_path,
                        root,
                        "report_deterministic_confidence_mismatch",
                        "Report confidence is not the deterministic reconstruction "
                        "of finish provenance and trace evidence",
                    )
                )

    completion = trace.events[-1]
    raw_snapshot = trace.events[0].details.get("detector_snapshot")
    try:
        detector_snapshot = DeclineSnapshot.model_validate(raw_snapshot)
    except ValidationError:
        detector_snapshot = None
    expected_decline = (
        {
            "evidence_id": f"detector_{report.run_id}",
            "run_id": report.run_id,
            "source": "decline_detector",
            **detector_snapshot.model_dump(mode="json"),
        }
        if detector_snapshot is not None
        else None
    )
    if (
        expected_decline is None
        or report.decline.model_dump(mode="json") != expected_decline
    ):
        issues.append(
            _issue(
                report_path,
                root,
                "report_detector_mismatch",
                "Report decline evidence does not exactly match run_started",
            )
        )
    if completion.details.get("status") != report.run_status.value:
        issues.append(
            _issue(
                report_path,
                root,
                "report_trace_status_mismatch",
                "Report run status does not match run_completed",
            )
        )
    raw_trace_failure = completion.details.get("fallback_reason")
    if raw_trace_failure is None:
        raw_trace_failure = completion.details.get("message")
    trace_failure = raw_trace_failure if isinstance(raw_trace_failure, str) else None
    if report.failure_reason != trace_failure:
        issues.append(
            _issue(
                report_path,
                root,
                "report_failure_reason_mismatch",
                "Report failure reason does not match the terminal trace reason",
            )
        )
    report_action = report.action.action_id.value if report.action is not None else None
    trace_action = completion.details.get("next_best_action_id")
    if trace_action != report_action and not (
        report_action is None and trace_action is None
    ):
        issues.append(
            _issue(
                report_path,
                root,
                "report_trace_action_mismatch",
                "Report action does not match run_completed",
            )
        )
    passing_verdict = next(
        (
            event
            for event in reversed(trace.events)
            if event.event is AuditEventName.VERIFICATION_PASSED
        ),
        None,
    )
    if passing_verdict is not None and report.action is not None:
        if (
            passing_verdict.details.get("next_best_action_id")
            != report.action.action_id.value
            or passing_verdict.details.get("resolved_confidence")
            != report.action.resolved_confidence.value
            or passing_verdict.details.get("confidence_cap_applied")
            is not report.action.confidence_cap_applied
        ):
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_verdict_mismatch",
                    "Report action confidence does not match VERIFICATION_PASSED",
                )
            )
        expected_adjustments = passing_verdict.details.get("confidence_adjustments", [])
        actual_adjustments = [
            item.model_dump(mode="json")
            for item in report.action.confidence_adjustments
        ]
        if expected_adjustments != actual_adjustments:
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_confidence_adjustment_mismatch",
                    "Report confidence adjustments do not match VERIFICATION_PASSED",
                )
            )
        if confidence_policy is not None:
            deterministic_adjustments = [
                item.model_dump(mode="json")
                for item in confidence_policy.confidence_adjustments
            ]
            if (
                passing_verdict.details.get("resolved_confidence")
                != confidence_policy.resolved_confidence.value
                or passing_verdict.details.get("confidence_cap_applied")
                is not confidence_policy.confidence_cap_applied
                or passing_verdict.details.get("confidence_adjustments")
                != deterministic_adjustments
            ):
                issues.append(
                    _issue(
                        trace_path,
                        root,
                        "trace_deterministic_confidence_mismatch",
                        "VERIFICATION_PASSED confidence is not the deterministic "
                        "reconstruction of finish provenance and evidence",
                    )
                )
        try:
            definition = load_action_catalog().get(report.action.action_id)
        except ActionCatalogError as error:
            issues.append(
                _issue(
                    report_path,
                    root,
                    "action_catalog_unavailable",
                    f"Verifier could not resolve the action catalog: {error}",
                )
            )
        else:
            expected_rationale = (
                "Available verified evidence does not support a customer action."
                if report.action.action_id is ActionId.INSUFFICIENT_EVIDENCE
                else (
                    "The cited records satisfy the selected catalog action's "
                    "machine-checkable evidence policy; the recommendation remains "
                    "a human-reviewed test."
                )
            )
            if (
                report.action.description != definition.description
                or report.action.rationale != expected_rationale
                or report.action.recommended_success_metric
                != definition.success_metric.description
                or report.action.suggested_experiment
                != definition.experiment.description
            ):
                issues.append(
                    _issue(
                        report_path,
                        root,
                        "report_action_catalog_mismatch",
                        "Report action prose and measurement plan must exactly match "
                        "the code-owned catalog and verifier templates",
                    )
                )
            support_records = tuple(
                record
                for record, _ in trace.evidence
                if record.evidence_id in supporting_ids
            )

            def rule_satisfied(rule_index: int) -> bool:
                rule = definition.evidence_prerequisites[rule_index]
                matching = tuple(
                    record
                    for record in support_records
                    if record.source_tool in rule.source_tools
                    and record.metric in rule.metrics
                    and any(predicate.matches(record) for predicate in rule.predicates)
                )
                if rule.metric_match == "all" and not set(rule.metrics).issubset(
                    {record.metric for record in matching}
                ):
                    return False
                return (
                    len(matching) >= rule.minimum_matching_records
                    and len({record.source_tool for record in matching})
                    >= rule.minimum_distinct_tools
                )

            supported = (
                not support_records
                if report.action.action_id is ActionId.INSUFFICIENT_EVIDENCE
                else any(
                    rule_satisfied(index)
                    for index in range(len(definition.evidence_prerequisites))
                )
            )
            if not supported:
                issues.append(
                    _issue(
                        report_path,
                        root,
                        "report_action_evidence_mismatch",
                        "Report action does not satisfy its catalog evidence policy",
                    )
                )
    expected_limitation_values: list[str] = []
    if report.decline.partial_week_limitation:
        expected_limitation_values.append(report.decline.partial_week_limitation)
    expected_limitation_values.extend(
        limitation for step in expected_steps for limitation in step.limitations
    )
    for warning in expected_warnings:
        if not warning.unavailable:
            continue
        expected_limitation_values.append(
            f"{_TOOL_LABELS[warning.tool_name.value]} is unavailable after its "
            "bounded retry policy was exhausted."
        )
    expected_limitation_values.extend(
        limitation for record, _ in trace.evidence for limitation in record.limitations
    )
    if report.action is not None:
        # These raw tool-name notices come from the verifier's propagated
        # limitations, in addition to the report builder's humanized warning.
        expected_limitation_values.extend(
            f"{warning.tool_name.value} is unavailable after its bounded retry "
            "policy was exhausted."
            for warning in expected_warnings
            if warning.unavailable
        )
        if confidence_policy is not None:
            expected_limitation_values.extend(confidence_policy.context_limitations)
            expected_limitation_values.extend(
                confidence_policy.category_context_limitations
            )
        expected_limitation_values.extend(_VERIFIED_UNCERTAINTIES)
    trace_failure = _terminal_trace_reason(trace.events)
    if trace_failure is not None:
        expected_limitation_values.append(trace_failure)
    expected_limitation_values.extend(expected_verification_issues)
    expected_limitations = _deduplicate_public_text(expected_limitation_values)
    if len(report.limitations) != len(set(report.limitations)) or set(
        report.limitations
    ) != set(expected_limitations):
        issues.append(
            _issue(
                report_path,
                root,
                "report_limitation_mismatch",
                "Report limitations are not the exact detector, trace, evidence, "
                "confidence, failure, and verifier reconstruction",
            )
        )

    # Deterministic source-owned limitations may legitimately contain cohort sizes,
    # weeks, timeouts, or Type A coupon counts. Re-scan only report-authored extras;
    # exact reconstruction above is the authority for legitimate quantities.
    expected_limitation_set = set(expected_limitations)
    expected_verification_set = set(expected_verification_issues)
    unexpected_public_prose = (
        *(item for item in report.limitations if item not in expected_limitation_set),
        *(
            item
            for item in report.verification_issues
            if item not in expected_verification_set
        ),
    )
    if any(
        not is_report_safe_qualitative(item) for item in unexpected_public_prose
    ) and not any(item.code == "unsafe_report_prose" for item in issues):
        issues.append(
            _issue(
                report_path,
                root,
                "unsafe_report_prose",
                "Report prose contains a forbidden numerical, causal, or exposure "
                "claim",
            )
        )
    return issues


def _manifest_id_list(
    manifest_path: Path,
    root: Path,
    data: Mapping[str, object],
    key: str,
) -> tuple[tuple[str, ...], list[VerificationIssue]]:
    raw = data.get(key)
    if not isinstance(raw, list) or any(
        not isinstance(item, str) or not item for item in raw
    ):
        return (), [
            _issue(
                manifest_path,
                root,
                "malformed_manifest_household_ids",
                f"{key} must be a list of non-empty household IDs",
            )
        ]
    values = cast(tuple[str, ...], tuple(raw))
    if len(values) != len(set(values)):
        return values, [
            _issue(
                manifest_path,
                root,
                "duplicate_manifest_household_id",
                f"{key} contains a duplicate household ID",
            )
        ]
    return values, []


def _validate_manifest_households(
    manifest_path: Path,
    root: Path,
    data: Mapping[str, object],
    reports_by_path: Mapping[Path, ReportData],
) -> list[VerificationIssue]:
    keys = (
        "selected_household_ids",
        "completed_household_ids",
        "failed_household_ids",
        "skipped_household_ids",
    )
    if not any(key in data for key in keys):
        return []
    issues: list[VerificationIssue] = []
    resolved: dict[str, tuple[str, ...]] = {}
    for key in keys:
        values, value_issues = _manifest_id_list(manifest_path, root, data, key)
        resolved[key] = values
        issues.extend(value_issues)

    selected = set(resolved["selected_household_ids"])
    completed = set(resolved["completed_household_ids"])
    failed = set(resolved["failed_household_ids"])
    skipped = set(resolved["skipped_household_ids"])
    terminal_groups = (completed, failed, skipped)
    if any(
        left & right
        for index, left in enumerate(terminal_groups)
        for right in terminal_groups[index + 1 :]
    ):
        issues.append(
            _issue(
                manifest_path,
                root,
                "manifest_household_status_overlap",
                "Completed, failed, and skipped household IDs must be disjoint",
            )
        )
    if selected != completed | failed | skipped:
        issues.append(
            _issue(
                manifest_path,
                root,
                "manifest_household_reconciliation_failed",
                "Selected households do not exactly reconcile to terminal statuses",
            )
        )

    direct_report = reports_by_path.get(manifest_path.parent / "report.json")
    if direct_report is not None:
        expected_mode = _model_execution_for_backend(
            data.get("backend"), data.get("execution_mode")
        )
        if (
            data.get("artifact_profile") != "standalone_run"
            or data.get("schema_version") != 1
            or data.get("product") != "WhyBack"
            or data.get("model_execution") != expected_mode
            or data.get("timing_mode") != "actual_utc_and_monotonic"
            or data.get("human_review_required") is not True
            or data.get("customer_outreach_executed") is not False
            or "source_manifest" not in data
        ):
            issues.append(
                _issue(
                    manifest_path,
                    root,
                    "manifest_standalone_profile_invalid",
                    "A standalone run needs the strict standalone_run publication "
                    "profile",
                )
            )
        expected_terminal = (
            failed if direct_report.run_status.value == "failed" else completed
        )
        if (
            selected != {direct_report.household_id}
            or expected_terminal != {direct_report.household_id}
            or skipped
            or any(
                candidate.is_dir() and candidate.name.startswith("customer_")
                for candidate in manifest_path.parent.iterdir()
            )
        ):
            issues.append(
                _issue(
                    manifest_path,
                    root,
                    "manifest_standalone_run_mismatch",
                    "Standalone manifest status must exactly match its sibling report",
                )
            )
        return issues

    customer_directories = {
        candidate.name.removeprefix("customer_"): candidate
        for candidate in manifest_path.parent.iterdir()
        if candidate.is_dir() and candidate.name.startswith("customer_")
    }
    if set(customer_directories) != completed | failed:
        issues.append(
            _issue(
                manifest_path,
                root,
                "manifest_artifact_directory_mismatch",
                "Customer artifact directories do not exactly match completed and "
                "failed household IDs",
            )
        )
    for household_id, directory in customer_directories.items():
        report = reports_by_path.get(directory / "report.json")
        if report is None:
            issues.append(
                _issue(
                    directory,
                    root,
                    "customer_report_missing",
                    "Customer artifact directory has no valid report.json",
                )
            )
            continue
        expected_status_group = (
            completed if report.run_status.value != "failed" else failed
        )
        if (
            report.household_id != household_id
            or household_id not in expected_status_group
        ):
            issues.append(
                _issue(
                    directory,
                    root,
                    "manifest_customer_status_mismatch",
                    "Customer directory, report owner, and manifest status disagree",
                )
            )
    return issues


def _render_results_markdown(
    *,
    data: Mapping[str, object],
    reports: Sequence[ReportData],
) -> str | None:
    backend = data.get("backend")
    dataset_kind = data.get("dataset_kind")
    if backend not in {"scripted", "gemini", "openai"} or dataset_kind not in {
        "synthetic",
        "official_complete_journey",
    }:
        return None
    dataset_label = (
        "synthetic fixture"
        if dataset_kind == "synthetic"
        else "official full Complete Journey"
    )
    rows: list[str] = []
    for report in reports:
        action = (
            report.action.action_id.value
            if report.action is not None
            else "UNAVAILABLE"
        )
        rows.append(
            f"| {report.household_id} | {report.decline.decline_score:.3f} "
            f"| {report.run_status.value} | {action} |"
        )
    backend_note = (
        "Scripted runs are deterministic orchestration controls and are not "
        "presented as live model judgments. All displayed metrics were computed "
        "by the deterministic detector or registered analytical tools."
        if backend == "scripted"
        else (
            "These runs used the configured Gemini function-calling backend."
            if backend == "gemini" and reports
            else "No live model call was attempted because GEMINI_API_KEY was absent."
            if backend == "gemini"
            else "These runs used the configured OpenAI Responses backend."
            if reports
            else "No live model call was attempted because OPENAI_API_KEY was absent."
        )
    )
    return "\n".join(
        [
            "# WhyBack demo results",
            "",
            "### Find the why. Choose the way back.",
            "",
            f"Dataset: **{dataset_label}**. Backend: **{backend}**.",
            "",
            backend_note,
            "",
            "| Household | Decline score | Status | Human-reviewed action |",
            "|---|---:|---|---|",
            *rows,
            "",
            "The decline score is a transparent heuristic, not a churn probability.",
            "Every action is a recommendation requiring human review; no outreach "
            "was executed.",
            "",
        ]
    )


def _validate_results_index(
    manifest_path: Path,
    root: Path,
    data: Mapping[str, object],
    reports_by_path: Mapping[Path, ReportData],
) -> list[VerificationIssue]:
    if manifest_path.parent / "report.json" in reports_by_path:
        return []
    raw_selected = data.get("selected_household_ids")
    raw_completed = data.get("completed_household_ids")
    raw_failed = data.get("failed_household_ids")
    if not all(
        isinstance(item, list) for item in (raw_selected, raw_completed, raw_failed)
    ):
        return []
    selected = tuple(
        item for item in cast(list[object], raw_selected) if isinstance(item, str)
    )
    terminal = {
        item
        for raw in (cast(list[object], raw_completed), cast(list[object], raw_failed))
        for item in raw
        if isinstance(item, str)
    }
    ordered_reports: list[ReportData] = []
    for household_id in selected:
        if household_id not in terminal:
            continue
        report = reports_by_path.get(
            manifest_path.parent / f"customer_{household_id}" / "report.json"
        )
        if report is not None:
            ordered_reports.append(report)
    issues: list[VerificationIssue] = []
    results_path = manifest_path.parent / "results.json"
    expected_results = [report.model_dump(mode="json") for report in ordered_reports]
    value, parse_issues = _load_json(results_path, root)
    issues.extend(parse_issues)
    if value != expected_results:
        issues.append(
            _issue(
                results_path,
                root,
                "results_index_mismatch",
                "results.json is not the exact selected-order customer report index",
            )
        )
    expected_markdown = _render_results_markdown(data=data, reports=ordered_reports)
    markdown_path = manifest_path.parent / "RESULTS.md"
    if expected_markdown is not None:
        issues.extend(
            _validate_exact_render(
                markdown_path,
                root,
                expected_markdown,
                missing_code="results_markdown_missing",
                mismatch_code="results_markdown_mismatch",
                label="demo results Markdown",
            )
        )
    return issues


def _validate_source_manifest(
    manifest_path: Path,
    root: Path,
    validation: ManifestValidation,
    reports_by_path: Mapping[Path, ReportData],
    traces_by_path: Mapping[Path, TraceValidation],
) -> list[VerificationIssue]:
    data = validation.data
    if data is None:
        return []
    dataset_kind = data.get("dataset_kind")
    reference = data.get("source_manifest")
    if reference is None and dataset_kind != "official_complete_journey":
        return []
    if not isinstance(reference, str) or not reference:
        return [
            _issue(
                manifest_path,
                root,
                "source_manifest_missing",
                "Official artifacts must declare a committed source manifest",
            )
        ]
    source_path = _safe_manifest_path(root, manifest_path, reference)
    if source_path is None or source_path not in validation.declared_files:
        return [
            _issue(
                manifest_path,
                root,
                "source_manifest_unsafe",
                "source_manifest must resolve to a hashed file inside the "
                "artifact tree",
            )
        ]
    raw, parse_issues = _load_json(source_path, root)
    issues = list(parse_issues)
    if not isinstance(raw, Mapping):
        issues.append(
            _issue(
                source_path,
                root,
                "malformed_source_manifest",
                "Data provenance root must be an object",
            )
        )
        return issues
    if set(raw) != {"schema_version", "dataset_kind", "manifest_sha256", "manifest"}:
        issues.append(
            _issue(
                source_path,
                root,
                "malformed_source_manifest",
                "Data provenance must contain only its version, kind, hash, and "
                "manifest",
            )
        )
    if raw.get("schema_version") != 1 or raw.get("dataset_kind") != dataset_kind:
        issues.append(
            _issue(
                source_path,
                root,
                "source_manifest_identity_mismatch",
                "Data provenance version or dataset kind disagrees with the manifest",
            )
        )
    try:
        embedded = DataManifest.model_validate(raw.get("manifest"))
    except ValidationError as error:
        issues.append(
            _issue(
                source_path,
                root,
                "malformed_source_manifest",
                f"Embedded prepared-data manifest is invalid: {error}",
            )
        )
        return issues
    canonical = (
        json.dumps(embedded.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()
    canonical_hash = hashlib.sha256(canonical).hexdigest()
    if raw.get("manifest_sha256") != canonical_hash:
        issues.append(
            _issue(
                source_path,
                root,
                "source_manifest_hash_mismatch",
                "manifest_sha256 does not match canonical embedded-manifest bytes",
            )
        )
    if (
        embedded.source_repository != data.get("dataset_source_repository")
        or embedded.source_commit != data.get("dataset_source_commit")
        or embedded.preparation_code_sha256 != preparation_code_sha256()
    ):
        issues.append(
            _issue(
                source_path,
                root,
                "source_manifest_identity_mismatch",
                "Embedded source or preparation-code identity disagrees with the "
                "published artifact",
            )
        )
    source_entries = {item.filename: item for item in embedded.sources}
    prepared_entries = {item.filename: item for item in embedded.prepared}
    if (
        len(source_entries) != len(embedded.sources)
        or len(prepared_entries) != len(embedded.prepared)
        or any(_SHA256.fullmatch(item.sha256) is None for item in embedded.sources)
        or any(_SHA256.fullmatch(item.sha256) is None for item in embedded.prepared)
    ):
        issues.append(
            _issue(
                source_path,
                root,
                "source_manifest_hashes_invalid",
                "Source and prepared entries need unique names and lowercase SHA-256",
            )
        )
    if dataset_kind == "official_complete_journey":
        expected_sources = {
            item.name: (item.sha256, item.size_bytes) for item in SOURCE_FILES
        }
        actual_sources = {
            item.filename: (item.sha256, item.size_bytes) for item in embedded.sources
        }
        if actual_sources != expected_sources:
            issues.append(
                _issue(
                    source_path,
                    root,
                    "official_source_set_mismatch",
                    "Embedded official source files do not match the pinned set, "
                    "hashes, and sizes",
                )
            )
    expected_hashes = {
        "manifest/manifest.json": canonical_hash,
        **{f"source/{item.filename}": item.sha256 for item in embedded.sources},
        **{f"prepared/{item.filename}": item.sha256 for item in embedded.prepared},
    }
    contained_reports = [
        report
        for path, report in reports_by_path.items()
        if path.resolve() in validation.declared_files
    ]
    contained_results = [
        result
        for path, trace in traces_by_path.items()
        if path.resolve() in validation.declared_files
        for result in trace.tool_results
    ]
    if any(
        dict(report.provenance.source_hashes) != expected_hashes
        for report in contained_reports
    ) or any(
        dict(result.provenance.source_hashes) != expected_hashes
        for result in contained_results
    ):
        issues.append(
            _issue(
                source_path,
                root,
                "source_hash_reconciliation_failed",
                "Report or ToolResult source hashes disagree with data provenance",
            )
        )
    return issues


def _validate_provenance(
    report_path: Path,
    trace_path: Path,
    root: Path,
    report: ReportData,
    trace: TraceValidation,
    manifests: Sequence[tuple[Path, ManifestValidation]],
) -> list[VerificationIssue]:
    dumped = report.model_dump(mode="json")
    raw_provenance = dumped.get("provenance")
    if not isinstance(raw_provenance, Mapping):
        return []
    provenance = cast(Mapping[str, object], raw_provenance)
    issues: list[VerificationIssue] = []
    known_values = (
        report.provenance.dataset_kind,
        report.provenance.dataset_source_repository,
        report.provenance.dataset_source_commit,
        report.provenance.backend,
        report.provenance.execution_mode,
        report.provenance.model,
        report.provenance.application_version,
        report.provenance.prompt_version,
    )
    if (
        any(not value or value == "unspecified" for value in known_values)
        or _SHA256.fullmatch(report.provenance.prompt_hash) is None
        or not report.provenance.source_hashes
        or any(
            not key or _SHA256.fullmatch(value) is None
            for key, value in report.provenance.source_hashes.items()
        )
        or (
            report.provenance.backend == "scripted"
            and report.provenance.execution_mode != "scripted_control"
        )
        or (
            report.provenance.backend == "gemini"
            and report.provenance.execution_mode != "live_gemini"
        )
        or (
            report.provenance.backend == "openai"
            and report.provenance.execution_mode != "live_openai"
        )
    ):
        issues.append(
            _issue(
                report_path,
                root,
                "report_provenance_incomplete",
                "Report provenance must identify known data, source hashes, backend, "
                "model, application, prompt, and timing",
            )
        )

    run_started = trace.events[0]
    trace_checks = {
        "dataset_kind": run_started.details.get("dataset_kind"),
        "dataset_source_repository": run_started.details.get(
            "dataset_source_repository"
        ),
        "dataset_source_commit": run_started.details.get("dataset_source_commit"),
        "model": run_started.details.get("model"),
        "application_version": run_started.details.get("application_version"),
        "prompt_version": run_started.details.get("prompt_version"),
        "prompt_hash": run_started.details.get("prompt_hash"),
        "timing_mode": run_started.details.get("timing_mode"),
    }
    for key, trace_value in trace_checks.items():
        if (
            key in provenance
            and trace_value is not None
            and provenance[key] != trace_value
        ):
            issues.append(
                _issue(
                    report_path,
                    root,
                    "report_trace_provenance_mismatch",
                    f"Report provenance {key!r} disagrees with run_started",
                )
            )
    execution_mode = provenance.get("execution_mode")
    expected_execution_mode = _model_execution_for_backend(
        provenance.get("backend"), trace.mode
    )
    if (
        execution_mode is not None
        and expected_execution_mode is not None
        and execution_mode != expected_execution_mode
    ):
        issues.append(
            _issue(
                report_path,
                root,
                "report_trace_provenance_mismatch",
                "Report execution mode disagrees with its trace",
            )
        )
    provider_ids = [
        event.details.get("provider_call_id")
        for event in trace.events
        if event.event is AuditEventName.MODEL_DECISION_RECEIVED
    ]
    provider_id_mismatch = (
        report.provenance.backend == "gemini"
        and any(
            not isinstance(value, str) or not value.strip() or value.startswith("resp_")
            for value in provider_ids
        )
    ) or (
        report.provenance.backend == "openai"
        and any(
            not isinstance(value, str) or not value.startswith("resp_")
            for value in provider_ids
        )
    )
    if trace.mode == "live" and provider_id_mismatch:
        issues.append(
            _issue(
                report_path,
                root,
                "report_trace_provider_mismatch",
                "Provider call identifiers disagree with report backend provenance",
            )
        )
    if report.provenance.generated_at < trace.events[-1].timestamp:
        issues.append(
            _issue(
                report_path,
                root,
                "report_trace_provenance_mismatch",
                "Report generation time predates trace completion",
            )
        )
    for result in trace.tool_results:
        result_checks = {
            "dataset_source_commit": result.provenance.dataset_source_commit,
            "source_hashes": dict(result.provenance.source_hashes),
            "application_version": result.provenance.application_version,
        }
        for key, result_value in result_checks.items():
            if key in provenance and provenance[key] != result_value:
                issues.append(
                    _issue(
                        trace_path,
                        root,
                        "report_tool_provenance_mismatch",
                        f"ToolResult provenance {key!r} disagrees with the report",
                    )
                )

    containing = [
        item
        for item in manifests
        if item[1].is_artifact_manifest
        and (report_path.resolve() in item[1].declared_files)
    ]
    for manifest_path, manifest in containing:
        if manifest.data is None:
            continue
        manifest_checks = {
            "dataset_kind": manifest.data.get("dataset_kind"),
            "dataset_source_repository": manifest.data.get("dataset_source_repository"),
            "dataset_source_commit": manifest.data.get("dataset_source_commit"),
            "backend": manifest.data.get("backend"),
            "execution_mode": _model_execution_for_backend(
                manifest.data.get("backend"), manifest.data.get("execution_mode")
            ),
        }
        if (
            manifest.data.get("dataset_kind")
            not in {"synthetic", "official_complete_journey"}
            or not isinstance(manifest.data.get("dataset_source_repository"), str)
            or manifest.data.get("dataset_source_repository") == "unspecified"
            or not isinstance(manifest.data.get("dataset_source_commit"), str)
            or manifest.data.get("dataset_source_commit") == "unspecified"
            or manifest.data.get("backend") not in {"scripted", "gemini", "openai"}
            or manifest.data.get("execution_mode") not in {"scripted", "live"}
        ):
            issues.append(
                _issue(
                    manifest_path,
                    root,
                    "manifest_provenance_incomplete",
                    "Investigation manifest must record known dataset, source, "
                    "backend, and execution provenance",
                )
            )
        for key, manifest_value in manifest_checks.items():
            if (
                key in provenance
                and manifest_value is not None
                and provenance[key] != manifest_value
            ):
                issues.append(
                    _issue(
                        manifest_path,
                        root,
                        "report_manifest_provenance_mismatch",
                        f"Manifest {key!r} disagrees with report provenance",
                    )
                )
    return issues


def verify_artifact_tree(
    root: Path,
    *,
    allow_live_skipped: bool = False,
) -> ArtifactVerificationResult:
    """Validate a complete artifact tree without mutating it."""

    if root.is_symlink():
        issue = VerificationIssue(
            ".", "artifact_symlink_forbidden", "Artifact root cannot be a symlink"
        )
        return ArtifactVerificationResult(str(root), (), (), (issue,))
    root = root.resolve()
    if not root.is_dir():
        issue = VerificationIssue(
            ".", "artifact_root_missing", f"Artifact directory does not exist: {root}"
        )
        return ArtifactVerificationResult(str(root), (), (), (issue,))

    entries = tuple(root.rglob("*"))
    files = tuple(
        sorted(
            (path for path in entries if path.is_file() and not path.is_symlink()),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    )
    issues: list[VerificationIssue] = []
    for path in entries:
        if path.is_symlink():
            issues.append(
                _issue(
                    path,
                    root,
                    "artifact_symlink_forbidden",
                    "Portable artifact trees cannot contain symlinks",
                )
            )
    if not files:
        issues.append(
            VerificationIssue(".", "artifact_tree_empty", "Artifact tree is empty")
        )
    reports_by_path: dict[Path, ReportData] = {}
    reports_by_identity: dict[ArtifactIdentity, list[Path]] = {}
    parsed_json: dict[Path, object] = {}
    modes: set[ExecutionMode] = set()

    for path in files:
        if path.suffix.casefold() != ".json":
            continue
        value, parse_issues = _load_json(path, root)
        issues.extend(parse_issues)
        if value is None:
            continue
        parsed_json[path] = value
        if _looks_like_report(path, value):
            report, report_issues = _validate_report(path, root, value)
            issues.extend(report_issues)
            if report is not None:
                reports_by_path[path] = report
                identity = (report.run_id, report.household_id)
                reports_by_identity.setdefault(identity, []).append(path)
                issues.extend(
                    _validate_exact_render(
                        path.with_suffix(".md"),
                        root,
                        render_report_markdown(report),
                        missing_code="rendered_report_missing",
                        mismatch_code="report_render_mismatch",
                        label="Markdown report",
                    )
                )
                issues.extend(
                    _validate_exact_render(
                        path.with_suffix(".html"),
                        root,
                        render_report_html(report),
                        missing_code="rendered_report_missing",
                        mismatch_code="report_render_mismatch",
                        label="HTML report",
                    )
                )

    manifests: list[tuple[Path, ManifestValidation]] = []
    for path, value in parsed_json.items():
        if "manifest" in path.stem.casefold() or "status" in path.stem.casefold():
            validation = _validate_manifest(path, root, value)
            manifests.append((path, validation))
            modes.update(validation.modes)
            issues.extend(validation.issues)

    artifact_manifests = [item for item in manifests if item[1].is_artifact_manifest]
    if not artifact_manifests:
        issues.append(
            VerificationIssue(
                ".", "artifact_manifest_missing", "No artifact manifest was found"
            )
        )
    trace_modes: set[ExecutionMode] = set()
    traces_by_path: dict[Path, TraceValidation] = {}
    traces_by_identity: dict[ArtifactIdentity, list[Path]] = {}
    for path in files:
        suffix = path.suffix.casefold()
        if suffix == ".jsonl":
            trace = _validate_trace(path, root)
            traces_by_path[path] = trace
            issues.extend(trace.issues)
            if trace.identity is not None:
                traces_by_identity.setdefault(trace.identity, []).append(path)
            if trace.mode is not None:
                trace_modes.add(trace.mode)
            if trace.events:
                issues.extend(
                    _validate_exact_render(
                        path.with_suffix(".html"),
                        root,
                        render_trace_html(trace.events),
                        missing_code="trace_render_missing",
                        mismatch_code="trace_render_mismatch",
                        label="HTML trace viewer",
                    )
                )
    modes.update(trace_modes)

    for identity, paths in reports_by_identity.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(
                    _issue(
                        path,
                        root,
                        "duplicate_report_identity",
                        f"Multiple reports claim run {identity[0]!r} and household "
                        f"{identity[1]!r}",
                    )
                )
    report_runs: dict[str, list[Path]] = {}
    for (run_id, _), paths in reports_by_identity.items():
        report_runs.setdefault(run_id, []).extend(paths)
    for run_id, paths in report_runs.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(
                    _issue(
                        path,
                        root,
                        "duplicate_report_run_id",
                        f"Report run ID {run_id!r} is not globally unique",
                    )
                )

    for identity, paths in traces_by_identity.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(
                    _issue(
                        path,
                        root,
                        "duplicate_trace_identity",
                        f"Multiple traces claim run {identity[0]!r} and household "
                        f"{identity[1]!r}",
                    )
                )
    trace_runs: dict[str, list[Path]] = {}
    for (run_id, _), paths in traces_by_identity.items():
        trace_runs.setdefault(run_id, []).extend(paths)
    for run_id, paths in trace_runs.items():
        if len(paths) > 1:
            for path in paths:
                issues.append(
                    _issue(
                        path,
                        root,
                        "duplicate_trace_run_id",
                        f"Trace run ID {run_id!r} is not globally unique",
                    )
                )

    for identity in sorted(set(reports_by_identity) | set(traces_by_identity)):
        report_paths = reports_by_identity.get(identity, [])
        trace_paths = traces_by_identity.get(identity, [])
        if len(report_paths) != 1:
            for path in trace_paths or (root,):
                issues.append(
                    _issue(
                        path,
                        root,
                        "orphan_trace"
                        if not report_paths
                        else "report_trace_cardinality_mismatch",
                        f"Run {identity[0]!r} household {identity[1]!r} does not "
                        "have exactly one report",
                    )
                )
        if len(trace_paths) != 1:
            for path in report_paths or (root,):
                issues.append(
                    _issue(
                        path,
                        root,
                        "orphan_report"
                        if not trace_paths
                        else "report_trace_cardinality_mismatch",
                        f"Run {identity[0]!r} household {identity[1]!r} does not "
                        "have exactly one trace",
                    )
                )
        if len(report_paths) == len(trace_paths) == 1:
            report_path = report_paths[0]
            trace_path = trace_paths[0]
            report = reports_by_path[report_path]
            trace = traces_by_path[trace_path]
            issues.extend(
                _validate_report_trace_pair(
                    report_path,
                    trace_path,
                    root,
                    report,
                    trace,
                )
            )
            issues.extend(
                _validate_provenance(
                    report_path,
                    trace_path,
                    root,
                    report,
                    trace,
                    manifests,
                )
            )

    for manifest_path, manifest in artifact_manifests:
        if manifest.data is not None:
            issues.extend(
                _validate_manifest_households(
                    manifest_path,
                    root,
                    manifest.data,
                    reports_by_path,
                )
            )
            issues.extend(
                _validate_results_index(
                    manifest_path,
                    root,
                    manifest.data,
                    reports_by_path,
                )
            )
            issues.extend(
                _validate_source_manifest(
                    manifest_path,
                    root,
                    manifest,
                    reports_by_path,
                    traces_by_path,
                )
            )
        manifest_mode = (
            _mode(manifest.data.get("execution_mode"))
            if manifest.data is not None
            else None
        )
        if manifest_mode not in {"scripted", "live"}:
            continue
        for trace_path, trace in traces_by_path.items():
            if (
                trace_path.resolve() in manifest.declared_files
                and trace.mode is not None
                and trace.mode != manifest_mode
            ):
                issues.append(
                    _issue(
                        trace_path,
                        root,
                        "manifest_trace_mode_mismatch",
                        "Trace execution mode disagrees with its containing manifest",
                    )
                )

    skip_only = allow_live_skipped and bool(modes) and modes <= {"skipped"}
    if not reports_by_path and not skip_only:
        issues.append(
            VerificationIssue(
                ".",
                "validated_report_missing",
                "No valid WhyBack JSON report was found",
            )
        )
    if not traces_by_path and not skip_only:
        issues.append(
            VerificationIssue(
                ".", "audit_trace_missing", "No JSONL audit trace was found"
            )
        )

    if "live" in modes and "live" not in trace_modes:
        issues.append(
            VerificationIssue(
                ".",
                "live_label_mismatch",
                "Artifacts claim a live run, but only scripted traces are present",
            )
        )
    if not allow_live_skipped and "skipped" in modes:
        issues.append(
            VerificationIssue(
                ".",
                "unacknowledged_live_skip",
                "Use --allow-live-skipped to acknowledge absent live credentials",
            )
        )

    return ArtifactVerificationResult(
        root=str(root),
        checked_files=tuple(_relative(path, root) for path in files),
        execution_modes=tuple(sorted(modes)),
        issues=tuple(issues),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact_root",
        nargs="?",
        type=Path,
        default=Path("artifacts/demo"),
    )
    parser.add_argument(
        "--allow-live-skipped",
        action="store_true",
        help=(
            "Permit an honestly recorded skipped live attempt, including alongside "
            "historical live artifacts."
        ),
    )
    parser.add_argument("--json-output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run verification and return nonzero for every issue."""

    arguments = _parser().parse_args(argv)
    result = verify_artifact_tree(
        arguments.artifact_root,
        allow_live_skipped=arguments.allow_live_skipped,
    )
    rendered = json.dumps(result.as_json(), indent=2, sort_keys=True) + "\n"
    output = cast(Path | None, arguments.json_output)
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
