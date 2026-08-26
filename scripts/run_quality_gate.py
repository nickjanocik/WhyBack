"""Run WhyBack's complete quality gate and persist an auditable transcript."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as element_tree
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import uuid4

StepStatus = Literal["passed", "failed", "skipped"]
GateLifecycle = Literal["running", "completed"]

_SOURCE_DIRECTORIES = (
    "src",
    "tests",
    "scripts",
    "evals",
    "configs",
    "docs",
    ".github",
    "web",
)
_SOURCE_FILES = (
    ".env.example",
    ".gitleaksignore",
    ".gitignore",
    "AGENTS.md",
    "Makefile",
    "PLANS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
)
_IGNORED_PARTS = frozenset(
    {
        ".git",
        ".hypothesis",
        ".pytest_cache",
        ".pyright",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "node_modules",
    }
)
_REQUIRED_STEP_NAMES = frozenset(
    {
        "coverage_configuration",
        "frozen_sync",
        "web_frozen_install",
        "ruff_format",
        "ruff_lint",
        "pyright",
        "web_quality",
        "pytest",
        "test_output_validation",
        "deterministic_evals",
        "artifact_verification",
        "live_gemini_artifact_verification",
        "official_artifact_verification",
        "official_type_a_artifact_verification",
    }
)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Store a command's exit code and captured output streams."""

    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Describe the callable used to run quality-gate commands."""

    def __call__(self, command: tuple[str, ...], cwd: Path) -> ProcessResult:
        """Run one command in a directory and return its captured result."""

        ...


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One externally executed quality step."""

    name: str
    command: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True, slots=True)
class StepRecord:
    """Exact execution record for one command or internal check."""

    name: str
    kind: Literal["command", "internal_check"]
    required: bool
    status: StepStatus
    command: tuple[str, ...]
    started_at: str
    completed_at: str
    duration_seconds: float
    exit_code: int | None
    stdout: str
    stderr: str

    def as_json(self) -> dict[str, object]:
        """Return this step as a JSON-ready audit record."""

        return {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
            "status": self.status,
            "command": list(self.command),
            "command_display": shlex.join(self.command) if self.command else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True, slots=True)
class GatePaths:
    """Stable output locations for the quality invocation."""

    directory: Path
    audit_json: Path
    audit_markdown: Path
    junit_xml: Path
    coverage_json: Path
    artifact_verification_json: Path
    live_gemini_artifact_verification_json: Path
    official_artifact_verification_json: Path
    official_type_a_artifact_verification_json: Path
    eval_json: Path
    eval_markdown: Path

    @classmethod
    def under(cls, root: Path) -> GatePaths:
        """Return every quality-gate output path beneath a repository root."""

        directory = root / "artifacts" / "tests"
        return cls(
            directory=directory,
            audit_json=directory / "test_audit.json",
            audit_markdown=directory / "TEST_AUDIT.md",
            junit_xml=directory / "junit.xml",
            coverage_json=directory / "coverage.json",
            artifact_verification_json=directory / "artifact_verification.json",
            live_gemini_artifact_verification_json=(
                directory / "live_gemini_artifact_verification.json"
            ),
            official_artifact_verification_json=(
                directory / "official_artifact_verification.json"
            ),
            official_type_a_artifact_verification_json=(
                directory / "official_type_a_artifact_verification.json"
            ),
            eval_json=directory / "eval_report.json",
            eval_markdown=directory / "EVAL_REPORT.md",
        )


def utc_now() -> datetime:
    """Return the current UTC time through a helper that tests can replace."""

    return datetime.now(UTC)


