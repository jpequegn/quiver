"""Tests for benchmark runner and result classes."""

import pytest

from quiver.backends.duckdb import DuckDBBackend
from quiver.benchmark import BenchmarkResult, BenchmarkRunner


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_result_has_required_fields(self) -> None:
        """Result should have all required fields."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=10,
            warmup=3,
        )
        assert result.backend == "duckdb"
        assert result.query == "SELECT 1"
        assert result.iterations == 10
        assert result.warmup == 3
        assert result.query_times_ms == []
        assert result.fetch_times_ms == []
        assert result.total_times_ms == []
        assert result.rows_returned == 0

    def test_stats_returns_empty_dict_for_no_data(self) -> None:
        """Stats should return empty dict when no timing data."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=0,
            warmup=0,
        )
        assert result.stats() == {}

    def test_stats_calculates_min_max(self) -> None:
        """Stats should calculate min and max correctly."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=5,
            warmup=0,
            total_times_ms=[1.0, 2.0, 3.0, 4.0, 5.0],
        )
        stats = result.stats()
        assert stats["min_ms"] == 1.0
        assert stats["max_ms"] == 5.0

    def test_stats_calculates_mean(self) -> None:
        """Stats should calculate mean correctly."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=5,
            warmup=0,
            total_times_ms=[1.0, 2.0, 3.0, 4.0, 5.0],
        )
        stats = result.stats()
        assert stats["mean_ms"] == 3.0

    def test_stats_calculates_median(self) -> None:
        """Stats should calculate median correctly."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=5,
            warmup=0,
            total_times_ms=[1.0, 2.0, 3.0, 4.0, 5.0],
        )
        stats = result.stats()
        assert stats["median_ms"] == 3.0

    def test_stats_calculates_p95(self) -> None:
        """Stats should calculate 95th percentile correctly."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=100,
            warmup=0,
            total_times_ms=list(range(1, 101)),  # 1 to 100
        )
        stats = result.stats()
        # p95 of 1-100: index 95 (0-based) = value 96
        assert stats["p95_ms"] == 96

    def test_stats_calculates_stddev(self) -> None:
        """Stats should calculate standard deviation correctly."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=5,
            warmup=0,
            total_times_ms=[2.0, 2.0, 2.0, 2.0, 2.0],  # All same = 0 stddev
        )
        stats = result.stats()
        assert stats["stddev_ms"] == 0.0

    def test_stats_stddev_with_single_value(self) -> None:
        """Stats should handle single value (no stddev possible)."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=1,
            warmup=0,
            total_times_ms=[5.0],
        )
        stats = result.stats()
        assert stats["stddev_ms"] == 0.0

    def test_stats_includes_query_and_fetch_means(self) -> None:
        """Stats should include query and fetch time means."""
        result = BenchmarkResult(
            backend="duckdb",
            query="SELECT 1",
            iterations=3,
            warmup=0,
            query_times_ms=[1.0, 2.0, 3.0],
            fetch_times_ms=[0.1, 0.2, 0.3],
            total_times_ms=[1.1, 2.2, 3.3],
        )
        stats = result.stats()
        assert stats["query_mean_ms"] == 2.0
        assert stats["fetch_mean_ms"] == pytest.approx(0.2, rel=0.01)


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    def test_runner_requires_backend(self) -> None:
        """Runner should require a backend instance."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            assert runner._backend is backend

    def test_run_returns_benchmark_result(self) -> None:
        """Run should return a BenchmarkResult."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=5, warmup=2)
            assert isinstance(result, BenchmarkResult)

    def test_run_captures_backend_name(self) -> None:
        """Result should capture the backend name."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=3)
            assert result.backend == "duckdb"

    def test_run_captures_query(self) -> None:
        """Result should capture the query."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 42 as answer", iterations=3)
            assert result.query == "SELECT 42 as answer"

    def test_run_captures_iterations_and_warmup(self) -> None:
        """Result should capture iterations and warmup counts."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=10, warmup=5)
            assert result.iterations == 10
            assert result.warmup == 5

    def test_run_collects_correct_number_of_samples(self) -> None:
        """Run should collect timing samples equal to iterations."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=7, warmup=2)
            assert len(result.total_times_ms) == 7
            assert len(result.query_times_ms) == 7
            assert len(result.fetch_times_ms) == 7

    def test_run_captures_row_count(self) -> None:
        """Result should capture number of rows returned."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run(
                "SELECT * FROM (VALUES (1), (2), (3)) AS t(n)",
                iterations=3,
            )
            assert result.rows_returned == 3

    def test_run_timing_values_are_positive(self) -> None:
        """All timing values should be positive."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=5)
            for t in result.total_times_ms:
                assert t > 0
            for t in result.query_times_ms:
                assert t >= 0
            for t in result.fetch_times_ms:
                assert t >= 0

    def test_run_total_equals_query_plus_fetch(self) -> None:
        """Total time should equal query time plus fetch time."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=5)
            for i in range(len(result.total_times_ms)):
                expected = result.query_times_ms[i] + result.fetch_times_ms[i]
                assert result.total_times_ms[i] == pytest.approx(expected, rel=0.001)

    def test_run_native_returns_result(self) -> None:
        """run_native should return a BenchmarkResult."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run_native("SELECT 1", iterations=3)
            assert isinstance(result, BenchmarkResult)

    def test_run_native_marks_backend_as_native(self) -> None:
        """run_native should mark backend name with _native suffix."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run_native("SELECT 1", iterations=3)
            assert result.backend == "duckdb_native"

    def test_warmup_runs_do_not_affect_results(self) -> None:
        """Warmup iterations should not be included in timing data."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=5, warmup=10)
            # Should have exactly 5 samples, not 15
            assert len(result.total_times_ms) == 5

    def test_stats_available_after_run(self) -> None:
        """Stats should be available after running benchmark."""
        with DuckDBBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=10)
            stats = result.stats()
            assert "mean_ms" in stats
            assert "median_ms" in stats
            assert "p95_ms" in stats
            assert "stddev_ms" in stats


class TestBenchmarkRunnerWithSQLite:
    """Tests for BenchmarkRunner with SQLite backend."""

    def test_runner_works_with_sqlite(self) -> None:
        """Runner should work with SQLite backend."""
        from quiver.backends.sqlite import SQLiteBackend

        with SQLiteBackend() as backend:
            runner = BenchmarkRunner(backend)
            result = runner.run("SELECT 1", iterations=5)
            assert result.backend == "sqlite"
            assert len(result.total_times_ms) == 5

    def test_same_query_benchmarks_both_backends(self) -> None:
        """Same query should benchmark on both backends."""
        from quiver.backends.sqlite import SQLiteBackend

        query = "SELECT 42 as answer"

        with DuckDBBackend() as duckdb:
            duckdb_runner = BenchmarkRunner(duckdb)
            duckdb_result = duckdb_runner.run(query, iterations=5)

        with SQLiteBackend() as sqlite:
            sqlite_runner = BenchmarkRunner(sqlite)
            sqlite_result = sqlite_runner.run(query, iterations=5)

        # Both should complete successfully with valid results
        assert duckdb_result.backend == "duckdb"
        assert sqlite_result.backend == "sqlite"
        assert duckdb_result.rows_returned == 1
        assert sqlite_result.rows_returned == 1
