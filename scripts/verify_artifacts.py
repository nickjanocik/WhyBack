"""Fail-closed verification for reviewer-facing WhyBack artifacts.

The verifier deliberately checks portable files without running an investigation.
It validates strict report and audit schemas, evidence references, execution-mode
labels, and every file digest declared by an artifact manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from whyback.observability import AuditEvent, AuditEventName, read_audit_events
from whyback.reporting.models import ReportData
from whyback.tools.contracts import SUCCESS_STATUSES

ExecutionMode = Literal["scripted", "live", "skipped"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPORT_NAMES = frozenset({"report.json", "customer_report.json"})
_BRANDING = (
    "WhyBack",
    "Find the why. Choose the way back.",
    "WhyBack Investigator",
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


def _validate_rendered_report(path: Path, root: Path) -> list[VerificationIssue]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [_issue(path, root, "unreadable_report", str(error))]
    missing = [item for item in _BRANDING[:2] if item not in text]
    if "human review" not in text.casefold():
        missing.append("human review")
    if not missing:
        return []
    return [
        _issue(
            path,
            root,
            "rendered_report_incomplete",
            "Rendered report is missing: " + ", ".join(missing),
        )
    ]


def _trace_execution_mode(events: Sequence[AuditEvent]) -> ExecutionMode | None:
    if not events:
        return None
    model = events[0].details.get("model")
    if not isinstance(model, str):
        return None
    return "scripted" if model.startswith("scripted/") else "live"


def _validate_trace(
    path: Path,
    root: Path,
    reports_by_run: Mapping[str, ReportData],
) -> tuple[ExecutionMode | None, list[VerificationIssue]]:
    try:
        events = read_audit_events(path)
    except (OSError, ValueError) as error:
        return None, [
            _issue(path, root, "malformed_trace", f"Trace validation failed: {error}")
        ]
    if not events:
        return None, [_issue(path, root, "empty_trace", "Trace has no events")]

    issues: list[VerificationIssue] = []
    run_ids = {str(event.run_id) for event in events}
    households = {event.household_id for event in events}
    if len(run_ids) != 1 or len(households) != 1:
        issues.append(
            _issue(
                path,
                root,
                "mixed_trace_identity",
                "One trace must contain exactly one run and household",
            )
        )
    if events[0].event is not AuditEventName.RUN_STARTED:
        issues.append(
            _issue(path, root, "trace_start_missing", "First event is not run_started")
        )
    if events[-1].event is not AuditEventName.RUN_COMPLETED:
        issues.append(
            _issue(
                path,
                root,
                "trace_completion_missing",
                "Last event is not run_completed",
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

    run_id = str(events[0].run_id)
    report = reports_by_run.get(run_id)
    if report is not None:
        ledger_ids = {item.evidence_id for item in report.evidence_ledger}
        evidence_bearing_events = {
            AuditEventName.TOOL_COMPLETED,
            AuditEventName.TOOL_PARTIAL,
            AuditEventName.EVIDENCE_ADDED,
            AuditEventName.VERIFICATION_PASSED,
            AuditEventName.RUN_COMPLETED,
        }
        for event in events:
            # A rejected finish proposal may intentionally cite an unsupported ID;
            # that is verifier evidence, not accepted report evidence.
            if event.event not in evidence_bearing_events:
                continue
            referenced: list[str] = []
            for key in (
                "evidence_id",
                "evidence_ids",
                "added_evidence_ids",
                "supporting_evidence_ids",
                "counterevidence_ids",
            ):
                raw = event.details.get(key)
                if isinstance(raw, str):
                    referenced.append(raw)
                elif isinstance(raw, list):
                    referenced.extend(item for item in raw if isinstance(item, str))
            for evidence_id in referenced:
                if evidence_id not in ledger_ids:
                    issues.append(
                        _issue(
                            path,
                            root,
                            "trace_evidence_mismatch",
                            f"Trace references {evidence_id!r} outside its "
                            "report ledger",
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
            or not model.startswith("gpt-")
            or not provider_ids
            or any(
                not isinstance(value, str) or not value.startswith("resp_")
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
    return mode, issues


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


def _validate_manifest(
    path: Path, root: Path, value: object
) -> tuple[set[ExecutionMode], list[VerificationIssue]]:
    if not isinstance(value, Mapping):
        return set(), [
            _issue(path, root, "malformed_manifest", "Manifest root must be an object")
        ]
    data = cast(Mapping[str, object], value)
    modes: set[ExecutionMode] = set()
    issues: list[VerificationIssue] = []
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
        return modes, [
            *issues,
            _issue(
                path,
                root,
                "malformed_manifest",
                "Manifest has no recognized artifact, data, or status records",
            ),
        ]

    if isinstance(records, Mapping):
        for relative_path, expected_hash in records.items():
            issues.extend(
                _validate_hash_record(path, root, relative_path, expected_hash)
            )
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
            issues.extend(
                _validate_hash_record(
                    path,
                    root,
                    record.get("path") or record.get("filename"),
                    record.get("sha256"),
                )
            )
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
    return modes, issues


def verify_artifact_tree(
    root: Path,
    *,
    allow_live_skipped: bool = False,
) -> ArtifactVerificationResult:
    """Validate a complete artifact tree without mutating it."""

    root = root.resolve()
    if not root.is_dir():
        issue = VerificationIssue(
            ".", "artifact_root_missing", f"Artifact directory does not exist: {root}"
        )
        return ArtifactVerificationResult(str(root), (), (), (issue,))

    files = tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    )
    issues: list[VerificationIssue] = []
    if not files:
        issues.append(
            VerificationIssue(".", "artifact_tree_empty", "Artifact tree is empty")
        )
    reports: dict[str, ReportData] = {}
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
                reports[report.run_id] = report

    for path, value in parsed_json.items():
        if "manifest" in path.stem.casefold() or "status" in path.stem.casefold():
            found_modes, manifest_issues = _validate_manifest(path, root, value)
            modes.update(found_modes)
            issues.extend(manifest_issues)

    if not any("manifest" in path.stem.casefold() for path in parsed_json):
        issues.append(
            VerificationIssue(
                ".", "artifact_manifest_missing", "No artifact manifest was found"
            )
        )
    trace_modes: set[ExecutionMode] = set()
    trace_count = 0
    for path in files:
        suffix = path.suffix.casefold()
        if suffix == ".jsonl":
            trace_count += 1
            trace_mode, trace_issues = _validate_trace(path, root, reports)
            issues.extend(trace_issues)
            if trace_mode is not None:
                trace_modes.add(trace_mode)
        elif suffix in {".md", ".html"} and "report" in path.stem.casefold():
            issues.extend(_validate_rendered_report(path, root))
    modes.update(trace_modes)

    skip_only = allow_live_skipped and bool(modes) and modes <= {"skipped"}
    if not reports and not skip_only:
        issues.append(
            VerificationIssue(
                ".",
                "validated_report_missing",
                "No valid WhyBack JSON report was found",
            )
        )
    if trace_count == 0 and not skip_only:
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
    if allow_live_skipped:
        if "live" in modes:
            issues.append(
                VerificationIssue(
                    ".",
                    "live_output_with_absent_credentials",
                    "Live output cannot be accepted when credentials are "
                    "declared absent",
                )
            )
    elif "skipped" in modes:
        issues.append(
            VerificationIssue(
                ".",
                "unacknowledged_live_skip",
                "Use --allow-live-skipped to acknowledge absent live credentials",
            )
        )

    # A credential is never read or recorded. This warning only catches the
    # contradictory case where CI says credentials are absent while one is set.
    if allow_live_skipped and os.getenv("OPENAI_API_KEY"):
        issues.append(
            VerificationIssue(
                ".",
                "credential_mode_conflict",
                "--allow-live-skipped was used while OPENAI_API_KEY is present",
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
            "Declare that live credentials are absent; reject any live-labeled output."
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
