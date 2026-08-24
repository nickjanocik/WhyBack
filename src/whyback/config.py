"""Typed application configuration loaded from TOML and environment values."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SOURCE_REPOSITORY = "bradleyboehmke/completejourney"
SOURCE_COMMIT = "5b5d06192b9856edd04e4d405787af2f2e4a1fef"


class ApplicationConfig(BaseModel):
    """Stable product identity."""

    model_config = ConfigDict(frozen=True)

    name: str = "WhyBack"
    agent_name: str = "WhyBack Investigator"
    tagline: str = "Find the why. Choose the way back."


class DataConfig(BaseModel):
    """Pinned data source and analytical window configuration."""

    model_config = ConfigDict(frozen=True)

    source_repository: str = SOURCE_REPOSITORY
    source_commit: str = SOURCE_COMMIT
    baseline_weeks: int = Field(default=8, ge=1)
    recent_weeks: int = Field(default=8, ge=1)


class DetectionConfig(BaseModel):
    """Transparent decline-detector policy."""

    model_config = ConfigDict(frozen=True)

    minimum_baseline_active_weeks: int = Field(default=4, ge=1)
    minimum_baseline_distinct_baskets: int = Field(default=6, ge=1)
    minimum_baseline_retailer_sales_value: float = Field(default=0.0, ge=0.0)
    decline_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    sensitivity_thresholds: tuple[float, ...] = (0.20, 0.30, 0.40)


class AgentConfig(BaseModel):
    """Hard investigation budgets and model defaults."""

    model_config = ConfigDict(frozen=True)

    max_tool_executions: int = Field(default=5, ge=1)
    max_model_decisions: int = Field(default=6, ge=1)
    tool_timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_retryable_retries: int = Field(default=1, ge=0, le=1)
    default_model: str = "gpt-5.6-sol"
    default_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "medium"


class Settings(BaseModel):
    """Complete application configuration."""

    model_config = ConfigDict(frozen=True)

    application: ApplicationConfig = ApplicationConfig()
    data: DataConfig = DataConfig()
    detection: DetectionConfig = DetectionConfig()
    agent: AgentConfig = AgentConfig()
    data_dir: Path = Path("data")
    artifact_dir: Path = Path("artifacts/local")
    model: str = "gpt-5.6-sol"
    reasoning_effort: Literal["minimal", "low", "medium", "high"] = "medium"


def load_settings(path: Path = Path("configs/app.toml")) -> Settings:
    """Load checked-in defaults and apply narrowly scoped environment overrides."""

    raw: dict[str, object] = {}
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)

    agent = AgentConfig.model_validate(raw.get("agent", {}))
    return Settings(
        application=ApplicationConfig.model_validate(raw.get("application", {})),
        data=DataConfig.model_validate(raw.get("data", {})),
        detection=DetectionConfig.model_validate(raw.get("detection", {})),
        agent=agent,
        data_dir=Path(os.getenv("WHYBACK_DATA_DIR", "data")),
        artifact_dir=Path(os.getenv("WHYBACK_ARTIFACT_DIR", "artifacts/local")),
        model=os.getenv("RETENTION_MODEL", agent.default_model),
        reasoning_effort=os.getenv(  # type: ignore[arg-type]
            "RETENTION_REASONING_EFFORT", agent.default_reasoning_effort
        ),
    )
