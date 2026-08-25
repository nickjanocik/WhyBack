from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from whyback.observability import (
    REDACTED_VALUE,
    AuditEvent,
    AuditEventName,
    AuditJsonlWriter,
    SecretHandling,
    UnsafeAuditDetailError,
    read_audit_events,
    sanitize_details,
)

RUN_ID = UUID("00000000-0000-0000-0000-000000000001")


def _event(name: AuditEventName, *, step: int) -> AuditEvent:
    return AuditEvent(
        timestamp=datetime(2026, 8, 24, 12, step, tzinfo=UTC),
        event=name,
        run_id=RUN_ID,
        household_id="181",
        details={"step": step, "summary": f"external summary {step}"},
    )


def test_writer_appends_compact_valid_jsonl_in_order(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    expected = (
        _event(AuditEventName.RUN_STARTED, step=0),
        _event(AuditEventName.TOOL_COMPLETED, step=1),
        _event(AuditEventName.RUN_COMPLETED, step=2),
    )

    with AuditJsonlWriter(path, flush=True, fsync=False) as writer:
        for event in expected:
            writer.append(event)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert all(line == line.strip() and "\n" not in line for line in lines)
    assert [json.loads(line)["event"] for line in lines] == [
        event.event.value for event in expected
    ]
    assert read_audit_events(path) == expected


def test_reopening_writer_never_overwrites_existing_trace(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    first = _event(AuditEventName.RUN_STARTED, step=0)
    second = _event(AuditEventName.RUN_COMPLETED, step=1)

    with AuditJsonlWriter(path) as writer:
        writer.append(first)
    with AuditJsonlWriter(path) as writer:
        writer.append(second)

    assert read_audit_events(path) == (first, second)


def test_sanitizer_recursively_redacts_secret_keys_and_values() -> None:
    details = sanitize_details(
        {
            "provider": "openai",
            "api_key": "do-not-write-me",
            "nested": {
                "authorization": "Bearer do-not-write-me-either",
                "safe": ["summary", "sk-1234567890abcdefghijklmnop"],
            },
        }
    )

    assert details == {
        "provider": "openai",
        "api_key": REDACTED_VALUE,
        "nested": {
            "authorization": REDACTED_VALUE,
            "safe": ["summary", REDACTED_VALUE],
        },
    }


def test_sanitizer_redacts_gemini_and_legacy_openai_api_key_fields() -> None:
    details = sanitize_details(
        {
            "gemini_api_key": "gemini-placeholder-secret",
            "openai_api_key": "legacy-placeholder-secret",
        }
    )

    assert details == {
        "gemini_api_key": REDACTED_VALUE,
        "openai_api_key": REDACTED_VALUE,
    }


def test_sanitizer_can_reject_secrets_and_always_rejects_hidden_reasoning() -> None:
    with pytest.raises(UnsafeAuditDetailError, match="secret-like audit field"):
        sanitize_details(
            {"password": "value"},
            secret_handling=SecretHandling.REJECT,
        )

    for key in (
        "chain_of_thought",
        "thought_process",
        "reasoning_trace",
        "deliberation",
        "internal_analysis",
        "private_thoughts",
    ):
        with pytest.raises(ValidationError, match="hidden reasoning"):
            AuditEvent(
                event=AuditEventName.MODEL_DECISION_RECEIVED,
                run_id=RUN_ID,
                household_id="181",
                details={key: "must never be persisted"},
            )


def test_audit_event_normalizes_aware_timestamp_to_utc() -> None:
    event = AuditEvent(
        timestamp=datetime(
            2026,
            8,
            24,
            7,
            tzinfo=timezone(-timedelta(hours=5)),
        ),
        event=AuditEventName.RUN_STARTED,
        run_id=RUN_ID,
        household_id="181",
    )

    assert event.timestamp == datetime(2026, 8, 24, 12, tzinfo=UTC)
    assert event.timestamp.utcoffset() == timedelta(0)


def test_audit_event_is_strict_and_immutable() -> None:
    event = _event(AuditEventName.RUN_STARTED, step=0)

    with pytest.raises(ValidationError, match="Instance is frozen"):
        event.household_id = "changed"
    with pytest.raises(TypeError, match="immutable"):
        event.details["chain_of_thought"] = "must never be persisted"
    with pytest.raises(ValidationError):
        AuditEvent.model_validate(
            {
                "event": AuditEventName.RUN_STARTED,
                "run_id": str(RUN_ID),
                "household_id": "181",
            }
        )


def test_writer_revalidates_an_event_at_the_persistence_boundary(
    tmp_path: Path,
) -> None:
    event = _event(AuditEventName.RUN_STARTED, step=0)
    # Simulate an exotic caller bypassing the public immutable interface.
    dict.__setitem__(event.details, "api_key", "plaintext-secret")

    path = tmp_path / "trace.jsonl"
    with AuditJsonlWriter(path) as writer:
        writer.append(event)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["details"]["api_key"] == REDACTED_VALUE
