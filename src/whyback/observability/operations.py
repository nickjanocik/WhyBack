"""Identifier-minimized operational health and drift audits for run artifacts.

The auditor is post-hoc and read-only. Public results contain aggregates, never
household IDs, run IDs, raw event details, provider IDs, or input paths.
"""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from statistics import fmean
from typing import Literal, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    model_validator,
)

from whyback.agent.state import RunStatus
from whyback.agent.verifier import VerificationIssueCode
from whyback.immutability import frozen_mapping
from whyback.observability.audit import AuditTraceReadError, read_audit_events
from whyback.observability.events import AuditEvent, AuditEventName
from whyback.reporting.models import ReportData
from whyback.tools.contracts import ToolName, ToolStatus

DEFAULT_MINIMUM_RUNS = 20
DEFAULT_DISTANCE_THRESHOLD = 0.20
JsonObject = dict[str, JsonValue]

_TOOL_EVENTS = frozenset(
    {
        AuditEventName.TOOL_COMPLETED,
        AuditEventName.TOOL_PARTIAL,
        AuditEventName.TOOL_FAILED,
    }
)
_ERROR_STATUSES = frozenset(
    status.value
    for status in (
        ToolStatus.MISSING_DATA,
        ToolStatus.INVALID_REQUEST,
        ToolStatus.RETRYABLE_ERROR,
        ToolStatus.FATAL_ERROR,
    )
)
_LIMITATIONS = (
    "Recorded I/O tokens are traced input plus output tokens, not provider-total "
    "tokens, cost, or hidden-reasoning usage.",
    "Queue age, bytes scanned, reviewer timing, cost, detector version, and action-"
    "catalog version are not present in the local trace.",
    "A drift distance describes distribution change; it does not establish cause or "
    "a production service-level objective breach.",
)


class OperationalInputStatus(StrEnum):
    """Whether an artifact root is safe to summarize as one cohort."""

    READY = "ready"
    PARTIAL = "partial"
    INVALID = "invalid"
    MIXED_COHORT = "mixed_cohort"


class DriftStatus(StrEnum):
    """Closed vocabulary for a cohort-level drift result."""

    STABLE = "stable"
    DETECTED = "detected"
    INSUFFICIENT = "insufficient"
    INCOMPATIBLE = "incompatible"


class CompatibilityKey(BaseModel):
    """Recorded workload identity required before cohorts may be compared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_schema_version: int = Field(ge=1)
    dataset_kind: Literal["synthetic", "official_complete_journey", "unspecified"]
    dataset_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_hashes_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    backend: Literal["scripted", "gemini", "openai", "unspecified"]
    execution_mode: Literal[
        "scripted_control", "live_gemini", "live_openai", "unspecified"
    ]
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timing_mode: Literal["actual_utc_and_monotonic"]

    def serialized(self) -> str:
        """Return a stable value suitable for cohort set membership."""

        return self.model_dump_json()


class OperationalHealthReport(BaseModel):
    """Aggregate health for strict report/trace pairs below one root."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    status: OperationalInputStatus
    compatibility: CompatibilityKey | None
    discovered_run_count: int = Field(ge=0)
    valid_run_count: int = Field(ge=0)
    invalid_run_count: int = Field(ge=0)
    issues: tuple[dict[str, str], ...]
    application_version_counts: dict[str, int]
    categorical_metrics: dict[str, dict[str, int]]
    numeric_metrics: dict[str, JsonObject]
    rates: dict[str, JsonObject]
    per_tool_metrics: dict[str, JsonObject]
    limitations: tuple[str, ...] = _LIMITATIONS

    @model_validator(mode="after")
    def freeze_aggregates(self) -> Self:
        """Deep-freeze nested aggregate mappings after validation."""

        object.__setattr__(
            self,
            "issues",
            tuple(frozen_mapping(issue) for issue in self.issues),
        )
        for field in (
            "application_version_counts",
            "categorical_metrics",
            "numeric_metrics",
            "rates",
            "per_tool_metrics",
        ):
            object.__setattr__(self, field, frozen_mapping(getattr(self, field)))
        return self


