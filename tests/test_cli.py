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
