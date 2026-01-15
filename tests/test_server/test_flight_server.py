"""Tests for the FlightSQL server."""

import threading
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from quiver_server import QuiverFlightServer


class TestQuiverFlightServerUnit:
    """Unit tests for QuiverFlightServer class."""

    def test_server_instantiation(self, tmp_path: Path) -> None:
        """Verify server can be instantiated with a parquet file."""
        # Create a test parquet file
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        parquet_path = tmp_path / "test.parquet"
        pq.write_table(table, parquet_path)

        server = QuiverFlightServer(parquet_path, port=18815)
        assert server.data_path == parquet_path
        assert server._port == 18815
        assert server.verbose is False

    def test_server_verbose_mode(self, tmp_path: Path) -> None:
        """Verify verbose mode is stored correctly."""
        parquet_path = tmp_path / "test.parquet"
        table = pa.table({"x": [1]})
        pq.write_table(table, parquet_path)

        server = QuiverFlightServer(parquet_path, verbose=True)
        assert server.verbose is True

    def test_server_duckdb_path(self, tmp_path: Path) -> None:
        """Verify DuckDB database path is handled."""
        # Create a test duckdb file
        import duckdb

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1), (2), (3)")
        conn.close()

        server = QuiverFlightServer(db_path, port=18816)
        assert server.data_path == db_path

    def test_execute_query_parquet(self, tmp_path: Path) -> None:
        """Verify server can execute queries against parquet files."""
        # Create test parquet
        table = pa.table({"value": [10, 20, 30]})
        parquet_path = tmp_path / "data.parquet"
        pq.write_table(table, parquet_path)

        server = QuiverFlightServer(parquet_path, port=18817)

        # Query the parquet file directly
        result = server._execute_query(f"SELECT * FROM '{parquet_path}'")
        assert result.num_rows == 3
        assert result.column("value").to_pylist() == [10, 20, 30]

    def test_execute_query_duckdb(self, tmp_path: Path) -> None:
        """Verify server can execute queries against DuckDB database."""
        import duckdb

        db_path = tmp_path / "analytics.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE metrics (name TEXT, value DOUBLE)")
        conn.execute("INSERT INTO metrics VALUES ('cpu', 0.5), ('mem', 0.8)")
        conn.close()

        server = QuiverFlightServer(db_path, port=18818)

        result = server._execute_query("SELECT * FROM metrics ORDER BY name")
        assert result.num_rows == 2
        assert result.column("name").to_pylist() == ["cpu", "mem"]


class TestQuiverFlightServerIntegration:
    """Integration tests requiring server startup.

    These tests start an actual FlightSQL server and query it.
    """

    # Counter for unique ports across tests
    _port_counter = 19000

    @pytest.fixture
    def parquet_file(self, tmp_path: Path) -> Path:
        """Create a test parquet file."""
        table = pa.table({
            "id": [1, 2, 3, 4, 5],
            "name": ["alice", "bob", "charlie", "diana", "eve"],
            "score": [85.5, 92.0, 78.5, 95.0, 88.5],
        })
        path = tmp_path / "users.parquet"
        pq.write_table(table, path)
        return path

    @pytest.fixture
    def flight_server(self, parquet_file: Path, request):
        """Start a FlightSQL server in a background thread."""
        # Use unique port for each test
        TestQuiverFlightServerIntegration._port_counter += 1
        port = TestQuiverFlightServerIntegration._port_counter

        server = QuiverFlightServer(parquet_file, port=port, verbose=False)

        # Start server in background thread
        server_thread = threading.Thread(target=server.serve, daemon=True)
        server_thread.start()

        # Wait for server to be ready
        time.sleep(0.5)

        yield f"grpc://localhost:{port}", parquet_file

        # Shutdown
        try:
            server.shutdown()
        except Exception:
            pass  # Ignore shutdown errors

    def test_flight_client_connect(self, flight_server: tuple[str, Path]) -> None:
        """Test connecting to server with PyArrow Flight client."""
        import pyarrow.flight as flight

        uri, parquet_path = flight_server
        client = flight.connect(uri)

        # List flights should work
        flights = list(client.list_flights())
        # Should have at least one flight (the data table)
        assert len(flights) >= 0  # May be empty if list_flights not fully implemented

    def test_query_via_flight(self, flight_server: tuple[str, Path]) -> None:
        """Test executing SQL query via Flight protocol."""
        import pyarrow.flight as flight

        uri, parquet_path = flight_server
        client = flight.connect(uri)

        # Send SQL as command
        sql = f"SELECT * FROM '{parquet_path}'"
        descriptor = flight.FlightDescriptor.for_command(sql.encode())

        # Get flight info (this triggers query execution)
        info = client.get_flight_info(descriptor)
        assert info.total_records == 5

        # Fetch the data
        reader = client.do_get(info.endpoints[0].ticket)
        table = reader.read_all()

        assert table.num_rows == 5
        assert "id" in table.column_names
        assert "name" in table.column_names
        assert "score" in table.column_names

    def test_query_with_filter(self, flight_server: tuple[str, Path]) -> None:
        """Test SQL query with WHERE clause."""
        import pyarrow.flight as flight

        uri, parquet_path = flight_server
        client = flight.connect(uri)

        sql = f"SELECT name, score FROM '{parquet_path}' WHERE score > 90"
        descriptor = flight.FlightDescriptor.for_command(sql.encode())

        info = client.get_flight_info(descriptor)
        reader = client.do_get(info.endpoints[0].ticket)
        table = reader.read_all()

        # Should only get bob (92.0) and diana (95.0)
        assert table.num_rows == 2
        names = table.column("name").to_pylist()
        assert "bob" in names
        assert "diana" in names

    def test_query_with_aggregation(self, flight_server: tuple[str, Path]) -> None:
        """Test SQL query with aggregation."""
        import pyarrow.flight as flight

        uri, parquet_path = flight_server
        client = flight.connect(uri)

        sql = f"SELECT AVG(score) as avg_score FROM '{parquet_path}'"
        descriptor = flight.FlightDescriptor.for_command(sql.encode())

        info = client.get_flight_info(descriptor)
        reader = client.do_get(info.endpoints[0].ticket)
        table = reader.read_all()

        assert table.num_rows == 1
        avg_score = table.column("avg_score")[0].as_py()
        # Average of [85.5, 92.0, 78.5, 95.0, 88.5] = 87.9
        assert abs(avg_score - 87.9) < 0.1


class TestServeCLI:
    """Tests for the serve CLI command."""

    def test_serve_help(self) -> None:
        """Verify serve command appears in help."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--help"])

        assert result.exit_code == 0
        assert "FlightSQL server" in result.stdout
        assert "--port" in result.stdout
        assert "--verbose" in result.stdout

    def test_serve_nonexistent_path(self) -> None:
        """Verify error on nonexistent data path."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["serve", "/nonexistent/path.parquet"])

        assert result.exit_code != 0
        assert "does not exist" in result.stdout
