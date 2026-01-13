"""SQLite backend implementation using ADBC.

SQLite via ADBC demonstrates the driver abstraction - the same Arrow-based
interface works across different database engines.

Learning notes:
- SQLite ADBC driver is a separate package: adbc-driver-sqlite
- Uses standard ADBC DBAPI interface
- Returns Arrow tables just like DuckDB, showing the abstraction
- No native Arrow path (unlike DuckDB), so execute_native uses same path
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import pyarrow as pa

from quiver.backends.base import get_registry

if TYPE_CHECKING:
    pass


class SQLiteBackend:
    """SQLite backend using ADBC for Arrow-native database access.

    This backend demonstrates ADBC with SQLite, showing how the same
    Arrow-based interface works across different database engines.

    Attributes:
        name: Backend identifier ("sqlite").
        path: Database file path, or ":memory:" for in-memory database.

    Example:
        >>> backend = SQLiteBackend()
        >>> backend.connect()
        >>> result = backend.execute("SELECT 1 as num")
        >>> print(result.to_pandas())
        >>> backend.close()

        # Or using context manager:
        >>> with SQLiteBackend() as backend:
        ...     result = backend.execute("SELECT 1 as num")
    """

    name: str = "sqlite"

    def __init__(self, path: str = ":memory:") -> None:
        """Initialize SQLite backend.

        Args:
            path: Database file path. Defaults to ":memory:" for in-memory database.
        """
        self._path = path
        self._conn: Any | None = None

    def connect(self) -> None:
        """Establish connection to SQLite database via ADBC.

        Creates a new SQLite connection using the ADBC driver.
        For in-memory databases, this creates a fresh database.
        For file paths, it opens or creates the database file.
        """
        import adbc_driver_sqlite.dbapi as sqlite_dbapi

        self._conn = sqlite_dbapi.connect(self._path)

    def execute(self, sql: str) -> pa.Table:
        """Execute SQL query via ADBC and return Arrow Table.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to database.
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")

        with self._conn.cursor() as cursor:
            cursor.execute(sql)
            # Check if this is a query that returns results
            if cursor.description is not None:
                return cursor.fetch_arrow_table()
            else:
                # For INSERT/CREATE/etc., return empty table
                return pa.table({})

    def execute_native(self, sql: str) -> pa.Table:
        """Execute SQL query via ADBC (same as execute for SQLite).

        SQLite via ADBC doesn't have a separate native Arrow path like DuckDB.
        This method exists for API consistency but uses the same ADBC path.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to database.
        """
        # SQLite doesn't have a native Arrow path, use ADBC
        return self.execute(sql)

    def close(self) -> None:
        """Close the database connection and release resources."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def supports_native_comparison(self) -> bool:
        """Check if this backend supports native vs ADBC comparison.

        Returns:
            False - SQLite only has the ADBC path, no native Arrow interface.
        """
        return False

    def __enter__(self) -> Self:
        """Enter context manager, establishing connection."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager, closing connection."""
        self.close()


# Register SQLite backend in the global registry
get_registry().register("sqlite", SQLiteBackend)
