"""Parser for Daily Holdings PDF inputs used to source Repo Cash values."""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from stranske_pdf_extract.providers.text_baseline import TextBaselineProvider

from counter_risk.normalize import canonicalize_name
from counter_risk.parsers._xlsx_reader import coerce_accounting_float

_log = logging.getLogger(__name__)

_EXPECTED_REPO_COUNTERPARTIES: tuple[str, ...] = (
    "ASL",
    "South Street",
    "Buckler",
    "CIBC",
    "Daiwa",
)

_COUNTERPARTY_ALIASES: dict[str, tuple[str, ...]] = {
    "ASL": ("asl", "a.s.l"),
    "South Street": (
        "south street",
        "south st",
        "southstreet",
    ),
    "Buckler": ("buckler", "buckler capital"),
    "CIBC": (
        "cibc",
        "canadian imperial bank of commerce",
    ),
    "Daiwa": ("daiwa", "daiwa securities"),
}

_AMOUNT_PATTERN = re.compile(r"(?P<value>\(?\$?[-+]?\d[\d,]*(?:\.\d+)?\)?)")


class DailyHoldingsPdfError(ValueError):
    """Raised when Daily Holdings parsing fails validation."""


def parse_daily_holdings_pdf(path: Path | str) -> dict[str, float]:
    """Parse Repo Cash amounts by counterparty from a Daily Holdings PDF.

    Returns a mapping of canonicalized counterparty labels to cash amounts.
    """

    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Daily Holdings PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise DailyHoldingsPdfError(
            f"Daily Holdings input must be a .pdf file, got: {pdf_path.name}"
        )

    text = _extract_text(pdf_path)
    if not text.strip():
        raise DailyHoldingsPdfError(
            f"Daily Holdings PDF did not contain extractable text: {pdf_path}"
        )

    repo_cash_by_counterparty = _extract_repo_cash_values(text)
    if not repo_cash_by_counterparty:
        raise DailyHoldingsPdfError(
            "Unable to find Repo Cash counterparty values in Daily Holdings PDF"
        )

    return dict(sorted(repo_cash_by_counterparty.items(), key=lambda item: item[0].casefold()))


def expected_repo_counterparties() -> tuple[str, ...]:
    """Return the expected canonical Daily Holdings Repo Cash counterparties."""

    return _EXPECTED_REPO_COUNTERPARTIES


def _extract_text(path: Path) -> str:
    output = TextBaselineProvider(ocr_extract=_tesseract_ocr_extract).extract_modalities(
        path.name,
        path.read_bytes(),
    )
    return "\n".join(block.text for block in output.text_blocks if block.text.strip())


def _tesseract_ocr_extract(content: bytes) -> Sequence[str]:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        _log.debug("pytesseract/pdf2image not installed, skipping OCR")
        return ()

    lines: list[str] = []
    try:
        for image in convert_from_bytes(content):
            text = pytesseract.image_to_string(image) or ""
            if text:
                lines.append(text)
    except Exception:
        _log.warning("OCR extraction failed", exc_info=True)
        return ()

    return tuple(lines)


def _extract_repo_cash_values(text: str) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)

    for raw_line in text.splitlines():
        line = canonicalize_name(raw_line)
        if not line:
            continue

        parsed = _parse_counterparty_amount_line(line)
        if parsed is None:
            continue

        counterparty, amount = parsed
        totals[counterparty] += amount

    cleaned = {
        counterparty: amount
        for counterparty, amount in totals.items()
        if math.isfinite(amount) and amount != 0.0
    }
    return cleaned


def _parse_counterparty_amount_line(line: str) -> tuple[str, float] | None:
    match = None
    for candidate in _AMOUNT_PATTERN.finditer(line):
        match = candidate
    if match is None:
        return None

    amount_text = match.group("value")
    amount = _parse_amount(amount_text)
    if amount is None:
        return None

    prefix = line[: match.start()].strip(" :-")
    if not prefix:
        return None

    canonical_counterparty = _match_counterparty(prefix)
    if canonical_counterparty is None:
        return None

    return canonical_counterparty, amount


def _match_counterparty(text: str) -> str | None:
    lowered = canonicalize_name(text).casefold()
    for canonical_name, aliases in _COUNTERPARTY_ALIASES.items():
        for alias in aliases:
            alias_norm = canonicalize_name(alias).casefold()
            pattern = rf"\b{re.escape(alias_norm)}\b"
            if re.search(pattern, lowered):
                return canonical_name
    return None


def _parse_amount(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None

    try:
        return coerce_accounting_float(text, strip_percent=False)
    except ValueError:
        return None


__all__ = [
    "DailyHoldingsPdfError",
    "expected_repo_counterparties",
    "parse_daily_holdings_pdf",
]
