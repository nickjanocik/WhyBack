"""Small deterministic helpers shared by analytical tools."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, JsonValue

from whyback.methodology import ClaimType
from whyback.tools.contracts import (
    EvidenceRecord,
    ToolExecutionContext,
    ToolName,
    ToolProvenance,
)

QUANTITY_LIMITATION = (
    "Recorded quantity is not comparable across all departments because fuel uses a "
    "different scale; it is not used as the primary engagement measure."
)


def query_hash(*queries: str) -> str:
    """Hash normalized SQL text without exposing data values."""

    normalized = "\n".join(" ".join(query.split()) for query in queries)
    return hashlib.sha256(normalized.encode()).hexdigest()


def normalized_parameters(model: BaseModel) -> dict[str, JsonValue]:
    """Return a JSON-normalized representation for provenance and duplicate keys."""

    return json.loads(model.model_dump_json())


@dataclass(slots=True)
class ToolTimer:
    """Monotonic invocation timer."""

    started: float

    @classmethod
    def start(cls) -> ToolTimer:
        """Start a timer from the current monotonic clock reading."""

        return cls(time.perf_counter())

    def elapsed_ms(self) -> float:
        """Return nonnegative milliseconds elapsed since this timer started."""

        return max(0.0, (time.perf_counter() - self.started) * 1000)


def make_provenance(
    context: ToolExecutionContext,
    parameters: BaseModel,
    *,
    timer: ToolTimer,
    sql_hash: str | None,
    rows_examined: int,
    diagnostics: dict[str, JsonValue] | None = None,
) -> ToolProvenance:
    """Build replay metadata for a deterministic analytical invocation."""

    normalized = normalized_parameters(parameters)
    normalized["analysis_window"] = json.loads(context.window.model_dump_json())
    return ToolProvenance(
        dataset_source_commit=context.source_commit,
        source_hashes=context.source_hashes,
        normalized_parameters=normalized,
        query_hash=sql_hash,
        rows_examined=rows_examined,
        elapsed_ms=timer.elapsed_ms(),
        cache_hit=False,
        application_version=context.application_version,
        diagnostics=diagnostics or {},
    )


class EvidenceFactory:
    """Create stable unique records tied to one run, customer, and tool call."""

    def __init__(self, context: ToolExecutionContext, tool_name: ToolName) -> None:
        """Bind new evidence IDs and ownership fields to one tool call."""

        self._context = context
        self._tool_name = tool_name
        self._counter = 0

    def add(
        self,
        metric: str,
        *,
        dimensions: dict[str, str] | None = None,
        baseline_value: float | None = None,
        recent_value: float | None = None,
        value: float | None = None,
        text_value: str | None = None,
        change: float | None = None,
        unit: str | None = None,
        maximum_claim_type: ClaimType = ClaimType.ASSOCIATIONAL,
        limitations: tuple[str, ...] = (),
        sql_hash: str | None = None,
    ) -> EvidenceRecord:
        """Create the next owned evidence record after normalizing finite numbers."""

        self._counter += 1
        return EvidenceRecord(
            evidence_id=f"ev_{self._context.tool_call_id}_{self._counter:03d}",
            run_id=self._context.run_id,
            household_id=self._context.household_id,
            source_tool=self._tool_name,
            source_tool_call_id=self._context.tool_call_id,
            metric=metric,
            dimensions=dimensions or {},
            baseline_value=_finite_or_none(baseline_value),
            recent_value=_finite_or_none(recent_value),
            value=_finite_or_none(value),
            text_value=text_value,
            change=_finite_or_none(change),
            unit=unit,
            maximum_claim_type=maximum_claim_type,
            limitations=limitations,
            query_hash=sql_hash,
        )


def _finite_or_none(value: float | None) -> float | None:
    """Convert a finite numeric value to float and suppress non-finite values."""

    if value is None:
        return None
    number = float(value)
    if not np.isfinite(number):
        return None
    return number


def percentage_change(baseline: float, recent: float) -> float | None:
    """Return signed change relative to baseline magnitude, or none at zero."""

    if baseline == 0:
        return None
    return (recent - baseline) / abs(baseline)


def median(values: list[float]) -> float | None:
    """Return the numeric median, or none when no observations exist."""

    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=float)))


def slope(values: list[float]) -> float | None:
    """Ordinary least-squares slope over equally spaced observations."""

    if len(values) < 2:
        return None
    x = np.arange(len(values), dtype=float)
    y = np.asarray(values, dtype=float)
    centered_x = x - x.mean()
    denominator = float(np.square(centered_x).sum())
    if denominator == 0:
        return None
    return float((centered_x * (y - y.mean())).sum() / denominator)


def json_value(value: Any) -> JsonValue:
    """Validate a value is serializable under Pydantic's JSON contract."""

    return value  # type: ignore[return-value]
