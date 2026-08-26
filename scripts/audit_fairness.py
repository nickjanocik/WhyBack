"""Build an aggregate post-hoc demographic audit from verified WhyBack inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import ValidationError

try:
    from scripts.verify_artifacts import verify_artifact_tree
except ModuleNotFoundError:  # Direct script execution places scripts/ on sys.path.
    from verify_artifacts import verify_artifact_tree

from whyback.agent.actions import ActionId
from whyback.config import DetectionConfig, load_settings
from whyback.data.manifest import DataManifest
from whyback.data.repository import DataRepository
from whyback.detection.decline import WindowSpec, detect_declines
from whyback.governance.fairness import (
    FairnessAudit,
    FairnessAuditPolicy,
    FairnessAuditProvenance,
    PipelineMembership,
    build_fairness_audit,
)
from whyback.reporting.models import ReportData
from whyback.reporting.population import PopulationSummary


@dataclass(frozen=True, slots=True)
class _ArtifactContext:
    """Hold verified artifact policy and private outcome memberships."""

    policy: DetectionConfig
    baseline_weeks: int
    recent_weeks: int
    expected_eligible: int
    expected_flagged: int
    selected: frozenset[str]
    completed: frozenset[str] | None
    insufficient: frozenset[str] | None
    failed: frozenset[str] | None
    governed_action: frozenset[str] | None
    backend: str
    execution_mode: str
    manifest_sha256: str


def _sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for one local file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> object:
    """Read one JSON value for strict caller-side validation."""

    return cast(object, json.loads(path.read_text(encoding="utf-8")))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Require a JSON object without exposing its values in errors."""

    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _safe_path(root: Path, relative: object, label: str) -> Path:
    """Resolve one artifact file without permitting path traversal."""

    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"{label} must name an artifact-relative file")
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    if not path.is_relative_to(resolved_root) or not path.is_file():
        raise ValueError(f"{label} is missing or outside the artifact root")
    return path


def _identifiers(value: object, label: str) -> frozenset[str]:
    """Parse a unique private identifier list from an artifact manifest."""

    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must contain nonblank strings")
    items = cast(list[str], value)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must not contain duplicates")
    return frozenset(items)


def _artifact_context(
    root: Path,
    prepared_manifest: DataManifest,
    prepared_manifest_sha256: str,
) -> _ArtifactContext:
    """Verify one artifact and load its detector policy and terminal outcomes."""

    verification = verify_artifact_tree(root, allow_live_skipped=True)
    if not verification.passed:
        raise ValueError(
            f"Artifact verification failed with {len(verification.issues)} issue(s)"
        )
    manifest_path = root.resolve() / "manifest.json"
    manifest = _mapping(_json(manifest_path), "Artifact manifest")
    if (
        manifest.get("dataset_source_repository") != prepared_manifest.source_repository
        or manifest.get("dataset_source_commit") != prepared_manifest.source_commit
    ):
        raise ValueError("Artifact and prepared-data source identities do not match")
    source_provenance = _mapping(
        _json(
            _safe_path(
                root,
                manifest.get("source_manifest"),
                "source_manifest",
            )
        ),
        "Artifact source provenance",
    )
    if source_provenance.get("manifest_sha256") != prepared_manifest_sha256:
        raise ValueError("Artifact outcomes do not match the prepared-data manifest")
    population = PopulationSummary.model_validate_json(
        _safe_path(
            root, manifest.get("population_summary"), "population_summary"
        ).read_text(encoding="utf-8")
    )
    counts = {item.cohort: item.household_count for item in population.cohorts}
    selected = _identifiers(
        manifest.get("selected_household_ids"), "selected_household_ids"
    )
    backend = manifest.get("backend")
    mode = manifest.get("execution_mode")
    if not isinstance(backend, str) or not isinstance(mode, str):
        raise ValueError("Artifact backend and execution mode must be strings")
    completed = insufficient = failed = governed_action = None
    if mode != "skipped":
        raw_reports = _json(_safe_path(root, "results.json", "results.json"))
        if not isinstance(raw_reports, list):
            raise ValueError("results.json must contain a report list")
        reports = tuple(ReportData.model_validate(item) for item in raw_reports)
        owners = frozenset(item.household_id for item in reports)
        if len(owners) != len(reports) or owners != selected:
            raise ValueError("Reports do not reconcile to the selected batch")
        completed = frozenset(
            item.household_id
            for item in reports
            if item.run_status.value == "completed"
        )
        insufficient = frozenset(
            item.household_id
            for item in reports
            if item.run_status.value == "insufficient_evidence"
        )
        failed = frozenset(
            item.household_id for item in reports if item.run_status.value == "failed"
        )
        governed_action = frozenset(
            item.household_id
            for item in reports
            if item.run_status.value == "completed"
            and item.action is not None
            and item.action.action_id is not ActionId.INSUFFICIENT_EVIDENCE
        )
    windows = population.analysis_windows
    return _ArtifactContext(
        policy=population.detector_policy,
        baseline_weeks=windows.baseline_end_week - windows.baseline_start_week + 1,
        recent_weeks=windows.recent_end_week - windows.recent_start_week + 1,
        expected_eligible=counts["eligible"],
        expected_flagged=counts["flagged"],
        selected=selected,
        completed=completed,
        insufficient=insufficient,
        failed=failed,
        governed_action=governed_action,
        backend=backend,
        execution_mode=mode,
        manifest_sha256=_sha256(manifest_path),
    )


