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
    """Test backends command exists."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    assert "duckdb" in result.stdout.lower()