class OperationalDriftReport(BaseModel):
    """A compatibility-gated baseline/current comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal[1] = 1
    status: DriftStatus
    compatibility: CompatibilityKey | None
    baseline_valid_run_count: int = Field(ge=0)
    current_valid_run_count: int = Field(ge=0)
    minimum_runs: int = Field(ge=DEFAULT_MINIMUM_RUNS)
    distance_threshold: float = Field(ge=0.0, le=1.0)
    metrics: tuple[JsonObject, ...]
    limitations: tuple[str, ...] = _LIMITATIONS

    @model_validator(mode="after")
    def freeze_metrics(self) -> Self:
        """Deep-freeze each metric document after validation."""

        object.__setattr__(
            self,
            "metrics",
            tuple(frozen_mapping(metric) for metric in self.metrics),
        )
        return self


@dataclass(frozen=True, slots=True)
class _ToolObservation:
    """One identifier-free terminal tool observation."""

    name: str
    status: str
    latency_ms: float | None
    rows_examined: float | None


@dataclass(frozen=True, slots=True)
class _RunMetrics:
    """Internal identifier-free measurements shared by the reducers."""

    identity_ref: str
    compatibility: CompatibilityKey
    application_version: str
    numeric: Mapping[str, float | None]
    categorical: Mapping[str, tuple[str, ...]]
    counters: Mapping[str, int]
    verified: bool
    fallback: bool
    tools: tuple[_ToolObservation, ...]
    attempts: tuple[str, ...]
    retries: tuple[str, ...]


def _percentile(ordered: Sequence[float], quantile: float) -> float:
    """Return a linearly interpolated percentile from ordered values."""

    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def summarize_numeric(values: Sequence[int | float]) -> JsonObject:
    """Summarize finite observations without retaining them publicly."""

    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise ValueError("Operational metrics must be finite")
    if not ordered:
        return {"count": 0}
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "mean": fmean(ordered),
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99),
        "maximum": ordered[-1],
    }


def total_variation_distance(baseline: Sequence[str], current: Sequence[str]) -> float:
    """Return total-variation distance over the union of categories."""

    if not baseline or not current:
        raise ValueError("Total-variation distance requires nonempty samples")
    left, right = Counter(baseline), Counter(current)
    return 0.5 * math.fsum(
        abs(left[key] / len(baseline) - right[key] / len(current))
        for key in set(left).union(right)
    )


def kolmogorov_smirnov_distance(
    baseline: Sequence[int | float], current: Sequence[int | float]
) -> float:
    """Return the exact two-sample empirical KS distance."""

    if not baseline or not current:
        raise ValueError("KS distance requires nonempty samples")
    left, right = sorted(map(float, baseline)), sorted(map(float, current))
    if any(not math.isfinite(value) for value in (*left, *right)):
        raise ValueError("KS samples must be finite")
    return max(
        abs(
            bisect_right(left, value) / len(left)
            - bisect_right(right, value) / len(right)
        )
        for value in set(left).union(right)
    )


def _rate(numerator: int, denominator: int) -> JsonObject:
    """Build an exact rate while preserving an empty denominator."""

    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _content_ref(path: Path) -> str:
    """Hash content into a reference that exposes no path identifier."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        digest.update(b"unreadable-operational-input")
    return digest.hexdigest()[:12]


def _fingerprint(label: str, *values: str) -> str:
    """Hash one domain-separated set of private or unbounded labels."""

    digest = hashlib.sha256(label.encode())
    for value in values:
        encoded = value.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _issue(path: Path, code: str, message: str) -> dict[str, str]:
    """Construct an identifier-minimized loader issue."""

    return {"code": code, "source_ref": _content_ref(path), "message": message}


