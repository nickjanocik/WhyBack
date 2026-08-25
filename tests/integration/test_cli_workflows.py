from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from whyback.cli import app
from whyback.data.prepare import prepare_frames_for_tests
from whyback.demo import synthetic_demo_frames


def _prepared_fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    data_root = tmp_path / "data"
    prepare_frames_for_tests(synthetic_demo_frames(), data_root / "prepared")
    return data_root, {
        "WHYBACK_DATA_DIR": str(data_root),
        "WHYBACK_ARTIFACT_DIR": str(tmp_path / "local-artifacts"),
    }


def test_cli_config_status_and_full_prepare_guard(tmp_path: Path) -> None:
    data_root, environment = _prepared_fixture(tmp_path)
    runner = CliRunner()

    config_result = runner.invoke(app, ["config"], env=environment)
    status_result = runner.invoke(app, ["data", "status"], env=environment)
    guarded_prepare = runner.invoke(app, ["data", "prepare"], env=environment)

    assert config_result.exit_code == 0
    assert '"name": "WhyBack"' in config_result.stdout
    assert status_result.exit_code == 0
    assert "Data directory:" in status_result.stdout
    assert data_root.name in status_result.stdout
    assert "Prepared manifest: available" in status_result.stdout
    assert guarded_prepare.exit_code == 2
    assert "pass --full" in guarded_prepare.stderr


def test_cli_detect_investigate_and_verify_round_trip(tmp_path: Path) -> None:
    data_root, environment = _prepared_fixture(tmp_path)
    prepared = data_root / "prepared"
    detector_output = tmp_path / "detector"
    run_output = tmp_path / "single-run"
    runner = CliRunner()

    detected = runner.invoke(
        app,
        ["detect", "--top", "2", "--output-dir", str(detector_output)],
        env=environment,
    )
    investigated = runner.invoke(
        app,
        [
            "investigate",
            "--household-id",
            "101",
            "--data-dir",
            str(prepared),
            "--output-dir",
            str(run_output),
        ],
        env=environment,
    )
    verified = runner.invoke(
        app,
        ["verify-artifacts", str(run_output)],
        env=environment,
    )

    assert detected.exit_code == 0, detected.output
    assert "WhyBack decline candidates" in detected.stdout
    assert (detector_output / "decline_candidates.csv").is_file()
    assert (detector_output / "sensitivity.csv").is_file()
    assert investigated.exit_code == 0, investigated.output
    assert "Investigation completed" in investigated.stdout
    assert (run_output / "manifest.json").is_file()
    assert verified.exit_code == 0, verified.output
    assert '"passed": true' in verified.stdout


def test_cli_demo_and_invalid_backend_paths(tmp_path: Path) -> None:
    _, environment = _prepared_fixture(tmp_path)
    demo_output = tmp_path / "demo"
    runner = CliRunner()

    demo_result = runner.invoke(
        app,
        ["demo", "--customers", "1", "--output-dir", str(demo_output)],
        env=environment,
    )
    invalid_demo = runner.invoke(
        app,
        ["demo", "--backend", "unsupported", "--output-dir", str(tmp_path / "bad")],
        env=environment,
    )
    invalid_investigation = runner.invoke(
        app,
        ["investigate", "--household-id", "101", "--backend", "unsupported"],
        env=environment,
    )

    assert demo_result.exit_code == 0, demo_result.output
    assert "Generated 1 reports for 101" in demo_result.stdout
    assert (demo_output / "manifest.json").is_file()
    assert invalid_demo.exit_code == 2
    assert "backend must be" in invalid_demo.stderr
    assert invalid_investigation.exit_code == 2
    assert "backend must be" in invalid_investigation.stderr


def test_cli_rejects_retired_openai_backend(tmp_path: Path) -> None:
    _, environment = _prepared_fixture(tmp_path)
    runner = CliRunner()

    demo_result = runner.invoke(
        app,
        ["demo", "--backend", "openai", "--output-dir", str(tmp_path / "demo")],
        env=environment,
    )
    investigation_result = runner.invoke(
        app,
        ["investigate", "--household-id", "101", "--backend", "openai"],
        env=environment,
    )

    expected = "backend must be 'scripted' or 'gemini'"
    assert demo_result.exit_code == 2
    assert expected in demo_result.stderr
    assert investigation_result.exit_code == 2
    assert expected in investigation_result.stderr


def test_cli_gemini_investigation_reports_missing_key(tmp_path: Path) -> None:
    data_root, environment = _prepared_fixture(tmp_path)
    environment["GEMINI_API_KEY"] = ""
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "investigate",
            "--household-id",
            "101",
            "--backend",
            "gemini",
            "--data-dir",
            str(data_root / "prepared"),
            "--output-dir",
            str(tmp_path / "gemini-run"),
        ],
        env=environment,
    )

    assert result.exit_code == 1
    assert "GEMINI_API_KEY is required for the gemini backend" in result.stdout


def test_cli_verifies_historical_skip_with_current_key_present(tmp_path: Path) -> None:
    status_path = tmp_path / "live_model_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "skipped_no_api_key",
                "execution_mode": "skipped",
                "reason": "GEMINI_API_KEY was absent.",
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_mode": "skipped",
                "reason": "GEMINI_API_KEY was absent.",
                "files": {
                    status_path.name: hashlib.sha256(
                        status_path.read_bytes()
                    ).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["verify-artifacts", str(tmp_path)],
        env={"GEMINI_API_KEY": "test-placeholder-not-a-real-key"},
    )

    assert result.exit_code == 0, result.output
    assert '"passed": true' in result.stdout