def _timestamp(value: datetime) -> str:
    """Render a timestamp in UTC using the portable trailing-Z form."""

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def subprocess_runner(command: tuple[str, ...], cwd: Path) -> ProcessResult:
    """Execute one command without shell interpolation and capture both streams."""

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return ProcessResult(127, "", f"{type(error).__name__}: {error}\n")
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_tree_hash(root: Path) -> str:
    """Hash reviewable source inputs while excluding generated/local state."""

    candidates: set[Path] = set()
    for relative in _SOURCE_FILES:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            candidates.add(path)
    for relative in _SOURCE_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            continue
        candidates.update(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not _IGNORED_PARTS.intersection(path.relative_to(root).parts)
        )

    digest = hashlib.sha256()
    for path in sorted(candidates, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _quiet_command(
    runner: CommandRunner, command: tuple[str, ...], root: Path
) -> str | None:
    """Return trimmed command output only when the command succeeds."""

    result = runner(command, root)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _read_toml(path: Path) -> Mapping[str, object]:
    """Read a TOML mapping, returning an empty mapping when it is unavailable."""

    try:
        with path.open("rb") as stream:
            return cast(Mapping[str, object], tomllib.load(stream))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _nested_mapping(value: object) -> Mapping[str, object]:
    """Return a mapping value or an empty mapping for an unexpected type."""

    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def dataset_metadata(root: Path) -> dict[str, object]:
    """Describe official prepared-data availability without requiring it."""

    config = _read_toml(root / "configs" / "app.toml")
    configured = _nested_mapping(config.get("data"))
    manifest_path = root / "data" / "prepared" / "manifest.json"
    metadata: dict[str, object] = {
        "status": "unavailable",
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "source_repository": configured.get("source_repository"),
        "source_commit": configured.get("source_commit"),
    }
    if not manifest_path.is_file():
        return metadata
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("manifest root is not an object")
        sources = raw.get("sources")
        prepared = raw.get("prepared")
        if not isinstance(sources, list) or not isinstance(prepared, list):
            raise ValueError("manifest is missing source or prepared entries")
        source_hashes = {
            str(entry.get("filename")): str(entry.get("sha256"))
            for entry in sources
            if isinstance(entry, Mapping)
            and isinstance(entry.get("filename"), str)
            and isinstance(entry.get("sha256"), str)
        }
        prepared_hashes = {
            str(entry.get("filename")): str(entry.get("sha256"))
            for entry in prepared
            if isinstance(entry, Mapping)
            and isinstance(entry.get("filename"), str)
            and isinstance(entry.get("sha256"), str)
        }
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        metadata.update(status="invalid", error=str(error))
        return metadata
    metadata.update(
        status="available",
        manifest_sha256=sha256_file(manifest_path),
        source_repository=raw.get("source_repository"),
        source_commit=raw.get("source_commit"),
        source_file_count=len(sources),
        prepared_table_count=len(prepared),
        source_hashes=source_hashes,
        prepared_hashes=prepared_hashes,
    )
    return metadata


def model_metadata(root: Path) -> dict[str, object]:
    """Capture model configuration without reading or recording a credential."""

    config = _read_toml(root / "configs" / "app.toml")
    agent = _nested_mapping(config.get("agent"))
    configured_model = agent.get("default_model", "gemini-3.7-flash")
    configured_level = agent.get("default_thinking_level", "medium")
    gemini_api_key_present = bool((os.getenv("GEMINI_API_KEY") or "").strip())
    return {
        "model": os.getenv("RETENTION_MODEL", str(configured_model)),
        "thinking_level": os.getenv("RETENTION_THINKING_LEVEL", str(configured_level)),
        "gemini_api_key_present": gemini_api_key_present,
        "live_execution_permitted": gemini_api_key_present,
    }


def collect_environment(root: Path, runner: CommandRunner) -> dict[str, object]:
    """Collect replay metadata before the gate creates or modifies artifacts."""

    lock_path = root / "uv.lock"
    git_head = _quiet_command(runner, ("git", "rev-parse", "HEAD"), root)
    git_branch = _quiet_command(runner, ("git", "branch", "--show-current"), root)
    git_status_result = runner(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"), root
    )
    git_status = (
        git_status_result.stdout.strip() if git_status_result.returncode == 0 else None
    )
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "uv_version": _quiet_command(runner, ("uv", "--version"), root),
        "lock_sha256": sha256_file(lock_path) if lock_path.is_file() else None,
        "source_tree_sha256": source_tree_hash(root),
        "git_head": git_head,
        "git_branch": git_branch,
        "git_dirty": bool(git_status) if git_status is not None else None,
        "git_status_porcelain": git_status,
        "source_dataset": dataset_metadata(root),
        "model_configuration": model_metadata(root),
    }


