"""Tests for the FlightSQL backend."""

import pytest

from quiver.backends import FlightSQLBackend, get_registry


class TestFlightSQLBackend:
    """Tests for FlightSQLBackend class."""

    def test_backend_registered(self) -> None:
        """Verify FlightSQL backend is registered in the registry."""
        registry = get_registry()
        assert "flightsql" in registry.list_backends()
        assert registry.get("flightsql") == FlightSQLBackend

    def test_backend_name(self) -> None:
        """Verify backend name is set correctly."""
        backend = FlightSQLBackend()
        assert backend.name == "flightsql"

    def test_default_uri(self) -> None:
        """Verify default URI is localhost."""
        backend = FlightSQLBackend()
        assert backend._uri == "grpc://localhost:8815"

    def test_custom_uri(self) -> None:
        """Verify custom URI is stored correctly."""
        backend = FlightSQLBackend(uri="grpc://myserver:9090")
        assert backend._uri == "grpc://myserver:9090"

    def test_token_stored(self) -> None:
        """Verify authentication token is stored."""
        backend = FlightSQLBackend(token="my-secret-token")
        assert backend._token == "my-secret-token"

    def test_uri_and_token(self) -> None:
        """Verify both URI and token can be set together."""
        backend = FlightSQLBackend(
            uri="grpc+tls://secure-server:8815",
            token="secure-token",
        )
        assert backend._uri == "grpc+tls://secure-server:8815"
        assert backend._token == "secure-token"

    def test_supports_native_comparison(self) -> None:
        """Verify FlightSQL doesn't support native comparison."""
        backend = FlightSQLBackend()
        assert backend.supports_native_comparison() is False

    def test_execute_without_connect_raises(self) -> None:
        """Verify execute raises error when not connected."""
        backend = FlightSQLBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.execute("SELECT 1")

    def test_execute_native_without_connect_raises(self) -> None:
        """Verify execute_native raises error when not connected."""
        backend = FlightSQLBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.execute_native("SELECT 1")

    def test_close_without_connect_is_safe(self) -> None:
        """Verify close() is safe to call without connect()."""
        backend = FlightSQLBackend()
        backend.close()  # Should not raise


class TestFlightSQLDriverImport:
    """Tests for FlightSQL driver import handling."""

    def test_connect_import_error_message(self) -> None:
        """Verify helpful error message when driver not installed."""
        try:
            import adbc_driver_flightsql  # noqa: F401

            pytest.skip("adbc-driver-flightsql is installed, skipping import error test")
        except ImportError:
            # Driver not installed, test the error handling
            backend = FlightSQLBackend()
            with pytest.raises(ImportError) as exc_info:
                backend.connect()

            assert "adbc-driver-flightsql" in str(exc_info.value)
            assert "pip install quiver[flightsql]" in str(exc_info.value)


class TestFlightSQLIntegration:
    """Integration tests requiring a FlightSQL server.

    These tests are skipped by default since they require a running
    FlightSQL server. To run them, set up a local FlightSQL server
    and remove the skip decorator.
    """

    @pytest.fixture
    def has_flightsql_driver(self) -> bool:
        """Check if FlightSQL driver is available."""
        try:
            import adbc_driver_flightsql  # noqa: F401

            return True
        except ImportError:
            return False

    @pytest.mark.skip(reason="Requires running FlightSQL server")
    def test_connect_to_server(self) -> None:
        """Test connecting to a real FlightSQL server."""
        backend = FlightSQLBackend(uri="grpc://localhost:8815")
        backend.connect()
        backend.close()

    @pytest.mark.skip(reason="Requires running FlightSQL server")
    def test_execute_query(self) -> None:
        """Test executing a query against a real FlightSQL server."""
        with FlightSQLBackend(uri="grpc://localhost:8815") as backend:
            result = backend.execute("SELECT 1 as num")
            assert result.num_rows == 1

    @pytest.mark.skip(reason="Requires running FlightSQL server with auth")
    def test_connect_with_token(self) -> None:
        """Test connecting with authentication token."""
        with FlightSQLBackend(
            uri="grpc://localhost:8815",
            token="test-token",
        ) as backend:
            result = backend.execute("SELECT 1 as num")
            assert result.num_rows == 1
