# Quiver - Universal ADBC Query Tool

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A Python CLI and library providing unified access to multiple databases via ADBC, with built-in benchmarking to compare drivers and connection methods.

**Architecture:** Backend abstraction layer where each ADBC driver implements a common Protocol. CLI built with Typer, outputs formatted with Rich. Includes a minimal FlightSQL server for learning the protocol from both sides.

**Tech Stack:** Python 3.11+, uv (package manager), Typer (CLI), Rich (output), PyArrow (Arrow + Flight), adbc-driver-manager, DuckDB, SQLite

---

## Learning Priorities

1. **Explore ecosystem** - Multiple ADBC drivers (DuckDB, SQLite, FlightSQL, InfluxDB)
2. **Compare performance** - Benchmark ADBC vs native connectors
3. **Build practical** - Reusable CLI/library for future projects
4. **Understand protocol** - FlightSQL server to see both sides

---

## Project Structure

```
quiver/
├── src/quiver/
│   ├── __init__.py
│   ├── cli.py              # Typer-based CLI entry point
│   ├── config.py           # Configuration loading
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract backend protocol
│   │   ├── duckdb.py       # DuckDB ADBC driver
│   │   ├── sqlite.py       # SQLite ADBC driver
│   │   ├── flightsql.py    # Generic FlightSQL client
│   │   └── influxdb.py     # InfluxDB via FlightSQL
│   ├── benchmark/
│   │   ├── __init__.py
│   │   ├── runner.py       # Benchmark orchestration
│   │   └── reporters.py    # Output formats (table, JSON, CSV)
│   └── loaders/
│       ├── __init__.py
│       ├── financial.py    # Stock/crypto data loaders
│       └── observability.py # Metrics generators
├── src/quiver_server/
│   ├── __init__.py
│   └── flight_server.py    # Minimal FlightSQL server
├── tests/
│   ├── conftest.py
│   ├── test_backends/
│   ├── test_benchmark/
│   └── test_loaders/
├── pyproject.toml
└── README.md
```

---

## CLI Commands

```bash
# Query execution
quiver query "SELECT * FROM trades LIMIT 10" --backend duckdb

# List backends and status
quiver backends

# Benchmark across backends
quiver benchmark "SELECT count(*) FROM trades" --backends duckdb,sqlite --iterations 100

# Compare ADBC vs native
quiver compare "SELECT * FROM trades" --backend duckdb --iterations 50

# Load sample data
quiver load financial --backend duckdb --symbol AAPL --days 365
quiver load observability --backend influxdb --metrics 10000

# FlightSQL learning server
quiver serve --port 8815 --data ./sample.parquet

# Setup and diagnostics
quiver init
quiver doctor
```

---

## Backend Protocol

```python
from typing import Protocol
import pyarrow as pa

class Backend(Protocol):
    name: str

    def connect(self) -> None: ...
    def execute(self, sql: str) -> pa.Table: ...
    def execute_native(self, sql: str) -> pa.Table: ...
    def close(self) -> None: ...
    def supports_native_comparison(self) -> bool: ...
```

---

## Configuration

File: `~/.config/quiver/config.toml`

```toml
[backends.duckdb]
type = "duckdb"
path = "~/.local/share/quiver/default.duckdb"

[backends.sqlite]
type = "sqlite"
path = "~/.local/share/quiver/default.sqlite"

[backends.influxdb]
type = "flightsql"
host = "localhost:8086"
token = "${INFLUXDB_TOKEN}"

[defaults]
backend = "duckdb"
output = "table"
```

---

## Data Schemas

**Financial (trades):**
```sql
CREATE TABLE trades (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    vwap DOUBLE
);
```

**Observability (metrics):**
```sql
CREATE TABLE metrics (
    timestamp TIMESTAMP,
    host VARCHAR,
    service VARCHAR,
    metric_name VARCHAR,
    value DOUBLE,
    tags VARCHAR
);
```
