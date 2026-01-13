"""Quiver CLI - Universal ADBC query tool."""

import json
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from quiver import __version__
from quiver.backends import get_registry
from quiver.benchmark import BenchmarkRunner
from quiver.output import OutputFormat, format_output


class BenchmarkOutputFormat(str, Enum):
    """Output formats for benchmark results."""

    TABLE = "table"
    JSON = "json"

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


def _check_backend_status(name: str) -> tuple[bool, str]:
    """Check if a backend is available and working.

    Args:
        name: Backend name to check.

    Returns:
        Tuple of (is_available, status_message).
    """
    registry = get_registry()
    try:
        backend_cls = registry.get(name)
        # Try to instantiate and connect briefly
        backend = backend_cls()
        backend.connect()
        backend.close()
        return True, "available"
    except KeyError:
        return False, "not registered"
    except ImportError as e:
        return False, f"missing dependency: {e}"
    except Exception as e:
        return False, f"error: {e}"


# Known backends (registered + planned)
KNOWN_BACKENDS = {
    "duckdb": "Embedded analytical database with native Arrow support",
    "sqlite": "Embedded SQL database via ADBC driver",
    "flightsql": "Generic FlightSQL client for remote databases",
    "influxdb": "InfluxDB time-series database via FlightSQL",
}


@app.command()
def backends() -> None:
    """List available backends and their status."""
    registry = get_registry()
    registered = registry.list_backends()

    table = Table(title="Quiver Backends")
    table.add_column("Backend", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Description")

    for name, description in KNOWN_BACKENDS.items():
        if name in registered:
            available, status = _check_backend_status(name)
            if available:
                status_display = "[green]available[/green]"
            else:
                status_display = f"[yellow]{status}[/yellow]"
        else:
            status_display = "[dim]not installed[/dim]"

        table.add_row(name, status_display, description)

    console.print(table)
    console.print()
    console.print(f"[dim]Registered backends: {len(registered)}[/dim]")


@app.command()
def query(
    sql: str = typer.Argument(..., help="SQL query to execute."),
    backend: str = typer.Option(
        "duckdb",
        "--backend",
        "-b",
        help="Backend to use for query execution.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table, json, csv, or arrow.",
    ),
) -> None:
    """Execute a SQL query against a backend and display results.

    Examples:
        quiver query "SELECT 1 as num"
        quiver query "SELECT * FROM trades" --backend duckdb
        quiver query "SELECT * FROM trades" --output json
        quiver query "SELECT * FROM trades" -b duckdb -o csv
    """
    registry = get_registry()

    # Get backend class
    try:
        backend_cls = registry.get(backend)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Execute query
    try:
        with backend_cls() as db:
            result = db.execute(sql)
    except Exception as e:
        console.print(f"[red]Error executing query: {e}[/red]")
        raise typer.Exit(1)

    # Format and display output
    output_str = format_output(result, output, console)
    if output_str is not None:
        # For json/csv, print the raw string (no Rich formatting)
        print(output_str)


@app.command()
def benchmark(
    sql: str = typer.Argument(..., help="SQL query to benchmark."),
    backends_str: str = typer.Option(
        "duckdb",
        "--backends",
        "-b",
        help="Comma-separated list of backends to benchmark.",
    ),
    iterations: int = typer.Option(
        10,
        "--iterations",
        "-i",
        help="Number of timed iterations per backend.",
    ),
    warmup: int = typer.Option(
        3,
        "--warmup",
        "-w",
        help="Number of warmup iterations (not included in results).",
    ),
    output: BenchmarkOutputFormat = typer.Option(
        BenchmarkOutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table or json.",
    ),
) -> None:
    """Benchmark a SQL query across one or more backends.

    Examples:
        quiver benchmark "SELECT 1"
        quiver benchmark "SELECT * FROM trades" --backends duckdb,sqlite
        quiver benchmark "SELECT 1" --iterations 100 --warmup 5
        quiver benchmark "SELECT 1" -b duckdb,sqlite -o json
    """
    registry = get_registry()
    backend_names = [b.strip() for b in backends_str.split(",")]

    # Validate backends exist
    for name in backend_names:
        try:
            registry.get(name)
        except KeyError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    # Run benchmarks
    results = []
    for name in backend_names:
        backend_cls = registry.get(name)
        try:
            with backend_cls() as db:
                runner = BenchmarkRunner(db)
                result = runner.run(sql, iterations=iterations, warmup=warmup)
                results.append(result)
        except Exception as e:
            console.print(f"[red]Error benchmarking {name}: {e}[/red]")
            raise typer.Exit(1)

    # Output results
    if output == BenchmarkOutputFormat.JSON:
        json_results = []
        for r in results:
            stats = r.stats()
            json_results.append(
                {
                    "backend": r.backend,
                    "query": r.query,
                    "iterations": r.iterations,
                    "warmup": r.warmup,
                    "rows_returned": r.rows_returned,
                    **stats,
                }
            )
        print(json.dumps(json_results, indent=2))
    else:
        # Table output
        table = Table(title="Benchmark Results")
        table.add_column("Backend", style="cyan")
        table.add_column("Mean (ms)", justify="right")
        table.add_column("Median (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")
        table.add_column("Stddev", justify="right")
        table.add_column("Rows", justify="right")

        for r in results:
            stats = r.stats()
            table.add_row(
                r.backend,
                f"{stats.get('mean_ms', 0):.2f}",
                f"{stats.get('median_ms', 0):.2f}",
                f"{stats.get('p95_ms', 0):.2f}",
                f"{stats.get('stddev_ms', 0):.2f}",
                str(r.rows_returned),
            )

        console.print(table)
        console.print()
        console.print(f"[dim]Query: {sql}[/dim]")
        console.print(f"[dim]Iterations: {iterations}, Warmup: {warmup}[/dim]")


if __name__ == "__main__":
    app()
