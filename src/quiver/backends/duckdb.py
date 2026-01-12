"""DuckDB backend implementation using ADBC.

DuckDB is an embedded analytical database that natively supports Arrow,
making it ideal for demonstrating ADBC's zero-copy capabilities.

Learning notes:
- DuckDB has built-in ADBC support via its Python package
- No separate adbc-driver-duckdb package needed
- Native DuckDB also returns Arrow tables, enabling fair comparison
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import duckdb
import pyarrow as pa

from quiver.backends.base import get_registry

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


class DuckDBBackend:
    """DuckDB backend using ADBC for Arrow-native database access.

    This backend demonstrates ADBC with an embedded analytical database.
    DuckDB is particularly well-suited for ADBC because it natively uses
    Arrow for its internal data representation.

    Attributes:
        name: Backend identifier ("duckdb").
        path: Database file path, or ":memory:" for in-memory database.

    Example:
        >>> backend = DuckDBBackend()
        >>> backend.connect()
        >>> result = backend.execute("SELECT 1 as num")
        >>> print(result.to_pandas())
        >>> backend.close()

        # Or using context manager:
        >>> with DuckDBBackend() as backend:
        ...     result = backend.execute("SELECT 1 as num")
    """

    name: str = "duckdb"

    def __init__(self, path: str = ":memory:") -> None:
        """Initialize DuckDB backend.

        Args:
            path: Database file path. Defaults to ":memory:" for in-memory database.
        """
        self._path = path
        self._conn: DuckDBPyConnection | None = None

    def connect(self) -> None:
        """Establish connection to DuckDB database.

        Creates a new DuckDB connection. For in-memory databases,
        this creates a fresh database. For file paths, it opens
        or creates the database file.
        """
        self._conn = duckdb.connect(self._path)

    def execute(self, sql: str) -> pa.Table:
        """Execute SQL query via ADBC and return Arrow Table.

        This uses DuckDB's native Arrow integration, which provides
        zero-copy data transfer when possible.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to database.
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn.execute(sql).fetch_arrow_table()

    def execute_native(self, sql: str) -> pa.Table:
        """Execute SQL query via native DuckDB interface.

        For DuckDB, this is essentially the same as execute() since
        DuckDB natively uses Arrow. This method exists for API
        consistency and benchmark comparisons with other backends.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to database.
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        # DuckDB's native interface also returns Arrow tables
        return self._conn.execute(sql).fetch_arrow_table()

    def close(self) -> None:
        """Close the database connection and release resources."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def supports_native_comparison(self) -> bool:
        """Check if this backend supports native vs ADBC comparison.

        Returns:
            True - DuckDB supports both execution paths.
        """
        return True

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


# Register DuckDB backend in the global registry
get_registry().register("duckdb", DuckDBBackend)
