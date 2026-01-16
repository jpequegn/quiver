"""Financial data loader for trading/market data."""

from datetime import datetime, timedelta

import numpy as np
import pyarrow as pa

from quiver.backends.base import Backend
from quiver.loaders.base import LoadResult

# Schema for the trades table
TRADES_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("us")),
        pa.field("symbol", pa.string()),
        pa.field("open", pa.float64()),
        pa.field("high", pa.float64()),
        pa.field("low", pa.float64()),
        pa.field("close", pa.float64()),
        pa.field("volume", pa.int64()),
        pa.field("vwap", pa.float64()),
    ]
)


class FinancialLoader:
    """Loader for financial/trading data.

    Supports two data sources:
    - Synthetic: Generates realistic price data using Geometric Brownian Motion
    - Real: Loads historical data from Yahoo Finance (requires yfinance)
    """

    def load_synthetic(
        self,
        backend: Backend,
        rows: int,
        symbols: list[str] | None = None,
    ) -> LoadResult:
        """Generate and load synthetic trading data.

        Uses Geometric Brownian Motion to generate realistic price paths.

        Args:
            backend: Backend to load data into.
            rows: Total number of rows to generate.
            symbols: List of symbols to generate (default: ["SYN"]).

        Returns:
            LoadResult with details of the loaded data.
        """
        symbols = symbols or ["SYN"]
        table = self._generate_synthetic(rows, symbols)

        self._create_and_load(backend, table)

        return LoadResult(
            table_name="trades",
            rows_loaded=table.num_rows,
            schema=table.schema,
            source="synthetic",
        )

    def load_real(
        self,
        backend: Backend,
        symbols: list[str],
        days: int = 365,
    ) -> LoadResult:
        """Load real market data from Yahoo Finance.

        Args:
            backend: Backend to load data into.
            symbols: List of ticker symbols to load.
            days: Number of days of historical data to fetch.

        Returns:
            LoadResult with details of the loaded data.

        Raises:
            ImportError: If yfinance is not installed.
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "yfinance is required for real market data. "
                "Install with: pip install quiver[finance]"
            )

        table = self._load_from_yfinance(yf, symbols, days)

        self._create_and_load(backend, table)

        return LoadResult(
            table_name="trades",
            rows_loaded=table.num_rows,
            schema=table.schema,
            source=f"yfinance:{','.join(symbols)}",
        )

    def _generate_synthetic(self, rows: int, symbols: list[str]) -> pa.Table:
        """Generate synthetic OHLCV data using Geometric Brownian Motion.

        Args:
            rows: Total number of rows to generate.
            symbols: List of symbols to generate data for.

        Returns:
            PyArrow Table with synthetic trading data.
        """
        rows_per_symbol = rows // len(symbols)
        all_data: dict[str, list] = {
            "timestamp": [],
            "symbol": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "vwap": [],
        }

        # GBM parameters
        mu = 0.0001  # daily drift
        sigma = 0.02  # daily volatility
        dt = 1.0  # time step

        for symbol in symbols:
            # Start price around $100
            np.random.seed(hash(symbol) % (2**32))  # Reproducible per symbol
            base_price = np.random.uniform(50, 200)

            # Generate timestamps (5-minute intervals)
            start_time = datetime.now() - timedelta(days=rows_per_symbol // 78)
            timestamps = [
                start_time + timedelta(minutes=5 * i) for i in range(rows_per_symbol)
            ]

            # Generate price path using GBM
            # S(t+1) = S(t) * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)
            prices = [base_price]
            for _ in range(rows_per_symbol - 1):
                z = np.random.standard_normal()
                next_price = prices[-1] * np.exp(
                    (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
                )
                prices.append(next_price)

            # Generate OHLCV from close prices
            for i, close in enumerate(prices):
                # Intraday volatility for O/H/L
                intraday_vol = sigma * 0.3
                open_price = close * (1 + np.random.uniform(-intraday_vol, intraday_vol))
                high_price = max(open_price, close) * (
                    1 + abs(np.random.normal(0, intraday_vol * 0.5))
                )
                low_price = min(open_price, close) * (
                    1 - abs(np.random.normal(0, intraday_vol * 0.5))
                )

                # Volume follows log-normal distribution
                base_volume = 1_000_000
                volume = int(base_volume * np.random.lognormal(0, 0.5))

                # VWAP approximation: (H + L + C) / 3
                vwap = (high_price + low_price + close) / 3

                all_data["timestamp"].append(timestamps[i])
                all_data["symbol"].append(symbol)
                all_data["open"].append(round(open_price, 4))
                all_data["high"].append(round(high_price, 4))
                all_data["low"].append(round(low_price, 4))
                all_data["close"].append(round(close, 4))
                all_data["volume"].append(volume)
                all_data["vwap"].append(round(vwap, 4))

        return pa.Table.from_pydict(all_data, schema=TRADES_SCHEMA)

    def _load_from_yfinance(self, yf, symbols: list[str], days: int) -> pa.Table:
        """Load data from Yahoo Finance and convert to Arrow Table.

        Args:
            yf: The yfinance module.
            symbols: List of ticker symbols.
            days: Number of days of history to fetch.

        Returns:
            PyArrow Table with market data.
        """
        all_data: dict[str, list] = {
            "timestamp": [],
            "symbol": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "vwap": [],
        }

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        for symbol in symbols:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval="1d")

            if df.empty:
                continue

            for idx, row in df.iterrows():
                all_data["timestamp"].append(idx.to_pydatetime())
                all_data["symbol"].append(symbol)
                all_data["open"].append(float(row["Open"]))
                all_data["high"].append(float(row["High"]))
                all_data["low"].append(float(row["Low"]))
                all_data["close"].append(float(row["Close"]))
                all_data["volume"].append(int(row["Volume"]))
                # VWAP approximation
                vwap = (row["High"] + row["Low"] + row["Close"]) / 3
                all_data["vwap"].append(float(vwap))

        return pa.Table.from_pydict(all_data, schema=TRADES_SCHEMA)

    def _create_and_load(self, backend: Backend, table: pa.Table) -> None:
        """Create the trades table and load data into the backend.

        Args:
            backend: Backend to load data into.
            table: PyArrow Table containing the data to load.
        """
        # Drop existing table if it exists (ignore errors)
        try:
            backend.execute("DROP TABLE IF EXISTS trades")
        except Exception:
            pass

        # Create table with schema
        create_sql = """
        CREATE TABLE trades (
            timestamp TIMESTAMP,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            vwap DOUBLE
        )
        """
        backend.execute(create_sql)

        # Insert data
        # DuckDB can directly query Arrow tables
        if backend.name == "duckdb":
            # Register the table temporarily and insert
            backend._conn.register("_temp_trades", table)
            backend.execute("INSERT INTO trades SELECT * FROM _temp_trades")
            backend._conn.unregister("_temp_trades")
        else:
            # For other backends, insert row by row (less efficient but universal)
            for batch in table.to_batches():
                for i in range(batch.num_rows):
                    row = {col: batch.column(col)[i].as_py() for col in table.column_names}
                    # Format timestamp for SQL
                    ts = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    sql = f"""
                    INSERT INTO trades VALUES (
                        '{ts}',
                        '{row["symbol"]}',
                        {row["open"]},
                        {row["high"]},
                        {row["low"]},
                        {row["close"]},
                        {row["volume"]},
                        {row["vwap"]}
                    )
                    """
                    backend.execute(sql)
