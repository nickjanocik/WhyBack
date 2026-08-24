"""WhyBack command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

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
