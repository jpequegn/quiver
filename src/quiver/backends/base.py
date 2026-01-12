"""Base backend protocol and registry for ADBC drivers."""

from typing import Protocol, runtime_checkable

import pyarrow as pa


@runtime_checkable
class Backend(Protocol):
    """Protocol defining the interface all ADBC backends must implement.

    This protocol uses structural subtyping - any class with these methods
    and attributes is considered a Backend, without explicit inheritance.

    Attributes:
        name: Unique identifier for this backend (e.g., "duckdb", "sqlite").

    Methods:
        connect: Establish connection to the database.
        execute: Execute SQL via ADBC and return Arrow Table.
        execute_native: Execute SQL via native connector and return Arrow Table.
        close: Close the database connection.
        supports_native_comparison: Whether this backend supports native vs ADBC comparison.
    """

    name: str

    def connect(self) -> None:
        """Establish connection to the database."""
        ...

    def execute(self, sql: str) -> pa.Table:
        """Execute SQL query via ADBC and return results as Arrow Table.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.
        """
        ...

    def execute_native(self, sql: str) -> pa.Table:
        """Execute SQL query via native connector and return results as Arrow Table.

        This method is used for benchmarking ADBC vs native performance.

        Args:
            sql: SQL query string to execute.

        Returns:
            PyArrow Table containing query results.
        """
        ...

    def close(self) -> None:
        """Close the database connection and release resources."""
        ...

    def supports_native_comparison(self) -> bool:
        """Check if this backend supports native vs ADBC comparison benchmarks.

        Returns:
            True if the backend has both ADBC and native execution paths.
        """
        ...


class BackendRegistry:
    """Registry for managing available backend implementations.

    The registry allows backends to be registered by name and retrieved
    for instantiation. This enables dynamic backend selection via CLI.

    Example:
        >>> registry = BackendRegistry()
        >>> registry.register("duckdb", DuckDBBackend)
        >>> backend_cls = registry.get("duckdb")
        >>> backend = backend_cls()
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._backends: dict[str, type[Backend]] = {}

    def register(self, name: str, backend_cls: type[Backend]) -> None:
        """Register a backend class under the given name.

        Args:
            name: Unique name for the backend.
            backend_cls: Backend class to register.
        """
        self._backends[name] = backend_cls

    def get(self, name: str) -> type[Backend]:
        """Get a backend class by name.

        Args:
            name: Name of the backend to retrieve.

        Returns:
            The backend class.

        Raises:
            KeyError: If no backend is registered with that name.
        """
        if name not in self._backends:
            available = ", ".join(self._backends.keys()) or "none"
            raise KeyError(f"Unknown backend: {name!r}. Available: {available}")
        return self._backends[name]

    def list_backends(self) -> list[str]:
        """List all registered backend names.

        Returns:
            List of registered backend names.
        """
        return list(self._backends.keys())


# Global registry instance (singleton pattern)
_registry: BackendRegistry | None = None


def get_registry() -> BackendRegistry:
    """Get the global backend registry.

    Returns:
        The singleton BackendRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = BackendRegistry()
    return _registry
