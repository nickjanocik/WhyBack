"""Reproducible synthetic and official-data demo orchestration."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from whyback.agent.actions import load_action_catalog
from whyback.agent.faults import DemoFaultInjector, DemoFaultScenario
from whyback.agent.openai_backend import OpenAIResponsesBackend
from whyback.agent.runner import InvestigationOutcome, InvestigationRunner
from whyback.agent.scripted_backend import ScriptedBackend
from whyback.agent.scripted_plans import ScriptedPlan, build_scripted_plan
from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY, load_settings
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository
from whyback.detection.decline import (
    DeclineSnapshot,
    candidates_frame,
    detect_declines,
    sensitivity_diagnostics,
)
from whyback.observability import AuditJsonlWriter
from whyback.reporting import write_report_bundle, write_trace_html
from whyback.tools.registry import build_tool_registry

type BackendName = Literal["scripted", "openai"]
type DatasetKind = Literal["synthetic", "official_complete_journey"]
_DEMO_NAMESPACE = uuid5(NAMESPACE_URL, "https://github.com/whyback/demo")


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


class _IncrementingClock:
    def __init__(self, start: datetime) -> None:
        self._next = start

    def __call__(self) -> datetime:
        value = self._next
        self._next += timedelta(seconds=1)
        return value


def _timestamp_for(run_id: UUID) -> datetime:
    seconds = int(run_id.hex[:6], 16) % 86_400
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


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


def _demo_run_id(dataset_kind: DatasetKind, household_id: str, label: str) -> UUID:
    return uuid5(_DEMO_NAMESPACE, f"{dataset_kind}:{household_id}:{label}")


def synthetic_demo_frames() -> dict[str, pd.DataFrame]:
    """Create a compact, hand-auditable 16-week source-shaped dataset."""

    transactions: list[dict[str, object]] = []
    households = ("101", "102", "103", "104", "105", "106")
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


def _source_hashes(prepared_dir: Path) -> dict[str, str]:
    manifest_path = prepared_dir / "manifest.json"
    if not manifest_path.is_file():
        return {}
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        return {}
    return {
        str(item["filename"]): str(item["sha256"])
        for item in sources
        if isinstance(item, dict) and "filename" in item and "sha256" in item
    }


def _make_backend(
    backend: BackendName,
    *,
    snapshot: DeclineSnapshot,
    run_id: UUID,
    plan: ScriptedPlan,
) -> ScriptedBackend | OpenAIResponsesBackend:
    if backend == "scripted":
        return ScriptedBackend(
            build_scripted_plan(
                plan=plan,
                run_id=run_id,
                household_id=snapshot.household_id,
            )
        )
    settings = load_settings()
    return OpenAIResponsesBackend(
        model=settings.model,
        reasoning_effort=settings.reasoning_effort,
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
) -> InvestigationOutcome:
    """Run the real bounded loop and write a complete report and trace bundle."""

    label = f"{backend}:{plan.value}:{demo_fault.value if demo_fault else 'no-fault'}"
    run_id = _demo_run_id(dataset_kind, snapshot.household_id, label)
    trace_path = output_directory / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.unlink(missing_ok=True)
    selected_backend = _make_backend(
        backend,
        snapshot=snapshot,
        run_id=run_id,
        plan=plan,
    )
    injector = (
        DemoFaultInjector(demo_fault, enabled=True) if demo_fault is not None else None
    )
    with (
        DataRepository(prepared_dir) as repository,
        AuditJsonlWriter(trace_path) as writer,
    ):
        runner = InvestigationRunner(
            backend=selected_backend,
            registry=build_tool_registry(),
            repository=repository,
            action_catalog=load_action_catalog(),
            source_hashes=_source_hashes(prepared_dir),
            fault_injector=injector,
            audit_writer=writer,
            event_clock=_IncrementingClock(_timestamp_for(run_id)),
        )
        outcome = runner.run(snapshot, run_id=run_id)
    write_report_bundle(outcome, output_directory)
    write_trace_html(trace_path, output_directory / "trace.html")
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
                "computed by the registered analytical tools."
                if backend == "scripted"
                else (
                    "These runs used the configured OpenAI Responses backend."
                    if outcomes
                    else "No live model call was attempted because OPENAI_API_KEY "
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


def _write_demo_index(
    output_directory: Path,
    *,
    outcomes: list[InvestigationOutcome],
    dataset_kind: DatasetKind,
    backend: BackendName,
    selected_ids: tuple[str, ...],
    source_manifest: str | None,
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
        "dataset_source_repository": SOURCE_REPOSITORY,
        "dataset_source_commit": SOURCE_COMMIT,
        "source_manifest": source_manifest,
        "backend": backend,
        "execution_mode": execution_mode,
        "reason": (
            "OPENAI_API_KEY was absent; no live model call was attempted."
            if execution_mode == "skipped"
            else None
        ),
        "model_execution": {
            "scripted": "scripted_control",
            "live": "live_openai",
            "skipped": "skipped_no_api_key",
        }[execution_mode],
        "selection_rule": (
            "Highest-ranked eligible decline scores; stable ID tie-break."
        ),
        "selected_household_ids": selected_ids,
        "completed_household_ids": completed,
        "failed_household_ids": failed,
        "skipped_household_ids": selected_ids if execution_mode == "skipped" else (),
        "human_review_required": True,
        "customer_outreach_executed": False,
        "files": _artifact_hashes(output_directory),
    }
    _write_json(output_directory / "manifest.json", manifest)


def build_synthetic_demo(
    output_directory: Path,
    *,
    customers: int = 5,
    backend: BackendName = "scripted",
) -> DemoBuildSummary:
    """Generate deterministic no-credential reports plus failure/partial examples."""

    if customers < 1 or customers > 5:
        raise ValueError("Synthetic demos support between one and five customers")
    if backend == "openai":
        raise ValueError("The OpenAI demo must use official prepared data")
    output_directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="whyback-demo-") as temporary:
        prepared_dir = Path(temporary) / "prepared"
        prepare_frames_for_tests(synthetic_demo_frames(), prepared_dir)
        with DataRepository(
            prepared_dir, required_tables=("household_week",)
        ) as repository:
            candidates = detect_declines(repository)
        selected = tuple(item for item in candidates if item.flagged)[:customers]
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


def build_official_demo(
    prepared_dir: Path,
    output_directory: Path,
    *,
    customers: int = 5,
    backend: BackendName = "openai",
) -> DemoBuildSummary:
    """Select the official top households and optionally run the live backend."""

    if customers < 1:
        raise ValueError("customers must be positive")
    output_directory.mkdir(parents=True, exist_ok=True)
    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        candidates = detect_declines(repository)
    flagged = tuple(item for item in candidates if item.flagged)
    selected = flagged[:customers]
    candidates_frame(flagged).to_csv(
        output_directory / "decline_candidates.csv", index=False
    )
    candidates_frame(sensitivity_diagnostics(candidates, (0.20, 0.30, 0.40))).to_csv(
        output_directory / "sensitivity.csv", index=False
    )

    outcomes: list[InvestigationOutcome] = []
    if backend == "openai" and not os.getenv("OPENAI_API_KEY"):
        selected_ids = tuple(item.household_id for item in selected)
        _write_json(
            output_directory / "live_model_status.json",
            {
                "status": "skipped_no_api_key",
                "execution_mode": "skipped",
                "reason": (
                    "OPENAI_API_KEY was absent; no live model call was attempted."
                ),
                "model": load_settings().model,
                "selected_household_ids": selected_ids,
                "exact_command": ("uv run whyback demo --customers 5 --backend openai"),
                "reports_generated": False,
            },
        )
        _write_demo_index(
            output_directory,
            outcomes=outcomes,
            dataset_kind="official_complete_journey",
            backend=backend,
            selected_ids=selected_ids,
            source_manifest=str(prepared_dir / "manifest.json"),
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
            source_manifest=str(prepared_dir / "manifest.json"),
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
        live_model_executed=backend == "openai" and bool(outcomes),
        manifest_path=output_directory / "manifest.json",
        report_count=len(outcomes),
    )


def locate_snapshot(prepared_dir: Path, household_id: str) -> DeclineSnapshot:
    """Resolve one eligible detector snapshot or raise a precise user error."""

    with DataRepository(
        prepared_dir, required_tables=("household_week",)
    ) as repository:
        candidates = detect_declines(repository)
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
