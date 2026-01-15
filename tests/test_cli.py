"""Tests for the CLI interface."""

from typer.testing import CliRunner

from quiver import __version__
from quiver.cli import app

runner = CliRunner()


def test_version() -> None:
    """Test --version flag shows version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help() -> None:
    """Test --help shows help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Universal ADBC query tool" in result.stdout


def test_backends_command() -> None:
    """Test backends command shows table with backends."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    # Should show all known backends
    assert "duckdb" in result.stdout.lower()
    assert "sqlite" in result.stdout.lower()
    assert "flightsql" in result.stdout.lower()
    assert "influxdb" in result.stdout.lower()


def test_backends_shows_duckdb_available() -> None:
    """Test backends command shows DuckDB as available."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    # DuckDB should be available since it's installed
    assert "available" in result.stdout.lower()


def test_backends_shows_table_headers() -> None:
    """Test backends command shows proper table structure."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    # Should have table headers
    assert "Backend" in result.stdout
    assert "Status" in result.stdout
    assert "Description" in result.stdout


def test_backends_shows_registered_count() -> None:
    """Test backends command shows count of registered backends."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    # Should show registered count
    assert "Registered backends:" in result.stdout


# Query command tests


def test_query_simple_select() -> None:
    """Test query command executes simple SQL."""
    result = runner.invoke(app, ["query", "SELECT 1 as num"])
    assert result.exit_code == 0
    assert "num" in result.stdout
    assert "1" in result.stdout


def test_query_with_backend_option() -> None:
    """Test query command accepts --backend option."""
    result = runner.invoke(app, ["query", "SELECT 42 as answer", "--backend", "duckdb"])
    assert result.exit_code == 0
    assert "42" in result.stdout


def test_query_default_output_is_table() -> None:
    """Test query command defaults to table output with Rich formatting."""
    result = runner.invoke(app, ["query", "SELECT 'hello' as greeting"])
    assert result.exit_code == 0
    # Rich tables have box-drawing characters or column headers
    assert "greeting" in result.stdout
    assert "hello" in result.stdout


def test_query_json_output() -> None:
    """Test query command with --output json."""
    result = runner.invoke(app, ["query", "SELECT 1 as num, 'test' as name", "--output", "json"])
    assert result.exit_code == 0
    # JSON output should be parseable
    import json

    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["num"] == 1
    assert data[0]["name"] == "test"


def test_query_csv_output() -> None:
    """Test query command with --output csv."""
    result = runner.invoke(app, ["query", "SELECT 1 as num, 'test' as name", "--output", "csv"])
    assert result.exit_code == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
    assert "num" in lines[0]
    assert "name" in lines[0]
    assert "1" in lines[1]
    assert "test" in lines[1]


def test_query_arrow_output_shows_schema() -> None:
    """Test query command with --output arrow shows schema info."""
    result = runner.invoke(app, ["query", "SELECT 1 as num, 'test' as name", "--output", "arrow"])
    assert result.exit_code == 0
    # Should show schema information
    assert "num" in result.stdout
    assert "name" in result.stdout
    # Should indicate it's Arrow schema
    assert "int" in result.stdout.lower() or "schema" in result.stdout.lower()


def test_query_multiple_rows() -> None:
    """Test query command with multiple result rows."""
    result = runner.invoke(
        app, ["query", "SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS t(id, letter)"]
    )
    assert result.exit_code == 0
    assert "1" in result.stdout
    assert "2" in result.stdout
    assert "3" in result.stdout


def test_query_invalid_sql_shows_error() -> None:
    """Test query command shows error for invalid SQL."""
    result = runner.invoke(app, ["query", "SELEKT * FORM nowhere"])
    assert result.exit_code != 0
    # Should show some error indication
    assert "error" in result.stdout.lower() or result.exit_code == 1


def test_query_unknown_backend_shows_error() -> None:
    """Test query command shows error for unknown backend."""
    result = runner.invoke(app, ["query", "SELECT 1", "--backend", "nonexistent"])
    assert result.exit_code != 0