def _build(
    prepared_dir: Path,
    artifact_root: Path | None,
    attributes: Sequence[str] | None,
    minimum_group_size: int,
) -> FairnessAudit:
    """Build an audit from prepared data and optional verified outcomes."""

    settings = load_settings()
    prepared_hash = _sha256(prepared_dir / "manifest.json")
    with DataRepository(
        prepared_dir, required_tables=("household_week", "demographics")
    ) as repository:
        manifest = repository.manifest
        if manifest is None:
            raise ValueError("Prepared-data manifest validation was not performed")
        context = (
            _artifact_context(artifact_root, manifest, prepared_hash)
            if artifact_root is not None
            else None
        )
        policy = context.policy if context else settings.detection
        baseline = context.baseline_weeks if context else settings.data.baseline_weeks
        recent = context.recent_weeks if context else settings.data.recent_weeks
        candidates = detect_declines(
            repository, policy, baseline_weeks=baseline, recent_weeks=recent
        )
        max_week = int(repository.scalar("SELECT MAX(week) FROM household_week"))
        windows = WindowSpec.from_max_week(
            max_week, baseline_weeks=baseline, recent_weeks=recent
        )
        observed_frame = repository.query(
            "SELECT DISTINCT household_id FROM household_week ORDER BY household_id"
        )
        demographics = repository.query("SELECT * FROM demographics")
    observed = frozenset(str(item) for item in observed_frame.household_id.tolist())
    eligible = frozenset(item.household_id for item in candidates)
    flagged = frozenset(item.household_id for item in candidates if item.flagged)
    if context and (
        len(eligible) != context.expected_eligible
        or len(flagged) != context.expected_flagged
    ):
        raise ValueError("Recomputed detector cohorts disagree with the artifact")
    memberships = PipelineMembership(
        observed=observed,
        eligible=eligible,
        flagged=flagged,
        selected=context.selected if context else None,
        completed=context.completed if context else None,
        insufficient_evidence=context.insufficient if context else None,
        failed=context.failed if context else None,
        governed_action=context.governed_action if context else None,
    )
    provenance = FairnessAuditProvenance(
        dataset_source_repository=manifest.source_repository,
        dataset_source_commit=manifest.source_commit,
        prepared_manifest_sha256=prepared_hash,
        artifact_manifest_sha256=context.manifest_sha256 if context else None,
        detector_policy=policy,
        baseline_start_week=windows.baseline_start,
        baseline_end_week=windows.baseline_end,
        recent_start_week=windows.recent_start,
        recent_end_week=windows.recent_end,
        backend=context.backend if context else None,
        execution_mode=context.execution_mode if context else None,
    )
    return build_fairness_audit(
        demographics=demographics,
        memberships=memberships,
        attributes=attributes,
        policy=FairnessAuditPolicy(minimum_group_size=minimum_group_size),
        provenance=provenance,
    )


def _parser() -> argparse.ArgumentParser:
    """Define the standalone additive fairness-audit command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, default=Path("data/prepared"))
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--attribute", action="append", default=None)
    parser.add_argument("--minimum-group-size", type=int, default=20)
    parser.add_argument("--json-output", type=Path, default=None)
    return parser


def _validate_output(output: Path | None, inputs: Sequence[Path]) -> None:
    """Keep audit output outside validated inputs and symbolic-link chains."""

    if output is None:
        return
    absolute = output.absolute()
    if absolute.is_symlink():
        raise ValueError("Fairness output cannot traverse a symbolic link")
    resolved = output.resolve()
    if any(resolved.is_relative_to(source.resolve()) for source in inputs):
        raise ValueError("Fairness output must remain outside validated inputs")


def _write(audit: FairnessAudit, destination: Path | None) -> None:
    """Print stable JSON or atomically publish it to an explicit destination."""

    rendered = audit.model_dump_json(indent=2) + "\n"
    if destination is None:
        print(rendered, end="")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(rendered)
            stream.flush()
            temporary = Path(stream.name)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only audit and return nonzero for invalid inputs."""

    arguments = _parser().parse_args(argv)
    prepared = cast(Path, arguments.prepared_dir)
    artifact = cast(Path | None, arguments.artifact_root)
    output = cast(Path | None, arguments.json_output)
    try:
        _validate_output(
            output,
            (prepared, *(() if artifact is None else (artifact,))),
        )
        audit = _build(
            prepared,
            artifact,
            cast(list[str] | None, arguments.attribute),
            cast(int, arguments.minimum_group_size),
        )
        _write(audit, output)
    except ValidationError:
        print(
            "Fairness audit failed because an input violated its validated schema.",
            file=sys.stderr,
        )
        return 1
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Fairness audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
