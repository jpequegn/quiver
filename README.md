# Quiver

Universal ADBC query tool - explore Arrow database connectivity across multiple backends.

Quiver is a learning-focused CLI tool that demonstrates how to use [Apache Arrow Database Connectivity (ADBC)](https://arrow.apache.org/adbc/) to query different databases through a unified interface. It's designed to help developers understand ADBC concepts while providing practical benchmarking capabilities.

## What is ADBC?

**Arrow Database Connectivity (ADBC)** is a columnar, minimal-overhead alternative to JDBC/ODBC for analytical workloads. Key benefits:

- **Zero-copy data access** - Results come back as Arrow tables, avoiding row-by-row conversion overhead
- **Columnar format** - Native support for analytical queries and vectorized processing
- **Unified API** - Same interface works across DuckDB, SQLite, PostgreSQL, Flight SQL, and more
- **Language agnostic** - C API with bindings for Python, R, Go, Java, and others

## Why Quiver?

1. **Learning tool** - Explore how ADBC works with hands-on examples
2. **Unified interface** - Query DuckDB, SQLite, InfluxDB, and FlightSQL servers with the same commands
3. **Benchmarking** - Compare performance across backends and measure ADBC vs native overhead
4. **Sample data** - Built-in loaders for financial and observability datasets

## Installation

```bash
# Using uv (recommended)
uv pip install quiver

# Or clone and install locally
git clone https://github.com/jpequegn/quiver.git
cd quiver
uv sync

# Install with specific backends
uv sync --extra duckdb --extra sqlite

# Install with all backends
uv sync --all-extras
```

### Backend Dependencies

| Backend | Install Command | Description |
|---------|-----------------|-------------|
| DuckDB | `uv sync --extra duckdb` | Embedded analytical database |
| SQLite | `uv sync --extra sqlite` | Embedded SQL database |
| FlightSQL | `uv sync --extra flightsql` | Remote databases via Arrow Flight |
| InfluxDB | `uv sync --extra influxdb` | Time-series database |
| Finance | `uv sync --extra finance` | Yahoo Finance data loader |

## Quick Start

```bash
# List available backends
quiver backends

# Run a simple query with DuckDB (default)
quiver query "SELECT 1 as num, 'hello' as greeting"

# Query with different output formats
quiver query "SELECT 1, 2, 3" --output json
quiver query "SELECT 1, 2, 3" --output csv
quiver query "SELECT 1, 2, 3" --output table

# Load sample data and query it
quiver load financial --synthetic --rows 10000
quiver query "SELECT symbol, AVG(price) as avg_price FROM trades GROUP BY symbol"

# Benchmark a query
quiver benchmark "SELECT COUNT(*) FROM trades" --iterations 50
```

## Commands

### `quiver backends`

List all available backends and their status.

```bash
quiver backends
```

### `quiver query`

Execute a SQL query against a backend.

```bash
# Basic query (uses DuckDB by default)
quiver query "SELECT 1 as num"

# Specify backend
quiver query "SELECT * FROM trades LIMIT 10" --backend duckdb

# Different output formats
quiver query "SELECT * FROM trades" --output json
quiver query "SELECT * FROM trades" --output csv
quiver query "SELECT * FROM trades" --output arrow

# Query a FlightSQL server
quiver query "SELECT * FROM my_table" --backend flightsql --host grpc://localhost:8815
```

**Options:**
- `-b, --backend` - Backend to use (default: duckdb)
- `-o, --output` - Output format: table, json, csv, arrow (default: table)
- `-H, --host` - Host URI for remote backends
- `-t, --token` - Authentication token for remote backends

### `quiver benchmark`

Benchmark a SQL query across one or more backends.

```bash
# Benchmark with default settings (10 iterations, 3 warmup)
quiver benchmark "SELECT COUNT(*) FROM trades"

# Multiple backends
quiver benchmark "SELECT 1" --backends duckdb,sqlite

# Custom iterations
quiver benchmark "SELECT 1" --iterations 100 --warmup 10

# JSON output for CI/scripts
quiver benchmark "SELECT 1" --output json
```

**Options:**
- `-b, --backends` - Comma-separated list of backends (default: duckdb)
- `-i, --iterations` - Number of timed iterations (default: 10)
- `-w, --warmup` - Warmup iterations before timing (default: 3)
- `-o, --output` - Output format: table, json (default: table)
- `-H, --host` - Host URI for remote backends
- `-t, --token` - Authentication token

### `quiver compare`

Compare ADBC performance against native database connectors.

```bash
# Compare ADBC vs native DuckDB
quiver compare "SELECT * FROM trades" --backend duckdb

# With more iterations for accuracy
quiver compare "SELECT 1" --iterations 100

# JSON output
quiver compare "SELECT 1" --output json
```

This command answers: "What's the overhead of using ADBC vs native connectors?"

For columnar databases like DuckDB, ADBC often has **zero or negative overhead** because both use Arrow natively.

### `quiver load`

Load sample datasets into backends for testing.

#### Financial Data

```bash
# Load synthetic trading data (default)
quiver load financial --synthetic --rows 100000

# Load real data from Yahoo Finance
quiver load financial --symbol AAPL --days 365
quiver load financial --symbols AAPL,GOOGL,MSFT --days 365
```

Creates a `trades` table with columns: `timestamp`, `symbol`, `price`, `volume`, `side`.

#### Observability Data

```bash
# Load synthetic metrics data
quiver load observability --metrics 100000

# Customize hosts and services
quiver load observability --metrics 1000000 --hosts 50 --services 20
```

Creates a `metrics` table with columns: `timestamp`, `host`, `service`, `cpu_usage`, `memory_usage`, `request_latency_ms`, `error_rate`.

### `quiver serve`

Start a FlightSQL server for learning and testing.

```bash
# Serve a Parquet file
quiver serve trades.parquet

# Serve a DuckDB database
quiver serve analytics.duckdb --port 9000

# Verbose mode to see protocol details
quiver serve ./data/ --verbose
```

Then connect with:
```bash
quiver query "SELECT * FROM trades" --backend flightsql --host grpc://localhost:8815
```

## Backends

### DuckDB

Embedded analytical database with native Arrow support. Best for:
- Local analytical queries
- Parquet/CSV file analysis
- Learning ADBC concepts

```bash
quiver query "SELECT * FROM read_parquet('data.parquet')" --backend duckdb
```

### SQLite

Classic embedded SQL database via ADBC driver. Useful for:
- Comparing ADBC overhead vs native
- Simple relational data

```bash
quiver query "SELECT sqlite_version()" --backend sqlite
```

### FlightSQL

Connect to remote databases that support Arrow Flight SQL protocol:

```bash
quiver query "SELECT * FROM my_table" \
  --backend flightsql \
  --host grpc://server:8815 \
  --token my-auth-token
```

### InfluxDB

Time-series database via FlightSQL interface:

```bash
quiver query "SELECT * FROM metrics WHERE time > now() - 1h" \
  --backend influxdb \
  --host grpc://localhost:8086 \
  --token my-influx-token
```

## Understanding Benchmarks

Quiver's benchmark results include:

| Metric | Description |
|--------|-------------|
| **Mean** | Average execution time |
| **Median** | Middle value (less affected by outliers) |
| **P95** | 95th percentile (worst-case typical) |
| **Stddev** | Standard deviation (consistency) |

### Example Output

```
┌─────────┬───────────┬────────────┬──────────┬─────────┬──────┐
│ Backend │ Mean (ms) │ Median (ms)│ P95 (ms) │ Stddev  │ Rows │
├─────────┼───────────┼────────────┼──────────┼─────────┼──────┤
│ duckdb  │     0.42  │      0.41  │    0.48  │   0.03  │    1 │
│ sqlite  │     0.38  │      0.37  │    0.44  │   0.04  │    1 │
└─────────┴───────────┴────────────┴──────────┴─────────┴──────┘
```

### ADBC vs Native Comparison

The `compare` command shows overhead percentage:

- **Positive %** - Native is slower than ADBC (ADBC wins!)
- **Negative %** - Native is faster than ADBC
- **~0%** - No significant difference

For DuckDB, ADBC typically shows zero overhead because DuckDB uses Arrow internally.

## Development

```bash
# Clone the repository
git clone https://github.com/jpequegn/quiver.git
cd quiver

# Install with all dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src

# Linting
uv run ruff check src tests

# Type checking
uv run mypy src

# Format code
uv run ruff format src tests
```

### Project Structure

```
quiver/
├── src/
│   ├── quiver/
│   │   ├── __init__.py
│   │   ├── cli.py           # CLI commands
│   │   ├── backends/        # Backend implementations
│   │   │   ├── base.py      # Backend protocol
│   │   │   ├── duckdb.py
│   │   │   ├── sqlite.py
│   │   │   ├── flightsql.py
│   │   │   └── influxdb.py
│   │   ├── benchmark.py     # Benchmarking logic
│   │   ├── loaders/         # Data loaders
│   │   └── output.py        # Output formatting
│   └── quiver_server/       # FlightSQL server
├── tests/
├── pyproject.toml
└── README.md
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│  quiver query | benchmark | compare | load | serve           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Backend Protocol                           │
│  connect() | execute() | execute_native() | close()          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌──────────┬──────────┼──────────┬─────────────┐
│          │          │          │             │
▼          ▼          ▼          ▼             ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌─────────┐
│DuckDB│ │SQLite│ │FlightSQL│ │InfluxDB│ │  ...    │
└──────┘ └──────┘ └────────┘ └────────┘ └─────────┘
    │        │         │          │
    └────────┴─────────┴──────────┘
                  │
         ┌───────▼───────┐
         │  ADBC Layer   │
         │ (Arrow Tables)│
         └───────────────┘
```

## License

MIT

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## Resources

- [Apache Arrow](https://arrow.apache.org/)
- [ADBC Documentation](https://arrow.apache.org/adbc/)
- [DuckDB](https://duckdb.org/)
- [Arrow Flight SQL](https://arrow.apache.org/docs/format/FlightSql.html)
