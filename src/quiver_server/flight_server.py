"""FlightSQL server implementation using PyArrow Flight.

This is a learning server to understand the FlightSQL protocol from the server side.
It uses DuckDB as the query engine, allowing it to serve Parquet files, DuckDB
databases, or query files directly via SQL.

Learning notes:
- FlightSQL extends Arrow Flight with SQL-specific commands
- GetFlightInfo receives SQL and returns metadata about the result
- DoGet streams the actual Arrow record batches
- Commands are serialized as Protocol Buffers in the Flight descriptor
"""

from __future__ import annotations

import uuid
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.flight as flight


class QuiverFlightServer(flight.FlightServerBase):
    """Minimal FlightSQL server backed by DuckDB.

    This server accepts SQL queries via the FlightSQL protocol and executes
    them using DuckDB. It can serve data from Parquet files, DuckDB databases,
    or directories of data files.

    Attributes:
        data_path: Path to data file or directory.
        verbose: Whether to log protocol details.

    Example:
        >>> server = QuiverFlightServer("trades.parquet", port=8815)
        >>> server.serve()  # Blocks until shutdown
    """

    def __init__(
        self,
        data_path: str | Path,
        host: str = "localhost",
        port: int = 8815,
        verbose: bool = False,
    ) -> None:
        """Initialize the FlightSQL server.

        Args:
            data_path: Path to Parquet file, DuckDB database, or directory.
            host: Host to bind to (default: localhost).
            port: Port to listen on (default: 8815).
            verbose: Log FlightSQL protocol details.
        """
        location = flight.Location.for_grpc_tcp(host, port)
        super().__init__(location)

        self.data_path = Path(data_path)
        self.verbose = verbose
        self._host = host
        self._port = port

        # Store query results by ticket handle
        self._results: dict[str, pa.Table] = {}

        # Initialize DuckDB connection
        self._conn = self._create_connection()

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection based on data path type.

        Returns:
            DuckDB connection configured for the data source.
        """
        if self.data_path.suffix == ".duckdb":
            # Open existing DuckDB database
            return duckdb.connect(str(self.data_path), read_only=True)
        else:
            # Use in-memory DuckDB that can query files directly
            return duckdb.connect(":memory:")

    def _log(self, message: str) -> None:
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[FlightSQL] {message}")

    def _execute_query(self, sql: str) -> pa.Table:
        """Execute SQL query via DuckDB and return Arrow table.

        Args:
            sql: SQL query to execute.

        Returns:
            PyArrow Table with query results.
        """
        self._log(f"Executing: {sql}")
        result = self._conn.execute(sql).fetch_arrow_table()
        self._log(f"Result: {result.num_rows} rows, {result.num_columns} columns")
        return result

    def get_flight_info(
        self,
        context: flight.ServerCallContext,
        descriptor: flight.FlightDescriptor,
    ) -> flight.FlightInfo:
        """Handle GetFlightInfo request - receive SQL query.

        This is called when a client wants to execute a SQL query. We parse
        the SQL from the descriptor, execute it, store the result, and return
        metadata about where to fetch the results.

        Args:
            context: Server call context.
            descriptor: Contains the SQL command.

        Returns:
            FlightInfo with endpoint to fetch results.
        """
        # Extract SQL from descriptor command
        # FlightSQL sends commands as serialized protobuf, but for simplicity
        # we'll also accept raw SQL in the descriptor path or command
        sql = self._extract_sql(descriptor)
        self._log(f"GetFlightInfo: {sql}")

        # Execute query and store result
        result = self._execute_query(sql)

        # Generate unique ticket handle
        handle = str(uuid.uuid4())
        self._results[handle] = result

        # Build FlightInfo response
        ticket = flight.Ticket(handle.encode())
        endpoint = flight.FlightEndpoint(ticket, [f"grpc://{self._host}:{self._port}"])

        return flight.FlightInfo(
            schema=result.schema,
            descriptor=descriptor,
            endpoints=[endpoint],
            total_records=result.num_rows,
            total_bytes=result.nbytes,
        )

    def _extract_sql(self, descriptor: flight.FlightDescriptor) -> str:
        """Extract SQL query from FlightDescriptor.

        Handles both raw SQL (for testing) and FlightSQL protobuf commands.

        Args:
            descriptor: Flight descriptor containing SQL.

        Returns:
            SQL query string.

        Raises:
            flight.FlightServerError: If SQL cannot be extracted.
        """
        # Try command bytes first (FlightSQL uses this)
        if descriptor.command:
            try:
                # Try to decode as raw SQL string first
                sql = descriptor.command.decode("utf-8")
                # Check if it looks like SQL
                if sql.strip().upper().startswith(("SELECT", "WITH", "SHOW", "DESCRIBE")):
                    return sql
            except UnicodeDecodeError:
                pass

            # Try to parse as FlightSQL protobuf
            try:
                # pyarrow._flight._messages could be used to parse CommandStatementQuery
                # For now, fall through to error
                pass
            except ImportError:
                pass

        # Try path for simple string commands
        if descriptor.path:
            return "/".join(p.decode() if isinstance(p, bytes) else p for p in descriptor.path)

        raise flight.FlightServerError("Could not extract SQL from descriptor")

    def do_get(
        self,
        context: flight.ServerCallContext,
        ticket: flight.Ticket,
    ) -> flight.RecordBatchStream:
        """Handle DoGet request - stream query results.

        Called after GetFlightInfo to actually stream the Arrow data.

        Args:
            context: Server call context.
            ticket: Ticket from FlightInfo endpoint.

        Returns:
            RecordBatchStream of query results.
        """
        handle = ticket.ticket.decode()
        self._log(f"DoGet: ticket={handle[:8]}...")

        if handle not in self._results:
            raise flight.FlightServerError(f"Unknown ticket: {handle}")

        result = self._results.pop(handle)
        batches = result.to_batches()
        self._log(f"DoGet: streaming {len(batches)} batches ({result.num_rows} rows)")

        return flight.RecordBatchStream(result)

    def list_flights(
        self,
        context: flight.ServerCallContext,
        criteria: bytes,
    ) -> list[flight.FlightInfo]:
        """List available tables/flights.

        Args:
            context: Server call context.
            criteria: Filter criteria (unused).

        Returns:
            List of FlightInfo for available tables.
        """
        self._log("ListFlights")

        # Get tables from DuckDB
        if self.data_path.suffix == ".duckdb":
            tables_result = self._conn.execute("SHOW TABLES").fetchall()
            tables = [row[0] for row in tables_result]
        elif self.data_path.suffix == ".parquet":
            # Single parquet file - expose as 'data' table
            tables = ["data"]
        elif self.data_path.is_dir():
            # List parquet files in directory
            tables = [f.stem for f in self.data_path.glob("*.parquet")]
        else:
            tables = []

        flights = []
        for table in tables:
            descriptor = flight.FlightDescriptor.for_path(table)
            # Get schema by querying the table
            try:
                if self.data_path.suffix == ".parquet":
                    schema = self._conn.execute(
                        f"SELECT * FROM '{self.data_path}' LIMIT 0"
                    ).fetch_arrow_table().schema
                elif self.data_path.is_dir():
                    schema = self._conn.execute(
                        f"SELECT * FROM '{self.data_path}/{table}.parquet' LIMIT 0"
                    ).fetch_arrow_table().schema
                else:
                    schema = self._conn.execute(
                        f"SELECT * FROM {table} LIMIT 0"
                    ).fetch_arrow_table().schema

                flights.append(
                    flight.FlightInfo(
                        schema=schema,
                        descriptor=descriptor,
                        endpoints=[],
                        total_records=-1,
                        total_bytes=-1,
                    )
                )
            except Exception as e:
                self._log(f"Error getting schema for {table}: {e}")

        return flights

    def serve(self) -> None:
        """Start serving and block until shutdown."""
        print(f"FlightSQL server listening on grpc://{self._host}:{self._port}")
        print(f"Serving: {self.data_path}")
        print("Press Ctrl+C to stop")
        super().serve()

    def shutdown(self) -> None:
        """Shutdown the server gracefully."""
        self._log("Shutting down server")
        self._conn.close()
        super().shutdown()
