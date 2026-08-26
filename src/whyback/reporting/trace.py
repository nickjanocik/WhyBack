"""Render append-only WhyBack JSONL traces as self-contained static HTML."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import JsonValue

from whyback.observability import AuditEvent, AuditEventName, read_audit_events
from whyback.reporting.models import TraceEventData, TraceViewData

_TEMPLATE_DIRECTORY: Final = Path(__file__).with_name("templates")
_EVENT_TITLES: Final = {
    AuditEventName.RUN_STARTED: "Investigation started",
    AuditEventName.MODEL_DECISION_REQUESTED: "Decision requested",
    AuditEventName.MODEL_DECISION_RECEIVED: "Decision received",
    AuditEventName.TOOL_REQUESTED: "Analytical tool requested",
    AuditEventName.TOOL_STARTED: "Tool attempt started",
    AuditEventName.TOOL_COMPLETED: "Tool completed",
    AuditEventName.TOOL_PARTIAL: "Tool returned partial evidence",
    AuditEventName.TOOL_FAILED: "Tool failed",
    AuditEventName.RETRY_SCHEDULED: "Bounded retry scheduled",
    AuditEventName.EVIDENCE_ADDED: "Evidence added to ledger",
    AuditEventName.FINISH_REQUESTED: "Finish proposed",
    AuditEventName.VERIFICATION_STARTED: "Deterministic verification started",
    AuditEventName.VERIFICATION_REJECTED: "Verification rejected proposal",
    AuditEventName.VERIFICATION_PASSED: "Verification passed",
    AuditEventName.RUN_COMPLETED: "Investigation completed",
}


def _category(name: AuditEventName) -> str:
    """Map an audit event to the timeline section used by the trace viewer."""

    if name in {
        AuditEventName.MODEL_DECISION_REQUESTED,
        AuditEventName.MODEL_DECISION_RECEIVED,
        AuditEventName.FINISH_REQUESTED,
    }:
        return "decision"
    if name in {
        AuditEventName.TOOL_REQUESTED,
        AuditEventName.TOOL_STARTED,
        AuditEventName.TOOL_COMPLETED,
        AuditEventName.TOOL_PARTIAL,
        AuditEventName.TOOL_FAILED,
    }:
        return "tool"
    if name is AuditEventName.RETRY_SCHEDULED:
        return "retry"
    if name is AuditEventName.EVIDENCE_ADDED:
        return "evidence"
    if name in {
        AuditEventName.VERIFICATION_STARTED,
        AuditEventName.VERIFICATION_REJECTED,
        AuditEventName.VERIFICATION_PASSED,
    }:
        return "verifier"
    return "run"


def _first_string(
    details: Mapping[str, JsonValue], keys: tuple[str, ...]
) -> str | None:
    """Return the first nonempty string stored under the preferred detail keys."""

    for key in keys:
        value = details.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_number(
    details: Mapping[str, JsonValue], keys: tuple[str, ...]
) -> float | None:
    """Return the first numeric, non-boolean value under the preferred keys."""

    for key in keys:
        value = details.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _string_tuple(value: JsonValue | None) -> tuple[str, ...]:
    """Normalize a string or string-valued JSON list into an immutable tuple."""

    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _evidence_ids(details: Mapping[str, JsonValue]) -> tuple[str, ...]:
    """Extract the first supported evidence-ID representation from event details."""

    for key in ("evidence_ids", "added_evidence_ids", "supporting_evidence_ids"):
        values = _string_tuple(details.get(key))
        if values:
            return values
    evidence_id = _first_string(details, ("evidence_id",))
    return (evidence_id,) if evidence_id else ()


def _retry_label(name: AuditEventName, details: Mapping[str, JsonValue]) -> str | None:
    """Describe the scheduled attempt for retry events only."""

    if name is not AuditEventName.RETRY_SCHEDULED:
        return None
    attempt = details.get("attempt") or details.get("next_attempt")
    return f"retry attempt {attempt}" if isinstance(attempt, int) else "retry scheduled"


def _verifier_label(name: AuditEventName) -> str | None:
    """Reduce verifier lifecycle events to the status shown in the timeline."""

    if name is AuditEventName.VERIFICATION_PASSED:
        return "passed"
    if name is AuditEventName.VERIFICATION_REJECTED:
        return "rejected"
    if name is AuditEventName.VERIFICATION_STARTED:
        return "started"
    return None


def build_trace_view(events: Sequence[AuditEvent]) -> TraceViewData:
    """Build a chronological viewer boundary from validated audit events."""

    rendered: list[TraceEventData] = []
    final_action: str | None = None
    verifier_status = "not recorded"
    for sequence, event in enumerate(events, start=1):
        details = event.details
        event_action = _first_string(
            details,
            ("next_best_action_id", "action_id", "final_action"),
        )
        if event_action:
            final_action = event_action
        verifier_label = _verifier_label(event.event)
        if verifier_label:
            verifier_status = verifier_label
        rendered.append(
            TraceEventData(
                sequence=sequence,
                timestamp=event.timestamp.isoformat().replace("+00:00", "Z"),
                event=event.event.value,
                category=_category(event.event),
                title=_EVENT_TITLES[event.event],
                tool_name=_first_string(
                    details,
                    ("tool_name", "selected_tool", "tool"),
                ),
                status=_first_string(
                    details,
                    ("status", "final_status", "run_status"),
                ),
                latency_ms=_first_number(details, ("elapsed_ms", "latency_ms")),
                evidence_ids=_evidence_ids(details),
                retry_label=_retry_label(event.event, details),
                verifier_label=verifier_label,
                final_action=event_action,
                details=dict(details),
            )
        )
    first = events[0] if events else None
    return TraceViewData(
        run_id=str(first.run_id) if first else None,
        household_id=first.household_id if first else None,
        event_count=len(events),
        decision_count=sum(
            event.event is AuditEventName.MODEL_DECISION_RECEIVED for event in events
        ),
        tool_attempt_count=sum(
            event.event is AuditEventName.TOOL_STARTED for event in events
        ),
        retry_count=sum(
            event.event is AuditEventName.RETRY_SCHEDULED for event in events
        ),
        verifier_status=verifier_status,
        final_action=final_action,
        events=tuple(rendered),
    )


def _pretty_json(value: object) -> str:
    """Format arbitrary event details for readable display in the HTML trace."""

    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def render_trace_html(events_or_path: Sequence[AuditEvent] | Path) -> str:
    """Read a trace when needed and render an offline, self-contained viewer."""

    events = (
        read_audit_events(events_or_path)
        if isinstance(events_or_path, Path)
        else tuple(events_or_path)
    )
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIRECTORY),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    environment.filters["pretty_json"] = _pretty_json
    return environment.get_template("trace.html.j2").render(
        trace=build_trace_view(events)
    )


def write_trace_html(trace_path: Path, output_path: Path) -> Path:
    """Render a JSONL trace into a sibling-independent local HTML file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_trace_html(trace_path), encoding="utf-8")
    return output_path
