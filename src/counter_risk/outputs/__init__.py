"""Pluggable output generator interfaces and implementations."""

from .base import OutputContext, OutputGenerator
from .historical_workbook import (
    HistoricalWalWorkbookOutputGenerator,
    HistoricalWorkbookOutputGenerator,
)
from .pdf_export import PDFExportGenerator
from .ppt_link_refresh import (
    PptLinkRefreshOutputGenerator,
    PptLinkRefreshResult,
    PptLinkRefreshStatus,
)
from .ppt_screenshot import PptScreenshotOutputGenerator
from .registry import OutputGeneratorRegistry, OutputGeneratorRegistryContext

__all__ = [
    "HistoricalWalWorkbookOutputGenerator",
    "HistoricalWorkbookOutputGenerator",
    "OutputContext",
    "OutputGenerator",
    "OutputGeneratorRegistry",
    "OutputGeneratorRegistryContext",
    "PDFExportGenerator",
    "PptLinkRefreshOutputGenerator",
    "PptLinkRefreshResult",
    "PptLinkRefreshStatus",
    "PptScreenshotOutputGenerator",
]
