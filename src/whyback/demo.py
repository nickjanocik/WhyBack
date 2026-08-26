"""Reproducible synthetic and official-data demo orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from whyback.agent.actions import load_action_catalog
from whyback.agent.faults import DemoFaultInjector, DemoFaultScenario
from whyback.agent.gemini_backend import GeminiFunctionCallingBackend
from whyback.agent.runner import InvestigationOutcome, InvestigationRunner
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.scripted_plans import ScriptedPlan, build_scripted_plan
from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY, load_settings
from whyback.data.manifest import DataManifest
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.demo_limits import MIN_DEMO_CUSTOMERS, validate_demo_customer_count
from whyback.detection.decline import (
    DeclineSnapshot,
    candidates_frame,
    detect_declines,
    sensitivity_diagnostics,
)
from whyback.observability import AuditJsonlWriter
from whyback.provenance import RunProvenance
from whyback.reporting import write_report_bundle, write_trace_html
from whyback.tools.registry import build_tool_registry

type BackendName = Literal["scripted", "gemini"]
type DatasetKind = Literal["synthetic", "official_complete_journey"]
_DEMO_NAMESPACE = uuid5(NAMESPACE_URL, "https://github.com/whyback/demo")
SYNTHETIC_DATASET_VERSION = "whyback-synthetic-fixture-v1"
SYNTHETIC_DATASET_REPOSITORY = "whyback/synthetic-fixture"
_ARTIFACT_OWNERSHIP_MARKER = ".whyback-owned-artifact-root.json"
_ARTIFACT_OWNERSHIP_DOCUMENT = {
    "schema_version": 1,
    "product": "WhyBack",
    "scope": "replaceable_generated_artifact_tree",
}


def _gemini_api_key_present() -> bool:
    """Return whether the configured Gemini credential contains non-space text."""

    return bool((os.getenv("GEMINI_API_KEY") or "").strip())


class DemoBuildSummary(BaseModel):
    """Stable command boundary returned after generating reviewer artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    output_directory: Path
    dataset_kind: DatasetKind
    backend: BackendName
    selected_household_ids: tuple[str, ...]
    completed_household_ids: tuple[str, ...]
    failed_household_ids: tuple[str, ...]
    live_model_executed: bool
    manifest_path: Path
    report_count: int = Field(ge=0)


def _select_requested_households(
    flagged: Sequence[DeclineSnapshot],
    customers: int,
    *,
    dataset_label: str,
) -> tuple[DeclineSnapshot, ...]:
    """Return an exact top-ranked batch or fail instead of silently truncating."""

    if len(flagged) < customers:
        raise ValueError(
            f"{dataset_label} contains {len(flagged)} flagged households; "
            f"cannot satisfy the requested batch of {customers}"
        )
    return tuple(flagged[:customers])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True, default=str)}\n",
        encoding="utf-8",
    )


def _write_ownership_marker(directory: Path) -> None:
    _write_json(directory / _ARTIFACT_OWNERSHIP_MARKER, _ARTIFACT_OWNERSHIP_DOCUMENT)


