"""Typed execution provenance shared by investigation and report boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from whyback import __version__
from whyback.agent.prompts import PROMPT_HASH, PROMPT_VERSION
from whyback.immutability import frozen_mapping


class RunProvenance(BaseModel):
    """Standalone identity for the data, backend, code, prompt, and clock used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_kind: Literal["synthetic", "official_complete_journey", "unspecified"] = (
        "unspecified"
    )
    dataset_source_repository: str = "unspecified"
    dataset_source_commit: str = "unspecified"
    source_hashes: dict[str, str] = Field(default_factory=dict)
    backend: Literal["scripted", "gemini", "openai", "unspecified"] = "unspecified"
    execution_mode: Literal[
        "scripted_control", "live_gemini", "live_openai", "unspecified"
    ] = "unspecified"
    model: str = "unspecified"
    application_version: str = __version__
    prompt_version: str = PROMPT_VERSION
    prompt_hash: str = PROMPT_HASH
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    timing_mode: Literal["actual_utc_and_monotonic"] = "actual_utc_and_monotonic"

    @field_validator("generated_at")
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def freeze_hashes(self) -> Self:
        object.__setattr__(self, "source_hashes", frozen_mapping(self.source_hashes))
        return self
