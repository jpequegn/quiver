"""FlightSQL learning server.

This package provides a minimal FlightSQL server for understanding the
protocol from the server side. It uses DuckDB as the query engine.
"""

from quiver_server.flight_server import QuiverFlightServer

__all__ = ["QuiverFlightServer"]
