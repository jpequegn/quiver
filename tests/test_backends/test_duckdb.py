"""Tests for DuckDB backend implementation."""

import pyarrow as pa

from quiver.backends import get_registry
from quiver.backends.duckdb import DuckDBBackend


class TestDuckDBBackend:
    """Tests for the DuckDB ADBC backend."""

    def test_backend_has_correct_name(self) -> None:
        """Backend should identify as 'duckdb'."""
        backend = DuckDBBackend()
        assert backend.name == "duckdb"

    def test_connect_creates_connection(self) -> None:
        """Connect should establish a database connection."""
        backend = DuckDBBackend()
        backend.connect()
        assert backend._conn is not None
        backend.close()

    def test_connect_with_path(self) -> None:
        """Connect should support file-based databases."""
        backend = DuckDBBackend(path=":memory:")
        backend.connect()
        assert backend._conn is not None
        backend.close()

    def test_close_releases_connection(self) -> None:
        """Close should release the database connection."""
        backend = DuckDBBackend()
        backend.connect()
        backend.close()
        assert backend._conn is None

    def test_execute_returns_arrow_table(self) -> None:
        """Execute should return a PyArrow Table."""
        backend = DuckDBBackend()
        backend.connect()
        result = backend.execute("SELECT 1 as num, 'hello' as greeting")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 1
        assert "num" in result.column_names
        assert "greeting" in result.column_names
        backend.close()

    def test_execute_with_multiple_rows(self) -> None:
        """Execute should handle multiple rows."""
        backend = DuckDBBackend()
        backend.connect()
        result = backend.execute("SELECT * FROM (VALUES (1), (2), (3)) AS t(num)")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 3
        backend.close()

    def test_execute_native_returns_arrow_table(self) -> None:
        """Execute native should also return a PyArrow Table."""
        backend = DuckDBBackend()
        backend.connect()
        result = backend.execute_native("SELECT 1 as num")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 1
        backend.close()

    def test_supports_native_comparison(self) -> None:
        """DuckDB should support native comparison."""
        backend = DuckDBBackend()
        assert backend.supports_native_comparison() is True

    def test_execute_and_native_return_same_data(self) -> None:
        """Both execution paths should return equivalent data."""
        backend = DuckDBBackend()
        backend.connect()

        sql = "SELECT 42 as answer"
        adbc_result = backend.execute(sql)
        native_result = backend.execute_native(sql)

        assert adbc_result.num_rows == native_result.num_rows
        assert adbc_result.column_names == native_result.column_names
        assert adbc_result.to_pydict() == native_result.to_pydict()

        backend.close()

    def test_context_manager(self) -> None:
        """Backend should support context manager protocol."""
        with DuckDBBackend() as backend:
            result = backend.execute("SELECT 1 as num")
            assert result.num_rows == 1

    def test_create_table_and_query(self) -> None:
        """Should be able to create tables and query them."""
        backend = DuckDBBackend()
        backend.connect()

        # Create and populate a table
        backend.execute("CREATE TABLE test_table (id INTEGER, name VARCHAR)")
        backend.execute("INSERT INTO test_table VALUES (1, 'Alice'), (2, 'Bob')")

        # Query the table
        result = backend.execute("SELECT * FROM test_table ORDER BY id")
        assert result.num_rows == 2
        data = result.to_pydict()
        assert data["id"] == [1, 2]
        assert data["name"] == ["Alice", "Bob"]

        backend.close()


class TestDuckDBRegistration:
    """Tests for DuckDB backend registration."""

    def test_duckdb_is_registered(self) -> None:
        """DuckDB should be registered in the global registry."""
        registry = get_registry()
        assert "duckdb" in registry.list_backends()

    def test_can_get_duckdb_from_registry(self) -> None:
        """Should be able to get DuckDB backend class from registry."""
        registry = get_registry()
        backend_cls = registry.get("duckdb")
        assert backend_cls is DuckDBBackend
