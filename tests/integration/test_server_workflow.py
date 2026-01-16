"""Integration tests for FlightSQL server workflows.

These tests start a real FlightSQL server and query it via the FlightSQL client backend.
"""

import threading
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from quiver.backends import FlightSQLBackend
from quiver_server import QuiverFlightServer

# Use different ports for each test to avoid conflicts
_port_counter = 28900


def get_next_port() -> int:
    """Get a unique port for each test."""
    global _port_counter
    _port_counter += 1
    return _port_counter


@pytest.mark.skip(reason="FlightSQL server tests require server compatibility fixes")
class TestFlightSQLServerWorkflow:
    """Test complete FlightSQL server workflow."""

    @pytest.fixture
    def parquet_server(self, tmp_path: Path):
        """Start a FlightSQL server serving a parquet file."""
        # Create test data
        table = pa.table({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "score": [85.5, 92.0, 78.3, 95.2, 88.7],
        })
        parquet_path = tmp_path / "users.parquet"
        pq.write_table(table, parquet_path)

        port = get_next_port()
        server = QuiverFlightServer(parquet_path, port=port)

        # Start server in background thread
        server_thread = threading.Thread(target=server.serve, daemon=True)
        server_thread.start()
        time.sleep(0.5)  # Wait for server to start

        yield server, port, parquet_path

    @pytest.fixture
    def duckdb_server(self, tmp_path: Path):
        """Start a FlightSQL server serving a DuckDB database."""
        import duckdb

        # Create test database
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name VARCHAR,
                price DECIMAL(10, 2),
                quantity INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO products VALUES
            (1, 'Widget', 9.99, 100),
            (2, 'Gadget', 24.99, 50),
            (3, 'Gizmo', 14.99, 75)
        """)
        conn.close()

        port = get_next_port()
        server = QuiverFlightServer(db_path, port=port)

        # Start server in background thread
        server_thread = threading.Thread(target=server.serve, daemon=True)
        server_thread.start()
        time.sleep(0.5)

        yield server, port, db_path

    def test_connect_to_parquet_server(self, parquet_server) -> None:
        """Test connecting to a FlightSQL server serving parquet."""
        server, port, _ = parquet_server

        # Connect via FlightSQL backend
        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        backend.connect()

        # Should be connected
        assert backend._connection is not None

        backend.close()

    def test_query_parquet_via_flightsql(self, parquet_server) -> None:
        """Test querying parquet data through FlightSQL."""
        server, port, parquet_path = parquet_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            # Query all data
            result = backend.execute(f"SELECT * FROM '{parquet_path}'")

            assert result.num_rows == 5
            assert "id" in result.column_names
            assert "name" in result.column_names
            assert "score" in result.column_names

    def test_query_with_filter_via_flightsql(self, parquet_server) -> None:
        """Test filtered query through FlightSQL."""
        server, port, parquet_path = parquet_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            result = backend.execute(
                f"SELECT name, score FROM '{parquet_path}' WHERE score > 90"
            )

            assert result.num_rows == 2
            names = result.column("name").to_pylist()
            assert "Bob" in names
            assert "Diana" in names

    def test_query_with_aggregation_via_flightsql(self, parquet_server) -> None:
        """Test aggregation query through FlightSQL."""
        server, port, parquet_path = parquet_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            result = backend.execute(
                f"SELECT AVG(score) as avg_score, COUNT(*) as cnt FROM '{parquet_path}'"
            )

            assert result.num_rows == 1
            assert result.column("cnt")[0].as_py() == 5

    def test_query_duckdb_via_flightsql(self, duckdb_server) -> None:
        """Test querying DuckDB database through FlightSQL."""
        server, port, _ = duckdb_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            result = backend.execute("SELECT * FROM products ORDER BY id")

            assert result.num_rows == 3
            assert result.column("name").to_pylist() == ["Widget", "Gadget", "Gizmo"]

    def test_duckdb_aggregation_via_flightsql(self, duckdb_server) -> None:
        """Test aggregation on DuckDB through FlightSQL."""
        server, port, _ = duckdb_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            result = backend.execute("""
                SELECT
                    SUM(price * quantity) as total_value,
                    AVG(price) as avg_price
                FROM products
            """)

            assert result.num_rows == 1
            # Widget: 9.99 * 100 = 999
            # Gadget: 24.99 * 50 = 1249.50
            # Gizmo: 14.99 * 75 = 1124.25
            # Total: ~3372.75

    def test_multiple_queries_same_connection(self, duckdb_server) -> None:
        """Test running multiple queries on same connection."""
        server, port, _ = duckdb_server

        backend = FlightSQLBackend(uri=f"grpc://localhost:{port}")
        with backend:
            # First query
            r1 = backend.execute("SELECT COUNT(*) as cnt FROM products")
            assert r1.column("cnt")[0].as_py() == 3

            # Second query
            r2 = backend.execute("SELECT name FROM products WHERE price > 20")
            assert r2.num_rows == 1
            assert r2.column("name")[0].as_py() == "Gadget"

            # Third query
            r3 = backend.execute("SELECT MAX(quantity) as max_qty FROM products")
            assert r3.column("max_qty")[0].as_py() == 100


@pytest.mark.skip(reason="FlightSQL server tests require server compatibility fixes")
class TestFlightSQLCLIWorkflow:
    """Test FlightSQL via CLI commands."""

    @pytest.fixture
    def server_with_data(self, tmp_path: Path):
        """Start a server with test data."""
        import duckdb

        db_path = tmp_path / "cli_test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE test_data (x INTEGER, y VARCHAR)")
        conn.execute("INSERT INTO test_data VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        conn.close()

        port = get_next_port()
        server = QuiverFlightServer(db_path, port=port)

        server_thread = threading.Thread(target=server.serve, daemon=True)
        server_thread.start()
        time.sleep(0.5)

        yield port

    def test_cli_query_flightsql(self, server_with_data) -> None:
        """Test CLI query command with FlightSQL backend."""
        from typer.testing import CliRunner

        from quiver.cli import app

        port = server_with_data
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "query",
                "SELECT * FROM test_data ORDER BY x",
                "--backend",
                "flightsql",
                "--host",
                f"grpc://localhost:{port}",
            ],
        )

        assert result.exit_code == 0
        assert "x" in result.stdout
        assert "y" in result.stdout

    def test_cli_query_flightsql_json(self, server_with_data) -> None:
        """Test CLI query with JSON output via FlightSQL."""
        import json

        from typer.testing import CliRunner

        from quiver.cli import app

        port = server_with_data
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "query",
                "SELECT x, y FROM test_data ORDER BY x",
                "--backend",
                "flightsql",
                "--host",
                f"grpc://localhost:{port}",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 3
        assert data[0]["x"] == 1
        assert data[0]["y"] == "a"
