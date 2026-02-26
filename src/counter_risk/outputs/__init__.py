"""Pluggable output generator interfaces and implementations."""

from .base import OutputContext, OutputGenerator
from .historical_workbook import (
    HistoricalWalWorkbookOutputGenerator,
    HistoricalWorkbookOutputGenerator,
)
from .ppt_screenshot import PptScreenshotOutputGenerator

__all__ = [
    "HistoricalWalWorkbookOutputGenerator",
    "HistoricalWorkbookOutputGenerator",
    "OutputContext",
    "OutputGenerator",
    "PptScreenshotOutputGenerator",
]
