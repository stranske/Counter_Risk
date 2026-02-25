"""Pluggable output generator interfaces and implementations."""

from .base import OutputContext, OutputGenerator
from .historical_workbook import HistoricalWalWorkbookOutputGenerator

__all__ = ["HistoricalWalWorkbookOutputGenerator", "OutputContext", "OutputGenerator"]
