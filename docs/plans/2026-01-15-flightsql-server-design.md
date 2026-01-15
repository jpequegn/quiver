# FlightSQL Learning Server Design

## Overview

Minimal FlightSQL server to understand the protocol from both client and server sides. Uses DuckDB as the query engine, integrated into the main `quiver` CLI as `quiver serve`.

## Architecture

```
┌─────────────────────────────────────────┐
│            quiver serve CLI             │
│  (port, data path, verbose flag)        │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         QuiverFlightServer              │
│  - Extends pa.flight.FlightServerBase   │
│  - Handles GetFlightInfo, DoGet         │
│  - Delegates SQL to DuckDB              │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│            DuckDB Backend               │
│  - Executes SQL queries                 │
│  - Returns PyArrow Tables               │
│  - Can query Parquet/CSV directly       │
└─────────────────────────────────────────┘
```

## Files

- `src/quiver_server/__init__.py` - exports QuiverFlightServer
- `src/quiver_server/flight_server.py` - server implementation
- `src/quiver/cli.py` - add `serve` command
- `tests/test_server/test_flight_server.py` - tests

## FlightSQL Methods

**Implementing:**
- `do_get_flight_info` - receive SQL, return FlightInfo with endpoint
- `do_get` - execute SQL via DuckDB, stream Arrow results
- `list_flights` - list available tables (optional)

**Not implementing:**
- `do_put` - no writes
- `do_action` - no custom actions
- Authentication - learning server only

## CLI Interface

```bash
quiver serve trades.parquet              # Serve Parquet file
quiver serve analytics.duckdb            # Serve DuckDB database
quiver serve ./data/ --port 9000         # Serve directory on custom port
quiver serve trades.parquet --verbose    # Log protocol details
```

**Options:**
- `DATA` (argument): Path to Parquet, DuckDB, or directory
- `--port` / `-p`: Server port (default: 8815)
- `--verbose` / `-V`: Log FlightSQL protocol messages

## Data Path Handling

- `.parquet` file → DuckDB queries via `SELECT * FROM 'path.parquet'`
- `.duckdb` file → DuckDB opens directly
- Directory → DuckDB queries via `SELECT * FROM 'dir/*.parquet'`

## Testing

- Unit tests for server class instantiation and SQL parsing
- Integration tests start server, query via FlightSQLBackend
- Fixture manages server lifecycle in background thread
