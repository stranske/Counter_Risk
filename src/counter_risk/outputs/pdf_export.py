"""Output generator for distribution PDF export via PowerPoint COM."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from counter_risk.integrations.powerpoint_com import is_powerpoint_com_available
from counter_risk.outputs.base import OutputContext, OutputGenerator

LOGGER = logging.getLogger(__name__)
_PDF_FIXED_FORMAT_TYPE = 2  # ppFixedFormatTypePDF

_ComAvailabilityChecker = Callable[[], bool]
_PptxToPdfExporter = Callable[[Path, Path], None]


def export_pptx_to_pdf_via_com(source_pptx: Path, pdf_path: Path) -> None:
    """Export a PowerPoint deck to PDF using PowerPoint COM automation."""
    from counter_risk.integrations.powerpoint_com import initialize_powerpoint_application

    app: Any | None = None
    presentation: Any | None = None
    try:
        app = initialize_powerpoint_application()
        with suppress(Exception):
            app.Visible = 0
        presentation = app.Presentations.Open(str(source_pptx), False, True, False)
        presentation.ExportAsFixedFormat(str(pdf_path), _PDF_FIXED_FORMAT_TYPE)
    finally:
        if presentation is not None:
            with suppress(Exception):
                presentation.Close()
        if app is not None:
            with suppress(Exception):
                app.Quit()


@dataclass(frozen=True)
class PDFExportGenerator(OutputGenerator):
    """Generate a distribution PDF output when COM export is available."""

    source_pptx: Path
    warnings: list[str]
    name: str = "pdf_export"
    com_availability_checker: _ComAvailabilityChecker = is_powerpoint_com_available
    pptx_to_pdf_exporter: _PptxToPdfExporter = export_pptx_to_pdf_via_com

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        if not context.config.export_pdf:
            LOGGER.warning("distribution_pdf_skipped reason=export_pdf_disabled")
            return ()

        if not self.com_availability_checker():
            warning = (
                "distribution_pdf requested but PowerPoint COM is unavailable; "
                "skipping PDF generation"
            )
            self.warnings.append(warning)
            LOGGER.warning(
                "distribution_pdf_skipped reason=com_unavailable source=%s", self.source_pptx
            )
            return ()

        pdf_path = context.run_dir / f"{self.source_pptx.stem}.pdf"
        try:
            self.pptx_to_pdf_exporter(self.source_pptx, pdf_path)
        except Exception as exc:
            LOGGER.error("PDF export failed: %s", exc)
            raise RuntimeError(f"PDF export failed: {exc}") from exc

        LOGGER.info("distribution_pdf_complete path=%s", pdf_path)
        return (pdf_path,)
