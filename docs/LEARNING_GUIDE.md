# Arrow ADBC & FlightSQL Learning Guide

A curated learning path for understanding Apache Arrow ADBC and FlightSQL from fundamentals to advanced usage.

---

## Learning Path Overview

```
Phase 1: Arrow Fundamentals (Foundation)
    ↓
Phase 2: ADBC Concepts (Database Connectivity)
    ↓
Phase 3: FlightSQL (Network Protocol)
    ↓
Phase 4: Hands-on Implementation (Quiver Project)
```

---

## Phase 1: Arrow Fundamentals

**Goal:** Understand why Arrow exists and how columnar data works.

### 1.1 What is Columnar Data?

| Resource | Description | Level |
|----------|-------------|-------|
| [The Design of Apache Arrow](https://www.dremio.com/blog/the-design-of-apache-arrow/) | Wes McKinney's explanation of why Arrow was created | Beginner |
| [Columnar vs Row-Based Databases](https://www.youtube.com/watch?v=Vw1fCeD06YI) | Visual explanation of columnar storage benefits | Beginner |
| [Apache Arrow: A Cross-Language Platform](https://arrow.apache.org/overview/) | Official overview of Arrow's goals | Beginner |

**Key Concepts:**
- Row-based storage: good for OLTP, individual record access
- Columnar storage: good for OLAP, analytical queries, aggregations
- Arrow provides a language-independent columnar memory format

### 1.2 Arrow Memory Format

| Resource | Description | Level |
|----------|-------------|-------|
| [Arrow Columnar Format Spec](https://arrow.apache.org/docs/format/Columnar.html) | Official specification | Intermediate |
| [Understanding Arrow Memory Layout](https://arrow.apache.org/docs/python/memory.html) | How data is laid out in memory | Intermediate |
| [Zero-Copy Data Sharing](https://arrow.apache.org/blog/2017/08/08/plasma-object-store/) | Why zero-copy matters | Advanced |

**Key Concepts:**
- Fixed-width types (int32, float64) are contiguous in memory
- Variable-width types (strings) use offsets buffer
- Null bitmap tracks missing values
- Zero-copy = no serialization between systems using Arrow

### 1.3 PyArrow Basics

| Resource | Description | Level |
|----------|-------------|-------|
| [PyArrow Documentation](https://arrow.apache.org/docs/python/index.html) | Official Python bindings docs | Beginner |
| [PyArrow Getting Started](https://arrow.apache.org/docs/python/getstarted.html) | First steps with PyArrow | Beginner |
| [PyArrow Cookbook](https://arrow.apache.org/cookbook/py/) | Practical code examples | Intermediate |
| [PyArrow and Pandas](https://arrow.apache.org/docs/python/pandas.html) | Integration with pandas | Intermediate |

**Hands-on Exercise:**
```python
import pyarrow as pa

# Create a simple table
table = pa.table({
    "name": ["Alice", "Bob", "Charlie"],
    "age": [30, 25, 35],
    "score": [85.5, 92.0, 78.5]
})

# Inspect schema
print(table.schema)

# Convert to pandas
df = table.to_pandas()

# Zero-copy slice
slice = table.slice(0, 2)
```

---

## Phase 2: ADBC (Arrow Database Connectivity)

**Goal:** Understand ADBC's architecture and how it differs from ODBC/JDBC.

### 2.1 Why ADBC?

| Resource | Description | Level |
|----------|-------------|-------|
| [ADBC: Arrow Database Connectivity](https://arrow.apache.org/docs/format/ADBC.html) | Official ADBC specification | Beginner |
| [Introducing ADBC](https://arrow.apache.org/blog/2023/01/05/introducing-adbc/) | Launch blog post explaining motivation | Beginner |
| [ADBC: A New API Standard for Database Access](https://voltrondata.com/resources/adbc-arrow-database-connectivity) | Voltron Data overview | Beginner |

**Why ADBC over ODBC/JDBC?**

| Aspect | ODBC/JDBC | ADBC |
|--------|-----------|------|
| Data Format | Row-based | Columnar (Arrow) |
| Serialization | Always required | Often zero-copy |
| Bulk Operations | Row-at-a-time | Batch-native |
| Type System | Limited | Rich Arrow types |
| Performance | Serialization overhead | Up to 38x faster |

### 2.2 ADBC Architecture

| Resource | Description | Level |
|----------|-------------|-------|
| [ADBC Driver Manager](https://arrow.apache.org/adbc/current/driver/driver_manager.html) | How drivers are loaded and managed | Intermediate |
| [ADBC Python Documentation](https://arrow.apache.org/adbc/current/python/index.html) | Python-specific ADBC docs | Intermediate |
| [Writing an ADBC Driver](https://arrow.apache.org/adbc/current/driver/how_to.html) | Deep dive into driver internals | Advanced |

**Core ADBC Concepts:**
```
┌─────────────────────────────────────────────────────┐
│                   Your Application                   │
├─────────────────────────────────────────────────────┤
│                   ADBC API Layer                     │
│   (Database-agnostic interface)                      │
├────────────┬────────────┬────────────┬──────────────┤
│   DuckDB   │   SQLite   │ FlightSQL  │   InfluxDB   │
│   Driver   │   Driver   │   Driver   │    Driver    │
├────────────┴────────────┴────────────┴──────────────┤
│                   Arrow Memory                       │
│   (Zero-copy data sharing)                          │
└─────────────────────────────────────────────────────┘
```

### 2.3 ADBC Python Drivers

| Resource | Description | Level |
|----------|-------------|-------|
| [adbc-driver-manager PyPI](https://pypi.org/project/adbc-driver-manager/) | Core driver manager | Beginner |
| [adbc-driver-sqlite](https://arrow.apache.org/adbc/current/driver/sqlite.html) | SQLite ADBC driver | Beginner |
| [adbc-driver-postgresql](https://arrow.apache.org/adbc/current/driver/postgresql.html) | PostgreSQL ADBC driver | Intermediate |
| [adbc-driver-flightsql](https://arrow.apache.org/adbc/current/driver/flightsql.html) | FlightSQL ADBC driver | Intermediate |

**Hands-on Exercise:**
```python
import adbc_driver_duckdb.dbapi as duckdb_adbc

# Connect via ADBC
conn = duckdb_adbc.connect()
cursor = conn.cursor()

# Execute query - returns Arrow directly
cursor.execute("SELECT 1 as num, 'hello' as greeting")
table = cursor.fetch_arrow_table()

print(table.to_pandas())
conn.close()
```

---

## Phase 3: Arrow Flight & FlightSQL

**Goal:** Understand how Arrow data moves over the network efficiently.

### 3.1 Arrow Flight Basics

| Resource | Description | Level |
|----------|-------------|-------|
| [Arrow Flight Overview](https://arrow.apache.org/docs/format/Flight.html) | Official Flight specification | Beginner |
| [Arrow Flight RPC](https://arrow.apache.org/docs/python/flight.html) | Python Flight documentation | Intermediate |
| [Introducing Apache Arrow Flight](https://arrow.apache.org/blog/2019/10/13/introducing-arrow-flight/) | Original announcement blog | Beginner |
| [Building High-Performance Data Services](https://www.dremio.com/blog/building-high-performance-data-services/) | Real-world Flight usage | Intermediate |

**What is Arrow Flight?**
- RPC framework built on gRPC
- Designed specifically for Arrow data
- Parallel, streaming data transfer
- Built-in support for metadata, authentication

**Key Performance Numbers:**
- 6000+ MB/s throughput possible
- 20-30x faster than ODBC for large result sets
- Near-zero serialization overhead

### 3.2 FlightSQL Protocol

| Resource | Description | Level |
|----------|-------------|-------|
| [FlightSQL Specification](https://arrow.apache.org/docs/format/FlightSql.html) | Official FlightSQL protocol spec | Intermediate |
| [FlightSQL: An Open Source SQL over Arrow Flight](https://voltrondata.com/resources/flightsql-specification) | Voltron Data explanation | Beginner |
| [FlightSQL ADBC Driver](https://arrow.apache.org/adbc/current/driver/flightsql.html) | Using FlightSQL via ADBC | Intermediate |

**FlightSQL vs Flight:**
```
Arrow Flight = Generic RPC for Arrow data
     +
SQL Commands = FlightSQL
```

FlightSQL adds:
- Standard SQL commands (query, prepared statements)
- Catalog/schema discovery
- Transaction support

### 3.3 FlightSQL Server Implementation

| Resource | Description | Level |
|----------|-------------|-------|
| [PyArrow Flight Server](https://arrow.apache.org/docs/python/flight.html#writing-a-flight-server) | Building Flight servers in Python | Intermediate |
| [FlightSQL Server Example](https://github.com/apache/arrow/tree/main/python/examples/flight) | Official example code | Intermediate |
| [DuckDB Flight Extension](https://duckdb.org/docs/extensions/arrow.html) | DuckDB's Flight implementation | Advanced |

**Hands-on Exercise:**
```python
import pyarrow.flight as flight

# Connect to a FlightSQL server
client = flight.connect("grpc://localhost:8815")

# Get available tables
info = client.get_flight_info(
    flight.FlightDescriptor.for_command(b"SELECT * FROM trades")
)

# Stream the data
reader = client.do_get(info.endpoints[0].ticket)
table = reader.read_all()
```

---

## Phase 4: Database-Specific Resources

### 4.1 DuckDB + ADBC

| Resource | Description | Level |
|----------|-------------|-------|
| [DuckDB Python API](https://duckdb.org/docs/api/python/overview) | Native DuckDB Python docs | Beginner |
| [DuckDB ADBC](https://duckdb.org/docs/api/adbc.html) | DuckDB's ADBC support | Intermediate |
| [DuckDB Arrow Integration](https://duckdb.org/docs/guides/python/export_arrow.html) | Zero-copy Arrow export | Intermediate |

**Why DuckDB for learning ADBC?**
- Embedded (no server setup)
- Native Arrow support (zero-copy)
- Both ADBC and native interfaces for comparison

### 4.2 InfluxDB + FlightSQL

| Resource | Description | Level |
|----------|-------------|-------|
| [InfluxDB FlightSQL Documentation](https://docs.influxdata.com/influxdb/cloud-serverless/query-data/execute-queries/flight-sql/) | Official FlightSQL docs | Intermediate |
| [InfluxDB Python Client](https://docs.influxdata.com/influxdb/cloud-serverless/reference/client-libraries/flight/python-flight/) | Python Flight client for InfluxDB | Intermediate |
| [InfluxDB Arrow Support](https://docs.influxdata.com/influxdb/cloud-serverless/reference/internals/arrow/) | How InfluxDB uses Arrow | Advanced |

### 4.3 Other FlightSQL Databases

| Database | Resource | Notes |
|----------|----------|-------|
| Dremio | [Dremio Arrow Flight](https://docs.dremio.com/current/sonar/client-applications/arrow-flight/) | Enterprise data lakehouse |
| SQLite | [adbc-driver-sqlite](https://arrow.apache.org/adbc/current/driver/sqlite.html) | Embedded SQL database |
| PostgreSQL | [adbc-driver-postgresql](https://arrow.apache.org/adbc/current/driver/postgresql.html) | Traditional RDBMS with ADBC |
| Snowflake | [Snowflake Arrow](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-pandas) | Cloud data warehouse |

---

## Recommended Learning Order

### Week 1: Foundations
1. Read "The Design of Apache Arrow" blog post
2. Complete PyArrow Getting Started tutorial
3. Experiment with PyArrow tables in a notebook
4. Read "Introducing ADBC" blog post

### Week 2: ADBC Basics
1. Read ADBC specification overview
2. Install and test `adbc-driver-duckdb`
3. Compare ADBC vs native DuckDB Python API
4. Read about ADBC driver architecture

### Week 3: FlightSQL
1. Read Arrow Flight overview
2. Read FlightSQL specification
3. Set up a simple FlightSQL server
4. Connect to it using ADBC FlightSQL driver

### Week 4: Integration (Quiver Project)
1. Start implementing Quiver issues
2. Benchmark ADBC vs native connectors
3. Build FlightSQL learning server
4. Test with InfluxDB (Docker)

---

## Video Resources

| Title | Link | Duration | Level |
|-------|------|----------|-------|
| Apache Arrow: A Modern Columnar Data Format | [YouTube](https://www.youtube.com/watch?v=J7YBPGReIzc) | 30 min | Beginner |
| ADBC: Arrow Database Connectivity | [YouTube](https://www.youtube.com/watch?v=rYLYg6BKZCY) | 25 min | Intermediate |
| Arrow Flight Deep Dive | [YouTube](https://www.youtube.com/watch?v=tBq3E1_4W9c) | 40 min | Intermediate |
| CMU Database Systems - Arrow | [YouTube](https://www.youtube.com/watch?v=8wFmLi2LFRI) | 80 min | Advanced |

---

## Community & Support

| Resource | Description |
|----------|-------------|
| [Arrow Mailing Lists](https://arrow.apache.org/community/) | Official Apache Arrow community |
| [Arrow GitHub Discussions](https://github.com/apache/arrow/discussions) | Q&A and discussions |
| [DuckDB Discord](https://discord.gg/tcvwpjfnZx) | Active DuckDB community |
| [Stack Overflow - apache-arrow](https://stackoverflow.com/questions/tagged/apache-arrow) | Q&A |

---

## Quick Reference

### ADBC Python Packages

```bash
# Core
uv add adbc-driver-manager

# Drivers
uv add adbc-driver-sqlite
uv add adbc-driver-postgresql
uv add adbc-driver-flightsql
uv add duckdb  # Has built-in ADBC support

# Arrow
uv add pyarrow
```

### Common ADBC Patterns

```python
# Pattern 1: Simple query
import adbc_driver_sqlite.dbapi as sqlite_adbc

with sqlite_adbc.connect("file.db") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM table")
        table = cur.fetch_arrow_table()

# Pattern 2: Bulk ingestion
conn.adbc_ingest("table_name", arrow_table, mode="create")

# Pattern 3: Prepared statements
cur.adbc_prepare("SELECT * FROM t WHERE id = ?")
cur.execute(None, parameters=[42])
```

### FlightSQL Connection String

```python
import adbc_driver_flightsql.dbapi as flightsql

# Basic connection
conn = flightsql.connect("grpc://localhost:8815")

# With authentication
conn = flightsql.connect(
    "grpc://localhost:8815",
    db_kwargs={
        "username": "user",
        "password": "pass",
    }
)
```

---

## Next Steps

After reviewing these resources, you'll be well-prepared to implement the Quiver project with a deep understanding of:

1. **Why** Arrow and ADBC exist (the problem they solve)
2. **How** ADBC abstracts over different databases
3. **What** FlightSQL adds on top of Arrow Flight
4. **When** to use ADBC vs native connectors

Start with Issue #1 in the quiver repo when ready!
