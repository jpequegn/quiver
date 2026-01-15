"""Quiver CLI - Universal ADBC query tool."""

import json
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from quiver import __version__
from quiver.backends import get_registry
from quiver.benchmark import BenchmarkRunner
from quiver.loaders import FinancialLoader, ObservabilityLoader
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

# Subcommand group for data loading
load_app = typer.Typer(
    name="load",
    help="Load sample datasets into backends for testing and benchmarking.",
    no_args_is_help=True,
)
app.add_typer(load_app)


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


@app.command()
def compare(
    sql: str = typer.Argument(..., help="SQL query to benchmark."),
    backend: str = typer.Option(
        "duckdb",
        "--backend",
        "-b",
        help="Backend to compare ADBC vs native performance.",
    ),
    iterations: int = typer.Option(
        10,
        "--iterations",
        "-i",
        help="Number of timed iterations.",
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
    """Compare ADBC vs native connector performance for a backend.

    This command answers: "What's the overhead of using ADBC vs native?"
    For columnar databases like DuckDB, ADBC often has zero or negative overhead!

    Examples:
        quiver compare "SELECT 1"
        quiver compare "SELECT * FROM trades" --backend duckdb
        quiver compare "SELECT 1" --iterations 50 --warmup 5
        quiver compare "SELECT 1" -o json
    """
    registry = get_registry()

    # Get backend class
    try:
        backend_cls = registry.get(backend)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Check if backend supports native comparison
    with backend_cls() as db:
        if not db.supports_native_comparison():
            console.print(
                f"[red]Error: Backend '{backend}' does not support native comparison.[/red]"
            )
            console.print(
                "[dim]Only backends with both ADBC and native paths can be compared.[/dim]"
            )
            raise typer.Exit(1)

    # Run benchmarks
    try:
        with backend_cls() as db:
            runner = BenchmarkRunner(db)
            adbc_result = runner.run(sql, iterations=iterations, warmup=warmup)
            native_result = runner.run_native(sql, iterations=iterations, warmup=warmup)
    except Exception as e:
        console.print(f"[red]Error running comparison: {e}[/red]")
        raise typer.Exit(1)

    adbc_stats = adbc_result.stats()
    native_stats = native_result.stats()

    # Calculate percentage difference (positive = native is slower)
    adbc_mean = adbc_stats.get("mean_ms", 0)
    native_mean = native_stats.get("mean_ms", 0)
    if adbc_mean > 0:
        pct_diff = ((native_mean - adbc_mean) / adbc_mean) * 100
    else:
        pct_diff = 0.0

    # Output results
    if output == BenchmarkOutputFormat.JSON:
        json_results = [
            {
                "method": "ADBC",
                "mean_ms": adbc_stats.get("mean_ms", 0),
                "median_ms": adbc_stats.get("median_ms", 0),
                "p95_ms": adbc_stats.get("p95_ms", 0),
                "stddev_ms": adbc_stats.get("stddev_ms", 0),
                "vs_baseline": "baseline",
            },
            {
                "method": "Native",
                "mean_ms": native_stats.get("mean_ms", 0),
                "median_ms": native_stats.get("median_ms", 0),
                "p95_ms": native_stats.get("p95_ms", 0),
                "stddev_ms": native_stats.get("stddev_ms", 0),
                "vs_baseline_pct": pct_diff,
            },
        ]
        print(json.dumps(json_results, indent=2))
    else:
        # Table output
        table = Table(title=f"ADBC vs Native Comparison ({backend})")
        table.add_column("Method", style="cyan")
        table.add_column("Mean (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")
        table.add_column("vs ADBC", justify="right")

        # ADBC row (baseline)
        table.add_row(
            "ADBC",
            f"{adbc_stats.get('mean_ms', 0):.2f}",
            f"{adbc_stats.get('p95_ms', 0):.2f}",
            "[dim]baseline[/dim]",
        )

        # Native row (with percentage)
        if pct_diff > 0:
            pct_str = f"[red]+{pct_diff:.1f}%[/red]"
        elif pct_diff < 0:
            pct_str = f"[green]{pct_diff:.1f}%[/green]"
        else:
            pct_str = "0.0%"

        table.add_row(
            "Native",
            f"{native_stats.get('mean_ms', 0):.2f}",
            f"{native_stats.get('p95_ms', 0):.2f}",
            pct_str,
        )

        console.print(table)
        console.print()

        # Summary insight
        if pct_diff > 1:
            console.print(
                f"[yellow]Native is {pct_diff:.1f}% slower than ADBC - "
                "ADBC has no overhead here![/yellow]"
            )
        elif pct_diff < -1:
            console.print(
                f"[green]Native is {abs(pct_diff):.1f}% faster than ADBC.[/green]"
            )
        else:
            console.print("[dim]ADBC and native have similar performance.[/dim]")

        console.print(f"[dim]Query: {sql}[/dim]")
        console.print(f"[dim]Iterations: {iterations}, Warmup: {warmup}[/dim]")


@load_app.command("financial")
def load_financial(
    backend: str = typer.Option(
        "duckdb",
        "--backend",
        "-b",
        help="Backend to load data into.",
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Single ticker symbol to load (e.g., AAPL).",
    ),
    symbols: str | None = typer.Option(
        None,
        "--symbols",
        help="Comma-separated list of ticker symbols (e.g., AAPL,GOOGL,MSFT).",
    ),
    days: int = typer.Option(
        365,
        "--days",
        "-d",
        help="Number of days of historical data to fetch.",
    ),
    synthetic: bool = typer.Option(
        False,
        "--synthetic",
        help="Generate synthetic data instead of fetching real data.",
    ),
    rows: int = typer.Option(
        100_000,
        "--rows",
        "-r",
        help="Number of rows to generate (only with --synthetic).",
    ),
    output: BenchmarkOutputFormat = typer.Option(
        BenchmarkOutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table or json.",
    ),
) -> None:
    """Load financial/trading data into a backend.

    Supports two data sources:
    - Real: Historical data from Yahoo Finance (requires yfinance)
    - Synthetic: Generated data using Geometric Brownian Motion

    Examples:
        quiver load financial --synthetic --rows 100000
        quiver load financial --backend duckdb --symbol AAPL --days 365
        quiver load financial --symbols AAPL,GOOGL,MSFT --days 365
        quiver load financial --synthetic --rows 10000000
    """
    registry = get_registry()

    # Validate mutual exclusion
    real_data_requested = symbol is not None or symbols is not None
    if real_data_requested and synthetic:
        console.print(
            "[red]Error: Cannot use --symbol/--symbols with --synthetic. "
            "Choose one data source.[/red]"
        )
        raise typer.Exit(1)

    # Default to synthetic if nothing specified
    if not real_data_requested and not synthetic:
        synthetic = True

    # Get backend class
    try:
        backend_cls = registry.get(backend)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Load data
    loader = FinancialLoader()

    try:
        with backend_cls() as db:
            if synthetic:
                result = loader.load_synthetic(db, rows)
            else:
                # Parse symbols
                symbol_list = []
                if symbol:
                    symbol_list.append(symbol.upper())
                if symbols:
                    symbol_list.extend(s.strip().upper() for s in symbols.split(","))

                result = loader.load_real(db, symbol_list, days)
    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading data: {e}[/red]")
        raise typer.Exit(1)

    # Output results
    if output == BenchmarkOutputFormat.JSON:
        result_dict = {
            "table_name": result.table_name,
            "rows_loaded": result.rows_loaded,
            "source": result.source,
            "schema": [
                {"name": field.name, "type": str(field.type)}
                for field in result.schema
            ],
        }
        print(json.dumps(result_dict, indent=2))
    else:
        # Table output
        table = Table(title="Load Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Table", result.table_name)
        table.add_row("Rows Loaded", f"{result.rows_loaded:,}")
        table.add_row("Source", result.source)
        table.add_row("Backend", backend)

        console.print(table)
        console.print()

        # Show schema
        schema_table = Table(title="Schema")
        schema_table.add_column("Column", style="cyan")
        schema_table.add_column("Type")

        for field in result.schema:
            schema_table.add_row(field.name, str(field.type))

        console.print(schema_table)


@load_app.command("observability")
def load_observability(
    backend: str = typer.Option(
        "duckdb",
        "--backend",
        "-b",
        help="Backend to load data into.",
    ),
    metrics: int = typer.Option(
        100_000,
        "--metrics",
        "-m",
        help="Number of metric rows to generate.",
    ),
    hosts: int = typer.Option(
        10,
        "--hosts",
        help="Number of unique hosts to simulate.",
    ),
    services: int = typer.Option(
        5,
        "--services",
        help="Number of unique services to simulate.",
    ),
    output: BenchmarkOutputFormat = typer.Option(
        BenchmarkOutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format: table or json.",
    ),
) -> None:
    """Load synthetic observability/metrics data into a backend.

    Generates realistic monitoring metrics:
    - cpu_usage: 0-100, smooth random walk
    - memory_usage: 0-100, gradual changes
    - request_latency_ms: 1-1000, log-normal distribution
    - error_rate: 0-1, occasional spikes

    Examples:
        quiver load observability --metrics 100000
        quiver load observability --metrics 1000000 --hosts 50 --services 20
        quiver load observability --backend sqlite --metrics 10000
    """
    registry = get_registry()

    # Get backend class
    try:
        backend_cls = registry.get(backend)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Load data
    loader = ObservabilityLoader()

    try:
        with backend_cls() as db:
            result = loader.load_synthetic(db, metrics, hosts, services)
    except Exception as e:
        console.print(f"[red]Error loading data: {e}[/red]")
        raise typer.Exit(1)

    # Output results
    if output == BenchmarkOutputFormat.JSON:
        result_dict = {
            "table_name": result.table_name,
            "rows_loaded": result.rows_loaded,
            "source": result.source,
            "schema": [
                {"name": field.name, "type": str(field.type)}
                for field in result.schema
            ],
        }
        print(json.dumps(result_dict, indent=2))
    else:
        # Table output
        table = Table(title="Load Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Table", result.table_name)
        table.add_row("Rows Loaded", f"{result.rows_loaded:,}")
        table.add_row("Source", result.source)
        table.add_row("Backend", backend)

        console.print(table)
        console.print()

        # Show schema
        schema_table = Table(title="Schema")
        schema_table.add_column("Column", style="cyan")
        schema_table.add_column("Type")

        for field in result.schema:
            schema_table.add_row(field.name, str(field.type))

        console.print(schema_table)


if __name__ == "__main__":
    app()