def coverage_threshold(root: Path) -> float:
    """Read the configured fail-under value rather than duplicating policy."""

    config = _read_toml(root / "pyproject.toml")
    tool = _nested_mapping(config.get("tool"))
    coverage = _nested_mapping(tool.get("coverage"))
    report = _nested_mapping(coverage.get("report"))
    raw = report.get("fail_under")
    if (
        isinstance(raw, (int, float))
        and not isinstance(raw, bool)
        and 0.0 < float(raw) <= 100.0
    ):
        return float(raw)
    raise ValueError(
        "tool.coverage.report.fail_under must be numeric and within (0, 100]"
    )


def inspect_test_outputs(
    paths: GatePaths, minimum: float
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Parse stable test counts and branch coverage, returning every problem."""

    failures: list[str] = []
    summary: dict[str, object] = {}
    if not paths.junit_xml.is_file():
        failures.append(f"missing JUnit XML: {paths.junit_xml}")
    else:
        try:
            root = element_tree.parse(paths.junit_xml).getroot()
            suites = [
                item
                for item in root.iter()
                if item.tag.rsplit("}", maxsplit=1)[-1] == "testsuite"
                and not any(
                    child.tag.rsplit("}", maxsplit=1)[-1] == "testsuite"
                    for child in item
                )
            ]
            counts = {
                key: sum(int(item.attrib.get(key, "0")) for item in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
            duration = sum(float(item.attrib.get("time", "0")) for item in suites)
            if counts["tests"] <= 0:
                failures.append("JUnit XML recorded no tests")
            if counts["failures"] or counts["errors"]:
                failures.append(
                    "JUnit XML recorded "
                    f"{counts['failures']} failures and {counts['errors']} errors"
                )
            summary["junit"] = {**counts, "duration_seconds": duration}
        except (OSError, ValueError, element_tree.ParseError) as error:
            failures.append(f"malformed JUnit XML: {error}")

    percent: float | None = None
    branches: int | None = None
    if not paths.coverage_json.is_file():
        failures.append(f"missing coverage JSON: {paths.coverage_json}")
    else:
        try:
            raw = json.loads(paths.coverage_json.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping):
                raise ValueError("coverage root is not an object")
            totals = raw.get("totals")
            if not isinstance(totals, Mapping):
                raise ValueError("coverage totals are absent")
            raw_percent = totals.get("percent_covered")
            raw_branches = totals.get("num_branches")
            if not isinstance(raw_percent, (int, float)) or isinstance(
                raw_percent, bool
            ):
                raise ValueError("percent_covered is not numeric")
            if not isinstance(raw_branches, int) or isinstance(raw_branches, bool):
                raise ValueError("num_branches is not an integer")
            percent = float(raw_percent)
            branches = raw_branches
            summary["coverage"] = {
                "percent_covered": percent,
                "num_statements": totals.get("num_statements"),
                "covered_lines": totals.get("covered_lines"),
                "missing_lines": totals.get("missing_lines"),
                "num_branches": branches,
                "covered_branches": totals.get("covered_branches"),
                "missing_branches": totals.get("missing_branches"),
                "minimum_percent": minimum,
            }
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            failures.append(f"malformed coverage JSON: {error}")
    if branches is not None and branches <= 0:
        failures.append("coverage JSON did not record branch measurements")
    if percent is not None and percent < minimum:
        failures.append(
            f"coverage {percent:.2f}% is below the configured {minimum:.2f}% gate"
        )
    return summary, tuple(failures)


def validate_test_outputs(paths: GatePaths, minimum: float) -> tuple[bool, str]:
    """Validate JUnit plus branch-coverage JSON and enforce the coverage gate."""

    summary, failures = inspect_test_outputs(paths, minimum)
    coverage = _nested_mapping(summary.get("coverage"))
    junit = _nested_mapping(summary.get("junit"))
    message = (
        f"JUnit recorded {junit.get('tests')} tests; branch-aware coverage is "
        f"{coverage.get('percent_covered')}% across "
        f"{coverage.get('num_branches')} branches (minimum {minimum:.2f}%)."
        if not failures
        else "\n".join(failures)
    )
    return not failures, message


def discover_eval_input(root: Path) -> Path | None:
    """Find the single conventional deterministic normalized-run fixture."""

    demo = root / "artifacts" / "demo"
    candidates = (
        demo / "evals" / "normalized_runs.json",
        demo / "normalized_runs.json",
        demo / "eval_input.json",
        demo / "eval-input.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def build_command_specs(
    root: Path,
    paths: GatePaths,
    *,
    allow_live_skipped: bool,
) -> tuple[CommandSpec, ...]:
    """Build the required commands in their stable execution order."""

    def relative(path: Path) -> str:
        """Render a gate output path relative to the repository root."""

        return path.relative_to(root).as_posix()

    artifact_command = [
        "uv",
        "run",
        "python",
        "scripts/verify_artifacts.py",
        "artifacts/demo",
        "--json-output",
        relative(paths.artifact_verification_json),
    ]
    if allow_live_skipped:
        artifact_command.append("--allow-live-skipped")
    live_gemini_command = [
        "uv",
        "run",
        "python",
        "scripts/verify_artifacts.py",
        "artifacts/live-gemini-synthetic-failure",
        "--json-output",
        relative(paths.live_gemini_artifact_verification_json),
    ]
    official_command = [
        "uv",
        "run",
        "python",
        "scripts/verify_artifacts.py",
        "artifacts/official",
        "--json-output",
        relative(paths.official_artifact_verification_json),
    ]
    if allow_live_skipped:
        official_command.append("--allow-live-skipped")
    official_type_a_command = [
        "uv",
        "run",
        "python",
        "scripts/verify_artifacts.py",
        "artifacts/official-type-a",
        "--json-output",
        relative(paths.official_type_a_artifact_verification_json),
    ]
    return (
        CommandSpec("frozen_sync", ("uv", "sync", "--frozen", "--extra", "dev")),
        CommandSpec(
            "web_frozen_install",
            ("npm", "--prefix", "web", "ci", "--ignore-scripts"),
        ),
        CommandSpec("ruff_format", ("uv", "run", "ruff", "format", "--check", ".")),
        CommandSpec("ruff_lint", ("uv", "run", "ruff", "check", ".")),
        CommandSpec("pyright", ("uv", "run", "pyright")),
        CommandSpec("web_quality", ("npm", "--prefix", "web", "run", "check")),
        CommandSpec(
            "pytest",
            (
                "uv",
                "run",
                "pytest",
                "--cov=whyback",
                "--cov-branch",
                f"--cov-report=json:{relative(paths.coverage_json)}",
                f"--junitxml={relative(paths.junit_xml)}",
            ),
        ),
        CommandSpec("artifact_verification", tuple(artifact_command)),
        CommandSpec(
            "live_gemini_artifact_verification",
            tuple(live_gemini_command),
        ),
        CommandSpec("official_artifact_verification", tuple(official_command)),
        CommandSpec(
            "official_type_a_artifact_verification",
            tuple(official_type_a_command),
        ),
    )


def _run_step(
    spec: CommandSpec,
    root: Path,
    runner: CommandRunner,
    now: Callable[[], datetime],
    monotonic: Callable[[], float],
) -> StepRecord:
    """Execute one external gate command and record its timing and output."""

    started_wall = now()
    started_clock = monotonic()
    result = runner(spec.command, root)
    completed_clock = monotonic()
    completed_wall = now()
    return StepRecord(
        name=spec.name,
        kind="command",
        required=spec.required,
        status="passed" if result.returncode == 0 else "failed",
        command=spec.command,
        started_at=_timestamp(started_wall),
        completed_at=_timestamp(completed_wall),
        duration_seconds=max(0.0, completed_clock - started_clock),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _internal_step(
    name: str,
    passed: bool,
    message: str,
    now: Callable[[], datetime],
) -> StepRecord:
    """Create a zero-duration record for an in-process quality check."""

    timestamp = _timestamp(now())
    return StepRecord(
        name=name,
        kind="internal_check",
        required=True,
        status="passed" if passed else "failed",
        command=(),
        started_at=timestamp,
        completed_at=timestamp,
        duration_seconds=0.0,
        exit_code=0 if passed else 1,
        stdout=f"{message}\n" if passed else "",
        stderr=f"{message}\n" if not passed else "",
    )


def _missing_eval(now: Callable[[], datetime]) -> StepRecord:
    """Create the failed step recorded when the required eval input is absent."""

    timestamp = _timestamp(now())
    return StepRecord(
        name="deterministic_evals",
        kind="command",
        required=True,
        status="failed",
        command=(),
        started_at=timestamp,
        completed_at=timestamp,
        duration_seconds=0.0,
        exit_code=1,
        stdout="",
        stderr="Required normalized-run eval fixture was unavailable.\n",
    )


def _atomic_write(path: Path, text: str) -> None:
    """Publish text by replacing the destination with a completed temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def load_prior_invocations(path: Path) -> tuple[dict[str, object], ...]:
    """Load prior complete invocations so a rerun cannot erase failures."""

    if not path.is_file():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Prior test audit root is not an object")
    raw_invocations = raw.get("invocations")
    candidates: list[object]
    if isinstance(raw_invocations, list):
        candidates = raw_invocations
    elif raw.get("gate_name") == "deterministic_quality_gate":
        candidates = [raw]
    else:
        raise ValueError("Prior test audit has an unknown schema")
    invocations: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise ValueError(f"Prior invocation {index} is not an object")
        normalized = dict(candidate)
        normalized.pop("invocations", None)
        invocations.append(normalized)
    return tuple(invocations)


def render_audit_markdown(audit: Mapping[str, object]) -> str:
    """Render a human-readable transcript from the JSON-authoritative audit."""

    passed = bool(audit.get("passed"))
    environment = _nested_mapping(audit.get("environment"))
    lines = [
        "# WhyBack test audit",
        "",
        f"Overall result: **{'PASS' if passed else 'FAIL'}**",
        "",
        f"Invocation: `{audit.get('invocation_id')}`",
        f"Started: `{audit.get('started_at')}`",
        f"Completed: `{audit.get('completed_at')}`",
        f"Duration: `{audit.get('duration_seconds')} seconds`",
        "",
        "## Reproducibility metadata",
        "",
        f"- Git: `{environment.get('git_head')}` on "
        f"`{environment.get('git_branch')}` (dirty: "
        f"`{str(environment.get('git_dirty')).lower()}`)",
        f"- Python: `{environment.get('python_version')}` "
        f"(`{environment.get('python_implementation')}`)",
        f"- uv: `{environment.get('uv_version')}`",
        f"- Platform: `{environment.get('platform')}`",
        f"- Lock SHA-256: `{environment.get('lock_sha256')}`",
        f"- Source-tree SHA-256: `{environment.get('source_tree_sha256')}`",
        "",
        "```json",
        json.dumps(
            {
                "source_dataset": environment.get("source_dataset"),
                "model_configuration": environment.get("model_configuration"),
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Parsed test results",
        "",
        "```json",
        json.dumps(audit.get("test_summary", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Steps",
        "",
        "| Step | Required | Status | Exit | Duration |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    raw_steps = audit.get("steps")
    steps = raw_steps if isinstance(raw_steps, list) else []
    for raw in steps:
        step = _nested_mapping(raw)
        lines.append(
            f"| {step.get('name')} | {step.get('required')} | "
            f"{step.get('status')} | {step.get('exit_code')} | "
            f"{step.get('duration_seconds')}s |"
        )
    for raw in steps:
        step = _nested_mapping(raw)
        command = step.get("command_display") or "(internal or skipped)"
        lines.extend(
            (
                "",
                f"### {step.get('name')}",
                "",
                f"Command: `{command}`",
                "",
                f"Started: `{step.get('started_at')}`",
                f"Completed: `{step.get('completed_at')}`",
                "",
                "Stdout:",
                "",
                "```text",
                str(step.get("stdout") or ""),
                "```",
                "",
                "Stderr:",
                "",
                "```text",
                str(step.get("stderr") or ""),
                "```",
            )
        )
    failures = audit.get("failure_observations")
    lines.extend(("", "## Failure observations", ""))
    if isinstance(failures, list) and failures:
        lines.extend(f"- `{item}`" for item in failures)
    else:
        lines.append("None.")
    raw_invocations = audit.get("invocations")
    prior = raw_invocations[:-1] if isinstance(raw_invocations, list) else []
    lines.extend(("", "## Prior invocations retained", ""))
    if prior:
        lines.extend(
            (
                "| Invocation | Started | Result | Failures |",
                "| --- | --- | ---: | --- |",
            )
        )
        for raw in prior:
            item = _nested_mapping(raw)
            observed = item.get("failure_observations")
            rendered_failures = (
                ", ".join(str(value) for value in observed)
                if isinstance(observed, list) and observed
                else "none"
            )
            lines.append(
                f"| `{item.get('invocation_id')}` | `{item.get('started_at')}` | "
                f"{'pass' if item.get('passed') else 'fail'} | "
                f"{rendered_failures} |"
            )
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def _audit_document(
    *,
    invocation_id: str,
    started_at: datetime,
    completed_at: datetime,
    duration_seconds: float,
    environment: Mapping[str, object],
    coverage_minimum: float,
    allow_live_skipped: bool,
    steps: Sequence[StepRecord],
    failure_observations: Sequence[str],
    test_summary: Mapping[str, object],
    prior_invocations: Sequence[Mapping[str, object]],
    lifecycle: GateLifecycle,
) -> dict[str, object]:
    """Build the authoritative audit document for the gate's current lifecycle."""

    recorded_required = {step.name for step in steps if step.required}
    required_steps_complete = _REQUIRED_STEP_NAMES.issubset(recorded_required)
    unique_step_names = len({step.name for step in steps}) == len(steps)
    passed = (
        lifecycle == "completed"
        and required_steps_complete
        and unique_step_names
        and all(step.status == "passed" for step in steps if step.required)
    )
    current: dict[str, object] = {
        "schema_version": 2,
        "product_name": "WhyBack",
        "gate_name": "deterministic_quality_gate",
        "lifecycle": lifecycle,
        "invocation_id": invocation_id,
        "started_at": _timestamp(started_at),
        "completed_at": _timestamp(completed_at),
        "duration_seconds": max(0.0, duration_seconds),
        "passed": passed,
        "configuration": {
            "coverage_minimum_percent": coverage_minimum,
            "allow_live_skipped": allow_live_skipped,
        },
        "environment": dict(environment),
        "test_summary": dict(test_summary),
        "steps": [step.as_json() for step in steps],
        "failure_observations": list(failure_observations),
        "required_step_names": sorted(_REQUIRED_STEP_NAMES),
        "required_steps_complete": required_steps_complete,
    }
    current["invocations"] = [
        *(dict(item) for item in prior_invocations),
        dict(current),
    ]
    return current


def _persist_audit(paths: GatePaths, audit: Mapping[str, object]) -> None:
    """Atomically write matching JSON and Markdown audit documents."""

    _atomic_write(
        paths.audit_json,
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(paths.audit_markdown, render_audit_markdown(audit))


def run_quality_gate(
    root: Path,
    *,
    allow_live_skipped: bool = True,
    runner: CommandRunner = subprocess_runner,
    now: Callable[[], datetime] = utc_now,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[int, dict[str, object]]:
    """Run every gate step, retaining every failure observed in this invocation."""

    root = root.resolve()
    invocation_id = str(uuid4())
    started_at = now()
    started_clock = monotonic()
    environment = collect_environment(root, runner)
    paths = GatePaths.under(root)
    try:
        prior_invocations = load_prior_invocations(paths.audit_json)
        prior_audit_error: str | None = None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        prior_invocations = ()
        prior_audit_error = str(error)
        # Preserve the malformed prior content in the replacement audit instead
        # of silently discarding evidence of an earlier gate attempt.
        environment["unreadable_prior_audit"] = {
            "error": prior_audit_error,
            "sha256": sha256_file(paths.audit_json),
        }
    paths.directory.mkdir(parents=True, exist_ok=True)
    for stale_output in (
        paths.junit_xml,
        paths.coverage_json,
        paths.artifact_verification_json,
        paths.live_gemini_artifact_verification_json,
        paths.official_artifact_verification_json,
        paths.official_type_a_artifact_verification_json,
        paths.eval_json,
        paths.eval_markdown,
    ):
        stale_output.unlink(missing_ok=True)
    try:
        minimum = coverage_threshold(root)
        coverage_configuration_error: str | None = None
    except ValueError as error:
        # A missing policy must not silently weaken the gate. One hundred percent
        # is a conservative fallback while the explicit configuration failure is
        # retained in the audit.
        minimum = 100.0
        coverage_configuration_error = str(error)
    steps: list[StepRecord] = []
    failure_observations: list[str] = []
    test_summary: dict[str, object] = {}

    def persist_progress() -> None:
        """Checkpoint the running audit after each newly observed result."""

        audit = _audit_document(
            invocation_id=invocation_id,
            started_at=started_at,
            completed_at=now(),
            duration_seconds=monotonic() - started_clock,
            environment=environment,
            coverage_minimum=minimum,
            allow_live_skipped=allow_live_skipped,
            steps=steps,
            failure_observations=failure_observations,
            test_summary=test_summary,
            prior_invocations=prior_invocations,
            lifecycle="running",
        )
        _persist_audit(paths, audit)

    configuration_record = _internal_step(
        "coverage_configuration",
        coverage_configuration_error is None,
        coverage_configuration_error
        or f"Configured coverage minimum is {minimum:.2f}%.",
        now,
    )
    steps.append(configuration_record)
    if configuration_record.status == "failed":
        failure_observations.append(configuration_record.name)
    persist_progress()

    if prior_audit_error is not None:
        prior_record = _internal_step(
            "prior_audit_validation", False, prior_audit_error, now
        )
        steps.append(prior_record)
        failure_observations.append(prior_record.name)
        persist_progress()

    specs = build_command_specs(
        root,
        paths,
        allow_live_skipped=allow_live_skipped,
    )
    for spec in specs:
        if spec.name == "artifact_verification":
            eval_input = discover_eval_input(root)
            if eval_input is None:
                eval_record = _missing_eval(now)
            else:
                eval_record = _run_step(
                    CommandSpec(
                        "deterministic_evals",
                        (
                            "uv",
                            "run",
                            "python",
                            "evals/run_evals.py",
                            eval_input.relative_to(root).as_posix(),
                            "--json-output",
                            paths.eval_json.relative_to(root).as_posix(),
                            "--markdown-output",
                            paths.eval_markdown.relative_to(root).as_posix(),
                        ),
                    ),
                    root,
                    runner,
                    now,
                    monotonic,
                )
            steps.append(eval_record)
            if eval_record.required and eval_record.status == "failed":
                failure_observations.append(eval_record.name)
            persist_progress()

        record = _run_step(spec, root, runner, now, monotonic)
        steps.append(record)
        if record.required and record.status == "failed":
            failure_observations.append(record.name)
        persist_progress()

        if spec.name == "pytest":
            parsed_summary, _ = inspect_test_outputs(paths, minimum)
            test_summary.update(parsed_summary)
            outputs_passed, message = validate_test_outputs(paths, minimum)
            output_record = _internal_step(
                "test_output_validation", outputs_passed, message, now
            )
            steps.append(output_record)
            if output_record.status == "failed":
                failure_observations.append(output_record.name)
            persist_progress()

    completed_at = now()
    audit = _audit_document(
        invocation_id=invocation_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=monotonic() - started_clock,
        environment=environment,
        coverage_minimum=minimum,
        allow_live_skipped=allow_live_skipped,
        steps=steps,
        failure_observations=failure_observations,
        test_summary=test_summary,
        prior_invocations=prior_invocations,
        lifecycle="completed",
    )
    _persist_audit(paths, audit)
    return (0 if bool(audit["passed"]) else 1), audit


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for repository and live-run policy options."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/).",
    )
    parser.add_argument(
        "--allow-live-skipped",
        dest="allow_live_skipped",
        action="store_true",
        help=(
            "Permit an honestly recorded skipped-live status (the default when "
            "credentials are unavailable)."
        ),
    )
    parser.add_argument(
        "--require-live",
        dest="allow_live_skipped",
        action="store_false",
        help="Require the official artifact to contain completed live model runs.",
    )
    parser.set_defaults(allow_live_skipped=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the quality gate, print its audit JSON, and return its exit code."""

    arguments = _parser().parse_args(argv)
    exit_code, audit = run_quality_gate(
        arguments.root,
        allow_live_skipped=arguments.allow_live_skipped,
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
