"""WhyBack command-line interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from whyback import __version__
from whyback.config import load_settings

app = typer.Typer(
    name="whyback",
    help="Evidence-grounded customer retention investigations.",
    no_args_is_help=True,
)
data_app = typer.Typer(help="Acquire and prepare pinned Complete Journey data.")
app.add_typer(data_app, name="data")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"WhyBack {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Find the why. Choose the way back."""


@app.command("config")
def show_config() -> None:
    """Show effective non-secret configuration."""

    settings = load_settings()
    console.print_json(settings.model_dump_json(indent=2))


@data_app.command("status")
def data_status() -> None:
    """Show the configured pinned source and local data path."""

    settings = load_settings()
    console.print(f"Source: {settings.data.source_repository}")
    console.print(f"Commit: {settings.data.source_commit}")
    console.print(f"Data directory: {settings.data_dir}")
    manifest_path = settings.data_dir / "prepared" / "manifest.json"
    console.print(
        f"Prepared manifest: {'available' if manifest_path.is_file() else 'missing'}"
    )


@data_app.command("download")
def data_download(
    force: Annotated[
        bool, typer.Option(help="Replace and reverify existing source files.")
    ] = False,
) -> None:
    """Download the official files at the configured pinned commit."""

    from whyback.data.download import download_sources

    settings = load_settings()
    hashes = download_sources(settings.data_dir / "raw", force=force)
    console.print(f"Verified {len(hashes)} official source files.")


@data_app.command("prepare")
def data_prepare(
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            help="Prepare the complete transaction and promotion data.",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option(help="Rebuild prepared data even when hashes match.")
    ] = False,
    download: Annotated[
        bool,
        typer.Option(
            "--download/--no-download",
            help="Acquire missing official source files before preparation.",
        ),
    ] = True,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override the configured local data directory."),
    ] = None,
) -> None:
    """Prepare validated canonical Parquet tables and a hash manifest."""

    if not full:
        raise typer.BadParameter(
            "WhyBack does not silently substitute a sample; pass --full."
        )
    from whyback.data.download import download_sources
    from whyback.data.prepare import prepare_data

    settings = load_settings()
    root = data_dir or settings.data_dir
    raw_dir = root / "raw"
    if download:
        download_sources(raw_dir)
    manifest = prepare_data(raw_dir, root / "prepared", force=force)
    console.print(
        f"Prepared {len(manifest.prepared)} tables from "
        f"{sum(entry.row_count for entry in manifest.sources):,} source rows."
    )
    console.print(f"Manifest: {root / 'prepared' / 'manifest.json'}")