def _is_owned_artifact_tree(directory: Path) -> bool:
    marker = directory / _ARTIFACT_OWNERSHIP_MARKER
    try:
        return json.loads(marker.read_text(encoding="utf-8")) == (
            _ARTIFACT_OWNERSHIP_DOCUMENT
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def _demo_run_id(dataset_kind: DatasetKind, household_id: str, label: str) -> UUID:
    return uuid5(_DEMO_NAMESPACE, f"{dataset_kind}:{household_id}:{label}")


def synthetic_demo_frames() -> dict[str, pd.DataFrame]:
    """Create a compact, hand-auditable 16-week source-shaped dataset."""

    transactions: list[dict[str, object]] = []
    # Twenty-four households keep the fixture compact while clearing the declared
    # population/category cohort minimum of 20 after target exclusion. The first
    # six retain the original hand-auditable decline profiles; the remainder form
    # a stable contemporaneous comparison population.
    households = tuple(str(identifier) for identifier in range(101, 125))
    recent_active_weeks = {
        "101": 2,
        "102": 3,
        "103": 4,
        "104": 5,
        "105": 6,
        "106": 8,
    }
    recent_values = {
        "101": 6.0,
        "102": 7.0,
        "103": 8.0,
        "104": 9.0,
        "105": 9.5,
        "106": 10.0,
    }
    recent_active_weeks.update(
        {household_id: 8 for household_id in households if household_id >= "107"}
    )
    recent_values.update(
        {household_id: 10.0 for household_id in households if household_id >= "107"}
    )
    for household_index, household_id in enumerate(households, start=1):
        store_id = str(10 + household_index % 2)
        for week in range(1, 9):
            for visit in range(2):
                basket_id = f"{household_id}{week:02d}{visit}"
                product_id = ("1000", "2000", "3000")[(week + visit) % 3]
                timestamp = datetime(2017, 1, 1) + timedelta(
                    days=(week - 1) * 7 + visit
                )
                transactions.append(
                    {
                        "household_id": household_id,
                        "store_id": store_id,
                        "basket_id": basket_id,
                        "product_id": product_id,
                        "quantity": 1.0,
                        "sales_value": 10.0,
                        "retail_disc": 0.0,
                        "coupon_disc": 0.0,
                        "coupon_match_disc": 0.0,
                        "week": week,
                        "transaction_timestamp": timestamp.replace(hour=10).isoformat(),
                    }
                )
        for offset in range(recent_active_weeks[household_id]):
            week = 9 + offset
            product_id = ("1000", "2000", "3000")[(week + household_index) % 3]
            timestamp = datetime(2017, 3, 1) + timedelta(days=offset * 7)
            transactions.append(
                {
                    "household_id": household_id,
                    "store_id": store_id if household_id != "104" else "12",
                    "basket_id": f"{household_id}{week:02d}0",
                    "product_id": product_id,
                    "quantity": 1.0,
                    "sales_value": recent_values[household_id],
                    "retail_disc": 1.0 if week % 2 == 0 else 0.0,
                    "coupon_disc": 0.5 if household_id == "101" and week == 9 else 0.0,
                    "coupon_match_disc": 0.0,
                    "week": week,
                    "transaction_timestamp": timestamp.replace(hour=11).isoformat(),
                }
            )

    promotions: list[dict[str, object]] = []
    for product_id in ("1000", "2000", "3000"):
        for store_id in ("10", "11", "12"):
            for week in range(1, 17):
                promotions.append(
                    {
                        "product_id": product_id,
                        "store_id": store_id,
                        "display_location": "3" if week % 2 == 0 else "0",
                        "mailer_location": "A" if week % 3 == 0 else "0",
                        "week": week,
                    }
                )
                if product_id == "1000" and store_id == "10" and week == 2:
                    promotions.append(
                        {
                            "product_id": product_id,
                            "store_id": store_id,
                            "display_location": "5",
                            "mailer_location": "0",
                            "week": week,
                        }
                    )

    products = pd.DataFrame(
        [
            {
                "product_id": "1000",
                "manufacturer_id": "1",
                "department": "GROCERY",
                "brand": "National",
                "product_category": "SOUP",
                "product_type": "CANNED",
                "package_size": "10 OZ",
            },
            {
                "product_id": "2000",
                "manufacturer_id": "2",
                "department": "GROCERY",
                "brand": "Private",
                "product_category": "PASTA",
                "product_type": "DRY",
                "package_size": "12 OZ",
            },
            {
                "product_id": "3000",
                "manufacturer_id": "3",
                "department": "PRODUCE",
                "brand": "National",
                "product_category": None,
                "product_type": None,
                "package_size": None,
            },
        ]
    )
    campaigns = pd.DataFrame(
        [
            {"campaign_id": "1", "household_id": "101"},
            {"campaign_id": "2", "household_id": "102"},
        ]
    )
    campaign_descriptions = pd.DataFrame(
        [
            {
                "campaign_id": "1",
                "campaign_type": "Type A",
                "start_date": "2017-01-01",
                "end_date": "2017-04-30",
            },
            {
                "campaign_id": "2",
                "campaign_type": "Type B",
                "start_date": "2017-01-01",
                "end_date": "2017-04-30",
            },
        ]
    )
    coupons = pd.DataFrame(
        [
            {"coupon_upc": "900", "product_id": "1000", "campaign_id": "1"},
            {"coupon_upc": "901", "product_id": "2000", "campaign_id": "2"},
        ]
    )
    coupon_redemptions = pd.DataFrame(
        [
            {
                "household_id": "101",
                "coupon_upc": "900",
                "campaign_id": "1",
                "redemption_date": "2017-03-01",
            }
        ]
    )
    return {
        "transactions": pd.DataFrame(transactions),
        "promotions": pd.DataFrame(promotions),
        "products": products,
        "demographics": pd.DataFrame(
            [{"household_id": item} for item in households[:2]]
        ),
        "campaigns": campaigns,
        "campaign_descriptions": campaign_descriptions,
        "coupons": coupons,
        "coupon_redemptions": coupon_redemptions,
    }


def _dataset_kind_for_manifest(manifest: DataManifest) -> DatasetKind:
    if (
        manifest.source_repository == SYNTHETIC_DATASET_REPOSITORY
        and manifest.source_commit == SYNTHETIC_DATASET_VERSION
    ):
        return "synthetic"
    elif (
        manifest.source_repository == SOURCE_REPOSITORY
        and manifest.source_commit == SOURCE_COMMIT
    ):
        return "official_complete_journey"
    else:
        raise ValueError(
            "Prepared data has an unsupported source identity: "
            f"{manifest.source_repository}@{manifest.source_commit}"
        )


def _validated_dataset_identity(
    manifest: DataManifest, expected_kind: DatasetKind
) -> tuple[str, str]:
    actual_kind = _dataset_kind_for_manifest(manifest)
    if actual_kind != expected_kind:
        raise ValueError(
            f"Prepared data is {actual_kind}, not the requested {expected_kind}; "
            "refusing to publish misleading provenance."
        )
    return manifest.source_repository, manifest.source_commit


def identify_prepared_dataset(prepared_dir: Path) -> DatasetKind:
    """Validate a prepared dataset and return its honest publication label."""

    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        manifest = repository.manifest
        if manifest is None:
            raise ValueError("Prepared data manifest validation was not performed")
        return _dataset_kind_for_manifest(manifest)


def _manifest_hashes(prepared_dir: Path, manifest: DataManifest) -> dict[str, str]:
    return {
        "manifest/manifest.json": _sha256(prepared_dir / "manifest.json"),
        **{f"source/{item.filename}": item.sha256 for item in manifest.sources},
        **{f"prepared/{item.filename}": item.sha256 for item in manifest.prepared},
    }


def _make_backend(
    backend: BackendName,
    *,
    snapshot: DeclineSnapshot,
    run_id: UUID,
    plan: ScriptedPlan,
) -> ScriptedBackend | GeminiFunctionCallingBackend:
    if backend == "scripted":
        return ScriptedBackend(
            build_scripted_plan(
                plan=plan,
                run_id=run_id,
                household_id=snapshot.household_id,
            )
        )
    settings = load_settings()
    return GeminiFunctionCallingBackend(
        model=settings.model,
        thinking_level=settings.thinking_level,
    )


def run_investigation(
    *,
    prepared_dir: Path,
    snapshot: DeclineSnapshot,
    output_directory: Path,
    backend: BackendName,
    dataset_kind: DatasetKind,
    plan: ScriptedPlan = ScriptedPlan.STANDARD,
    demo_fault: DemoFaultScenario | None = None,
    write_manifest: bool = False,
) -> InvestigationOutcome:
    """Run the real bounded loop and write a complete report and trace bundle."""

    with DataRepository(prepared_dir) as repository:
        manifest = repository.manifest
        if manifest is None:
            raise ValueError("Prepared data manifest validation was not performed")
        source_repository, source_commit = _validated_dataset_identity(
            manifest, dataset_kind
        )
        source_hashes = _manifest_hashes(prepared_dir, manifest)
        label = (
            f"{backend}:{plan.value}:{demo_fault.value if demo_fault else 'no-fault'}"
        )
        run_id = (
            _demo_run_id(dataset_kind, snapshot.household_id, label)
            if backend == "scripted"
            else uuid4()
        )
        trace_path = output_directory / "trace.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        if backend == "scripted":
            trace_path.unlink(missing_ok=True)
        elif any(
            (output_directory / name).exists()
            for name in (
                "trace.jsonl",
                "trace.html",
                "report.json",
                "report.md",
                "report.html",
            )
        ):
            raise FileExistsError(
                "Live investigation output already exists; choose a new output "
                "directory to preserve the prior audit run."
            )
        selected_backend = _make_backend(
            backend,
            snapshot=snapshot,
            run_id=run_id,
            plan=plan,
        )
        injector = (
            DemoFaultInjector(demo_fault, enabled=True)
            if demo_fault is not None
            else None
        )
        with AuditJsonlWriter(trace_path) as writer:
            runner = InvestigationRunner(
                backend=selected_backend,
                registry=build_tool_registry(),
                repository=repository,
                action_catalog=load_action_catalog(),
                source_hashes=source_hashes,
                dataset_source_commit=source_commit,
                dataset_source_repository=source_repository,
                dataset_kind=dataset_kind,
                fault_injector=injector,
                audit_writer=writer,
            )
            outcome = runner.run(snapshot, run_id=run_id)
        outcome = outcome.model_copy(
            update={
                "provenance": RunProvenance(
                    dataset_kind=dataset_kind,
                    dataset_source_repository=source_repository,
                    dataset_source_commit=source_commit,
                    source_hashes=source_hashes,
                    backend=backend,
                    execution_mode=(
                        "scripted_control" if backend == "scripted" else "live_gemini"
                    ),
                    model=selected_backend.model_name,
                    generated_at=datetime.now(UTC),
                )
            }
        )
    write_report_bundle(outcome, output_directory)
    write_trace_html(trace_path, output_directory / "trace.html")
    if write_manifest:
        terminal = outcome.state.run_status.value in {
            "completed",
            "insufficient_evidence",
        }
        source_manifest: str | None = None
        if dataset_kind == "official_complete_journey":
            source_manifest = "data_provenance.json"
            _write_data_provenance(
                prepared_dir,
                output_directory / source_manifest,
                expected_kind=dataset_kind,
            )
        _write_json(
            output_directory / "manifest.json",
            {
                "schema_version": 1,
                "product": "WhyBack",
                "artifact_profile": "standalone_run",
                "dataset_kind": dataset_kind,
                "dataset_source_repository": source_repository,
                "dataset_source_commit": source_commit,
                "source_manifest": source_manifest,
                "backend": backend,
                "execution_mode": "scripted" if backend == "scripted" else "live",
                "model_execution": (
                    "scripted_control" if backend == "scripted" else "live_gemini"
                ),
                "timing_mode": "actual_utc_and_monotonic",
                "selected_household_ids": (snapshot.household_id,),
                "completed_household_ids": (snapshot.household_id,) if terminal else (),
                "failed_household_ids": () if terminal else (snapshot.household_id,),
                "skipped_household_ids": (),
                "human_review_required": True,
                "customer_outreach_executed": False,
                "files": _artifact_hashes(output_directory),
            },
        )
    return outcome


def _results_markdown(
    *,
    dataset_label: str,
    backend: BackendName,
    outcomes: list[InvestigationOutcome],
) -> str:
    rows = []
    for outcome in outcomes:
        state = outcome.state
        action = (
            outcome.verification.final.next_best_action_id.value
            if outcome.verification is not None
            and outcome.verification.final is not None
            else "UNAVAILABLE"
        )
        rows.append(
            f"| {state.household_id} | {state.detector_snapshot.decline_score:.3f} "
            f"| {state.run_status.value} | {action} |"
        )
    return "\n".join(
        [
            "# WhyBack demo results",
            "",
            "### Find the why. Choose the way back.",
            "",
            f"Dataset: **{dataset_label}**. Backend: **{backend}**.",
            "",
            (
                "Scripted runs are deterministic orchestration controls and are not "
                "presented as live model judgments. All displayed metrics were "
                "computed by the deterministic detector or registered analytical "
                "tools."
                if backend == "scripted"
                else (
                    "These runs used the configured Gemini function-calling backend."
                    if outcomes
                    else "No live model call was attempted because GEMINI_API_KEY "
                    "was absent."
                )
            ),
            "",
            "| Household | Decline score | Status | Human-reviewed action |",
            "|---|---:|---|---|",
            *rows,
            "",
            "The decline score is a transparent heuristic, not a churn probability.",
            "Every action is a recommendation requiring human review; no outreach "
            "was executed.",
            "",
        ]
    )


def _artifact_hashes(output_directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(output_directory)): _sha256(path)
        for path in sorted(output_directory.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def _write_data_provenance(
    prepared_dir: Path,
    destination: Path,
    *,
    expected_kind: DatasetKind,
) -> None:
    """Commit-friendly snapshot of the validated prepared-data identity."""

    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        manifest = repository.manifest
        if manifest is None:
            raise ValueError("Prepared data manifest validation was not performed")
        actual_kind = _dataset_kind_for_manifest(manifest)
        if actual_kind != expected_kind:
            raise ValueError(
                f"Prepared data is {actual_kind}, not the requested {expected_kind}; "
                "refusing to publish misleading provenance."
            )
    _write_json(
        destination,
        {
            "schema_version": 1,
            "dataset_kind": actual_kind,
            "manifest_sha256": _sha256(prepared_dir / "manifest.json"),
            "manifest": manifest.model_dump(mode="json"),
        },
    )


def _write_demo_index(
    output_directory: Path,
    *,
    outcomes: list[InvestigationOutcome],
    dataset_kind: DatasetKind,
    backend: BackendName,
    selected_ids: tuple[str, ...],
    source_manifest: str | None,
    selection_rule: str = (
        "Highest-ranked eligible decline scores; stable ID tie-break."
    ),
) -> None:
    reports = [
        json.loads(
            (
                output_directory / f"customer_{item.state.household_id}" / "report.json"
            ).read_text(encoding="utf-8")
        )
        for item in outcomes
    ]
    _write_json(output_directory / "results.json", reports)
    (output_directory / "RESULTS.md").write_text(
        _results_markdown(
            dataset_label=(
                "synthetic fixture"
                if dataset_kind == "synthetic"
                else "official full Complete Journey"
            ),
            backend=backend,
            outcomes=outcomes,
        ),
        encoding="utf-8",
    )
    completed = tuple(
        item.state.household_id
        for item in outcomes
        if item.state.run_status.value in {"completed", "insufficient_evidence"}
    )
    execution_mode = (
        "scripted" if backend == "scripted" else "live" if outcomes else "skipped"
    )
    dataset_source_repository = (
        SYNTHETIC_DATASET_REPOSITORY
        if dataset_kind == "synthetic"
        else SOURCE_REPOSITORY
    )
    dataset_source_commit = (
        SYNTHETIC_DATASET_VERSION if dataset_kind == "synthetic" else SOURCE_COMMIT
    )
    failed = (
        tuple(
            item.state.household_id
            for item in outcomes
            if item.state.household_id not in completed
        )
        if execution_mode != "skipped"
        else ()
    )
    manifest = {
        "schema_version": 1,
        "product": "WhyBack",
        "tagline": "Find the why. Choose the way back.",
        "dataset_kind": dataset_kind,
        "dataset_source_repository": dataset_source_repository,
        "dataset_source_commit": dataset_source_commit,
        "source_manifest": source_manifest,
        "backend": backend,
        "execution_mode": execution_mode,
        "reason": (
            "GEMINI_API_KEY was absent; no live model call was attempted."
            if execution_mode == "skipped"
            else None
        ),
        "model_execution": {
            "scripted": "scripted_control",
            "live": "live_gemini",
            "skipped": "skipped_no_api_key",
        }[execution_mode],
        "timing_mode": "actual_utc_and_monotonic",
        "selection_rule": selection_rule,
        "selected_household_ids": selected_ids,
        "completed_household_ids": completed,
        "failed_household_ids": failed,
        "skipped_household_ids": selected_ids if execution_mode == "skipped" else (),
        "human_review_required": True,
        "customer_outreach_executed": False,
        "files": _artifact_hashes(output_directory),
    }
    _write_json(output_directory / "manifest.json", manifest)


def _build_synthetic_demo_contents(
    output_directory: Path,
    *,
    customers: int = MIN_DEMO_CUSTOMERS,
    backend: BackendName = "scripted",
) -> DemoBuildSummary:
    """Generate deterministic no-credential reports plus failure/partial examples."""

    validate_demo_customer_count(customers)
    if backend == "gemini":
        raise ValueError("The Gemini demo must use official prepared data")
    output_directory.mkdir(parents=True, exist_ok=True)
    _write_ownership_marker(output_directory)
    with TemporaryDirectory(prefix="whyback-demo-") as temporary:
        prepared_dir = Path(temporary) / "prepared"
        prepare_frames_for_tests(synthetic_demo_frames(), prepared_dir)
        settings = load_settings()
        with DataRepository(
            prepared_dir, required_tables=("household_week",)
        ) as repository:
            candidates = detect_declines(
                repository,
                settings.detection,
                baseline_weeks=settings.data.baseline_weeks,
                recent_weeks=settings.data.recent_weeks,
            )
        flagged = tuple(item for item in candidates if item.flagged)
        selected = _select_requested_households(
            flagged,
            customers,
            dataset_label="Synthetic data",
        )
        candidates_frame(candidates).to_csv(
            output_directory / "decline_candidates.csv", index=False
        )
        candidates_frame(
            sensitivity_diagnostics(candidates, (0.20, 0.30, 0.40))
        ).to_csv(output_directory / "sensitivity.csv", index=False)

        outcomes = [
            run_investigation(
                prepared_dir=prepared_dir,
                snapshot=snapshot,
                output_directory=(
                    output_directory / f"customer_{snapshot.household_id}"
                ),
                backend="scripted",
                dataset_kind="synthetic",
            )
            for snapshot in selected
        ]
        primary = selected[0]
        run_investigation(
            prepared_dir=prepared_dir,
            snapshot=primary,
            output_directory=output_directory / "failure_example",
            backend="scripted",
            dataset_kind="synthetic",
            plan=ScriptedPlan.PROMOTION_TIMEOUT,
            demo_fault=DemoFaultScenario.PROMOTION_TIMEOUT_ALWAYS,
        )
        run_investigation(
            prepared_dir=prepared_dir,
            snapshot=primary,
            output_directory=output_directory / "type_a_partial_example",
            backend="scripted",
            dataset_kind="synthetic",
            plan=ScriptedPlan.TYPE_A_PARTIAL,
        )
        from whyback.evaluation_cases import build_normalized_synthetic_runs

        build_normalized_synthetic_runs(
            output_directory / "evals" / "normalized_runs.json"
        )
        selected_ids = tuple(item.household_id for item in selected)
        _write_demo_index(
            output_directory,
            outcomes=outcomes,
            dataset_kind="synthetic",
            backend="scripted",
            selected_ids=selected_ids,
            source_manifest=None,
        )
    completed = tuple(
        item.state.household_id
        for item in outcomes
        if item.state.run_status.value in {"completed", "insufficient_evidence"}
    )
    failed = tuple(item for item in selected_ids if item not in completed)
    return DemoBuildSummary(
        output_directory=output_directory,
        dataset_kind="synthetic",
        backend="scripted",
        selected_household_ids=selected_ids,
        completed_household_ids=completed,
        failed_household_ids=failed,
        live_model_executed=False,
        manifest_path=output_directory / "manifest.json",
        report_count=len(outcomes),
    )


def _publish_staged_directory(staging: Path, destination: Path) -> None:
    """Atomically publish an exact owned tree while preserving rollback."""

    resolved_destination = destination.resolve()
    protected = {
        Path("/").resolve(),
        Path.cwd().resolve(),
        Path.home().resolve(),
        Path(__file__).parents[2].resolve(),
    }
    if resolved_destination in protected:
        raise ValueError("Refusing to replace a protected broad directory")
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError("Demo output must be a directory and cannot be a symlink")
    destination_was_empty = destination.exists() and not any(destination.iterdir())
    if (
        destination.exists()
        and not destination_was_empty
        and not _is_owned_artifact_tree(destination)
    ):
        raise ValueError(
            "Existing non-empty output is not marked as a replaceable WhyBack "
            "artifact tree"
        )
    if not _is_owned_artifact_tree(staging):
        raise ValueError("Staging directory lacks the WhyBack ownership marker")
    backup = destination.parent / f".{destination.name}.backup-{uuid4().hex}"
    moved_existing = False
    try:
        if destination.exists():
            destination.replace(backup)
            moved_existing = True
        staging.replace(destination)
    except Exception:
        if moved_existing and backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    if moved_existing:
        if destination_was_empty:
            backup.rmdir()
        elif not _is_owned_artifact_tree(backup):
            raise RuntimeError("Refusing to remove an unowned artifact backup")
        else:
            shutil.rmtree(backup)


def build_synthetic_demo(
    output_directory: Path,
    *,
    customers: int = MIN_DEMO_CUSTOMERS,
    backend: BackendName = "scripted",
) -> DemoBuildSummary:
    """Build an exact synthetic artifact tree in staging, then publish it."""

    validate_demo_customer_count(customers)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        mkdtemp(
            prefix=f".{output_directory.name}.staging-",
            dir=output_directory.parent,
        )
    )
    try:
        summary = _build_synthetic_demo_contents(
            staging,
            customers=customers,
            backend=backend,
        )
        _publish_staged_directory(staging, output_directory)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return summary.model_copy(
        update={
            "output_directory": output_directory,
            "manifest_path": output_directory / "manifest.json",
        }
    )


def _build_official_demo_contents(
    prepared_dir: Path,
    output_directory: Path,
    *,
    customers: int = MIN_DEMO_CUSTOMERS,
    backend: BackendName = "gemini",
) -> DemoBuildSummary:
    """Select the official top households and optionally run the live backend."""

    validate_demo_customer_count(customers)
    output_directory.mkdir(parents=True, exist_ok=True)
    _write_ownership_marker(output_directory)
    settings = load_settings()
    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        candidates = detect_declines(
            repository,
            settings.detection,
            baseline_weeks=settings.data.baseline_weeks,
            recent_weeks=settings.data.recent_weeks,
        )
    flagged = tuple(item for item in candidates if item.flagged)
    selected = _select_requested_households(
        flagged,
        customers,
        dataset_label="Official data",
    )
    candidates_frame(flagged).to_csv(
        output_directory / "decline_candidates.csv", index=False
    )
    candidates_frame(sensitivity_diagnostics(candidates, (0.20, 0.30, 0.40))).to_csv(
        output_directory / "sensitivity.csv", index=False
    )
    _write_data_provenance(
        prepared_dir,
        output_directory / "data_provenance.json",
        expected_kind="official_complete_journey",
    )

    outcomes: list[InvestigationOutcome] = []
    if backend == "gemini" and not _gemini_api_key_present():
        selected_ids = tuple(item.household_id for item in selected)
        _write_json(
            output_directory / "live_model_status.json",
            {
                "status": "skipped_no_api_key",
                "execution_mode": "skipped",
                "reason": (
                    "GEMINI_API_KEY was absent; no live model call was attempted."
                ),
                "model": load_settings().model,
                "selected_household_ids": selected_ids,
                "exact_command": (
                    f"uv run whyback demo --customers {customers} --backend gemini"
                ),
                "reports_generated": False,
            },
        )
        _write_demo_index(
            output_directory,
            outcomes=outcomes,
            dataset_kind="official_complete_journey",
            backend=backend,
            selected_ids=selected_ids,
            source_manifest="data_provenance.json",
        )
    else:
        for snapshot in selected:
            outcomes.append(
                run_investigation(
                    prepared_dir=prepared_dir,
                    snapshot=snapshot,
                    output_directory=(
                        output_directory / f"customer_{snapshot.household_id}"
                    ),
                    backend=backend,
                    dataset_kind="official_complete_journey",
                )
            )
        selected_ids = tuple(item.household_id for item in selected)
        _write_demo_index(
            output_directory,
            outcomes=outcomes,
            dataset_kind="official_complete_journey",
            backend=backend,
            selected_ids=selected_ids,
            source_manifest="data_provenance.json",
        )
    completed = tuple(
        item.state.household_id
        for item in outcomes
        if item.state.run_status.value in {"completed", "insufficient_evidence"}
    )
    return DemoBuildSummary(
        output_directory=output_directory,
        dataset_kind="official_complete_journey",
        backend=backend,
        selected_household_ids=selected_ids,
        completed_household_ids=completed,
        failed_household_ids=(
            tuple(item for item in selected_ids if item not in completed)
            if outcomes
            else ()
        ),
        live_model_executed=backend == "gemini" and bool(outcomes),
        manifest_path=output_directory / "manifest.json",
        report_count=len(outcomes),
    )


def _has_preserved_run_artifacts(directory: Path) -> bool:
    if not directory.exists():
        return False
    return any(directory.rglob("trace.jsonl")) or any(directory.rglob("report.json"))


def _initialize_live_official_output(destination: Path) -> None:
    """Replace only an empty or explicitly replaceable tree before a live run."""

    if _has_preserved_run_artifacts(destination):
        raise FileExistsError(
            "Official run artifacts already exist; choose a new output directory "
            "so no historical live or scripted audit is deleted."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        mkdtemp(
            prefix=f".{destination.name}.live-initialization-",
            dir=destination.parent,
        )
    )
    try:
        _write_ownership_marker(staging)
        _publish_staged_directory(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def build_official_demo(
    prepared_dir: Path,
    output_directory: Path,
    *,
    customers: int = MIN_DEMO_CUSTOMERS,
    backend: BackendName = "gemini",
) -> DemoBuildSummary:
    """Build official status artifacts without overwriting any prior run audit."""

    validate_demo_customer_count(customers)
    if _has_preserved_run_artifacts(output_directory):
        raise FileExistsError(
            "Official run artifacts already exist; choose a new output directory "
            "so no historical live or scripted audit is deleted."
        )
    if backend == "gemini" and _gemini_api_key_present():
        _initialize_live_official_output(output_directory)
        return _build_official_demo_contents(
            prepared_dir,
            output_directory,
            customers=customers,
            backend=backend,
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        mkdtemp(
            prefix=f".{output_directory.name}.staging-",
            dir=output_directory.parent,
        )
    )
    try:
        summary = _build_official_demo_contents(
            prepared_dir,
            staging,
            customers=customers,
            backend=backend,
        )
        _publish_staged_directory(staging, output_directory)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return summary.model_copy(
        update={
            "output_directory": output_directory,
            "manifest_path": output_directory / "manifest.json",
        }
    )


def _build_official_type_a_contents(
    prepared_dir: Path, output_directory: Path
) -> DemoBuildSummary:
    settings = load_settings()
    output_directory.mkdir(parents=True, exist_ok=True)
    _write_ownership_marker(output_directory)
    with DataRepository(
        prepared_dir,
        required_tables=(
            "household_week",
            "campaigns",
            "campaign_descriptions",
        ),
    ) as repository:
        candidates = detect_declines(
            repository,
            settings.detection,
            baseline_weeks=settings.data.baseline_weeks,
            recent_weeks=settings.data.recent_weeks,
        )
        type_a_frame = repository.query(
            """
            SELECT DISTINCT c.household_id
            FROM campaigns AS c
            JOIN campaign_descriptions AS d USING (campaign_id)
            WHERE LOWER(TRIM(d.campaign_type)) = 'type a'
            ORDER BY c.household_id
            """
        )
    type_a_ids = {str(value) for value in type_a_frame["household_id"].tolist()}
    snapshot = next(
        (
            item
            for item in candidates
            if item.flagged and item.household_id in type_a_ids
        ),
        None,
    )
    if snapshot is None:
        raise ValueError("No flagged official Type A participant was available")
    outcome = run_investigation(
        prepared_dir=prepared_dir,
        snapshot=snapshot,
        output_directory=output_directory / f"customer_{snapshot.household_id}",
        backend="scripted",
        dataset_kind="official_complete_journey",
        plan=ScriptedPlan.TYPE_A_PARTIAL,
    )
    candidates_frame(tuple(item for item in candidates if item.flagged)).to_csv(
        output_directory / "decline_candidates.csv", index=False
    )
    _write_data_provenance(
        prepared_dir,
        output_directory / "data_provenance.json",
        expected_kind="official_complete_journey",
    )
    _write_demo_index(
        output_directory,
        outcomes=[outcome],
        dataset_kind="official_complete_journey",
        backend="scripted",
        selected_ids=(snapshot.household_id,),
        source_manifest="data_provenance.json",
        selection_rule=(
            "Highest-ranked flagged official household with recorded Type A "
            "campaign participation; stable detector ranking and ID tie-break."
        ),
    )
    completed = (
        (snapshot.household_id,)
        if outcome.state.run_status.value in {"completed", "insufficient_evidence"}
        else ()
    )
    return DemoBuildSummary(
        output_directory=output_directory,
        dataset_kind="official_complete_journey",
        backend="scripted",
        selected_household_ids=(snapshot.household_id,),
        completed_household_ids=completed,
        failed_household_ids=() if completed else (snapshot.household_id,),
        live_model_executed=False,
        manifest_path=output_directory / "manifest.json",
        report_count=1,
    )


def build_official_type_a_example(
    prepared_dir: Path, output_directory: Path
) -> DemoBuildSummary:
    """Publish the legitimate official Type A partial-evidence control."""

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        mkdtemp(
            prefix=f".{output_directory.name}.staging-",
            dir=output_directory.parent,
        )
    )
    try:
        summary = _build_official_type_a_contents(prepared_dir, staging)
        _publish_staged_directory(staging, output_directory)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return summary.model_copy(
        update={
            "output_directory": output_directory,
            "manifest_path": output_directory / "manifest.json",
        }
    )


def locate_snapshot(
    prepared_dir: Path,
    household_id: str,
    *,
    baseline_weeks: int = 8,
    recent_weeks: int = 8,
) -> DeclineSnapshot:
    """Resolve one eligible detector snapshot or raise a precise user error."""

    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        candidates = detect_declines(
            repository,
            baseline_weeks=baseline_weeks,
            recent_weeks=recent_weeks,
        )
    for candidate in candidates:
        if candidate.household_id == household_id:
            return candidate
    raise ValueError(
        f"Household {household_id!r} does not have an eligible detector baseline"
    )


def run_id_for_testing(
    dataset_kind: DatasetKind, household_id: str, label: str
) -> UUID:
    """Expose stable IDs for golden-trace normalization tests."""

    return _demo_run_id(dataset_kind, household_id, label)
