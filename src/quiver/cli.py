"""Quiver CLI - Universal ADBC query tool."""

import typer
from rich.console import Console

from quiver import __version__

app = typer.Typer(
    name="quiver",
    help="Universal ADBC query tool - explore Arrow connectivity across multiple backends.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"quiver version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Quiver - Universal ADBC query tool."""
    pass


@app.command()
def backends() -> None:
    """List available backends and their status."""
    console.print("[yellow]Backend listing not yet implemented.[/yellow]")
    console.print("Available backends will include: duckdb, sqlite, flightsql, influxdb")


if __name__ == "__main__":
    app()
