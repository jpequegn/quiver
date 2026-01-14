"""Tests for the financial data loader."""

import pytest
import pyarrow as pa

from quiver.backends.duckdb import DuckDBBackend
from quiver.loaders import FinancialLoader, LoadResult, TRADES_SCHEMA


class TestFinancialLoader:
    """Tests for FinancialLoader class."""

    def test_synthetic_generation_row_count(self) -> None:
        """Verify synthetic generator produces expected row count."""
        loader = FinancialLoader()
        table = loader._generate_synthetic(1000, ["SYN"])
        assert table.num_rows == 1000

    def test_synthetic_generation_multiple_symbols(self) -> None:
        """Verify synthetic generation with multiple symbols."""
        loader = FinancialLoader()
        symbols = ["SYN1", "SYN2", "SYN3"]
        table = loader._generate_synthetic(300, symbols)
        # 300 rows / 3 symbols = 100 rows per symbol
        assert table.num_rows == 300

        # Check all symbols are present
        unique_symbols = set(table.column("symbol").to_pylist())
        assert unique_symbols == {"SYN1", "SYN2", "SYN3"}

    def test_synthetic_generation_schema(self) -> None:
        """Verify generated table matches expected schema."""
        loader = FinancialLoader()
        table = loader._generate_synthetic(100, ["SYN"])

        assert table.schema == TRADES_SCHEMA
        assert table.schema.names == [
            "timestamp",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
        ]

    def test_synthetic_gbm_realistic_prices(self) -> None:
        """Verify GBM produces realistic prices (no negative, reasonable range)."""
        loader = FinancialLoader()
        table = loader._generate_synthetic(1000, ["SYN"])

        open_prices = table.column("open").to_pylist()
        high_prices = table.column("high").to_pylist()
        low_prices = table.column("low").to_pylist()
        close_prices = table.column("close").to_pylist()

        # No negative prices
        assert all(p > 0 for p in open_prices)
        assert all(p > 0 for p in high_prices)
        assert all(p > 0 for p in low_prices)
        assert all(p > 0 for p in close_prices)

        # High >= Low for each row
        for h, l in zip(high_prices, low_prices):
            assert h >= l, f"High ({h}) should be >= Low ({l})"

        # Prices in reasonable range (started around $50-200, shouldn't explode)
        all_prices = open_prices + high_prices + low_prices + close_prices
        assert min(all_prices) > 0.01  # Not effectively zero
        assert max(all_prices) < 10000  # Not astronomical

    def test_synthetic_volume_positive(self) -> None:
        """Verify generated volumes are positive integers."""
        loader = FinancialLoader()
        table = loader._generate_synthetic(100, ["SYN"])

        volumes = table.column("volume").to_pylist()
        assert all(v > 0 for v in volumes)
        assert all(isinstance(v, int) for v in volumes)

    def test_load_synthetic_into_duckdb(self) -> None:
        """End-to-end: generate synthetic data and load into DuckDB."""
        loader = FinancialLoader()

        with DuckDBBackend() as backend:
            result = loader.load_synthetic(backend, rows=500)

            assert isinstance(result, LoadResult)
            assert result.table_name == "trades"
            assert result.rows_loaded == 500
            assert result.source == "synthetic"

            # Verify data is queryable
            query_result = backend.execute("SELECT COUNT(*) as cnt FROM trades")
            count = query_result.column("cnt").to_pylist()[0]
            assert count == 500

    def test_load_synthetic_multiple_symbols(self) -> None:
        """Test loading synthetic data with multiple symbols."""
        loader = FinancialLoader()

        with DuckDBBackend() as backend:
            result = loader.load_synthetic(
                backend, rows=300, symbols=["AAPL", "GOOGL", "MSFT"]
            )

            assert result.rows_loaded == 300

            # Verify all symbols present
            query_result = backend.execute(
                "SELECT DISTINCT symbol FROM trades ORDER BY symbol"
            )
            symbols = query_result.column("symbol").to_pylist()
            assert symbols == ["AAPL", "GOOGL", "MSFT"]

    def test_load_result_schema(self) -> None:
        """Verify LoadResult contains correct schema information."""
        loader = FinancialLoader()

        with DuckDBBackend() as backend:
            result = loader.load_synthetic(backend, rows=100)

            assert result.schema == TRADES_SCHEMA
            assert len(result.schema) == 8
            assert result.schema.field("timestamp").type == pa.timestamp("us")
            assert result.schema.field("symbol").type == pa.string()
            assert result.schema.field("volume").type == pa.int64()


class TestYFinanceIntegration:
    """Tests for Yahoo Finance integration (skipped if yfinance not available)."""

    @pytest.fixture
    def has_yfinance(self) -> bool:
        """Check if yfinance is available."""
        try:
            import yfinance  # noqa: F401

            return True
        except ImportError:
            return False

    def test_yfinance_import_error(self) -> None:
        """Verify graceful error when yfinance not installed."""
        loader = FinancialLoader()

        # This test always passes - it's about the error message
        # When yfinance is not installed, ImportError should mention installation
        try:
            import yfinance  # noqa: F401

            pytest.skip("yfinance is installed, skipping import error test")
        except ImportError:
            # yfinance not installed, test the loader's error handling
            with DuckDBBackend() as backend:
                with pytest.raises(ImportError) as exc_info:
                    loader.load_real(backend, ["AAPL"], days=30)

                assert "yfinance" in str(exc_info.value)
                assert "pip install quiver[finance]" in str(exc_info.value)

    @pytest.mark.skipif(
        True,  # Skip by default to avoid network calls in CI
        reason="Requires network access and yfinance",
    )
    def test_load_real_data(self) -> None:
        """Test loading real AAPL data (requires network and yfinance)."""
        loader = FinancialLoader()

        with DuckDBBackend() as backend:
            result = loader.load_real(backend, ["AAPL"], days=30)

            assert result.table_name == "trades"
            assert result.rows_loaded > 0
            assert "yfinance" in result.source
            assert "AAPL" in result.source


class TestLoadResultDataclass:
    """Tests for the LoadResult dataclass."""

    def test_load_result_creation(self) -> None:
        """Test LoadResult can be created with all fields."""
        result = LoadResult(
            table_name="test_table",
            rows_loaded=1000,
            schema=TRADES_SCHEMA,
            source="test",
        )

        assert result.table_name == "test_table"
        assert result.rows_loaded == 1000
        assert result.schema == TRADES_SCHEMA
        assert result.source == "test"
