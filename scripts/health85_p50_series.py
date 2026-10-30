#!/usr/bin/env python
"""Track Health 85 trailing-seven-day Gate p50 measurements for issue closure.

Health 85 posts daily comments on the source budget issue in the form::

    CI budget YYYY-MM-DD: p50=X.XX min; target=10 min; ...

Issue #1189 closes only after seven consecutive daily measurements report
``p50`` at or below the target, and the closer must attach that dated series.
This helper parses those comments, evaluates the consecutive under-target streak,
and refuses to report closure readiness early.

Refresh from live comments, then emit the dated closure series only when ready::

    gh api repos/OWNER/REPO/issues/1189/comments --paginate \\
      > docs/evidence/issue-1189/health85-comments-api.json
    python scripts/health85_p50_series.py \\
      docs/evidence/issue-1189/health85-p50-series.json \\
      --ingest-comments docs/evidence/issue-1189/health85-comments-api.json --write
    python scripts/health85_p50_series.py \\
      docs/evidence/issue-1189/health85-p50-series.json --require-ready
    python scripts/health85_p50_series.py \\
      docs/evidence/issue-1189/health85-p50-series.json --print-closure-comment

While ``ready_to_close`` is false, ``status.next_required_dates`` names the
Health 85 calendar days still required before the dated close comment may emit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

BUDGET_COMMENT_RE = re.compile(
    r"CI budget\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2}):\s*"
    r"p50=(?P<p50>[0-9]+(?:\.[0-9]+)?)\s*min"
    r"(?:;\s*target=(?P<target>[0-9]+(?:\.[0-9]+)?)\s*min)?"
    r"(?:;\s*distance=(?P<distance>[0-9]+(?:\.[0-9]+)?))?"
    r"(?:;\s*share=(?P<share>[0-9]+(?:\.[0-9]+)?)%)?"
    r"(?:;\s*drainable_in=(?P<drainable_in>[0-9]+))?"
    r"(?:;\s*longest_job=(?P<longest_job>[^\n]+))?",
    flags=re.IGNORECASE,
)

DEFAULT_TARGET_MINUTES = 10.0
DEFAULT_REQUIRED_CONSECUTIVE_DAYS = 7


@dataclass(frozen=True)
class Measurement:
    date: str
    p50_minutes: float
    target_minutes: float | None = None
    distance: float | None = None
    share: float | None = None
    drainable_in: int | None = None
    longest_job: str | None = None
    comment_url: str | None = None


@dataclass(frozen=True)
class SeriesStatus:
    streak: int
    required_consecutive_days: int
    target_minutes: float
    under_target_dates: tuple[str, ...]
    ready_to_close: bool
    remaining_days: int


def parse_budget_comment(text: str) -> Measurement | None:
    """Parse a Health 85 CI-budget comment body into a measurement, if present."""

    match = BUDGET_COMMENT_RE.search(text or "")
    if match is None:
        return None

    def _float(name: str) -> float | None:
        raw = match.group(name)
        return None if raw is None else float(raw)

    def _int(name: str) -> int | None:
        raw = match.group(name)
        return None if raw is None else int(raw)

    longest = match.group("longest_job")
    if longest is not None:
        longest = longest.strip().rstrip(".")
    return Measurement(
        date=match.group("date"),
        p50_minutes=float(match.group("p50")),
        target_minutes=_float("target"),
        distance=_float("distance"),
        share=_float("share"),
        drainable_in=_int("drainable_in"),
        longest_job=longest,
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def consecutive_under_target(
    measurements: Sequence[Measurement],
    *,
    target_minutes: float = DEFAULT_TARGET_MINUTES,
) -> tuple[int, tuple[str, ...]]:
    """Return trailing consecutive under-target calendar-day streak and those dates.

    The streak walks backward from the newest measurement. A gap in calendar
    days, an invalid (negative or non-finite) p50, or any day above the target
    ends the streak.
    """

    if not measurements:
        return 0, ()

    by_day = {_parse_date(item.date): item for item in measurements}
    newest = max(by_day)
    streak_dates: list[str] = []
    cursor = newest
    while cursor in by_day:
        item = by_day[cursor]
        if not 0 <= item.p50_minutes <= target_minutes:
            break
        streak_dates.append(item.date)
        cursor -= timedelta(days=1)
    streak_dates.reverse()
    return len(streak_dates), tuple(streak_dates)


def evaluate_series(
    measurements: Sequence[Measurement],
    *,
    target_minutes: float = DEFAULT_TARGET_MINUTES,
    required_consecutive_days: int = DEFAULT_REQUIRED_CONSECUTIVE_DAYS,
) -> SeriesStatus:
    streak, under_dates = consecutive_under_target(measurements, target_minutes=target_minutes)
    remaining = max(0, required_consecutive_days - streak)
    return SeriesStatus(
        streak=streak,
        required_consecutive_days=required_consecutive_days,
        target_minutes=target_minutes,
        under_target_dates=under_dates,
        ready_to_close=streak >= required_consecutive_days,
        remaining_days=remaining,
    )


def next_required_dates(
    measurements: Sequence[Measurement],
    *,
    target_minutes: float = DEFAULT_TARGET_MINUTES,
    required_consecutive_days: int = DEFAULT_REQUIRED_CONSECUTIVE_DAYS,
) -> tuple[str, ...]:
    """Return the next calendar dates still needed to finish the under-target streak.

    Empty when ``evaluate_series(...).ready_to_close`` is already true. When the
    series is empty, dates start from today is not guessed — returns an empty
    tuple so callers refresh Health 85 comments first.
    """

    status = evaluate_series(
        measurements,
        target_minutes=target_minutes,
        required_consecutive_days=required_consecutive_days,
    )
    if status.ready_to_close or not measurements:
        return ()
    newest = max(_parse_date(item.date) for item in measurements)
    # If the trailing streak does not include the newest day, recovery starts
    # the day after that newest measurement (Health 85 posts one budget/day).
    if status.under_target_dates:
        start = _parse_date(status.under_target_dates[-1]) + timedelta(days=1)
    else:
        start = newest + timedelta(days=1)
    return tuple(
        (start + timedelta(days=offset)).isoformat() for offset in range(status.remaining_days)
    )


def format_dated_p50_series(
    measurements: Sequence[Measurement],
    *,
    target_minutes: float = DEFAULT_TARGET_MINUTES,
) -> str:
    """Render the dated Gate p50 series markdown table for issue closure."""

    by_date = {item.date: item for item in measurements}
    lines = [
        "| Date | p50 (min) | ≤10? |",
        "| --- | ---: | :---: |",
    ]
    for day in sorted(by_date):
        item = by_date[day]
        under = "yes" if 0 <= item.p50_minutes <= target_minutes else "no"
        lines.append(f"| {item.date} | {item.p50_minutes:.2f} | {under} |")
    return "\n".join(lines)


def format_closure_comment(
    measurements: Sequence[Measurement],
    *,
    issue: int | None = 1189,
    target_minutes: float = DEFAULT_TARGET_MINUTES,
    required_consecutive_days: int = DEFAULT_REQUIRED_CONSECUTIVE_DAYS,
) -> str:
    """Build the issue-close comment body that attaches the dated p50 series.

    Raises ``ValueError`` unless the consecutive under-target streak already
    meets ``required_consecutive_days``. Callers must not close #1189 early.
    """

    status = evaluate_series(
        measurements,
        target_minutes=target_minutes,
        required_consecutive_days=required_consecutive_days,
    )
    if not status.ready_to_close:
        raise ValueError(
            "Health 85 Gate p50 series is not ready to close: "
            f"streak={status.streak}/{status.required_consecutive_days}, "
            f"remaining_days={status.remaining_days}"
        )

    issue_ref = f"#{issue}" if issue is not None else "this issue"
    table = format_dated_p50_series(measurements, target_minutes=target_minutes)
    under = ", ".join(status.under_target_dates)
    return (
        f"Closing {issue_ref}: Health 85 reported trailing-seven-day Gate p50 "
        f"at or below {target_minutes:g} min for "
        f"{status.required_consecutive_days} consecutive daily measurements "
        f"({under}).\n\n"
        f"Dated p50 series:\n\n{table}\n"
    )


def measurement_from_mapping(raw: dict[str, Any]) -> Measurement:
    return Measurement(
        date=str(raw["date"]),
        p50_minutes=float(raw["p50_minutes"]),
        target_minutes=(
            None if raw.get("target_minutes") is None else float(raw["target_minutes"])
        ),
        distance=None if raw.get("distance") is None else float(raw["distance"]),
        share=None if raw.get("share") is None else float(raw["share"]),
        drainable_in=(None if raw.get("drainable_in") is None else int(raw["drainable_in"])),
        longest_job=None if raw.get("longest_job") is None else str(raw["longest_job"]),
        comment_url=None if raw.get("comment_url") is None else str(raw["comment_url"]),
    )


def measurements_from_issue_comments(
    comments: Sequence[dict[str, Any]],
) -> list[Measurement]:
    """Extract Health 85 budget measurements from GitHub issue comment payloads.

    Accepts objects shaped like the GitHub Issues Comments API (``body``,
    ``html_url`` / ``url``). Later comments for the same calendar date win so a
    corrected Health 85 post replaces an earlier value for that day.
    """

    by_date: dict[str, Measurement] = {}
    for comment in comments:
        parsed = parse_budget_comment(str(comment.get("body") or ""))
        if parsed is None:
            continue
        url = comment.get("html_url") or comment.get("url")
        by_date[parsed.date] = Measurement(
            date=parsed.date,
            p50_minutes=parsed.p50_minutes,
            target_minutes=parsed.target_minutes,
            distance=parsed.distance,
            share=parsed.share,
            drainable_in=parsed.drainable_in,
            longest_job=parsed.longest_job,
            comment_url=None if url is None else str(url),
        )
    return sorted(by_date.values(), key=lambda item: item.date)


def merge_measurements(
    existing: Sequence[Measurement],
    incoming: Sequence[Measurement],
) -> list[Measurement]:
    """Merge series by calendar date; ``incoming`` wins on collisions."""

    by_date = {item.date: item for item in existing}
    for item in incoming:
        by_date[item.date] = item
    return sorted(by_date.values(), key=lambda item: item.date)


def load_series(path: Path) -> tuple[list[Measurement], float, int, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    measurements = [measurement_from_mapping(item) for item in payload["measurements"]]
    measurements.sort(key=lambda item: item.date)
    target = float(payload.get("target_minutes", DEFAULT_TARGET_MINUTES))
    required = int(payload.get("required_consecutive_days", DEFAULT_REQUIRED_CONSECUTIVE_DAYS))
    return measurements, target, required, payload


def series_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve non-derived series fields when rewriting measurements/status."""

    skip = {"measurements", "status", "target_minutes", "required_consecutive_days"}
    return {key: value for key, value in payload.items() if key not in skip}


