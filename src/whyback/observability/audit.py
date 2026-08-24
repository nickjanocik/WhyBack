"""Append-only JSONL persistence and reading for WhyBack audit events."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from types import TracebackType
from typing import TextIO

from pydantic import ValidationError

from whyback.observability.events import AuditEvent


class AuditTraceReadError(ValueError):
    """An audit JSONL record was empty, malformed, or failed validation."""


class AuditJsonlWriter:
    """Write compact events to a file opened exclusively in append mode."""

    def __init__(
        self,
        path: Path,
        *,
        flush: bool = True,
        fsync: bool = False,
    ) -> None:
        self.path = path
        self.flush_each_event = flush
        self.fsync_each_event = fsync
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream: TextIO = self.path.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        )
        self._lock = Lock()

    @property
    def closed(self) -> bool:
        return self._stream.closed

    def append(self, event: AuditEvent) -> None:
        """Append one validated event without truncating prior records."""

        line = event.model_dump_json()
        with self._lock:
            if self._stream.closed:
                raise ValueError("Cannot append to a closed audit writer")
            self._stream.write(f"{line}\n")
            if self.flush_each_event or self.fsync_each_event:
                self._stream.flush()
            if self.fsync_each_event:
                os.fsync(self._stream.fileno())

    def close(self) -> None:
        """Flush pending data and close the underlying append-only stream."""

        with self._lock:
            if self._stream.closed:
                return
            self._stream.flush()
            if self.fsync_each_event:
                os.fsync(self._stream.fileno())
            self._stream.close()

    def __enter__(self) -> AuditJsonlWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def iter_audit_events(path: Path) -> tuple[AuditEvent, ...]:
    """Read and validate a complete audit trace in its recorded order."""

    events: list[AuditEvent] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise AuditTraceReadError(
                    f"Audit trace {path} has a blank record at line {line_number}"
                )
            try:
                events.append(AuditEvent.model_validate_json(line))
            except (ValidationError, ValueError) as error:
                raise AuditTraceReadError(
                    f"Invalid audit event in {path} at line {line_number}: {error}"
                ) from error
    return tuple(events)


def read_audit_events(path: Path) -> tuple[AuditEvent, ...]:
    """Compatibility-friendly named reader for reporting code."""

    return iter_audit_events(path)
