"""InfluxDB backend implementation using FlightSQL via ADBC.

InfluxDB 2.x+ supports the FlightSQL protocol for high-performance
Arrow-native data access. This backend extends FlightSQLBackend
with InfluxDB-specific configuration.

Learning notes:
- InfluxDB uses FlightSQL on port 8086 (same as HTTP API)
- Authentication uses API tokens via Bearer authorization
- InfluxDB has concepts of org and bucket for data organization
- FlightSQL support in InfluxDB is experimental but functional
"""

from __future__ import annotations

from typing import Any

from quiver.backends.base import get_registry
from quiver.backends.flightsql import FlightSQLBackend


class InfluxDBBackend(FlightSQLBackend):
    """InfluxDB backend using FlightSQL via ADBC.

    This backend connects to InfluxDB 2.x+ using the FlightSQL protocol,
    providing high-performance Arrow-native access to time-series data.

    Attributes:
        name: Backend identifier ("influxdb").
        uri: Connection URI (e.g., "grpc://localhost:8086").
        token: InfluxDB API token for authentication.
        org: InfluxDB organization name.
        bucket: InfluxDB bucket name.

    Example:
        >>> backend = InfluxDBBackend(
        ...     uri="grpc://localhost:8086",
        ...     token="my-api-token",
        ...     org="myorg",
        ...     bucket="mybucket",
        ... )
        >>> backend.connect()
        >>> result = backend.execute("SELECT * FROM metrics")
        >>> backend.close()

        # Using context manager:
        >>> with InfluxDBBackend(uri="grpc://localhost:8086", token="token") as db:
        ...     result = db.execute("SELECT * FROM cpu WHERE time > now() - 1h")
    """

    name: str = "influxdb"

    def __init__(
        self,
        uri: str = "grpc://localhost:8086",
        token: str | None = None,
        org: str | None = None,
        bucket: str | None = None,
    ) -> None:
        """Initialize InfluxDB backend.

        Args:
            uri: InfluxDB FlightSQL URI. Defaults to "grpc://localhost:8086".
            token: InfluxDB API token for authentication.
            org: InfluxDB organization name (optional, for context).
            bucket: InfluxDB bucket name (optional, for context).
        """
        super().__init__(uri=uri, token=token)
        self._org = org
        self._bucket = bucket

    def connect(self) -> None:
        """Establish connection to InfluxDB via FlightSQL.

        Creates a new FlightSQL connection to InfluxDB. If org and bucket
        are provided, they may be included in connection metadata.

        Raises:
            ImportError: If adbc-driver-flightsql is not installed.
        """
        try:
            import adbc_driver_flightsql.dbapi as flightsql_dbapi
        except ImportError:
            raise ImportError(
                "adbc-driver-flightsql is required for InfluxDB backend. "
                "Install with: pip install quiver[flightsql]"
            )

        # Build connection kwargs
        db_kwargs: dict[str, Any] = {"uri": self._uri}

        # Build headers for InfluxDB authentication
        headers: dict[str, str] = {}

        # Add authentication token
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"

        # Add InfluxDB-specific headers if provided
        if self._org:
            headers["influx-org"] = self._org
        if self._bucket:
            headers["influx-bucket"] = self._bucket

        # Only add db_kwargs if we have headers
        if headers:
            db_kwargs["db_kwargs"] = headers

        self._conn = flightsql_dbapi.connect(**db_kwargs)

    @property
    def org(self) -> str | None:
        """Get the configured InfluxDB organization."""
        return self._org

    @property
    def bucket(self) -> str | None:
        """Get the configured InfluxDB bucket."""
        return self._bucket


# Register InfluxDB backend in the global registry
get_registry().register("influxdb", InfluxDBBackend)
