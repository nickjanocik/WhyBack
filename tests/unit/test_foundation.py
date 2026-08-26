"""Tests for WhyBack's foundation behavior."""

import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evals.run_evals import load_scenario_catalog
from whyback import __version__
from whyback.cli import app
from whyback.config import SOURCE_COMMIT, load_settings


def test_product_configuration_is_consistent() -> None:
    """Verify that product configuration is consistent."""

    settings = load_settings(Path("configs/app.toml"))

    assert settings.application.name == "WhyBack"
    assert settings.application.tagline == "Find the why. Choose the way back."
    assert settings.data.source_commit == SOURCE_COMMIT
    assert settings.agent.max_tool_executions == 5
    assert settings.agent.max_model_decisions == 6


def test_gemini_configuration_defaults_and_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that gemini configuration defaults and environment overrides."""

    monkeypatch.delenv("RETENTION_MODEL", raising=False)
    monkeypatch.delenv("RETENTION_THINKING_LEVEL", raising=False)

    defaults = load_settings(Path("configs/app.toml"))

    assert defaults.agent.default_model == "gemini-3.7-flash"
    assert defaults.agent.default_thinking_level == "medium"
    assert defaults.model == "gemini-3.7-flash"
    assert defaults.thinking_level == "medium"

    monkeypatch.setenv("RETENTION_MODEL", "gemini-migration-test")
    monkeypatch.setenv("RETENTION_THINKING_LEVEL", "high")

    overridden = load_settings(Path("configs/app.toml"))

    assert overridden.model == "gemini-migration-test"
    assert overridden.thinking_level == "high"


def test_interactions_sdk_floor_is_declared() -> None:
    """Verify that interactions sdk floor is declared."""

    configuration = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "google-genai>=2.3.0,<3" in configuration["project"]["dependencies"]


def test_cli_help_and_version() -> None:
    """Verify that cli help and version."""

    runner = CliRunner()

    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["--version"])

    assert help_result.exit_code == 0
    assert "Evidence-grounded" in help_result.stdout
    assert version_result.exit_code == 0
    assert version_result.stdout.strip() == f"WhyBack {__version__}"


def test_current_docs_match_the_verified_methodology_status() -> None:
    """Verify that current docs match the verified methodology status."""

    scenario_count = len(load_scenario_catalog().scenarios)
    readme = Path("README.md").read_text(encoding="utf-8")
    plans = Path("PLANS.md").read_text(encoding="utf-8")
    productionization = Path("docs/productionization.md").read_text(encoding="utf-8")

    assert scenario_count == 12
    assert "Twelve behavioral scenarios" in readme
    assert "twelve current behavioral scenarios" in productionization
    assert "| Requirement | Pre-change status" in plans
    assert "Every listed software gap is now verified." in plans
    assert "## Current completion boundaries" in plans
