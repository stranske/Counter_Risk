"""Parser for Daily Holdings PDF inputs used to source Repo Cash values."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from counter_risk.normalize import canonicalize_name

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
    pdfplumber_text = _extract_text_with_pdfplumber(path)
    if pdfplumber_text:
        return pdfplumber_text

    pypdf_text = _extract_text_with_pypdf(path)
    if pypdf_text:
        return pypdf_text

    ocr_text = _extract_text_with_ocr(path)
    if ocr_text:
        return ocr_text

    # Test fixtures may be sanitized text files with .pdf extension.
    raw = path.read_bytes()
    return raw.decode("utf-8", errors="ignore")


def _extract_text_with_pdfplumber(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except Exception:
        return ""

    lines: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    lines.append(page_text)
                for table in page.extract_tables() or []:
                    for row in table:
                        if not row:
                            continue
                        pieces = [str(cell).strip() for cell in row if cell not in (None, "")]
                        if pieces:
                            lines.append(" ".join(pieces))
    except Exception:
        return ""

    return "\n".join(lines)


def _extract_text_with_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]
    except Exception:
        return ""

    lines: list[str] = []
    try:
        reader = PdfReader(str(path))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text:
                lines.append(page_text)
    except Exception:
        return ""

    return "\n".join(lines)


def _extract_text_with_ocr(path: Path) -> str:
    try:
        import pytesseract  # type: ignore[import-untyped]
        from pdf2image import convert_from_path  # type: ignore[import-untyped]
    except Exception:
        return ""

    lines: list[str] = []
    try:
        for image in convert_from_path(str(path)):
            text = pytesseract.image_to_string(image) or ""
            if text:
                lines.append(text)
    except Exception:
        return ""

    return "\n".join(lines)


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
        if any(alias in lowered for alias in aliases):
            return canonical_name
    return None


def _parse_amount(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    normalized = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "")

    try:
        value = float(normalized)
    except ValueError:
        return None

    return -value if negative else value


__all__ = [
    "DailyHoldingsPdfError",
    "expected_repo_counterparties",
    "parse_daily_holdings_pdf",
]
