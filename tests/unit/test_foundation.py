from pathlib import Path

from typer.testing import CliRunner

from whyback import __version__
from whyback.cli import app
from whyback.config import SOURCE_COMMIT, load_settings


def test_product_configuration_is_consistent() -> None:
    settings = load_settings(Path("configs/app.toml"))

    assert settings.application.name == "WhyBack"
    assert settings.application.tagline == "Find the why. Choose the way back."
    assert settings.data.source_commit == SOURCE_COMMIT
    assert settings.agent.max_tool_executions == 5
    assert settings.agent.max_model_decisions == 6


def test_cli_help_and_version() -> None:
    runner = CliRunner()

    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["--version"])

    assert help_result.exit_code == 0
    assert "Evidence-grounded" in help_result.stdout
    assert version_result.exit_code == 0
    assert version_result.stdout.strip() == f"WhyBack {__version__}"