def test_query_short_options() -> None:
    """Test query command accepts short option forms."""
    result = runner.invoke(app, ["query", "SELECT 1 as num", "-b", "duckdb", "-o", "json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert data[0]["num"] == 1


# Benchmark command tests


def test_benchmark_simple_query() -> None:
    """Test benchmark command runs successfully."""
    result = runner.invoke(app, ["benchmark", "SELECT 1"])
    assert result.exit_code == 0
    # Should show timing results
    assert "mean" in result.stdout.lower() or "ms" in result.stdout.lower()


def test_benchmark_with_backend_option() -> None:
    """Test benchmark command accepts --backends option."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--backends", "duckdb"])
    assert result.exit_code == 0
    assert "duckdb" in result.stdout.lower()


def test_benchmark_multiple_backends() -> None:
    """Test benchmark command with multiple backends."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--backends", "duckdb,sqlite"])
    assert result.exit_code == 0
    assert "duckdb" in result.stdout.lower()
    assert "sqlite" in result.stdout.lower()


def test_benchmark_iterations_option() -> None:
    """Test benchmark command accepts --iterations option."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--iterations", "5"])
    assert result.exit_code == 0


def test_benchmark_warmup_option() -> None:
    """Test benchmark command accepts --warmup option."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--warmup", "2"])
    assert result.exit_code == 0


def test_benchmark_shows_table_output() -> None:
    """Test benchmark command shows Rich table by default."""
    result = runner.invoke(app, ["benchmark", "SELECT 1"])
    assert result.exit_code == 0
    # Should have table structure with headers
    assert "Backend" in result.stdout or "backend" in result.stdout.lower()


def test_benchmark_json_output() -> None:
    """Test benchmark command with --output json."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--output", "json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "backend" in data[0]
    assert "mean_ms" in data[0]


def test_benchmark_short_options() -> None:
    """Test benchmark command accepts short option forms."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "-b", "duckdb", "-i", "3", "-w", "1"])
    assert result.exit_code == 0


def test_benchmark_unknown_backend_shows_error() -> None:
    """Test benchmark command shows error for unknown backend."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--backends", "nonexistent"])
    assert result.exit_code != 0


def test_benchmark_invalid_sql_shows_error() -> None:
    """Test benchmark command shows error for invalid SQL."""
    result = runner.invoke(app, ["benchmark", "SELEKT * FORM nowhere"])
    assert result.exit_code != 0


# Compare command tests


def test_compare_simple_query() -> None:
    """Test compare command runs successfully."""
    result = runner.invoke(app, ["compare", "SELECT 1"])
    assert result.exit_code == 0
    # Should show ADBC and Native results
    assert "adbc" in result.stdout.lower()
    assert "native" in result.stdout.lower()


def test_compare_with_backend_option() -> None:
    """Test compare command accepts --backend option."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--backend", "duckdb"])
    assert result.exit_code == 0


def test_compare_iterations_option() -> None:
    """Test compare command accepts --iterations option."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--iterations", "5"])
    assert result.exit_code == 0


def test_compare_warmup_option() -> None:
    """Test compare command accepts --warmup option."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--warmup", "2"])
    assert result.exit_code == 0


def test_compare_shows_percentage_diff() -> None:
    """Test compare command shows percentage difference."""
    result = runner.invoke(app, ["compare", "SELECT 1"])
    assert result.exit_code == 0
    # Should show percentage or baseline indicator
    assert "%" in result.stdout or "baseline" in result.stdout.lower()


def test_compare_json_output() -> None:
    """Test compare command with --output json."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--output", "json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 2  # ADBC and Native
    assert any("adbc" in r["method"].lower() for r in data)
    assert any("native" in r["method"].lower() for r in data)


def test_compare_short_options() -> None:
    """Test compare command accepts short option forms."""
    result = runner.invoke(app, ["compare", "SELECT 1", "-b", "duckdb", "-i", "3", "-w", "1"])
    assert result.exit_code == 0


def test_compare_unknown_backend_shows_error() -> None:
    """Test compare command shows error for unknown backend."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--backend", "nonexistent"])
    assert result.exit_code != 0


def test_compare_unsupported_backend_shows_error() -> None:
    """Test compare command shows error for backend without native support."""
    # SQLite doesn't support native comparison
    result = runner.invoke(app, ["compare", "SELECT 1", "--backend", "sqlite"])
    assert result.exit_code != 0
    assert "native" in result.stdout.lower() or "support" in result.stdout.lower()


# Load command tests


def test_load_help() -> None:
    """Test load command shows help."""
    result = runner.invoke(app, ["load", "--help"])
    assert result.exit_code == 0
    assert "Load sample datasets" in result.stdout


