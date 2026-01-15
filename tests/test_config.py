"""Tests for the configuration module."""

import os
import tempfile
from pathlib import Path

import pytest

from quiver.config import (
    BackendConfig,
    QuiverConfig,
    create_default_config,
    expand_env_vars,
    expand_path,
    get_config_dir,
    get_config_path,
    load_config,
)


class TestExpandEnvVars:
    """Tests for environment variable expansion."""

    def test_no_vars(self) -> None:
        """String without env vars is unchanged."""
        assert expand_env_vars("hello world") == "hello world"

    def test_single_var(self) -> None:
        """Single env var is expanded."""
        os.environ["TEST_VAR_1"] = "secret"
        assert expand_env_vars("token=${TEST_VAR_1}") == "token=secret"
        del os.environ["TEST_VAR_1"]

    def test_multiple_vars(self) -> None:
        """Multiple env vars are expanded."""
        os.environ["TEST_HOST"] = "localhost"
        os.environ["TEST_PORT"] = "8080"
        result = expand_env_vars("http://${TEST_HOST}:${TEST_PORT}")
        assert result == "http://localhost:8080"
        del os.environ["TEST_HOST"]
        del os.environ["TEST_PORT"]

    def test_undefined_var_unchanged(self) -> None:
        """Undefined env vars are left as-is."""
        # Ensure var doesn't exist
        if "UNDEFINED_VAR_XYZ" in os.environ:
            del os.environ["UNDEFINED_VAR_XYZ"]
        assert expand_env_vars("${UNDEFINED_VAR_XYZ}") == "${UNDEFINED_VAR_XYZ}"


class TestExpandPath:
    """Tests for path expansion."""

    def test_tilde_expanded(self) -> None:
        """Tilde is expanded to home directory."""
        result = expand_path("~/.config/test")
        assert result.startswith(str(Path.home()))
        assert result.endswith(".config/test")

    def test_env_var_in_path(self) -> None:
        """Environment variable in path is expanded."""
        os.environ["TEST_DIR"] = "mydir"
        result = expand_path("~/${TEST_DIR}/file.txt")
        assert "mydir" in result
        del os.environ["TEST_DIR"]


class TestGetConfigPath:
    """Tests for config path helpers."""

    def test_default_config_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default config dir is ~/.config/quiver."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        config_dir = get_config_dir()
        assert config_dir == Path.home() / ".config" / "quiver"

    def test_xdg_config_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """XDG_CONFIG_HOME is respected."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        config_dir = get_config_dir()
        assert config_dir == Path("/custom/config/quiver")

    def test_config_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config path is config_dir/config.toml."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        config_path = get_config_path()
        assert config_path == Path.home() / ".config" / "quiver" / "config.toml"


class TestBackendConfig:
    """Tests for BackendConfig dataclass."""

    def test_minimal(self) -> None:
        """Minimal backend config with just type."""
        config = BackendConfig(type="duckdb")
        assert config.type == "duckdb"
        assert config.host is None
        assert config.token is None
        assert config.path is None

    def test_all_fields(self) -> None:
        """Backend config with all fields."""
        config = BackendConfig(
            type="influxdb",
            host="grpc://localhost:8086",
            token="secret",
            path="/data/db",
            org="myorg",
            bucket="metrics",
        )
        assert config.type == "influxdb"
        assert config.host == "grpc://localhost:8086"
        assert config.token == "secret"
        assert config.path == "/data/db"
        assert config.org == "myorg"
        assert config.bucket == "metrics"


class TestQuiverConfig:
    """Tests for QuiverConfig dataclass."""

    def test_defaults(self) -> None:
        """Default config values."""
        config = QuiverConfig()
        assert config.backends == {}
        assert config.default_backend == "duckdb"
        assert config.default_output == "table"

    def test_with_backends(self) -> None:
        """Config with backend configurations."""
        backends = {
            "duckdb": BackendConfig(type="duckdb"),
            "influx": BackendConfig(type="influxdb", host="grpc://localhost:8086"),
        }
        config = QuiverConfig(
            backends=backends,
            default_backend="influx",
            default_output="json",
        )
        assert len(config.backends) == 2
        assert config.default_backend == "influx"
        assert config.default_output == "json"


class TestLoadConfig:
    """Tests for loading configuration from TOML files."""

    def test_nonexistent_file(self) -> None:
        """Returns None for nonexistent config file."""
        result = load_config(Path("/nonexistent/path/config.toml"))
        assert result is None

    def test_minimal_config(self) -> None:
        """Load minimal valid config."""
        toml_content = """
