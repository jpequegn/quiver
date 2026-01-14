"""Tests for SQLite backend implementation."""

import pyarrow as pa

from quiver.backends import get_registry
from quiver.backends.sqlite import SQLiteBackend


class TestSQLiteBackend:
    """Tests for the SQLite ADBC backend."""

    def test_backend_has_correct_name(self) -> None:
        """Backend should identify as 'sqlite'."""
        backend = SQLiteBackend()
        assert backend.name == "sqlite"

    def test_connect_creates_connection(self) -> None:
        """Connect should establish a database connection."""
        backend = SQLiteBackend()
        backend.connect()
        assert backend._conn is not None
        backend.close()

    def test_connect_with_path(self) -> None:
        """Connect should support file-based databases."""
        backend = SQLiteBackend(path=":memory:")
        backend.connect()
        assert backend._conn is not None
        backend.close()

    def test_close_releases_connection(self) -> None:
        """Close should release the database connection."""
        backend = SQLiteBackend()
        backend.connect()
        backend.close()
        assert backend._conn is None

    def test_execute_returns_arrow_table(self) -> None:
        """Execute should return a PyArrow Table."""
        backend = SQLiteBackend()
        backend.connect()
        result = backend.execute("SELECT 1 as num, 'hello' as greeting")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 1
        assert "num" in result.column_names
        assert "greeting" in result.column_names
        backend.close()

    def test_execute_with_multiple_rows(self) -> None:
        """Execute should handle multiple rows."""
        backend = SQLiteBackend()
        backend.connect()
        # SQLite uses UNION ALL instead of VALUES for multiple rows
        result = backend.execute(
            "SELECT 1 as num UNION ALL SELECT 2 UNION ALL SELECT 3"
        )
        assert isinstance(result, pa.Table)
        assert result.num_rows == 3
        backend.close()

    def test_execute_native_returns_arrow_table(self) -> None:
        """Execute native should also return a PyArrow Table."""
        backend = SQLiteBackend()
        backend.connect()
        result = backend.execute_native("SELECT 1 as num")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 1
        backend.close()

    def test_supports_native_comparison(self) -> None:
        """SQLite should not support native comparison (ADBC only)."""
        backend = SQLiteBackend()
        # SQLite via ADBC doesn't have a separate native path
        assert backend.supports_native_comparison() is False

    def test_context_manager(self) -> None:
        """Backend should support context manager protocol."""
        with SQLiteBackend() as backend:
            result = backend.execute("SELECT 1 as num")
            assert result.num_rows == 1

    def test_create_table_and_query(self) -> None:
        """Should be able to create tables and query them."""
        backend = SQLiteBackend()
        backend.connect()

        # Create and populate a table
        backend.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        backend.execute("INSERT INTO test_table VALUES (1, 'Alice'), (2, 'Bob')")

        # Query the table
        result = backend.execute("SELECT * FROM test_table ORDER BY id")
        assert result.num_rows == 2
        data = result.to_pydict()
        assert data["id"] == [1, 2]
        assert data["name"] == ["Alice", "Bob"]

        backend.close()


class TestSQLiteRegistration:
    """Tests for SQLite backend registration."""

    def test_sqlite_is_registered(self) -> None:
        """SQLite should be registered in the global registry."""
        registry = get_registry()
        assert "sqlite" in registry.list_backends()

    def test_can_get_sqlite_from_registry(self) -> None:
        """Should be able to get SQLite backend class from registry."""
        registry = get_registry()
        backend_cls = registry.get("sqlite")
        assert backend_cls is SQLiteBackend


class TestSQLiteVsDuckDB:
    """Tests demonstrating ADBC abstraction - same queries work on both backends."""

    def test_same_simple_query_works_on_both(self) -> None:
        """Same simple query should work on both backends."""
        from quiver.backends.duckdb import DuckDBBackend

        sql = "SELECT 42 as answer"

        with DuckDBBackend() as duckdb:
            duckdb_result = duckdb.execute(sql)

        with SQLiteBackend() as sqlite:
            sqlite_result = sqlite.execute(sql)

        # Both return Arrow tables with same structure
        assert duckdb_result.column_names == sqlite_result.column_names
        assert duckdb_result.num_rows == sqlite_result.num_rows
        assert duckdb_result.to_pydict()["answer"] == sqlite_result.to_pydict()["answer"]

    def test_same_table_operations_work_on_both(self) -> None:
        """Same table creation and query should work on both backends."""
        from quiver.backends.duckdb import DuckDBBackend

        with DuckDBBackend() as duckdb:
            duckdb.execute("CREATE TABLE users (id INTEGER, name TEXT)")
            duckdb.execute("INSERT INTO users VALUES (1, 'Alice')")
            duckdb_result = duckdb.execute("SELECT * FROM users")

        with SQLiteBackend() as sqlite:
            sqlite.execute("CREATE TABLE users (id INTEGER, name TEXT)")
            sqlite.execute("INSERT INTO users VALUES (1, 'Alice')")
            sqlite_result = sqlite.execute("SELECT * FROM users")

        # Both produce equivalent results
        assert duckdb_result.to_pydict() == sqlite_result.to_pydict()
