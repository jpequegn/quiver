"""Data loaders for sample datasets."""

from quiver.loaders.base import LoadResult
from quiver.loaders.financial import TRADES_SCHEMA, FinancialLoader

__all__ = ["LoadResult", "FinancialLoader", "TRADES_SCHEMA"]
