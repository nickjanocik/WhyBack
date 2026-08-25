"""Append-only structured observability for WhyBack investigations."""

from whyback.observability.audit import (
    AuditJsonlWriter,
    AuditTraceReadError,
    iter_audit_events,
    read_audit_events,
)
from whyback.observability.events import (
    REDACTED_VALUE,
    AuditEvent,
    AuditEventName,
    SecretHandling,
    UnsafeAuditDetailError,
    sanitize_details,
    sanitize_public_text,
)

__all__ = [
    "REDACTED_VALUE",
    "AuditEvent",
    "AuditEventName",
    "AuditJsonlWriter",
    "AuditTraceReadError",
    "SecretHandling",
    "UnsafeAuditDetailError",
    "iter_audit_events",
    "read_audit_events",
    "sanitize_details",
    "sanitize_public_text",
]
