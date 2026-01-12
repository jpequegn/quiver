"""Backend implementations for various ADBC drivers."""

from quiver.backends.base import Backend, BackendRegistry, get_registry
from quiver.backends.duckdb import DuckDBBackend

__all__ = ["Backend", "BackendRegistry", "DuckDBBackend", "get_registry"]
