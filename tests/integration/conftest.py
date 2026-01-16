"""Shared fixtures for integration tests."""

import pytest

from quiver.backends import DuckDBBackend, SQLiteBackend, get_registry
from quiver.loaders import FinancialLoader, ObservabilityLoader


@pytest.fixture
def duckdb_backend():
    """Create a DuckDB backend for testing."""
    backend = DuckDBBackend()
    backend.connect()
    yield backend
    backend.close()


@pytest.fixture
def sqlite_backend():
    """Create a SQLite backend for testing."""
    backend = SQLiteBackend()
    backend.connect()
    yield backend
    backend.close()


@pytest.fixture
def duckdb_with_trades(duckdb_backend):
    """DuckDB backend with synthetic trade data loaded."""
    loader = FinancialLoader()
    loader.load_synthetic(duckdb_backend, rows=1000)
    return duckdb_backend


@pytest.fixture
def duckdb_with_metrics(duckdb_backend):
    """DuckDB backend with synthetic metrics data loaded."""
    loader = ObservabilityLoader()
    loader.load_synthetic(duckdb_backend, metrics=1000, hosts=5, services=3)
    return duckdb_backend


@pytest.fixture
def sqlite_with_trades(sqlite_backend):
    """SQLite backend with synthetic trade data loaded."""
    loader = FinancialLoader()
    loader.load_synthetic(sqlite_backend, rows=1000)
    return sqlite_backend


@pytest.fixture
def all_local_backends():
    """Get all available local backends."""
    registry = get_registry()
    backends = []

    for name in ["duckdb", "sqlite"]:
        if name in registry.list_backends():
            backend_cls = registry.get(name)
            backend = backend_cls()
            backend.connect()
            backends.append((name, backend))

    yield backends

    for _, backend in backends:
        backend.close()
