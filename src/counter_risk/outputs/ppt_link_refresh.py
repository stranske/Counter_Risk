"""Output generator for Master PPT link refresh via COM automation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from counter_risk.outputs.base import OutputContext, OutputGenerator
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names

LOGGER = logging.getLogger(__name__)


class PptLinkRefreshStatus(StrEnum):
    """Machine-readable statuses for PPT link refresh."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class PptLinkRefreshResult:
    """Result envelope for output-generator-driven link refresh."""

    status: PptLinkRefreshStatus
    error_detail: str | None = None


_PptLinkRefresher = Callable[[Path], object]
_PptLinkRefreshResultResolver = Callable[[object], PptLinkRefreshResult]


@dataclass(frozen=True)
class PptLinkRefreshOutputGenerator(OutputGenerator):
    """Refresh linked content in the generated Master PPT."""

    warnings: list[str]
    ppt_link_refresher: _PptLinkRefresher
    name: str = "ppt_link_refresh"
    refresh_result_resolver: _PptLinkRefreshResultResolver | None = None
    last_result: PptLinkRefreshResult | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.refresh_result_resolver is None:
            object.__setattr__(self, "refresh_result_resolver", resolve_ppt_link_refresh_result)

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        if not context.config.ppt_output_enabled:
            return ()

        master_pptx_path = (
            context.run_dir / resolve_ppt_output_names(context.as_of_date).master_filename
        )

        try:
            raw_result = self.ppt_link_refresher(master_pptx_path)
        except Exception as exc:
            LOGGER.error("Master PPT link refresh failed: %s", exc)
            result = PptLinkRefreshResult(
                status=PptLinkRefreshStatus.FAILED,
                error_detail=str(exc),
            )
        else:
            result = self.refresh_result_resolver(raw_result)

        object.__setattr__(self, "last_result", result)

        if result.status == PptLinkRefreshStatus.SKIPPED:
            self.warnings.append("PPT links not refreshed; COM refresh skipped")
        if result.status == PptLinkRefreshStatus.FAILED:
            self.warnings.append(
                "PPT links refresh failed; COM refresh encountered an error"
                if not result.error_detail
                else f"PPT links refresh failed; {result.error_detail}"
            )

        return ()


def resolve_ppt_link_refresh_result(raw_result: object) -> PptLinkRefreshResult:
    """Normalize legacy refresh return values into generator result envelopes."""

    if isinstance(raw_result, bool):
        return PptLinkRefreshResult(
            status=PptLinkRefreshStatus.SUCCESS if raw_result else PptLinkRefreshStatus.SKIPPED
        )

    status_value = getattr(raw_result, "status", None)
    error_detail = getattr(raw_result, "error_detail", None)

    if status_value is None:
        raise TypeError(
            "PPT link refresh result must be a bool or object with a 'status' attribute"
        )

    status_text = str(getattr(status_value, "value", status_value)).strip().lower()
    try:
        normalized_status = PptLinkRefreshStatus(status_text)
    except ValueError as exc:
        raise ValueError(f"Unsupported PPT link refresh status: {status_text!r}") from exc

    normalized_error = None if error_detail is None else str(error_detail)
    return PptLinkRefreshResult(status=normalized_status, error_detail=normalized_error)
