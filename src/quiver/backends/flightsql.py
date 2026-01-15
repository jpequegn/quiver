"""FlightSQL backend implementation using ADBC.

FlightSQL is a protocol for interacting with databases over Arrow Flight,
enabling high-performance data transfer over the network.

Learning notes:
- FlightSQL uses gRPC for transport with Arrow Flight protocol
- ADBC provides a standard interface that works with any FlightSQL server
- Authentication is typically token-based via headers
- URI format: grpc://host:port or grpc+tls://host:port for TLS
"""

from __future__ import annotations

from typing import Any, Self

import pyarrow as pa

from quiver.backends.base import get_registry


class FlightSQLBackend:
    """FlightSQL backend using ADBC for Arrow-native remote database access.

    This backend connects to any FlightSQL-compatible server (InfluxDB,
    Dremio, etc.) using the Arrow Flight SQL protocol over gRPC.

    Attributes:
        name: Backend identifier ("flightsql").
        uri: Connection URI (e.g., "grpc://localhost:8815").
        token: Optional authentication token.

    Example:
        >>> backend = FlightSQLBackend("grpc://localhost:8815")
        >>> backend.connect()
        >>> result = backend.execute("SELECT 1 as num")
        >>> print(result.to_pandas())
        >>> backend.close()

        # With authentication:
        >>> with FlightSQLBackend("grpc://localhost:8815", token="secret") as backend:
        ...     result = backend.execute("SELECT * FROM data")
    """

    name: str = "flightsql"

    def __init__(self, uri: str = "grpc://localhost:8815", token: str | None = None) -> None:
        """Initialize FlightSQL backend.

        Args:
            uri: FlightSQL server URI. Supports grpc:// and grpc+tls:// schemes.
                 Defaults to "grpc://localhost:8815".
            token: Optional authentication token for header-based auth.
        """
        self._uri = uri
        self._token = token
        self._conn: Any | None = None

    def connect(self) -> None:
        """Establish connection to FlightSQL server via ADBC.

        Creates a new FlightSQL connection using the ADBC driver.
        If a token is provided, it's sent as an authorization header.

        Raises:
            ImportError: If adbc-driver-flightsql is not installed.
        """
        try:
            import adbc_driver_flightsql.dbapi as flightsql_dbapi
        except ImportError:
            raise ImportError(
                "adbc-driver-flightsql is required for FlightSQL backend. "
                "Install with: pip install quiver[flightsql]"
            )

        # Build connection kwargs
        db_kwargs: dict[str, Any] = {"uri": self._uri}

        # Add authentication if token provided
        if self._token:
            # FlightSQL uses header-based auth
            db_kwargs["db_kwargs"] = {
                "authorization": f"Bearer {self._token}",
            }

        self._conn = flightsql_dbapi.connect(**db_kwargs)

    def execute(self, sql: str) -> pa.Table:
        """Execute SQL query via ADBC and return Arrow Table.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to server.
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
        """Execute SQL query via ADBC (same as execute for FlightSQL).

        FlightSQL is inherently an Arrow-native protocol, so there's no
        separate "native" path. This method exists for API consistency.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.

        Raises:
            RuntimeError: If not connected to server.
        """
        # FlightSQL is already Arrow-native, use ADBC path
        return self.execute(sql)

    def close(self) -> None:
        """Close the server connection and release resources."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def supports_native_comparison(self) -> bool:
        """Check if this backend supports native vs ADBC comparison.

        Returns:
            False - FlightSQL only has the ADBC/Arrow Flight path.
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


# Register FlightSQL backend in the global registry
get_registry().register("flightsql", FlightSQLBackend)