def _compatibility(report: ReportData) -> CompatibilityKey:
    """Derive compatibility only from recorded report provenance."""

    provenance = report.provenance
    source_hashes = json.dumps(
        dict(sorted(provenance.source_hashes.items())),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return CompatibilityKey(
        report_schema_version=report.schema_version,
        dataset_kind=provenance.dataset_kind,
        dataset_identity_sha256=_fingerprint(
            "dataset",
            provenance.dataset_source_repository,
            provenance.dataset_source_commit,
        ),
        source_hashes_sha256=hashlib.sha256(source_hashes).hexdigest(),
        backend=provenance.backend,
        execution_mode=provenance.execution_mode,
        model_sha256=_fingerprint("model", provenance.model),
        prompt_identity_sha256=_fingerprint(
            "prompt",
            provenance.prompt_version,
            provenance.prompt_hash,
        ),
        timing_mode=provenance.timing_mode,
    )


def _number(details: Mapping[str, JsonValue], key: str) -> float | None:
    """Read one optional finite nonnegative measurement."""

    value = details.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid operational field: {key}")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"Invalid operational field: {key}") from error
    if result < 0.0 or not math.isfinite(result):
        raise ValueError(f"Invalid operational field: {key}")
    return result


def _label(details: Mapping[str, JsonValue], key: str) -> str:
    """Read one required nonempty operational label."""

    value = details.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing operational field: {key}")
    return value


def _complete_sum(values: Sequence[float | None]) -> float | None:
    """Sum a metric only when every expected value was recorded."""

    if not values or any(value is None for value in values):
        return None
    return math.fsum(cast(Sequence[float], values))


def _validate(events: Sequence[AuditEvent], report: ReportData) -> None:
    """Validate lifecycle, order, ownership, status, and provenance."""

    starts = [item for item in events if item.event is AuditEventName.RUN_STARTED]
    ends = [item for item in events if item.event is AuditEventName.RUN_COMPLETED]
    if (
        not events
        or len(starts) != 1
        or len(ends) != 1
        or events[0] is not starts[0]
        or events[-1] is not ends[0]
    ):
        raise ValueError("Invalid run lifecycle")
    if any(b.timestamp < a.timestamp for a, b in pairwise(events)):
        raise ValueError("Nonmonotonic audit timestamps")
    first = events[0]
    if any(
        item.run_id != first.run_id or item.household_id != first.household_id
        for item in events
    ):
        raise ValueError("Mixed audit ownership")
    if (
        report.run_id != str(first.run_id)
        or report.household_id != first.household_id
        or ends[0].details.get("status") != report.run_status.value
    ):
        raise ValueError("Report and trace identity mismatch")
    expected = {
        "model": report.provenance.model,
        "prompt_version": report.provenance.prompt_version,
        "prompt_hash": report.provenance.prompt_hash,
        "dataset_kind": report.provenance.dataset_kind,
        "dataset_source_repository": report.provenance.dataset_source_repository,
        "dataset_source_commit": report.provenance.dataset_source_commit,
        "application_version": report.provenance.application_version,
        "timing_mode": report.provenance.timing_mode,
    }
    if any(starts[0].details.get(key) != value for key, value in expected.items()):
        raise ValueError("Report and trace provenance mismatch")
    pending_model = 0
    pending_verification = 0
    started_tools: set[str] = set()
    verification_passed_at: int | None = None
    for index, event in enumerate(events):
        if event.event is AuditEventName.MODEL_DECISION_REQUESTED:
            if pending_model:
                raise ValueError("Model decisions must remain sequential")
            pending_model += 1
        elif event.event in {
            AuditEventName.MODEL_DECISION_RECEIVED,
            AuditEventName.MODEL_DECISION_REJECTED,
        }:
            if not pending_model:
                raise ValueError("A model result lacks a preceding request")
            pending_model -= 1
        elif event.event is AuditEventName.TOOL_STARTED:
            call_id = _label(event.details, "tool_call_id")
            if call_id in started_tools:
                raise ValueError("A tool call started more than once")
            started_tools.add(call_id)
        elif event.event in _TOOL_EVENTS:
            if event.details.get("duplicate_refused") is True:
                continue
            call_id = _label(event.details, "tool_call_id")
            if call_id not in started_tools:
                raise ValueError("A tool result lacks a preceding start")
            started_tools.remove(call_id)
        elif event.event is AuditEventName.VERIFICATION_STARTED:
            if pending_verification:
                raise ValueError("Verification attempts must remain sequential")
            pending_verification += 1
        elif event.event in {
            AuditEventName.VERIFICATION_REJECTED,
            AuditEventName.VERIFICATION_PASSED,
        }:
            if not pending_verification:
                raise ValueError("A verification result lacks a preceding start")
            pending_verification -= 1
            if event.event is AuditEventName.VERIFICATION_PASSED:
                if verification_passed_at is not None:
                    raise ValueError("A run cannot pass verification more than once")
                verification_passed_at = index
    if started_tools or pending_verification:
        raise ValueError("The trace contains an unfinished operation")
    if pending_model and report.run_status is not RunStatus.FAILED:
        raise ValueError("A terminal result cannot leave a model request open")
    if verification_passed_at is not None and verification_passed_at != len(events) - 2:
        raise ValueError("Verification must pass immediately before completion")
    if (report.run_status is RunStatus.FAILED) == (verification_passed_at is not None):
        raise ValueError("Terminal status and verification outcome disagree")


def _issue_codes(events: Sequence[AuditEvent]) -> tuple[str, ...]:
    """Extract verifier codes without retaining issue messages."""

    result: list[str] = []
    for event in events:
        issues = (
            event.details.get("issues")
            if event.event is AuditEventName.VERIFICATION_REJECTED
            else None
        )
        if not isinstance(issues, Sequence) or isinstance(issues, str):
            continue
        for issue in issues:
            code = issue.get("code") if isinstance(issue, Mapping) else None
            if isinstance(code, str) and code:
                result.append(VerificationIssueCode(code).value)
    return tuple(result)


def _build_run(events: Sequence[AuditEvent], report: ReportData) -> _RunMetrics:
    """Reduce a strict pair to identifier-free measurements."""

    _validate(events, report)
    received = [
        item for item in events if item.event is AuditEventName.MODEL_DECISION_RECEIVED
    ]
    inputs = _complete_sum([_number(item.details, "input_tokens") for item in received])
    outputs = _complete_sum(
        [_number(item.details, "output_tokens") for item in received]
    )
    tools = tuple(
        _ToolObservation(
            name=ToolName(_label(item.details, "tool_name")).value,
            status=ToolStatus(_label(item.details, "status")).value,
            latency_ms=_number(item.details, "latency_ms"),
            rows_examined=_number(item.details, "rows_examined"),
        )
        for item in events
        if item.event in _TOOL_EVENTS
    )
    attempts = tuple(
        ToolName(_label(item.details, "tool_name")).value
        for item in events
        if item.event is AuditEventName.TOOL_STARTED
    )
    retries = tuple(
        ToolName(_label(item.details, "tool_name")).value
        for item in events
        if item.event is AuditEventName.RETRY_SCHEDULED
    )
    status = report.run_status.value
    numeric: dict[str, float | None] = {
        "run_duration_ms": (events[-1].timestamp - events[0].timestamp).total_seconds()
        * 1000,
        "model_requests_per_run": float(
            sum(
                item.event is AuditEventName.MODEL_DECISION_REQUESTED for item in events
            )
        ),
        "model_received_per_run": float(len(received)),
        "model_rejected_per_run": float(
            sum(item.event is AuditEventName.MODEL_DECISION_REJECTED for item in events)
        ),
        "recorded_model_latency_ms_per_run": _complete_sum(
            [_number(item.details, "latency_ms") for item in received]
        ),
        "recorded_input_tokens_per_run": inputs,
        "recorded_output_tokens_per_run": outputs,
        "recorded_io_tokens_per_run": (
            inputs + outputs if inputs is not None and outputs is not None else None
        ),
        "tool_attempts_per_run": float(len(attempts)),
        "tool_retries_per_run": float(len(retries)),
        "recorded_tool_latency_ms_per_run": _complete_sum(
            [item.latency_ms for item in tools]
        ),
        "recorded_rows_examined_per_run": _complete_sum(
            [item.rows_examined for item in tools]
        ),
        "verification_rejections_per_run": float(
            sum(item.event is AuditEventName.VERIFICATION_REJECTED for item in events)
        ),
        "evidence_added_per_run": float(
            sum(item.event is AuditEventName.EVIDENCE_ADDED for item in events)
        ),
    }
    return _RunMetrics(
        identity_ref=hashlib.sha256(report.run_id.encode()).hexdigest(),
        compatibility=_compatibility(report),
        application_version=report.provenance.application_version,
        numeric=numeric,
        categorical={
            "run_status": (status,),
            "final_action": (
                report.action.action_id.value if report.action is not None else "none",
            ),
            "tool_name": tuple(item.name for item in tools),
            "tool_status": tuple(item.status for item in tools),
            "verification_issue_code": _issue_codes(events),
        },
        counters={
            "model_requests": int(numeric["model_requests_per_run"] or 0),
            "model_rejections": int(numeric["model_rejected_per_run"] or 0),
            "tool_attempts": len(attempts),
            "tool_retries": len(retries),
            "tool_partials": sum(
                item.status == ToolStatus.PARTIAL.value for item in tools
            ),
            "tool_errors": sum(item.status in _ERROR_STATUSES for item in tools),
            "tool_outcomes": len(tools),
            "verification_rejections": int(
                numeric["verification_rejections_per_run"] or 0
            ),
        },
        verified=(
            report.run_status is not RunStatus.FAILED
            and any(item.event is AuditEventName.VERIFICATION_PASSED for item in events)
        ),
        fallback=any(
            item.details.get("deterministic_fallback") is True for item in events
        ),
        tools=tools,
        attempts=attempts,
        retries=retries,
    )


def _discover(root: Path) -> tuple[Path, ...]:
    """Find traces recursively, or accept one explicit regular trace."""

    if root.is_file():
        if root.name != "trace.jsonl" or root.is_symlink():
            raise ValueError("Explicit input must be a regular trace.jsonl")
        return (root,)
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError("Artifact root is unavailable")
    directories = {
        path.parent
        for filename in ("trace.jsonl", "report.json")
        for path in root.rglob(filename)
        if path.is_file() or path.is_symlink()
    }
    return tuple(
        directory / "trace.jsonl"
        for directory in sorted(directories, key=lambda path: path.as_posix())
    )


def _load(
    root: Path,
) -> tuple[tuple[_RunMetrics, ...], tuple[dict[str, str], ...], int]:
    """Load pairs while converting unsafe inputs to minimized issues."""

    traces = _discover(root)
    records: list[_RunMetrics] = []
    issues: list[dict[str, str]] = []
    identities: set[str] = set()
    for trace in traces:
        report_path = trace.with_name("report.json")
        if not trace.is_file() or trace.is_symlink():
            issues.append(
                _issue(report_path, "missing_trace", "A report lacks a regular trace.")
            )
            continue
        if not report_path.is_file() or report_path.is_symlink():
            issues.append(
                _issue(trace, "missing_report", "A trace lacks a regular report.")
            )
            continue
        try:
            events = read_audit_events(trace)
            report = ReportData.model_validate_json(
                report_path.read_text(encoding="utf-8")
            )
            record = _build_run(events, report)
            if record.identity_ref in identities:
                issues.append(
                    _issue(
                        trace,
                        "duplicate_run",
                        "A duplicate run identity was excluded from the cohort.",
                    )
                )
                continue
            identities.add(record.identity_ref)
            records.append(record)
        except (
            OSError,
            UnicodeError,
            AuditTraceReadError,
            ValidationError,
            ValueError,
        ):
            issues.append(
                _issue(trace, "invalid_pair", "A pair failed strict validation.")
            )
    return tuple(records), tuple(issues), len(traces)


def _counts(values: Sequence[str]) -> dict[str, int]:
    """Return stable category counts."""

    return dict(sorted(Counter(values).items()))


def _tools(records: Sequence[_RunMetrics]) -> dict[str, JsonObject]:
    """Build per-tool aggregates without retaining call identifiers."""

    result: dict[str, JsonObject] = {}
    for tool in ToolName:
        observed = [
            item
            for record in records
            for item in record.tools
            if item.name == tool.value
        ]
        attempts = sum(record.attempts.count(tool.value) for record in records)
        retries = sum(record.retries.count(tool.value) for record in records)
        if observed or attempts or retries:
            result[tool.value] = cast(
                JsonObject,
                {
                    "attempts": attempts,
                    "retries": retries,
                    "status_counts": _counts([item.status for item in observed]),
                    "latency_ms": summarize_numeric(
                        [
                            item.latency_ms
                            for item in observed
                            if item.latency_ms is not None
                        ]
                    ),
                    "rows_examined": summarize_numeric(
                        [
                            item.rows_examined
                            for item in observed
                            if item.rows_examined is not None
                        ]
                    ),
                },
            )
    return result


def _health(
    records: Sequence[_RunMetrics],
    issues: Sequence[dict[str, str]],
    discovered: int,
) -> OperationalHealthReport:
    """Reduce loaded records to the public health boundary."""

    keys = {record.compatibility.serialized() for record in records}
    compatibility = records[0].compatibility if len(keys) == 1 else None
    public_issues = list(issues)
    if not discovered:
        public_issues.append(
            {
                "code": "no_traces",
                "source_ref": hashlib.sha256(b"empty-root").hexdigest()[:12],
                "message": "No trace.jsonl inputs were discovered.",
            }
        )
    if len(keys) > 1:
        public_issues.append(
            {
                "code": "mixed_compatibility",
                "source_ref": hashlib.sha256(b"mixed-cohort").hexdigest()[:12],
                "message": "Valid runs contain multiple compatibility keys.",
            }
        )
    status = (
        OperationalInputStatus.INVALID
        if not records
        else OperationalInputStatus.MIXED_COHORT
        if len(keys) > 1
        else OperationalInputStatus.PARTIAL
        if issues
        else OperationalInputStatus.READY
    )
    categories = {
        name: [value for record in records for value in record.categorical[name]]
        for name in (
            "run_status",
            "final_action",
            "tool_name",
            "tool_status",
            "verification_issue_code",
        )
    }
    numeric = (
        {
            name: [
                value
                for record in records
                if (value := record.numeric[name]) is not None
            ]
            for name in records[0].numeric
        }
        if records
        else {}
    )

    def total(key: str) -> int:
        """Sum one internal counter across valid records."""

        return sum(record.counters[key] for record in records)

    valid = len(records)
    statuses = categories["run_status"]
    return OperationalHealthReport(
        status=status,
        compatibility=compatibility,
        discovered_run_count=discovered,
        valid_run_count=valid,
        invalid_run_count=discovered - valid,
        issues=tuple(public_issues),
        application_version_counts=_counts(
            [
                _fingerprint("application-version", item.application_version)[:12]
                for item in records
            ]
        ),
        categorical_metrics={
            name: _counts(values) for name, values in categories.items()
        },
        numeric_metrics={
            name: summarize_numeric(values) for name, values in numeric.items()
        },
        rates={
            "valid_input_rate": _rate(valid, discovered),
            "verified_terminal_rate": _rate(
                sum(item.verified for item in records), valid
            ),
            "actionable_completion_rate": _rate(
                statuses.count(RunStatus.COMPLETED.value), valid
            ),
            "insufficient_evidence_rate": _rate(
                statuses.count(RunStatus.INSUFFICIENT_EVIDENCE.value), valid
            ),
            "failed_run_rate": _rate(statuses.count(RunStatus.FAILED.value), valid),
            "model_rejection_rate": _rate(
                total("model_rejections"), total("model_requests")
            ),
            "model_usage_coverage_rate": _rate(
                sum(
                    item.numeric["recorded_io_tokens_per_run"] is not None
                    for item in records
                ),
                valid,
            ),
            "tool_retry_rate": _rate(total("tool_retries"), total("tool_attempts")),
            "tool_partial_rate": _rate(total("tool_partials"), total("tool_outcomes")),
            "tool_error_rate": _rate(total("tool_errors"), total("tool_outcomes")),
            "verification_rejection_run_rate": _rate(
                sum(item.counters["verification_rejections"] > 0 for item in records),
                valid,
            ),
            "deterministic_fallback_run_rate": _rate(
                sum(item.fallback for item in records), valid
            ),
        },
        per_tool_metrics=_tools(records),
    )


def summarize_operational_health(root: Path) -> OperationalHealthReport:
    """Read one root and return identifier-minimized health."""

    return _health(*_load(root))


def _metric(
    name: str,
    kind: Literal["numeric_ks", "categorical_tv"],
    baseline: Sequence[float] | Sequence[str],
    current: Sequence[float] | Sequence[str],
    minimum: int,
    threshold: float,
) -> JsonObject:
    """Assess one metric or state its sample-size limitation."""

    common: JsonObject = {
        "name": name,
        "kind": kind,
        "baseline_count": len(baseline),
        "current_count": len(current),
        "threshold": threshold,
    }
    if len(baseline) < minimum or len(current) < minimum:
        return {
            **common,
            "distance": None,
            "status": "insufficient",
            "reason": f"Both cohorts require at least {minimum} observations.",
        }
    distance = (
        kolmogorov_smirnov_distance(
            cast(Sequence[float], baseline), cast(Sequence[float], current)
        )
        if kind == "numeric_ks"
        else total_variation_distance(
            cast(Sequence[str], baseline), cast(Sequence[str], current)
        )
    )
    return {
        **common,
        "distance": distance,
        "status": (
            "detected"
            if distance > threshold
            or math.isclose(distance, threshold, rel_tol=1e-12, abs_tol=1e-12)
            else "stable"
        ),
        "reason": None,
    }


def compare_operational_cohorts(
    baseline_root: Path,
    current_root: Path,
    *,
    minimum_runs: int = DEFAULT_MINIMUM_RUNS,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> OperationalDriftReport:
    """Compare homogeneous roots after strict compatibility gating."""

    if minimum_runs < DEFAULT_MINIMUM_RUNS:
        raise ValueError("minimum_runs cannot be lower than 20")
    if not math.isfinite(distance_threshold) or not 0.0 <= distance_threshold <= 1.0:
        raise ValueError("distance_threshold must be in the closed unit interval")
    baseline, baseline_issues, baseline_count = _load(baseline_root)
    current, current_issues, current_count = _load(current_root)
    left = _health(baseline, baseline_issues, baseline_count)
    right = _health(current, current_issues, current_count)
    compatibility = (
        left.compatibility if left.compatibility == right.compatibility else None
    )
    if (
        left.status is OperationalInputStatus.MIXED_COHORT
        or (right.status is OperationalInputStatus.MIXED_COHORT)
        or (
            left.compatibility is not None
            and right.compatibility is not None
            and compatibility is None
        )
    ):
        status = DriftStatus.INCOMPATIBLE
    elif (
        left.status is not OperationalInputStatus.READY
        or right.status is not OperationalInputStatus.READY
        or compatibility is None
        or len(baseline) < minimum_runs
        or len(current) < minimum_runs
    ):
        status = DriftStatus.INSUFFICIENT
    else:
        status = DriftStatus.STABLE
    if status is not DriftStatus.STABLE:
        return OperationalDriftReport(
            status=status,
            compatibility=compatibility,
            baseline_valid_run_count=len(baseline),
            current_valid_run_count=len(current),
            minimum_runs=minimum_runs,
            distance_threshold=distance_threshold,
            metrics=(),
        )

    metrics: list[JsonObject] = []
    for name in baseline[0].numeric:
        metrics.append(
            _metric(
                name,
                "numeric_ks",
                [
                    value
                    for item in baseline
                    if (value := item.numeric[name]) is not None
                ],
                [
                    value
                    for item in current
                    if (value := item.numeric[name]) is not None
                ],
                minimum_runs,
                distance_threshold,
            )
        )
    for name in baseline[0].categorical:
        metrics.append(
            _metric(
                name,
                "categorical_tv",
                [value for item in baseline for value in item.categorical[name]],
                [value for item in current for value in item.categorical[name]],
                minimum_runs,
                distance_threshold,
            )
        )
    assessed = [item for item in metrics if item["status"] != "insufficient"]
    status = (
        DriftStatus.DETECTED
        if any(item["status"] == "detected" for item in assessed)
        else DriftStatus.STABLE
        if assessed
        else DriftStatus.INSUFFICIENT
    )
    return OperationalDriftReport(
        status=status,
        compatibility=compatibility,
        baseline_valid_run_count=len(baseline),
        current_valid_run_count=len(current),
        minimum_runs=minimum_runs,
        distance_threshold=distance_threshold,
        metrics=tuple(metrics),
    )


__all__ = [
    "DEFAULT_DISTANCE_THRESHOLD",
    "DEFAULT_MINIMUM_RUNS",
    "CompatibilityKey",
    "DriftStatus",
    "OperationalDriftReport",
    "OperationalHealthReport",
    "OperationalInputStatus",
    "compare_operational_cohorts",
    "kolmogorov_smirnov_distance",
    "summarize_numeric",
    "summarize_operational_health",
    "total_variation_distance",
]
