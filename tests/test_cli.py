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