[defaults]
backend = "sqlite"
output = "json"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            config = load_config(Path(f.name))

        os.unlink(f.name)

        assert config is not None
        assert config.default_backend == "sqlite"
        assert config.default_output == "json"
        assert config.backends == {}

    def test_full_config(self) -> None:
        """Load config with backend definitions."""
        toml_content = """
[defaults]
backend = "influxdb"
output = "table"

[backends.duckdb]
type = "duckdb"

[backends.influxdb]
type = "influxdb"
host = "grpc://localhost:8086"
token = "test-token"
org = "myorg"
bucket = "metrics"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            config = load_config(Path(f.name))

        os.unlink(f.name)

        assert config is not None
        assert config.default_backend == "influxdb"
        assert len(config.backends) == 2

        # Check DuckDB backend
        duckdb = config.backends["duckdb"]
        assert duckdb.type == "duckdb"

        # Check InfluxDB backend
        influx = config.backends["influxdb"]
        assert influx.type == "influxdb"
        assert influx.host == "grpc://localhost:8086"
        assert influx.token == "test-token"
        assert influx.org == "myorg"
        assert influx.bucket == "metrics"

    def test_env_var_expansion(self) -> None:
        """Environment variables in config are expanded."""
        os.environ["TEST_TOKEN"] = "secret-from-env"
        toml_content = """
[backends.flightsql]
type = "flightsql"
host = "grpc://localhost:8815"
token = "${TEST_TOKEN}"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            config = load_config(Path(f.name))

        os.unlink(f.name)
        del os.environ["TEST_TOKEN"]

        assert config is not None
        assert config.backends["flightsql"].token == "secret-from-env"

    def test_path_expansion(self) -> None:
        """Path values are expanded."""
        toml_content = """
[backends.sqlite]
type = "sqlite"
path = "~/data/test.db"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            config = load_config(Path(f.name))

        os.unlink(f.name)

        assert config is not None
        sqlite_path = config.backends["sqlite"].path
        assert sqlite_path is not None
        assert not sqlite_path.startswith("~")
        assert str(Path.home()) in sqlite_path

    def test_invalid_toml(self) -> None:
        """Invalid TOML raises ValueError."""
        toml_content = "this is not valid toml ["
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            with pytest.raises(ValueError, match="Invalid TOML"):
                load_config(Path(f.name))

        os.unlink(f.name)


class TestCreateDefaultConfig:
    """Tests for creating default config file."""

    def test_creates_config(self) -> None:
        """Creates config file in specified location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Temporarily override config path
            import quiver.config

            original_get_config_path = quiver.config.get_config_path
            quiver.config.get_config_path = lambda: config_path

            try:
                result = create_default_config()
                assert result == config_path
                assert config_path.exists()

                # Check content includes expected sections
                content = config_path.read_text()
                assert "[defaults]" in content
                assert "[backends.duckdb]" in content
            finally:
                quiver.config.get_config_path = original_get_config_path

    def test_raises_if_exists(self) -> None:
        """Raises FileExistsError if config already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("existing content")

            import quiver.config

            original_get_config_path = quiver.config.get_config_path
            quiver.config.get_config_path = lambda: config_path

            try:
                with pytest.raises(FileExistsError):
                    create_default_config()
            finally:
                quiver.config.get_config_path = original_get_config_path

    def test_force_overwrites(self) -> None:
        """Force flag overwrites existing config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("old content")

            import quiver.config

            original_get_config_path = quiver.config.get_config_path
            quiver.config.get_config_path = lambda: config_path

            try:
                result = create_default_config(force=True)
                assert result == config_path
                content = config_path.read_text()
                assert "[defaults]" in content
                assert "old content" not in content
            finally:
                quiver.config.get_config_path = original_get_config_path
