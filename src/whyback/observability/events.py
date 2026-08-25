"""Typed, sanitized events for WhyBack's append-only audit trace."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Self, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from whyback.immutability import frozen_mapping

REDACTED_VALUE = "[REDACTED]"


class AuditEventName(StrEnum):
    """The complete vocabulary of auditable WhyBack lifecycle events."""

    RUN_STARTED = "run_started"
    MODEL_DECISION_REQUESTED = "model_decision_requested"
    MODEL_DECISION_RECEIVED = "model_decision_received"
    TOOL_REQUESTED = "tool_requested"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_PARTIAL = "tool_partial"
    TOOL_FAILED = "tool_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    EVIDENCE_ADDED = "evidence_added"
    FINISH_REQUESTED = "finish_requested"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_REJECTED = "verification_rejected"
    VERIFICATION_PASSED = "verification_passed"
    RUN_COMPLETED = "run_completed"


class SecretHandling(StrEnum):
    """How the sanitizer handles a field whose key looks sensitive."""

    REDACT = "redact"
    REJECT = "reject"


class UnsafeAuditDetailError(ValueError):
    """Audit details contained secrets, hidden reasoning, or non-JSON data."""


_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "client_secret",
        "clientsecret",
        "cookie",
        "credential",
        "credentials",
        "gemini_api_key",
        "openai_api_key",
        "password",
        "passwd",
        "private_key",
        "privatekey",
        "refresh_token",
        "refreshtoken",
        "secret",
        "set_cookie",
        "token",
        "access_token",
        "accesstoken",
    }
)
_SECRET_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_client_secret",
    "_cookie",
    "_credentials",
    "_password",
    "_private_key",
    "_refresh_token",
    "_secret",
    "_access_token",
)
_HIDDEN_REASONING_KEYS = frozenset(
    {
        "analysis",
        "chain_of_thought",
        "chainofthought",
        "hidden_reasoning",
        "hiddenreasoning",
        "internal_analysis",
        "internal_reasoning",
        "internalreasoning",
        "deliberation",
        "private_thoughts",
        "reasoning",
        "reasoning_trace",
        "scratchpad",
        "thought_process",
    }
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9_-]{30,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
        r"[A-Za-z0-9_-]{8,}\b"
    ),
)


def _normalize_key(key: str) -> str:
    """Normalize common key spellings without retaining their original value."""

    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _is_secret_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _SECRET_KEYS or normalized.endswith(_SECRET_SUFFIXES)


def _is_hidden_reasoning_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _HIDDEN_REASONING_KEYS


def _looks_like_secret_value(value: str) -> bool:
    return any(
        pattern.search(value) is not None for pattern in _SENSITIVE_VALUE_PATTERNS
    )


def _sanitize_value(
    value: object,
    *,
    path: str,
    secret_handling: SecretHandling,
) -> JsonValue:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnsafeAuditDetailError(f"{path} must be a finite JSON number")
        return value
    if isinstance(value, str):
        if _looks_like_secret_value(value):
            if secret_handling is SecretHandling.REJECT:
                raise UnsafeAuditDetailError(f"{path} contains a secret-like value")
            return REDACTED_VALUE
        return value
    if isinstance(value, Mapping):
        sanitized: dict[str, JsonValue] = {}
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise UnsafeAuditDetailError(f"{path} contains a non-string key")
            child_path = f"{path}.{raw_key}"
            if _is_hidden_reasoning_key(raw_key):
                raise UnsafeAuditDetailError(
                    f"{child_path} is hidden reasoning and cannot be audited"
                )
            if _is_secret_key(raw_key):
                if secret_handling is SecretHandling.REJECT:
                    raise UnsafeAuditDetailError(
                        f"{child_path} is a secret-like audit field"
                    )
                sanitized[raw_key] = REDACTED_VALUE
                continue
            sanitized[raw_key] = _sanitize_value(
                child,
                path=child_path,
                secret_handling=secret_handling,
            )
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [
            _sanitize_value(
                item,
                path=f"{path}[{index}]",
                secret_handling=secret_handling,
            )
            for index, item in enumerate(value)
        ]
    raise UnsafeAuditDetailError(
        f"{path} contains non-JSON value of type {type(value).__name__}"
    )


def sanitize_details(
    details: Mapping[str, object],
    *,
    secret_handling: SecretHandling = SecretHandling.REDACT,
) -> dict[str, JsonValue]:
    """Return JSON-safe audit details with secrets removed.

    Secret-like keys and recognizable credential values are redacted by default.
    Callers that prefer fail-closed handling can choose ``REJECT``. Hidden model
    reasoning is always rejected because it is never valid audit content.
    """

    sanitized = _sanitize_value(
        details,
        path="details",
        secret_handling=secret_handling,
    )
    return cast(dict[str, JsonValue], sanitized)


def sanitize_public_text(value: object) -> str:
    """Return a report-safe external error string with credentials removed."""

    sanitized = sanitize_details({"message": str(value)})["message"]
    return sanitized if isinstance(sanitized, str) else REDACTED_VALUE


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for event defaults."""

    return datetime.now(UTC)


class AuditEvent(BaseModel):
    """One immutable event written as a single compact JSONL record."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
    )

    schema_version: int = Field(default=1, ge=1, le=1)
    timestamp: datetime = Field(default_factory=utc_now)
    event: AuditEventName
    run_id: UUID
    household_id: str = Field(min_length=1)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Audit timestamps must be timezone-aware UTC values")
        if value.utcoffset() != timedelta(0):
            value = value.astimezone(UTC)
        return value

    @field_validator("details", mode="before")
    @classmethod
    def sanitize_event_details(cls, value: object) -> dict[str, JsonValue]:
        if not isinstance(value, Mapping):
            raise ValueError("Audit details must be a mapping")
        return sanitize_details(value)

    @model_validator(mode="after")
    def freeze_event_details(self) -> Self:
        object.__setattr__(self, "details", frozen_mapping(self.details))
        return self