@app.command("detect")
def detect(
    top: Annotated[int, typer.Option(min=1, help="Maximum flagged rows to show.")] = 20,
    threshold: Annotated[
        float | None,
        typer.Option(min=0.0, max=1.0, help="Override the configured threshold."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            help="Optionally write decline_candidates.csv and sensitivity.csv."
        ),
    ] = None,
) -> None:
    """Rank eligible households with the transparent decline heuristic."""

    from whyback.data.repository import DataRepository
    from whyback.detection.decline import (
        candidates_frame,
        detect_declines,
        sensitivity_diagnostics,
    )

    settings = load_settings()
    with DataRepository(
        settings.data_dir / "prepared", required_tables=("household_week",)
    ) as repository:
        candidates = detect_declines(
            repository,
            settings.detection,
            baseline_weeks=settings.data.baseline_weeks,
            recent_weeks=settings.data.recent_weeks,
            threshold=threshold,
        )
    applied_threshold = (
        settings.detection.decline_threshold if threshold is None else threshold
    )
    flagged = [
        candidate
        for candidate in candidates
        if candidate.decline_score >= applied_threshold
    ]
    table = Table(title="WhyBack decline candidates")
    table.add_column("Rank", justify="right")
    table.add_column("Household")
    table.add_column("Score", justify="right")
    table.add_column("Baseline RSV", justify="right")
    table.add_column("Recent RSV", justify="right")
    table.add_column("Baseline trips", justify="right")
    table.add_column("Recent trips", justify="right")
    for rank, candidate in enumerate(flagged[:top], start=1):
        table.add_row(
            str(rank),
            candidate.household_id,
            f"{candidate.decline_score:.3f}",
            f"{candidate.baseline_retailer_sales_value:,.2f}",
            f"{candidate.recent_retailer_sales_value:,.2f}",
            str(candidate.baseline_distinct_baskets),
            str(candidate.recent_distinct_baskets),
        )
    console.print(table)
    console.print(
        f"{len(flagged):,} of {len(candidates):,} eligible households meet "
        f"the {applied_threshold:.2f} threshold. This score is not a churn probability."
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates_frame(flagged).to_csv(
            output_dir / "decline_candidates.csv", index=False
        )
        sensitivity = sensitivity_diagnostics(
            candidates, settings.detection.sensitivity_thresholds
        )
        candidates_frame(sensitivity).to_csv(
            output_dir / "sensitivity.csv", index=False
        )
        console.print(f"Wrote detector artifacts to {output_dir}")


@app.command("investigate")
def investigate(
    household_id: Annotated[
        str, typer.Option(help="Eligible household identifier to investigate.")
    ],
    backend: Annotated[
        str,
        typer.Option(help="Model backend: scripted or gemini."),
    ] = "scripted",
    output_dir: Annotated[
        Path | None,
        typer.Option(help="Directory for report and trace files."),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Prepared-data directory; defaults to data/prepared."),
    ] = None,
    demo_fault: Annotated[
        str | None,
        typer.Option(
            help="Explicit demo-only fault, such as promotion_response:timeout-always."
        ),
    ] = None,
) -> None:
    """Run one bounded investigation and write its replayable artifacts."""

    from whyback.agent.faults import DemoFaultScenario
    from whyback.agent.scripted_plans import ScriptedPlan
    from whyback.demo import (
        BackendName,
        identify_prepared_dataset,
        locate_snapshot,
        run_investigation,
    )

    if backend not in {"scripted", "gemini"}:
        raise typer.BadParameter("backend must be 'scripted' or 'gemini'")
    settings = load_settings()
    prepared = data_dir or settings.data_dir / "prepared"
    destination = output_dir or (settings.artifact_dir / f"customer_{household_id}")
    try:
        fault = DemoFaultScenario(demo_fault) if demo_fault is not None else None
    except ValueError as error:
        raise typer.BadParameter(f"Unknown demo fault: {demo_fault}") from error
    if fault is not None and backend != "scripted":
        raise typer.BadParameter(
            "Demo faults require --backend scripted so the path is reproducible"
        )
    plan = ScriptedPlan.PROMOTION_TIMEOUT if fault else ScriptedPlan.STANDARD
    try:
        snapshot = locate_snapshot(
            prepared,
            household_id,
            baseline_weeks=settings.data.baseline_weeks,
            recent_weeks=settings.data.recent_weeks,
        )
        dataset_kind = identify_prepared_dataset(prepared)
        outcome = run_investigation(
            prepared_dir=prepared,
            snapshot=snapshot,
            output_directory=destination,
            backend=cast(BackendName, backend),
            dataset_kind=dataset_kind,
            plan=plan,
            demo_fault=fault,
            write_manifest=True,
        )
    except (OSError, RuntimeError, ValueError) as error:
        console.print(f"[red]Investigation failed:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(
        f"Investigation {outcome.state.run_status.value}: {destination / 'report.html'}"
    )
    console.print(f"Replayable trace: {destination / 'trace.html'}")


@app.command("demo")
def demo(
    customers: Annotated[
        int,
        typer.Option(min=1, max=5, help="Number of top-ranked households."),
    ] = 5,
    backend: Annotated[
        str,
        typer.Option(help="scripted uses synthetic data; gemini uses official data."),
    ] = "scripted",
    output_dir: Annotated[
        Path | None,
        typer.Option(help="Override the reviewer-artifact directory."),
    ] = None,
) -> None:
    """Build the complete scripted demo or run the official live top five."""

    from whyback.demo import build_official_demo, build_synthetic_demo

    settings = load_settings()
    if backend == "scripted":
        destination = output_dir or Path("artifacts/demo")
        summary = build_synthetic_demo(destination, customers=customers)
    elif backend == "gemini":
        destination = output_dir or Path("artifacts/live")
        summary = build_official_demo(
            settings.data_dir / "prepared",
            destination,
            customers=customers,
            backend="gemini",
        )
    else:
        raise typer.BadParameter("backend must be 'scripted' or 'gemini'")
    console.print(
        f"Generated {summary.report_count} reports for "
        f"{', '.join(summary.selected_household_ids)}."
    )
    console.print(f"Manifest: {summary.manifest_path}")
    if backend == "gemini" and not summary.live_model_executed:
        console.print(
            "[yellow]Live model execution was skipped because GEMINI_API_KEY is "
            "absent.[/yellow]"
        )


@app.command("verify-artifacts")
def verify_artifacts(
    artifact_root: Annotated[
        Path,
        typer.Argument(help="Artifact tree to validate without modifying it."),
    ] = Path("artifacts/demo"),
) -> None:
    """Validate hashes, report grounding, trace order, and execution labels."""

    repository_verifier = Path(__file__).parents[2] / "scripts" / "verify_artifacts.py"
    packaged_verifier = Path(__file__).with_name("_scripts") / "verify_artifacts.py"
    verifier = (
        repository_verifier if repository_verifier.is_file() else packaged_verifier
    )
    if not verifier.is_file():
        console.print("[red]Artifact verifier is missing from scripts/.[/red]")
        raise typer.Exit(code=1)
    # Artifact truth is historical and must not depend on credentials exported
    # during a later verification session. Explicit skip records remain subject
    # to the verifier's strict skip schema and hash checks.
    command = [
        sys.executable,
        str(verifier),
        str(artifact_root),
        "--allow-live-skipped",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    console.print(completed.stdout, end="")
    if completed.stderr:
        console.print(completed.stderr, style="red", end="")
    if completed.returncode != 0:
        raise typer.Exit(code=1)


@app.command("official-type-a")
def official_type_a(
    output_dir: Annotated[
        Path,
        typer.Option(help="Reviewer-artifact directory for the scripted control."),
    ] = Path("artifacts/official-type-a"),
) -> None:
    """Build the official-data Type A partial-evidence scripted control."""

    from whyback.demo import build_official_type_a_example

    settings = load_settings()
    try:
        summary = build_official_type_a_example(
            settings.data_dir / "prepared", output_dir
        )
    except (OSError, RuntimeError, ValueError) as error:
        console.print(f"[red]Type A control failed:[/red] {error}")
        raise typer.Exit(code=1) from error
    console.print(
        "Generated official Type A scripted control for "
        f"{', '.join(summary.selected_household_ids)}: {summary.manifest_path}"
    )
