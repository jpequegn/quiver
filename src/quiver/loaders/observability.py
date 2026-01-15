"""Observability/metrics data loader for synthetic monitoring data."""

from datetime import datetime, timedelta

import numpy as np
import pyarrow as pa

from quiver.backends.base import Backend
from quiver.loaders.base import LoadResult


# Schema for the metrics table
METRICS_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us")),
        pa.field("host", pa.string()),
        pa.field("service", pa.string()),
        pa.field("metric_name", pa.string()),
        pa.field("value", pa.float64()),
        pa.field("tags", pa.string()),  # JSON string
    ]
)

# Metric type definitions with their characteristics
METRIC_TYPES = {
    "cpu_usage": {
        "min": 0.0,
        "max": 100.0,
        "base": 30.0,
        "volatility": 5.0,
        "description": "CPU usage percentage",
    },
    "memory_usage": {
        "min": 0.0,
        "max": 100.0,
        "base": 50.0,
        "volatility": 2.0,
        "description": "Memory usage percentage",
    },
    "request_latency_ms": {
        "min": 1.0,
        "max": 1000.0,
        "base": 50.0,
        "volatility": 20.0,
        "description": "Request latency in milliseconds",
    },
    "error_rate": {
        "min": 0.0,
        "max": 1.0,
        "base": 0.01,
        "volatility": 0.005,
        "description": "Error rate (0-1)",
    },
}


class ObservabilityLoader:
    """Loader for observability/metrics data.

    Generates synthetic metrics data that mimics real monitoring systems:
    - CPU usage: smooth random walk bounded 0-100
    - Memory usage: gradual changes bounded 0-100
    - Request latency: log-normal distribution
    - Error rate: mostly low with occasional spikes
    """

    def load_synthetic(
        self,
        backend: Backend,
        metrics: int,
        hosts: int = 10,
        services: int = 5,
    ) -> LoadResult:
        """Generate and load synthetic observability metrics.

        Args:
            backend: Backend to load data into.
            metrics: Total number of metric rows to generate.
            hosts: Number of unique hosts to simulate.
            services: Number of unique services to simulate.

        Returns:
            LoadResult with details of the loaded data.
        """
        table = self._generate_synthetic(metrics, hosts, services)

        self._create_and_load(backend, table)

        return LoadResult(
            table_name="metrics",
            rows_loaded=table.num_rows,
            schema=table.schema,
            source=f"synthetic:hosts={hosts},services={services}",
        )

    def _generate_synthetic(self, metrics: int, hosts: int, services: int) -> pa.Table:
        """Generate synthetic observability metrics.

        Args:
            metrics: Total number of metric rows to generate.
            hosts: Number of unique hosts.
            services: Number of unique services.

        Returns:
            PyArrow Table with synthetic metrics data.
        """
        all_data: dict[str, list] = {
            "timestamp": [],
            "host": [],
            "service": [],
            "metric_name": [],
            "value": [],
            "tags": [],
        }

        # Generate host and service names
        host_names = [f"host-{i:03d}" for i in range(hosts)]
        service_names = [f"service-{i:02d}" for i in range(services)]
        metric_names = list(METRIC_TYPES.keys())

        # Calculate how many data points per combination
        combinations = hosts * services * len(metric_names)
        points_per_combo = max(1, metrics // combinations)

        # Time interval between points (1 minute)
        start_time = datetime.now() - timedelta(minutes=points_per_combo)

        np.random.seed(42)  # Reproducible generation

        for host in host_names:
            for service in service_names:
                for metric_name in metric_names:
                    metric_config = METRIC_TYPES[metric_name]

                    # Generate time series for this combination
                    values = self._generate_metric_series(
                        metric_name,
                        metric_config,
                        points_per_combo,
                    )

                    for i, value in enumerate(values):
                        timestamp = start_time + timedelta(minutes=i)
                        tags = f'{{"host":"{host}","service":"{service}"}}'

                        all_data["timestamp"].append(timestamp)
                        all_data["host"].append(host)
                        all_data["service"].append(service)
                        all_data["metric_name"].append(metric_name)
                        all_data["value"].append(round(value, 4))
                        all_data["tags"].append(tags)

        return pa.Table.from_pydict(all_data, schema=METRICS_SCHEMA)

    def _generate_metric_series(
        self,
        metric_name: str,
        config: dict,
        count: int,
    ) -> list[float]:
        """Generate a time series for a specific metric type.

        Args:
            metric_name: Name of the metric.
            config: Configuration for this metric type.
            count: Number of data points to generate.

        Returns:
            List of metric values.
        """
        min_val = config["min"]
        max_val = config["max"]
        base = config["base"]
        volatility = config["volatility"]

        if metric_name == "request_latency_ms":
            # Log-normal distribution for latency
            values = np.random.lognormal(
                mean=np.log(base),
                sigma=0.5,
                size=count,
            )
            values = np.clip(values, min_val, max_val)
        elif metric_name == "error_rate":
            # Mostly low with occasional spikes
            values = np.abs(np.random.normal(base, volatility, count))
            # Add occasional spikes (5% chance)
            spikes = np.random.random(count) < 0.05
            values[spikes] = np.random.uniform(0.1, 0.5, np.sum(spikes))
            values = np.clip(values, min_val, max_val)
        else:
            # Random walk for CPU and memory usage
            values = [base]
            for _ in range(count - 1):
                change = np.random.normal(0, volatility)
                new_value = values[-1] + change
                new_value = np.clip(new_value, min_val, max_val)
                values.append(new_value)
            values = np.array(values)

        return values.tolist()

    def _create_and_load(self, backend: Backend, table: pa.Table) -> None:
        """Create the metrics table and load data into the backend.

        Args:
            backend: Backend to load data into.
            table: PyArrow Table containing the data to load.
        """
        # Drop existing table if it exists
        try:
            backend.execute("DROP TABLE IF EXISTS metrics")
        except Exception:
            pass

        # Create table with schema
        create_sql = """
        CREATE TABLE metrics (
            timestamp TIMESTAMP,
            host VARCHAR,
            service VARCHAR,
            metric_name VARCHAR,
            value DOUBLE,
            tags VARCHAR
        )
        """
        backend.execute(create_sql)

        # Insert data
        if backend.name == "duckdb":
            # DuckDB can directly query Arrow tables
            backend._conn.register("_temp_metrics", table)
            backend.execute("INSERT INTO metrics SELECT * FROM _temp_metrics")
            backend._conn.unregister("_temp_metrics")
        else:
            # For other backends, insert row by row
            for batch in table.to_batches():
                for i in range(batch.num_rows):
                    row = {col: batch.column(col)[i].as_py() for col in table.column_names}
                    ts = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    sql = f"""
                    INSERT INTO metrics VALUES (
                        '{ts}',
                        '{row["host"]}',
                        '{row["service"]}',
                        '{row["metric_name"]}',
                        {row["value"]},
                        '{row["tags"].replace("'", "''")}'
                    )
                    """
                    backend.execute(sql)
