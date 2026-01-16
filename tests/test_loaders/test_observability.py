"""Tests for the observability data loader."""

import pyarrow as pa

from quiver.backends.duckdb import DuckDBBackend
from quiver.loaders import METRICS_SCHEMA, LoadResult, ObservabilityLoader
from quiver.loaders.observability import METRIC_TYPES


class TestObservabilityLoader:
    """Tests for ObservabilityLoader class."""

    def test_synthetic_generation_produces_data(self) -> None:
        """Verify synthetic generator produces data."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=5, services=3)
        assert table.num_rows > 0

    def test_synthetic_generation_schema(self) -> None:
        """Verify generated table matches expected schema."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=5, services=3)

        assert table.schema == METRICS_SCHEMA
        assert table.schema.names == [
            "timestamp",
            "host",
            "service",
            "metric_name",
            "value",
            "tags",
        ]

    def test_synthetic_generation_hosts(self) -> None:
        """Verify correct number of unique hosts."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=5, services=2)

        unique_hosts = set(table.column("host").to_pylist())
        assert len(unique_hosts) == 5
        assert all(h.startswith("host-") for h in unique_hosts)

    def test_synthetic_generation_services(self) -> None:
        """Verify correct number of unique services."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=4)

        unique_services = set(table.column("service").to_pylist())
        assert len(unique_services) == 4
        assert all(s.startswith("service-") for s in unique_services)

    def test_synthetic_generation_metric_types(self) -> None:
        """Verify all metric types are generated."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=2)

        unique_metrics = set(table.column("metric_name").to_pylist())
        expected_metrics = set(METRIC_TYPES.keys())
        assert unique_metrics == expected_metrics

    def test_cpu_usage_bounds(self) -> None:
        """Verify CPU usage stays within 0-100 bounds."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=2)

        cpu_values = [
            row["value"]
            for row in table.to_pylist()
            if row["metric_name"] == "cpu_usage"
        ]

        assert all(0 <= v <= 100 for v in cpu_values)

    def test_memory_usage_bounds(self) -> None:
        """Verify memory usage stays within 0-100 bounds."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=2)

        memory_values = [
            row["value"]
            for row in table.to_pylist()
            if row["metric_name"] == "memory_usage"
        ]

        assert all(0 <= v <= 100 for v in memory_values)

    def test_request_latency_bounds(self) -> None:
        """Verify request latency stays within 1-1000 bounds."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=2)

        latency_values = [
            row["value"]
            for row in table.to_pylist()
            if row["metric_name"] == "request_latency_ms"
        ]

        assert all(1 <= v <= 1000 for v in latency_values)

    def test_error_rate_bounds(self) -> None:
        """Verify error rate stays within 0-1 bounds."""
        loader = ObservabilityLoader()
        table = loader._generate_synthetic(1000, hosts=2, services=2)

        error_values = [
            row["value"]
            for row in table.to_pylist()
            if row["metric_name"] == "error_rate"
        ]

        assert all(0 <= v <= 1 for v in error_values)

    def test_tags_are_valid_json(self) -> None:
        """Verify tags column contains valid JSON strings."""
        import json

        loader = ObservabilityLoader()
        table = loader._generate_synthetic(100, hosts=2, services=2)

        tags_values = table.column("tags").to_pylist()
        for tag in tags_values:
            parsed = json.loads(tag)
            assert "host" in parsed
            assert "service" in parsed

    def test_load_synthetic_into_duckdb(self) -> None:
        """End-to-end: generate synthetic data and load into DuckDB."""
        loader = ObservabilityLoader()

        with DuckDBBackend() as backend:
            result = loader.load_synthetic(backend, metrics=500, hosts=3, services=2)

            assert isinstance(result, LoadResult)
            assert result.table_name == "metrics"
            assert result.rows_loaded > 0
            assert "synthetic" in result.source
            assert "hosts=3" in result.source
            assert "services=2" in result.source

            # Verify data is queryable
            query_result = backend.execute("SELECT COUNT(*) as cnt FROM metrics")
            count = query_result.column("cnt").to_pylist()[0]
            assert count == result.rows_loaded

    def test_load_synthetic_query_by_metric(self) -> None:
        """Test querying loaded data by metric type."""
        loader = ObservabilityLoader()

        with DuckDBBackend() as backend:
            loader.load_synthetic(backend, metrics=1000, hosts=2, services=2)

            # Query CPU metrics
            cpu_result = backend.execute(
                "SELECT AVG(value) as avg_cpu FROM metrics WHERE metric_name = 'cpu_usage'"
            )
            avg_cpu = cpu_result.column("avg_cpu").to_pylist()[0]
            assert 0 < avg_cpu < 100

    def test_load_result_schema(self) -> None:
        """Verify LoadResult contains correct schema information."""
        loader = ObservabilityLoader()

        with DuckDBBackend() as backend:
            result = loader.load_synthetic(backend, metrics=100, hosts=2, services=2)

            assert result.schema == METRICS_SCHEMA
            assert len(result.schema) == 6
            assert result.schema.field("timestamp").type == pa.timestamp("us")
            assert result.schema.field("host").type == pa.string()
            assert result.schema.field("value").type == pa.float64()


class TestMetricSeries:
    """Tests for individual metric series generation."""

    def test_generate_cpu_series(self) -> None:
        """Test CPU metric series generation."""
        loader = ObservabilityLoader()
        config = METRIC_TYPES["cpu_usage"]
        series = loader._generate_metric_series("cpu_usage", config, 100)

        assert len(series) == 100
        assert all(0 <= v <= 100 for v in series)

    def test_generate_latency_series(self) -> None:
        """Test latency metric series generation (log-normal)."""
        loader = ObservabilityLoader()
        config = METRIC_TYPES["request_latency_ms"]
        series = loader._generate_metric_series("request_latency_ms", config, 100)

        assert len(series) == 100
        assert all(1 <= v <= 1000 for v in series)

    def test_generate_error_rate_series(self) -> None:
        """Test error rate series with occasional spikes."""
        loader = ObservabilityLoader()
        config = METRIC_TYPES["error_rate"]
        series = loader._generate_metric_series("error_rate", config, 100)

        assert len(series) == 100
        assert all(0 <= v <= 1 for v in series)
