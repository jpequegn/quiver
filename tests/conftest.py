"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_data() -> dict[str, list[float | str]]:
    """Provide sample data for testing."""
    return {
        "symbol": ["AAPL", "GOOGL", "MSFT"],
        "price": [150.0, 140.0, 380.0],
        "volume": [1000000, 500000, 750000],
    }