def series_to_jsonable(
    measurements: Sequence[Measurement],
    *,
    target_minutes: float,
    required_consecutive_days: int,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = evaluate_series(
        measurements,
        target_minutes=target_minutes,
        required_consecutive_days=required_consecutive_days,
    )
    needed = next_required_dates(
        measurements,
        target_minutes=target_minutes,
        required_consecutive_days=required_consecutive_days,
    )
    payload: dict[str, Any] = {
        **(meta or {}),
        "target_minutes": target_minutes,
        "required_consecutive_days": required_consecutive_days,
        "measurements": [asdict(item) for item in measurements],
        "status": {
            "streak": status.streak,
            "under_target_dates": list(status.under_target_dates),
            "ready_to_close": status.ready_to_close,
            "remaining_days": status.remaining_days,
            # Calendar dates Health 85 must still post ≤target before #1189 may close.
            "next_required_dates": list(needed),
        },
    }
    return payload


def ingest_comments_into_series(
    series_path: Path,
    comments: Sequence[dict[str, Any]],
    *,
    write: bool = False,
    updated_at: str | None = None,
) -> tuple[dict[str, Any], SeriesStatus]:
    """Merge Health 85 comments into a series file and optionally rewrite it."""

    existing, target, required, payload = load_series(series_path)
    incoming = measurements_from_issue_comments(comments)
    if not incoming:
        raise ValueError("no CI budget comments found in ingest payload")
    merged = merge_measurements(existing, incoming)
    meta = series_meta(payload)
    if updated_at is not None:
        meta["updated_at"] = updated_at
    else:
        # Prefer the newest ingested comment timestamp when available.
        newest_created = None
        for comment in comments:
            created = comment.get("created_at")
            if isinstance(created, str) and (newest_created is None or created > newest_created):
                body = str(comment.get("body") or "")
                if parse_budget_comment(body) is not None:
                    newest_created = created
        if newest_created is not None:
            meta["updated_at"] = newest_created
    refreshed = series_to_jsonable(
        merged,
        target_minutes=target,
        required_consecutive_days=required,
        meta=meta,
    )
    status = evaluate_series(merged, target_minutes=target, required_consecutive_days=required)
    if write:
        series_path.write_text(
            json.dumps(refreshed, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    return refreshed, status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "series_path",
        type=Path,
        help="Path to health85-p50-series.json",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit 1 unless the series already meets the seven-day closure rule",
    )
    parser.add_argument(
        "--ingest-comments",
        type=Path,
        help=(
            "JSON array of GitHub issue comments (gh api .../comments). "
            "Merges parsed CI-budget measurements into the series."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="With --ingest-comments, rewrite series_path after merging",
    )
    parser.add_argument(
        "--print-closure-comment",
        action="store_true",
        help=(
            "Print the dated p50 series close-comment body and exit 0 only when "
            "ready_to_close is true; otherwise exit 1 without emitting a close body"
        ),
    )
    args = parser.parse_args(argv)

    if args.ingest_comments is not None:
        raw = json.loads(args.ingest_comments.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("--ingest-comments expects a JSON array of comment objects")
        refreshed, status = ingest_comments_into_series(
            args.series_path,
            raw,
            write=args.write,
        )
        measurements = [measurement_from_mapping(item) for item in refreshed["measurements"]]
        needed = list(
            next_required_dates(
                measurements,
                target_minutes=status.target_minutes,
                required_consecutive_days=status.required_consecutive_days,
            )
        )
        report = {
            "issue": refreshed.get("issue"),
            "ingested_dates": [item["date"] for item in refreshed["measurements"]],
            "streak": status.streak,
            "required_consecutive_days": status.required_consecutive_days,
            "under_target_dates": list(status.under_target_dates),
            "ready_to_close": status.ready_to_close,
            "remaining_days": status.remaining_days,
            "next_required_dates": needed,
            "target_minutes": status.target_minutes,
            "wrote": bool(args.write),
            # Mirror persisted status so closer automation can trust one shape.
            "status": refreshed.get("status"),
        }
        if args.print_closure_comment:
            if not status.ready_to_close:
                print(json.dumps(report, indent=2, sort_keys=True))
                return 1
            print(
                format_closure_comment(
                    measurements,
                    issue=refreshed.get("issue"),
                    target_minutes=status.target_minutes,
                    required_consecutive_days=status.required_consecutive_days,
                )
            )
            return 0
        print(json.dumps(report, indent=2, sort_keys=True))
        if args.require_ready and not status.ready_to_close:
            return 1
        return 0

    measurements, target, required, payload = load_series(args.series_path)
    status = evaluate_series(
        measurements, target_minutes=target, required_consecutive_days=required
    )
    needed = list(
        next_required_dates(
            measurements,
            target_minutes=target,
            required_consecutive_days=required,
        )
    )
    # Keep CLI report aligned with series_to_jsonable status (incl. next dates).
    aligned_status = series_to_jsonable(
        measurements,
        target_minutes=target,
        required_consecutive_days=required,
        meta=series_meta(payload),
    )["status"]
    report = {
        "issue": payload.get("issue"),
        "streak": status.streak,
        "required_consecutive_days": status.required_consecutive_days,
        "under_target_dates": list(status.under_target_dates),
        "ready_to_close": status.ready_to_close,
        "remaining_days": status.remaining_days,
        "next_required_dates": needed,
        "target_minutes": status.target_minutes,
        "status": aligned_status,
    }
    if args.print_closure_comment:
        if not status.ready_to_close:
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1
        print(
            format_closure_comment(
                measurements,
                issue=payload.get("issue"),
                target_minutes=target,
                required_consecutive_days=required,
            )
        )
        return 0
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_ready and not status.ready_to_close:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
