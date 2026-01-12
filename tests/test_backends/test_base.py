"""Tests for backend base protocol and registry."""

import pyarrow as pa
import pytest

from quiver.backends.base import Backend, BackendRegistry, get_registry


class MockBackend:
    """A mock backend that implements the Backend protocol."""

    name: str = "mock"

    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def execute(self, sql: str) -> pa.Table:
        return pa.table({"result": [1, 2, 3]})

    def execute_native(self, sql: str) -> pa.Table:
        return pa.table({"result": [1, 2, 3]})

    def close(self) -> None:
        self._connected = False

    def supports_native_comparison(self) -> bool:
        return True


class IncompleteBackend:
    """A backend missing required methods."""

    name: str = "incomplete"


class TestBackendProtocol:
    """Tests for the Backend protocol."""

    def test_mock_backend_implements_protocol(self) -> None:
        """MockBackend should satisfy the Backend protocol."""
        backend: Backend = MockBackend()
        assert backend.name == "mock"

    def test_backend_connect_and_close(self) -> None:
        """Backend should support connect and close lifecycle."""
        backend = MockBackend()
        backend.connect()
        assert backend._connected is True
        backend.close()
        assert backend._connected is False

    def test_backend_execute_returns_arrow_table(self) -> None:
        """Execute should return a PyArrow Table."""
        backend = MockBackend()
        backend.connect()
        result = backend.execute("SELECT 1")
        assert isinstance(result, pa.Table)
        backend.close()

    def test_backend_execute_native_returns_arrow_table(self) -> None:
        """Execute native should also return a PyArrow Table."""
        backend = MockBackend()
        backend.connect()
        result = backend.execute_native("SELECT 1")
        assert isinstance(result, pa.Table)
        backend.close()

    def test_backend_supports_native_comparison(self) -> None:
        """Backend should report if it supports native comparison."""
        backend = MockBackend()
        assert backend.supports_native_comparison() is True


class TestBackendRegistry:
    """Tests for the backend registry."""

    def test_register_backend(self) -> None:
        """Should be able to register a backend class."""
        registry = BackendRegistry()
        registry.register("mock", MockBackend)
        assert "mock" in registry.list_backends()

    def test_get_backend(self) -> None:
        """Should be able to retrieve a registered backend class."""
        registry = BackendRegistry()
        registry.register("mock", MockBackend)
        backend_cls = registry.get("mock")
        assert backend_cls is MockBackend

    def test_get_unknown_backend_raises(self) -> None:
        """Getting unknown backend should raise KeyError."""
        registry = BackendRegistry()
        with pytest.raises(KeyError, match="unknown"):
            registry.get("unknown")

    def test_list_backends(self) -> None:
        """Should list all registered backend names."""
        registry = BackendRegistry()
        registry.register("mock1", MockBackend)
        registry.register("mock2", MockBackend)
        backends = registry.list_backends()
        assert "mock1" in backends
        assert "mock2" in backends

    def test_global_registry(self) -> None:
        """Should have a global registry accessible via get_registry."""
        registry = get_registry()
        assert isinstance(registry, BackendRegistry)

    def test_registry_is_singleton(self) -> None:
        """get_registry should return the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2
