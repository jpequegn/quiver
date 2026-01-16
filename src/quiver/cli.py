"""Quiver CLI - Universal ADBC query tool."""

import json
import os
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from quiver import __version__
from quiver.backends import get_registry
from quiver.benchmark import BenchmarkRunner
from quiver.config import (
    QuiverConfig,
    create_default_config,
    get_config_path,
    load_config,
)
from quiver.loaders import FinancialLoader, ObservabilityLoader
from quiver.output import OutputFormat, format_output


# Global config cache
_config: QuiverConfig | None = None
_config_loaded: bool = False


def get_config() -> QuiverConfig | None:
    """Get the loaded configuration, loading if necessary.

    Returns:
        QuiverConfig if available, None otherwise.
    """
    global _config, _config_loaded
    if not _config_loaded:
        try:
            _config = load_config()
        except ValueError:
            _config = None
        _config_loaded = True
    return _config


def get_default_backend() -> str:
    """Get default backend from config or environment.

    Priority: QUIVER_BACKEND env var > config > "duckdb"
    """
    env_backend = os.environ.get("QUIVER_BACKEND")
    if env_backend:
        return env_backend

    config = get_config()
    if config:
        return config.default_backend

    return "duckdb"


def get_default_output() -> str:
    """Get default output format from config or environment.

    Priority: QUIVER_OUTPUT env var > config > "table"
    """
    env_output = os.environ.get("QUIVER_OUTPUT")
    if env_output:
        return env_output

    config = get_config()
    if config:
        return config.default_output

    return "table"


def get_backend_config(backend_name: str) -> tuple[str | None, str | None]:
    """Get host and token for a backend from config.

    Args:
        backend_name: Name of the backend.

    Returns:
        Tuple of (host, token) from config, or (None, None) if not configured.
    """
    config = get_config()
    if config and backend_name in config.backends:
        bc = config.backends[backend_name]
        return bc.host, bc.token
    return None, None


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


def _create_backend(
    backend_name: str,
    host: str | None = None,
    token: str | None = None,
):
    """Create a backend instance with appropriate configuration.

    Args:
        backend_name: Name of the backend to create.
        host: Host URI for remote backends (FlightSQL, InfluxDB).
        token: Authentication token for remote backends.

    Returns:
        Configured backend instance.

    Raises:
        KeyError: If backend is not registered.
        ValueError: If required options are missing for a backend.
    """
    registry = get_registry()
    backend_cls = registry.get(backend_name)

    # FlightSQL and similar remote backends need host configuration
    if backend_name in ("flightsql", "influxdb"):
        if host is None:
            raise ValueError(
                f"--host is required for {backend_name} backend. "
                f"Example: --host grpc://localhost:8815"
            )
        return backend_cls(uri=host, token=token)

    # Local backends (duckdb, sqlite) don't need extra config
    return backend_cls()


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


# Backend classification for doctor command
LOCAL_BACKENDS = {"duckdb", "sqlite"}
REMOTE_BACKENDS = {"flightsql", "influxdb"}


def _get_package_version(package_name: str) -> str | None:
    """Get version of an installed package.

    Args:
        package_name: Name of the package (e.g., "pyarrow").

    Returns:
        Version string or None if not installed.
    """
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


def _check_backend_for_doctor(name: str) -> tuple[str, str, str]:
    """Check backend status for doctor command.

    Args:
        name: Backend name to check.

    Returns:
        Tuple of (status, style, message).
        Status: OK, SKIP, FAIL
        Style: Rich style string
        Message: Description of status
    """
    registry = get_registry()

    # Check if backend is registered
    if name not in registry.list_backends():
        return "SKIP", "dim", "Driver not installed"

    # For remote backends, just check if driver is importable
    if name in REMOTE_BACKENDS:
        try:
            registry.get(name)  # This triggers the import
            return "OK", "green", "Driver available (remote backend)"
        except ImportError as e:
            return "FAIL", "red", f"Import error: {e}"

    # For local backends, try to connect
    try:
        backend_cls = registry.get(name)
        backend = backend_cls()
        backend.connect()
        backend.close()
        return "OK", "green", "Connected successfully"
    except ImportError as e:
        return "FAIL", "red", f"Missing dependency: {e}"
    except Exception as e:
        return "FAIL", "red", f"Connection error: {e}"


