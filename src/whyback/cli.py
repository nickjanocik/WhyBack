"""WhyBack command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

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
            repository, settings.detection, threshold=threshold
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
