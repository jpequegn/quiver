# Financial Data Loader Design

**Issue:** #10 - Financial data loader
**Date:** 2026-01-14
**Status:** Approved

## Overview

Add `quiver load financial` command to load sample financial data for testing and benchmarking. Supports both real data from Yahoo Finance and synthetic data generation.

## CLI Design

```bash
# Synthetic data (default, no network dependency)
quiver load financial --backend duckdb --synthetic --rows 100000

# Real data from Yahoo Finance
quiver load financial --backend duckdb --symbol AAPL --days 365
quiver load financial --backend duckdb --symbols AAPL,GOOGL,MSFT --days 365
```

**Command signature:**
```python
@load_app.command("financial")
def load_financial(
    backend: str = typer.Option("duckdb", "--backend", "-b"),
    symbol: str | None = typer.Option(None, "--symbol", "-s"),
    symbols: str | None = typer.Option(None, "--symbols"),
    days: int = typer.Option(365, "--days", "-d"),
    synthetic: bool = typer.Option(False, "--synthetic"),
    rows: int = typer.Option(100_000, "--rows", "-r"),
    output: OutputFormat = typer.Option(OutputFormat.TABLE, "--output", "-o"),
) -> None:
```

**Behavior:**
- `--symbol`/`--symbols` and `--synthetic` are mutually exclusive
- If neither specified, defaults to synthetic with 100k rows
- Output shows load summary (rows loaded, table name, source)

## File Structure

```
src/quiver/loaders/
├── __init__.py      # Exports FinancialLoader, LoadResult
├── base.py          # LoadResult dataclass
└── financial.py     # FinancialLoader implementation
```

## Schema

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

## Loader Implementation

### LoadResult (base.py)

```python
@dataclass
class LoadResult:
    table_name: str
    rows_loaded: int
    schema: pa.Schema
    source: str  # "synthetic" | "yfinance:AAPL" | etc.
```

### FinancialLoader (financial.py)

```python
class FinancialLoader:
    def load_synthetic(self, backend: Backend, rows: int) -> LoadResult:
        """Generate synthetic trades using Geometric Brownian Motion."""

    def load_real(self, backend: Backend, symbols: list[str], days: int) -> LoadResult:
        """Load real data from Yahoo Finance (requires yfinance)."""
```

### Synthetic Data Generation

Uses Geometric Brownian Motion for realistic price paths:
- Parameters: mu=0.0001 (drift), sigma=0.02 (volatility)
- Starting price: ~$100
- Generates OHLCV candles with realistic high/low spreads

### yfinance Integration

- Optional dependency via `pip install quiver[finance]`
- Graceful ImportError with installation instructions
- Maps yfinance columns to trades schema
- Computes VWAP from available data

## Dependencies

Add to pyproject.toml:
```toml
[project.optional-dependencies]
finance = ["yfinance>=0.2.0"]
```

## Testing

```
tests/test_loaders/
├── __init__.py
└── test_financial.py
```

**Test cases:**
- Synthetic generation row count and schema validation
- GBM produces realistic prices (no negative, reasonable range)
- End-to-end load into DuckDB
- Graceful yfinance import error
- CLI integration tests
- Real data loading (skipped if yfinance not installed)

## Implementation Steps

1. Create `loaders/base.py` with LoadResult dataclass
2. Create `loaders/financial.py` with FinancialLoader class
3. Update `loaders/__init__.py` with exports
4. Add `load` subcommand group to cli.py
5. Add `load financial` command implementation
6. Add yfinance optional dependency to pyproject.toml
7. Create tests in `tests/test_loaders/test_financial.py`
8. Add CLI tests to `tests/test_cli.py`
