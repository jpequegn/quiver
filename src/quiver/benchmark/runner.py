"""Benchmark runner for measuring query performance.

This module provides infrastructure for benchmarking SQL queries across
different ADBC backends, capturing detailed timing metrics.

Learning notes:
- time.perf_counter() provides highest resolution timing
- Warmup runs help stabilize results (JIT, caching effects)
- Statistics help understand performance distribution
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quiver.backends.base import Backend


@dataclass
class BenchmarkResult:
    """Results from a benchmark run with timing metrics and statistics.

    Captures query execution timing broken down into query planning/execution
    time and result fetching time, allowing analysis of where time is spent.

    Attributes:
        backend: Name of the backend used.
        query: SQL query that was benchmarked.
        iterations: Number of timed iterations (excluding warmup).
        warmup: Number of warmup iterations.
        query_times_ms: Time spent in query execution per iteration.
        fetch_times_ms: Time spent fetching results per iteration.
        total_times_ms: Total time per iteration (query + fetch).
        rows_returned: Number of rows returned by the query.

    Example:
        >>> result = runner.run("SELECT * FROM trades", iterations=100)
        >>> print(result.stats())
        {'mean_ms': 2.34, 'p95_ms': 3.12, ...}
    """

    backend: str
    query: str
    iterations: int
    warmup: int
    query_times_ms: list[float] = field(default_factory=list)
    fetch_times_ms: list[float] = field(default_factory=list)
    total_times_ms: list[float] = field(default_factory=list)
    rows_returned: int = 0

    def stats(self) -> dict[str, float]:
        """Calculate statistics for the benchmark results.

        Returns:
            Dictionary with timing statistics:
            - min_ms: Minimum total time
            - max_ms: Maximum total time
            - mean_ms: Mean total time
            - median_ms: Median total time
            - p95_ms: 95th percentile total time
            - stddev_ms: Standard deviation of total time
            - query_mean_ms: Mean query execution time
            - fetch_mean_ms: Mean fetch time
        """
        if not self.total_times_ms:
            return {}

        sorted_times = sorted(self.total_times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        # Ensure we don't go out of bounds
        p95_index = min(p95_index, len(sorted_times) - 1)

        result = {
            "min_ms": min(self.total_times_ms),
            "max_ms": max(self.total_times_ms),
            "mean_ms": statistics.mean(self.total_times_ms),
            "median_ms": statistics.median(self.total_times_ms),
            "p95_ms": sorted_times[p95_index],
        }

        # stddev requires at least 2 data points
        if len(self.total_times_ms) >= 2:
            result["stddev_ms"] = statistics.stdev(self.total_times_ms)
        else:
            result["stddev_ms"] = 0.0

        # Add breakdown stats
        if self.query_times_ms:
            result["query_mean_ms"] = statistics.mean(self.query_times_ms)
        if self.fetch_times_ms:
            result["fetch_mean_ms"] = statistics.mean(self.fetch_times_ms)

        return result


class BenchmarkRunner:
    """Runner for executing benchmarks against ADBC backends.

    The runner handles warmup iterations, timing capture, and result
    aggregation. It measures both query execution and result fetching
    separately to understand where time is spent.

    Attributes:
        backend: The backend instance to benchmark against.

    Example:
        >>> from quiver.backends.duckdb import DuckDBBackend
        >>> with DuckDBBackend() as backend:
        ...     runner = BenchmarkRunner(backend)
        ...     result = runner.run("SELECT * FROM trades", iterations=100, warmup=5)
        ...     print(result.stats())
    """

    def __init__(self, backend: Backend) -> None:
        """Initialize the benchmark runner.

        Args:
            backend: Connected backend instance to benchmark against.
        """
        self._backend = backend

    def run(
        self,
        query: str,
        iterations: int = 10,
        warmup: int = 3,
    ) -> BenchmarkResult:
        """Run a benchmark for the given query.

        Executes warmup iterations first (not timed), then runs the
        specified number of timed iterations, capturing timing metrics.

        Args:
            query: SQL query to benchmark.
            iterations: Number of timed iterations to run.
            warmup: Number of warmup iterations (not included in results).

        Returns:
            BenchmarkResult with timing data and statistics.
        """
        result = BenchmarkResult(
            backend=self._backend.name,
            query=query,
            iterations=iterations,
            warmup=warmup,
        )

        # Warmup runs (not timed)
        for _ in range(warmup):
            self._backend.execute(query)

        # Timed runs
        for _ in range(iterations):
            query_time, fetch_time, total_time, rows = self._run_single(query)
            result.query_times_ms.append(query_time)
            result.fetch_times_ms.append(fetch_time)
            result.total_times_ms.append(total_time)
            result.rows_returned = rows  # Will be same each iteration

        return result

    def run_native(
        self,
        query: str,
        iterations: int = 10,
        warmup: int = 3,
    ) -> BenchmarkResult:
        """Run a benchmark using the native execution path.

        Same as run() but uses execute_native() for backends that
        support native vs ADBC comparison.

        Args:
            query: SQL query to benchmark.
            iterations: Number of timed iterations to run.
            warmup: Number of warmup iterations (not included in results).

        Returns:
            BenchmarkResult with timing data and statistics.
        """
        result = BenchmarkResult(
            backend=f"{self._backend.name}_native",
            query=query,
            iterations=iterations,
            warmup=warmup,
        )

        # Warmup runs (not timed)
        for _ in range(warmup):
            self._backend.execute_native(query)

        # Timed runs
        for _ in range(iterations):
            query_time, fetch_time, total_time, rows = self._run_single_native(query)
            result.query_times_ms.append(query_time)
            result.fetch_times_ms.append(fetch_time)
            result.total_times_ms.append(total_time)
            result.rows_returned = rows

        return result

    def _run_single(self, query: str) -> tuple[float, float, float, int]:
        """Run a single timed iteration via ADBC.

        Returns:
            Tuple of (query_time_ms, fetch_time_ms, total_time_ms, rows).
        """
        start = time.perf_counter()
        table = self._backend.execute(query)
        query_end = time.perf_counter()

        # Force materialization by accessing row count
        rows = table.num_rows
        fetch_end = time.perf_counter()

        query_time = (query_end - start) * 1000
        fetch_time = (fetch_end - query_end) * 1000
        total_time = (fetch_end - start) * 1000

        return query_time, fetch_time, total_time, rows

    def _run_single_native(self, query: str) -> tuple[float, float, float, int]:
        """Run a single timed iteration via native path.

        Returns:
            Tuple of (query_time_ms, fetch_time_ms, total_time_ms, rows).
        """
        start = time.perf_counter()
        table = self._backend.execute_native(query)
        query_end = time.perf_counter()

        # Force materialization by accessing row count
        rows = table.num_rows
        fetch_end = time.perf_counter()

        query_time = (query_end - start) * 1000
        fetch_time = (fetch_end - query_end) * 1000
        total_time = (fetch_end - start) * 1000

        return query_time, fetch_time, total_time, rows