def test_load_financial_help() -> None:
    """Test load financial command shows help."""
    result = runner.invoke(app, ["load", "financial", "--help"])
    assert result.exit_code == 0
    assert "financial" in result.stdout.lower() or "trading" in result.stdout.lower()


def test_load_financial_synthetic_default() -> None:
    """Test load financial defaults to synthetic data."""
    result = runner.invoke(app, ["load", "financial", "--rows", "100"])
    assert result.exit_code == 0
    assert "synthetic" in result.stdout.lower()
    assert "100" in result.stdout


def test_load_financial_synthetic_explicit() -> None:
    """Test load financial with explicit --synthetic flag."""
    result = runner.invoke(app, ["load", "financial", "--synthetic", "--rows", "500"])
    assert result.exit_code == 0
    assert "synthetic" in result.stdout.lower()
    assert "500" in result.stdout


def test_load_financial_shows_table_info() -> None:
    """Test load financial shows table and schema info."""
    result = runner.invoke(app, ["load", "financial", "--synthetic", "--rows", "100"])
    assert result.exit_code == 0
    # Should show table name
    assert "trades" in result.stdout.lower()
    # Should show schema columns
    assert "timestamp" in result.stdout.lower()
    assert "symbol" in result.stdout.lower()


def test_load_financial_json_output() -> None:
    """Test load financial with --output json."""
    import json

    result = runner.invoke(
        app, ["load", "financial", "--synthetic", "--rows", "100", "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["table_name"] == "trades"
    assert data["rows_loaded"] == 100
    assert data["source"] == "synthetic"
    assert "schema" in data


def test_load_financial_mutual_exclusion() -> None:
    """Test load financial rejects --symbol with --synthetic."""
    result = runner.invoke(
        app, ["load", "financial", "--synthetic", "--symbol", "AAPL"]
    )
    assert result.exit_code != 0
    assert "cannot" in result.stdout.lower() or "error" in result.stdout.lower()


def test_load_financial_short_options() -> None:
    """Test load financial accepts short option forms."""
    result = runner.invoke(app, ["load", "financial", "-b", "duckdb", "-r", "100"])
    assert result.exit_code == 0


def test_load_financial_unknown_backend_shows_error() -> None:
    """Test load financial shows error for unknown backend."""
    result = runner.invoke(
        app, ["load", "financial", "--backend", "nonexistent", "--synthetic"]
    )
    assert result.exit_code != 0


# Load observability command tests


def test_load_observability_help() -> None:
    """Test load observability command shows help."""
    result = runner.invoke(app, ["load", "observability", "--help"])
    assert result.exit_code == 0
    assert "observability" in result.stdout.lower() or "metrics" in result.stdout.lower()


def test_load_observability_default() -> None:
    """Test load observability with default options."""
    result = runner.invoke(app, ["load", "observability", "--metrics", "100"])
    assert result.exit_code == 0
    assert "metrics" in result.stdout.lower()


def test_load_observability_shows_table_info() -> None:
    """Test load observability shows table and schema info."""
    result = runner.invoke(app, ["load", "observability", "--metrics", "100"])
    assert result.exit_code == 0
    # Should show table name
    assert "metrics" in result.stdout.lower()
    # Should show schema columns
    assert "timestamp" in result.stdout.lower()
    assert "host" in result.stdout.lower()


def test_load_observability_with_hosts_services() -> None:
    """Test load observability with custom hosts and services."""
    result = runner.invoke(
        app, ["load", "observability", "--metrics", "200", "--hosts", "5", "--services", "3"]
    )
    assert result.exit_code == 0
    assert "hosts=5" in result.stdout.lower() or "5" in result.stdout


def test_load_observability_json_output() -> None:
    """Test load observability with --output json."""
    import json

    result = runner.invoke(
        app, ["load", "observability", "--metrics", "100", "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["table_name"] == "metrics"
    assert data["rows_loaded"] > 0
    assert "synthetic" in data["source"]
    assert "schema" in data


def test_load_observability_short_options() -> None:
    """Test load observability accepts short option forms."""
    result = runner.invoke(app, ["load", "observability", "-b", "duckdb", "-m", "100"])
    assert result.exit_code == 0


def test_load_observability_unknown_backend_shows_error() -> None:
    """Test load observability shows error for unknown backend."""
    result = runner.invoke(
        app, ["load", "observability", "--backend", "nonexistent", "--metrics", "100"]
    )
    assert result.exit_code != 0


# FlightSQL backend CLI tests


def test_backends_shows_flightsql() -> None:
    """Test backends command shows FlightSQL in the list."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    assert "flightsql" in result.stdout.lower()


def test_query_flightsql_requires_host() -> None:
    """Test query with FlightSQL backend requires --host option."""
    result = runner.invoke(app, ["query", "SELECT 1", "--backend", "flightsql"])
    assert result.exit_code != 0
    assert "host" in result.stdout.lower() or "--host" in result.stdout


def test_query_accepts_host_option() -> None:
    """Test query command accepts --host option."""
    # This will fail to connect but should accept the option
    result = runner.invoke(
        app, ["query", "SELECT 1", "--backend", "flightsql", "--host", "grpc://localhost:8815"]
    )
    # Exit code will be non-zero due to connection failure, but not argument error
    assert "--host" not in result.stdout or "required" not in result.stdout.lower()


def test_query_accepts_token_option() -> None:
    """Test query command accepts --token option."""
    # This will fail to connect but should accept the option
    result = runner.invoke(
        app,
        [
            "query",
            "SELECT 1",
            "--backend",
            "flightsql",
            "--host",
            "grpc://localhost:8815",
            "--token",
            "test-token",
        ],
    )
    # Should not complain about unknown option
    assert "no such option" not in result.stdout.lower()


def test_benchmark_flightsql_requires_host() -> None:
    """Test benchmark with FlightSQL backend requires --host option."""
    result = runner.invoke(app, ["benchmark", "SELECT 1", "--backends", "flightsql"])
    assert result.exit_code != 0
    assert "host" in result.stdout.lower() or "--host" in result.stdout


def test_compare_flightsql_requires_host() -> None:
    """Test compare with FlightSQL backend requires --host option."""
    result = runner.invoke(app, ["compare", "SELECT 1", "--backend", "flightsql"])
    assert result.exit_code != 0
    assert "host" in result.stdout.lower() or "--host" in result.stdout


# Config command tests


def test_init_help() -> None:
    """Test init command shows help."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "config" in result.stdout.lower()


def test_init_creates_config(tmp_path, monkeypatch) -> None:
    """Test init command creates config file."""
    import quiver.cli
    import quiver.config

    config_path = tmp_path / "config.toml"

    # Override config path
    monkeypatch.setattr(quiver.config, "get_config_path", lambda: config_path)

    # Reset config cache
    quiver.cli._config = None
    quiver.cli._config_loaded = False

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Created configuration file" in result.stdout
    assert config_path.exists()


def test_init_rejects_existing(tmp_path, monkeypatch) -> None:
    """Test init command rejects overwriting existing config."""
    import quiver.cli
    import quiver.config

    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    monkeypatch.setattr(quiver.config, "get_config_path", lambda: config_path)
    quiver.cli._config = None
    quiver.cli._config_loaded = False

    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "already exists" in result.stdout.lower() or "use --force" in result.stdout.lower()


def test_init_force_overwrites(tmp_path, monkeypatch) -> None:
    """Test init command with --force overwrites existing config."""
    import quiver.cli
    import quiver.config

    config_path = tmp_path / "config.toml"
    config_path.write_text("old content")

    monkeypatch.setattr(quiver.config, "get_config_path", lambda: config_path)
    quiver.cli._config = None
    quiver.cli._config_loaded = False

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    content = config_path.read_text()
    assert "[defaults]" in content


def test_config_no_file(tmp_path, monkeypatch) -> None:
    """Test config command when no config file exists."""
    import quiver.cli
    import quiver.config

    config_path = tmp_path / "nonexistent" / "config.toml"

    monkeypatch.setattr(quiver.config, "get_config_path", lambda: config_path)
    quiver.cli._config = None
    quiver.cli._config_loaded = False

    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "no configuration file" in result.stdout.lower()


def test_config_shows_loaded(tmp_path, monkeypatch) -> None:
    """Test config command shows loaded configuration."""
    import quiver.cli
    import quiver.config

    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[defaults]
backend = "sqlite"
output = "json"

[backends.duckdb]
type = "duckdb"
""")

    monkeypatch.setattr(quiver.config, "get_config_path", lambda: config_path)
    quiver.cli._config = None
    quiver.cli._config_loaded = False

    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "sqlite" in result.stdout
    assert "json" in result.stdout
    assert "duckdb" in result.stdout