@app.command()
def doctor() -> None:
    """Run diagnostic checks on backends and dependencies.

    Verifies that backends are working and shows installed versions
    of key dependencies. Useful for troubleshooting issues.

    Examples:
        quiver doctor
    """
    console.print()
    console.print("[bold]Quiver Diagnostics[/bold]")
    console.print("=" * 40)
    console.print()

    # Track if any critical failures occurred
    has_failures = False

    # Check backends
    backends_table = Table(title="Backends", show_header=True)
    backends_table.add_column("Backend", style="cyan", no_wrap=True)
    backends_table.add_column("Status", justify="center")
    backends_table.add_column("Details")

    for name in KNOWN_BACKENDS:
        status, style, message = _check_backend_for_doctor(name)

        if status == "OK":
            status_display = f"[green][OK][/green]"
        elif status == "SKIP":
            status_display = f"[dim][SKIP][/dim]"
        else:
            status_display = f"[red][FAIL][/red]"
            if name in LOCAL_BACKENDS:
                has_failures = True

        backends_table.add_row(name, status_display, f"[{style}]{message}[/{style}]")

    console.print(backends_table)
    console.print()

    # Check dependencies
    deps_table = Table(title="Dependencies", show_header=True)
    deps_table.add_column("Package", style="cyan", no_wrap=True)
    deps_table.add_column("Version", justify="right")

    # Core dependencies
    core_deps = [
        "pyarrow",
        "adbc-driver-manager",
    ]

    # Optional driver dependencies
    optional_deps = [
        "adbc-driver-duckdb",
        "adbc-driver-sqlite",
        "adbc-driver-flightsql",
    ]

    for pkg in core_deps:
        version = _get_package_version(pkg)
        if version:
            deps_table.add_row(pkg, f"[green]{version}[/green]")
        else:
            deps_table.add_row(pkg, "[red]not installed[/red]")
            has_failures = True

    for pkg in optional_deps:
        version = _get_package_version(pkg)
        if version:
            deps_table.add_row(pkg, f"[green]{version}[/green]")
        else:
            deps_table.add_row(pkg, "[dim]not installed[/dim]")

    console.print(deps_table)
    console.print()

    # Summary
    if has_failures:
        console.print("[red]✗ Some checks failed[/red]")
        raise typer.Exit(1)
    else:
        console.print("[green]✓ All checks passed[/green]")


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration file.",
    ),
) -> None:
    """Initialize Quiver configuration file.

    Creates a default configuration file at ~/.config/quiver/config.toml
    with sensible defaults and commented examples for various backends.

    Examples:
        quiver init           # Create default config
        quiver init --force   # Overwrite existing config
    """
    try:
        config_path = create_default_config(force=force)
        console.print(f"[green]Created configuration file:[/green] {config_path}")
        console.print()
        console.print("[dim]Edit the file to configure backends and defaults.[/dim]")
    except FileExistsError as e:
        console.print(f"[yellow]{e}[/yellow]")
        console.print("[dim]Use --force to overwrite.[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error creating config: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config() -> None:
    """Show current configuration.

    Displays the loaded configuration and its source.
    """
    config_path = get_config_path()
    cfg = get_config()

    if cfg is None:
        console.print(f"[yellow]No configuration file found at:[/yellow] {config_path}")
        console.print("[dim]Run 'quiver init' to create one.[/dim]")
        return

    console.print(f"[green]Configuration loaded from:[/green] {config_path}")
    console.print()

    # Show defaults
    table = Table(title="Defaults")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("backend", cfg.default_backend)
    table.add_row("output", cfg.default_output)
    console.print(table)
    console.print()

    # Show configured backends
    if cfg.backends:
        backends_table = Table(title="Configured Backends")
        backends_table.add_column("Name", style="cyan")
        backends_table.add_column("Type")
        backends_table.add_column("Host")

        for name, bc in cfg.backends.items():
            host_display = bc.host or "[dim]local[/dim]"
            backends_table.add_row(name, bc.type, host_display)

        console.print(backends_table)
    else:
        console.print("[dim]No backends configured.[/dim]")


@app.command()
def query(
    sql: str = typer.Argument(..., help="SQL query to execute."),
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="Backend to use for query execution (default: from config or 'duckdb').",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Host URI for remote backends (e.g., grpc://localhost:8815).",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Authentication token for remote backends.",
    ),
    output: OutputFormat | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output format: table, json, csv, or arrow (default: from config or 'table').",
    ),
) -> None:
    """Execute a SQL query against a backend and display results.

    Examples:
        quiver query "SELECT 1 as num"
        quiver query "SELECT * FROM trades" --backend duckdb
        quiver query "SELECT * FROM trades" --output json
        quiver query "SELECT * FROM trades" -b duckdb -o csv
        quiver query "SELECT 1" --backend flightsql --host grpc://localhost:8815
    """
    # Apply defaults from config
    if backend is None:
        backend = get_default_backend()

    if output is None:
        output_str = get_default_output()
        output = OutputFormat(output_str) if output_str in OutputFormat.__members__.values() else OutputFormat.TABLE

    # Get host/token from config if not provided
    if host is None or token is None:
        config_host, config_token = get_backend_config(backend)
        if host is None:
            host = config_host
        if token is None:
            token = config_token

    # Create backend instance
    try:
        db = _create_backend(backend, host, token)
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Execute query
    try:
        with db:
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
    backends_str: str | None = typer.Option(
        None,
        "--backends",
        "-b",
        help="Comma-separated list of backends to benchmark (default: from config or 'duckdb').",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Host URI for remote backends (e.g., grpc://localhost:8815).",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Authentication token for remote backends.",
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
        quiver benchmark "SELECT 1" -b flightsql --host grpc://localhost:8815
    """
    # Apply defaults from config
    if backends_str is None:
        backends_str = get_default_backend()
    backend_names = [b.strip() for b in backends_str.split(",")]

    # Run benchmarks
    results = []
    for name in backend_names:
        # Get host/token from config if not provided on command line
        backend_host, backend_token = host, token
        if backend_host is None or backend_token is None:
            config_host, config_token = get_backend_config(name)
            if backend_host is None:
                backend_host = config_host
            if backend_token is None:
                backend_token = config_token
        try:
            db = _create_backend(name, backend_host, backend_token)
            with db:
                runner = BenchmarkRunner(db)
                result = runner.run(sql, iterations=iterations, warmup=warmup)
                results.append(result)
        except (KeyError, ValueError) as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
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
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="Backend to compare ADBC vs native performance (default: from config or 'duckdb').",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Host URI for remote backends (e.g., grpc://localhost:8815).",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Authentication token for remote backends.",
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
    # Apply defaults from config
    if backend is None:
        backend = get_default_backend()

    # Get host/token from config if not provided
    if host is None or token is None:
        config_host, config_token = get_backend_config(backend)
        if host is None:
            host = config_host
        if token is None:
            token = config_token

    # Create backend instance
    try:
        db = _create_backend(backend, host, token)
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Check if backend supports native comparison
    with db:
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
        db = _create_backend(backend, host, token)
        with db:
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
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="Backend to load data into (default: from config or 'duckdb').",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Host URI for remote backends (e.g., grpc://localhost:8815).",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Authentication token for remote backends.",
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

    # Apply defaults from config
    if backend is None:
        backend = get_default_backend()

    # Get host/token from config if not provided
    if host is None or token is None:
        config_host, config_token = get_backend_config(backend)
        if host is None:
            host = config_host
        if token is None:
            token = config_token

    # Create backend instance
    try:
        db = _create_backend(backend, host, token)
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Load data
    loader = FinancialLoader()

    try:
        with db:
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
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="Backend to load data into (default: from config or 'duckdb').",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Host URI for remote backends (e.g., grpc://localhost:8815).",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Authentication token for remote backends.",
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
    # Apply defaults from config
    if backend is None:
        backend = get_default_backend()

    # Get host/token from config if not provided
    if host is None or token is None:
        config_host, config_token = get_backend_config(backend)
        if host is None:
            host = config_host
        if token is None:
            token = config_token

    # Create backend instance
    try:
        db = _create_backend(backend, host, token)
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Load data
    loader = ObservabilityLoader()

    try:
        with db:
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


@app.command()
def serve(
    data: str = typer.Argument(..., help="Path to Parquet file, DuckDB database, or directory."),
    port: int = typer.Option(
        8815,
        "--port",
        "-p",
        help="Port to listen on.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Log FlightSQL protocol details.",
    ),
) -> None:
    """Start a FlightSQL server for learning and testing.

    This server allows you to query data via the FlightSQL protocol,
    useful for understanding how Arrow Flight SQL works.

    Examples:
        quiver serve trades.parquet
        quiver serve analytics.duckdb --port 9000
        quiver serve ./data/ --verbose
    """
    from pathlib import Path

    from quiver_server import QuiverFlightServer

    data_path = Path(data)
    if not data_path.exists():
        console.print(f"[red]Error: Path does not exist: {data}[/red]")
        raise typer.Exit(1)

    try:
        server = QuiverFlightServer(
            data_path=data_path,
            port=port,
            verbose=verbose,
        )
        server.serve()
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
