"""Base classes and types for data loaders."""

from dataclasses import dataclass

import pyarrow as pa


@dataclass
class LoadResult:
    """Result of loading data into a backend.

    Attributes:
        table_name: Name of the table that was created/populated.
        rows_loaded: Number of rows inserted.
        schema: PyArrow schema of the loaded data.
        source: Description of the data source (e.g., "synthetic", "yfinance:AAPL").
    """

    table_name: str
    rows_loaded: int
    schema: pa.Schema
    source: str
