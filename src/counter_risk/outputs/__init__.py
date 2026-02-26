"""Pluggable output generator interfaces and implementations."""

from .base import OutputContext, OutputGenerator
from .historical_workbook import (
    HistoricalWalWorkbookOutputGenerator,
    HistoricalWorkbookOutputGenerator,
)
from .ppt_link_refresh import (
    PptLinkRefreshOutputGenerator,
    PptLinkRefreshResult,
    PptLinkRefreshStatus,
)
from .ppt_screenshot import PptScreenshotOutputGenerator

__all__ = [
    "HistoricalWalWorkbookOutputGenerator",
    "HistoricalWorkbookOutputGenerator",
    "OutputContext",
    "OutputGenerator",
    "PptLinkRefreshOutputGenerator",
    "PptLinkRefreshResult",
    "PptLinkRefreshStatus",
    "PptScreenshotOutputGenerator",
]
