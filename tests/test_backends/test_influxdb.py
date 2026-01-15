"""Tests for the InfluxDB backend."""

import pytest

from quiver.backends import InfluxDBBackend, get_registry
from quiver.backends.flightsql import FlightSQLBackend


class TestInfluxDBBackend:
    """Tests for InfluxDBBackend class."""

    def test_backend_registered(self) -> None:
        """Verify InfluxDB backend is registered in the registry."""
        registry = get_registry()
        assert "influxdb" in registry.list_backends()
        assert registry.get("influxdb") == InfluxDBBackend

    def test_backend_name(self) -> None:
        """Verify backend name is set correctly."""
        backend = InfluxDBBackend()
        assert backend.name == "influxdb"

    def test_inherits_from_flightsql(self) -> None:
        """Verify InfluxDBBackend inherits from FlightSQLBackend."""
        assert issubclass(InfluxDBBackend, FlightSQLBackend)
        backend = InfluxDBBackend()
        assert isinstance(backend, FlightSQLBackend)

    def test_default_uri(self) -> None:
        """Verify default URI is localhost:8086."""
        backend = InfluxDBBackend()
        assert backend._uri == "grpc://localhost:8086"

    def test_custom_uri(self) -> None:
        """Verify custom URI is stored correctly."""
        backend = InfluxDBBackend(uri="grpc://influxdb.example.com:8086")
        assert backend._uri == "grpc://influxdb.example.com:8086"

    def test_token_stored(self) -> None:
        """Verify authentication token is stored."""
        backend = InfluxDBBackend(token="my-api-token")
        assert backend._token == "my-api-token"

    def test_org_stored(self) -> None:
        """Verify organization is stored."""
        backend = InfluxDBBackend(org="myorg")
        assert backend._org == "myorg"
        assert backend.org == "myorg"

    def test_bucket_stored(self) -> None:
        """Verify bucket is stored."""
        backend = InfluxDBBackend(bucket="mybucket")
        assert backend._bucket == "mybucket"
        assert backend.bucket == "mybucket"

    def test_all_params(self) -> None:
        """Verify all parameters can be set together."""
        backend = InfluxDBBackend(
            uri="grpc://influxdb.example.com:8086",
            token="secret-token",
            org="quiver",
            bucket="metrics",
        )
        assert backend._uri == "grpc://influxdb.example.com:8086"
        assert backend._token == "secret-token"
        assert backend.org == "quiver"
        assert backend.bucket == "metrics"

    def test_supports_native_comparison(self) -> None:
        """Verify InfluxDB doesn't support native comparison (inherited)."""
        backend = InfluxDBBackend()
        assert backend.supports_native_comparison() is False

    def test_execute_without_connect_raises(self) -> None:
        """Verify execute raises error when not connected."""
        backend = InfluxDBBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.execute("SELECT 1")

    def test_close_without_connect_is_safe(self) -> None:
        """Verify close() is safe to call without connect()."""
        backend = InfluxDBBackend()
        backend.close()  # Should not raise


class TestInfluxDBDriverImport:
    """Tests for InfluxDB driver import handling."""

    def test_connect_import_error_message(self) -> None:
        """Verify helpful error message when driver not installed."""
        try:
            import adbc_driver_flightsql  # noqa: F401

            pytest.skip("adbc-driver-flightsql is installed, skipping import error test")
        except ImportError:
            # Driver not installed, test the error handling
            backend = InfluxDBBackend()
            with pytest.raises(ImportError) as exc_info:
                backend.connect()

            assert "adbc-driver-flightsql" in str(exc_info.value)
            assert "pip install quiver[flightsql]" in str(exc_info.value)


class TestInfluxDBIntegration:
    """Integration tests requiring a running InfluxDB instance.

    These tests are skipped by default since they require a running
    InfluxDB server with FlightSQL enabled. To run them:

    1. Start InfluxDB: docker compose -f docker/docker-compose.yml up -d
    2. Remove the skip decorator
    3. Run: pytest tests/test_backends/test_influxdb.py -v

    Note: InfluxDB FlightSQL is experimental and may not be enabled
    by default in all InfluxDB installations.
    """

    @pytest.fixture
    def influxdb_backend(self):
        """Create an InfluxDB backend configured for local Docker."""
        return InfluxDBBackend(
            uri="grpc://localhost:8086",
            token="quiver-test-token",
            org="quiver",
            bucket="metrics",
        )

    @pytest.mark.skip(reason="Requires running InfluxDB with FlightSQL")
    def test_connect_to_influxdb(self, influxdb_backend: InfluxDBBackend) -> None:
        """Test connecting to a real InfluxDB instance."""
        influxdb_backend.connect()
        influxdb_backend.close()

    @pytest.mark.skip(reason="Requires running InfluxDB with FlightSQL")
    def test_execute_query(self, influxdb_backend: InfluxDBBackend) -> None:
        """Test executing a query against InfluxDB."""
        with influxdb_backend:
            # Simple query to test connection
            result = influxdb_backend.execute("SELECT 1 as num")
            assert result.num_rows >= 0

    @pytest.mark.skip(reason="Requires running InfluxDB with FlightSQL")
    def test_query_metrics_bucket(self, influxdb_backend: InfluxDBBackend) -> None:
        """Test querying the metrics bucket."""
        with influxdb_backend:
            # Query the metrics bucket
            result = influxdb_backend.execute(
                "SELECT * FROM metrics WHERE time > now() - 1h LIMIT 10"
            )
            # Just verify we get a result without errors
            assert result is not None
