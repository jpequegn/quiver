"""Configuration management for Quiver.

Handles loading and parsing configuration from TOML files,
with support for environment variable expansion.

Config file location: ~/.config/quiver/config.toml (XDG spec)
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Default config directory following XDG Base Directory Specification
def get_config_dir() -> Path:
    """Get the configuration directory path.

    Returns:
        Path to config directory (~/.config/quiver by default).
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "quiver"
    return Path.home() / ".config" / "quiver"


def get_config_path() -> Path:
    """Get the configuration file path.

    Returns:
        Path to config.toml file.
    """
    return get_config_dir() / "config.toml"


@dataclass
class BackendConfig:
    """Configuration for a specific backend.

    Attributes:
        type: Backend type (duckdb, sqlite, flightsql, influxdb).
        host: Host URI for remote backends.
        token: Authentication token.
        path: File path for file-based backends.
        org: Organization (for InfluxDB).
        bucket: Bucket name (for InfluxDB).
    """

    type: str
    host: str | None = None
    token: str | None = None
    path: str | None = None
    org: str | None = None
    bucket: str | None = None


@dataclass
class QuiverConfig:
    """Main configuration object.

    Attributes:
        backends: Dictionary of named backend configurations.
        default_backend: Default backend to use when not specified.
        default_output: Default output format (table, json, csv, arrow).
    """

    backends: dict[str, BackendConfig] = field(default_factory=dict)
    default_backend: str = "duckdb"
    default_output: str = "table"


def expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.

    Supports ${VAR} syntax. Undefined variables are left as-is.

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with environment variables expanded.

    Example:
        >>> os.environ["TOKEN"] = "secret"
        >>> expand_env_vars("Bearer ${TOKEN}")
        'Bearer secret'
    """
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return pattern.sub(replacer, value)


def expand_path(value: str) -> str:
    """Expand ~ and environment variables in a path.

    Args:
        value: Path string potentially containing ~ or ${VAR}.

    Returns:
        Expanded path string.
    """
    # First expand env vars, then expand ~
    expanded = expand_env_vars(value)
    return str(Path(expanded).expanduser())


def _parse_backend_config(data: dict[str, Any]) -> BackendConfig:
    """Parse a backend configuration from TOML data.

    Args:
        data: Dictionary from TOML backend section.

    Returns:
        BackendConfig instance.
    """
    backend_type = data.get("type", "duckdb")

    # Expand environment variables in sensitive fields
    host = data.get("host")
    if host:
        host = expand_env_vars(host)

    token = data.get("token")
    if token:
        token = expand_env_vars(token)

    # Expand path
    path = data.get("path")
    if path:
        path = expand_path(path)

    return BackendConfig(
        type=backend_type,
        host=host,
        token=token,
        path=path,
        org=data.get("org"),
        bucket=data.get("bucket"),
    )


def load_config(config_path: Path | None = None) -> QuiverConfig | None:
    """Load configuration from TOML file.

    Args:
        config_path: Optional path to config file. If not provided,
                     uses default location (~/.config/quiver/config.toml).

    Returns:
        QuiverConfig if file exists and is valid, None otherwise.

    Raises:
        ValueError: If TOML is invalid.
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        return None

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"Invalid TOML in {config_path}: {e}") from e

    # Parse defaults section
    defaults = data.get("defaults", {})
    default_backend = defaults.get("backend", "duckdb")
    default_output = defaults.get("output", "table")

    # Parse backends section
    backends: dict[str, BackendConfig] = {}
    backends_data = data.get("backends", {})
    for name, backend_data in backends_data.items():
        if isinstance(backend_data, dict):
            backends[name] = _parse_backend_config(backend_data)

    return QuiverConfig(
        backends=backends,
        default_backend=default_backend,
        default_output=default_output,
    )


# Default config template for `quiver init`
DEFAULT_CONFIG_TEMPLATE = """\
# Quiver Configuration
# Location: ~/.config/quiver/config.toml

[defaults]
backend = "duckdb"
output = "table"

[backends.duckdb]
type = "duckdb"

# SQLite backend example:
# [backends.sqlite]
# type = "sqlite"
# path = "~/.local/share/quiver/data.db"

# FlightSQL backend example:
# [backends.flightsql]
# type = "flightsql"
# host = "grpc://localhost:8815"
# token = "${FLIGHTSQL_TOKEN}"

# InfluxDB backend example:
# [backends.influxdb]
# type = "influxdb"
# host = "grpc://localhost:8086"
# token = "${INFLUXDB_TOKEN}"
# org = "myorg"
# bucket = "metrics"
"""


def create_default_config(force: bool = False) -> Path:
    """Create default configuration file.

    Args:
        force: If True, overwrite existing config.

    Returns:
        Path to created config file.

    Raises:
        FileExistsError: If config exists and force is False.
    """
    config_path = get_config_path()

    if config_path.exists() and not force:
        raise FileExistsError(f"Config already exists: {config_path}")

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write default config
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)

    return config_path
