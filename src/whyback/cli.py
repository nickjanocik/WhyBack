"""WhyBack command-line interface."""

from __future__ import annotations

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
