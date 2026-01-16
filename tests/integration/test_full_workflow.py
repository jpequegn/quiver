"""Integration tests for full Quiver workflows.

These tests exercise the complete system: loading data, querying,
and benchmarking across multiple backends.
"""


from quiver.benchmark import BenchmarkRunner
from quiver.loaders import FinancialLoader


class TestFinancialWorkflow:
    """Test complete financial data workflow."""

    def test_load_query_workflow(self, duckdb_with_trades) -> None:
        """Test loading financial data and running queries."""
        backend = duckdb_with_trades

        # Query the loaded data
        result = backend.execute("SELECT COUNT(*) as cnt FROM trades")
        assert result.num_rows == 1
        assert result.column("cnt")[0].as_py() == 1000

    def test_query_aggregations(self, duckdb_with_trades) -> None:
        """Test aggregation queries on financial data."""
        backend = duckdb_with_trades

        # Group by symbol
        result = backend.execute("""
            SELECT symbol, COUNT(*) as trade_count, AVG(close) as avg_close
            FROM trades
            GROUP BY symbol
            ORDER BY trade_count DESC
        """)

        assert result.num_rows > 0
        # Should have symbol, trade_count, avg_close columns
        assert "symbol" in result.column_names
        assert "trade_count" in result.column_names
        assert "avg_close" in result.column_names

    def test_query_time_filtering(self, duckdb_with_trades) -> None:
        """Test time-based filtering on trades."""
        backend = duckdb_with_trades

        result = backend.execute("""
            SELECT * FROM trades
            WHERE timestamp >= '2020-01-01'
            LIMIT 100
        """)

        assert result.num_rows <= 100

    def test_benchmark_after_load(self, duckdb_with_trades) -> None:
        """Test benchmarking queries after loading data."""
        backend = duckdb_with_trades

        runner = BenchmarkRunner(backend)
        result = runner.run(
            "SELECT symbol, AVG(close) FROM trades GROUP BY symbol",
            iterations=5,
            warmup=2,
        )

        assert result.iterations == 5
        assert result.warmup == 2
        assert result.rows_returned > 0
        assert len(result.total_times_ms) == 5

        stats = result.stats()
        assert stats["mean_ms"] > 0
        assert stats["median_ms"] > 0


class TestObservabilityWorkflow:
    """Test complete observability/metrics workflow."""

    def test_load_query_workflow(self, duckdb_with_metrics) -> None:
        """Test loading metrics data and running queries."""
        backend = duckdb_with_metrics

        # Query the loaded data
        result = backend.execute("SELECT COUNT(*) as cnt FROM metrics")
        assert result.num_rows == 1
        # Number of rows depends on metrics * hosts * services combinations
        assert result.column("cnt")[0].as_py() > 0

    def test_metrics_aggregations(self, duckdb_with_metrics) -> None:
        """Test aggregation queries on metrics data."""
        backend = duckdb_with_metrics

        # Group by host - metrics table has: timestamp, host, service, metric_name, value, tags
        result = backend.execute("""
            SELECT host, AVG(value) as avg_value, COUNT(*) as cnt
            FROM metrics
            GROUP BY host
            ORDER BY avg_value DESC
        """)

        assert result.num_rows > 0
        assert "host" in result.column_names
        assert "avg_value" in result.column_names

    def test_service_filtering(self, duckdb_with_metrics) -> None:
        """Test filtering by service."""
        backend = duckdb_with_metrics

        result = backend.execute("""
            SELECT DISTINCT service FROM metrics
        """)

        # Should have multiple services
        assert result.num_rows > 0


class TestMultiBackendConsistency:
    """Test that queries return consistent results across backends."""

    def test_simple_query_consistency(self, all_local_backends) -> None:
        """Test that simple queries return same results across backends."""
        results = {}

        for name, backend in all_local_backends:
            result = backend.execute("SELECT 1 as num, 'hello' as greeting")
            results[name] = {
                "num": result.column("num")[0].as_py(),
                "greeting": result.column("greeting")[0].as_py(),
            }

        # All backends should return the same result
        values = list(results.values())
        for v in values[1:]:
            assert v == values[0], f"Inconsistent results: {results}"

    def test_aggregation_consistency(self, all_local_backends) -> None:
        """Test that aggregations return same results across backends."""
        # Load same data into each backend
        loader = FinancialLoader()

        for name, backend in all_local_backends:
            loader.load_synthetic(backend, rows=100)

        # Query each backend
        results = {}
        for name, backend in all_local_backends:
            result = backend.execute("SELECT COUNT(*) as cnt FROM trades")
            results[name] = result.column("cnt")[0].as_py()

        # All should have 100 rows
        for name, count in results.items():
            assert count == 100, f"{name} has {count} rows, expected 100"


class TestADBCVsNativeComparison:
    """Test ADBC vs native comparison functionality."""

    def test_duckdb_native_comparison(self, duckdb_with_trades) -> None:
        """Test that DuckDB supports native comparison."""
        backend = duckdb_with_trades

        assert backend.supports_native_comparison() is True

        # Run both ADBC and native queries
        adbc_result = backend.execute("SELECT COUNT(*) as cnt FROM trades")
        native_result = backend.execute_native("SELECT COUNT(*) as cnt FROM trades")

        # Results should be identical
        assert adbc_result.column("cnt")[0].as_py() == native_result.column("cnt")[0].as_py()

    def test_duckdb_compare_benchmark(self, duckdb_with_trades) -> None:
        """Test benchmarking both ADBC and native paths."""
        backend = duckdb_with_trades

        runner = BenchmarkRunner(backend)

        adbc_result = runner.run("SELECT COUNT(*) FROM trades", iterations=3, warmup=1)
        native_result = runner.run_native("SELECT COUNT(*) FROM trades", iterations=3, warmup=1)

        # Both should complete successfully
        assert adbc_result.iterations == 3
        assert native_result.iterations == 3
        assert adbc_result.rows_returned == native_result.rows_returned


class TestCLIIntegration:
    """Test CLI commands work end-to-end."""

    def test_cli_simple_query(self) -> None:
        """Test CLI query command with simple SQL."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()

        # Simple query that doesn't require pre-loaded data
        result = runner.invoke(app, ["query", "SELECT 1 as num, 'hello' as msg"])
        assert result.exit_code == 0
        assert "num" in result.stdout
        assert "msg" in result.stdout

    def test_cli_load_synthetic(self) -> None:
        """Test CLI load command with synthetic data."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()

        # Load synthetic data (creates in-memory, verifies it works)
        result = runner.invoke(app, ["load", "financial", "--synthetic", "--rows", "100"])
        assert result.exit_code == 0
        assert "100" in result.stdout

    def test_cli_benchmark(self) -> None:
        """Test CLI benchmark command."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()

        # Run benchmark
        result = runner.invoke(
            app, ["benchmark", "SELECT 1", "--backends", "duckdb", "--iterations", "3"]
        )
        assert result.exit_code == 0
        assert "duckdb" in result.stdout.lower()

    def test_cli_compare(self) -> None:
        """Test CLI compare command."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()

        # Run comparison
        result = runner.invoke(
            app, ["compare", "SELECT 1", "--backend", "duckdb", "--iterations", "3"]
        )
        assert result.exit_code == 0
        assert "adbc" in result.stdout.lower()
        assert "native" in result.stdout.lower()

    def test_cli_doctor(self) -> None:
        """Test CLI doctor command."""
        from typer.testing import CliRunner

        from quiver.cli import app

        runner = CliRunner()

        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "duckdb" in result.stdout.lower()
