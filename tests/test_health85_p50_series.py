"""Health 85 trailing Gate p50 series parsing and closure readiness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import health85_p50_series as series

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "docs" / "evidence" / "issue-1189" / "health85-p50-series.json"


def test_parse_budget_comment_extracts_fields() -> None:
    text = (
        "CI budget 2026-10-30: p50=2.08 min; target=10 min; distance=0.000; "
        "share=0.00%; drainable_in=4; longest_job=Python CI / python 3.14."
    )
    parsed = series.parse_budget_comment(text)
    assert parsed is not None
    assert parsed.date == "2026-10-30"
    assert parsed.p50_minutes == pytest.approx(2.08)
    assert parsed.target_minutes == pytest.approx(10.0)
    assert parsed.distance == pytest.approx(0.0)
    assert parsed.share == pytest.approx(0.0)
    assert parsed.drainable_in == 4
    assert parsed.longest_job == "Python CI / python 3.14"


def test_parse_budget_comment_ignores_unrelated_bodies() -> None:
    assert series.parse_budget_comment("PR #1207 merged after exact-head checks") is None


def test_consecutive_under_target_requires_calendar_continuity() -> None:
    measurements = [
        series.Measurement(date="2026-10-25", p50_minutes=19.97),
        series.Measurement(date="2026-10-26", p50_minutes=17.81),
        series.Measurement(date="2026-10-27", p50_minutes=17.29),
        series.Measurement(date="2026-10-28", p50_minutes=2.12),
        series.Measurement(date="2026-10-29", p50_minutes=2.08),
        series.Measurement(date="2026-10-30", p50_minutes=2.08),
    ]
    streak, dates = series.consecutive_under_target(measurements, target_minutes=10.0)
    assert streak == 3
    assert dates == ("2026-10-28", "2026-10-29", "2026-10-30")

    # A calendar gap after an under-target day resets the trailing streak.
    gapped = measurements + [series.Measurement(date="2026-11-01", p50_minutes=2.0)]
    streak, dates = series.consecutive_under_target(gapped, target_minutes=10.0)
    assert streak == 1
    assert dates == ("2026-11-01",)


def test_evaluate_series_refuses_early_closure() -> None:
    measurements = [
        series.Measurement(date="2026-10-28", p50_minutes=2.12),
        series.Measurement(date="2026-10-29", p50_minutes=2.08),
        series.Measurement(date="2026-10-30", p50_minutes=2.08),
    ]
    status = series.evaluate_series(measurements, target_minutes=10.0, required_consecutive_days=7)
    assert status.streak == 3
    assert status.ready_to_close is False
    assert status.remaining_days == 4

    # 28..31 Oct + 1..3 Nov — seven consecutive under-target calendar days.
    seven = [
        series.Measurement(date="2026-10-28", p50_minutes=2.0),
        series.Measurement(date="2026-10-29", p50_minutes=2.0),
        series.Measurement(date="2026-10-30", p50_minutes=2.0),
        series.Measurement(date="2026-10-31", p50_minutes=2.0),
        series.Measurement(date="2026-11-01", p50_minutes=2.0),
        series.Measurement(date="2026-11-02", p50_minutes=2.0),
        series.Measurement(date="2026-11-03", p50_minutes=2.0),
    ]
    ready = series.evaluate_series(seven, target_minutes=10.0, required_consecutive_days=7)
    assert ready.streak == 7
    assert ready.ready_to_close is True
    assert ready.remaining_days == 0


def test_over_target_day_resets_streak() -> None:
    measurements = [
        series.Measurement(date="2026-10-28", p50_minutes=2.0),
        series.Measurement(date="2026-10-29", p50_minutes=11.0),
        series.Measurement(date="2026-10-30", p50_minutes=2.0),
    ]
    status = series.evaluate_series(measurements, target_minutes=10.0)
    assert status.streak == 1
    assert status.under_target_dates == ("2026-10-30",)
    assert status.ready_to_close is False


def test_issue_1189_evidence_series_matches_health85_comments() -> None:
    measurements, target, required, payload = series.load_series(EVIDENCE)
    assert payload["issue"] == 1189
    assert target == pytest.approx(10.0)
    assert required == 7

    status = series.evaluate_series(
        measurements, target_minutes=target, required_consecutive_days=required
    )
    recorded = payload["status"]
    assert recorded["streak"] == status.streak
    assert recorded["under_target_dates"] == list(status.under_target_dates)
    assert recorded["ready_to_close"] is status.ready_to_close
    assert recorded["remaining_days"] == status.remaining_days

    # Through 2026-10-30 Health 85 posted three consecutive under-target days.
    # Do not mark the #1189 closure AC complete until ready_to_close flips true.
    assert status.under_target_dates == (
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    )
    assert status.streak == 3
    assert status.ready_to_close is False
    assert status.remaining_days == 4

    # Every checked-in under-target day must stay at or below the Gate target.
    by_date = {item.date: item for item in measurements}
    for day in status.under_target_dates:
        assert by_date[day].p50_minutes <= target


def test_cli_reports_remaining_days(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [
                    {"date": "2026-10-28", "p50_minutes": 2.12},
                    {"date": "2026-10-29", "p50_minutes": 2.08},
                    {"date": "2026-10-30", "p50_minutes": 2.08},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert series.main([str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["streak"] == 3
    assert payload["ready_to_close"] is False
    assert payload["remaining_days"] == 4
    assert series.main([str(path), "--require-ready"]) == 1


def _budget_comment(date: str, p50: float, *, drainable_in: int, url: str) -> dict:
    return {
        "body": (
            f"CI budget {date}: p50={p50} min; target=10 min; distance=0.000; "
            f"share=0.00%; drainable_in={drainable_in}; "
            "longest_job=Python CI / python 3.14."
        ),
        "html_url": url,
        "created_at": f"{date}T12:00:00Z",
    }


def test_consecutive_under_target_empty_series() -> None:
    streak, dates = series.consecutive_under_target([])
    assert streak == 0
    assert dates == ()


def test_ingest_comments_rejects_empty_budget_payload(tmp_path: Path) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no CI budget comments"):
        series.ingest_comments_into_series(path, [{"body": "not a budget comment"}])


def test_ingest_comments_honors_explicit_updated_at(tmp_path: Path) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [],
            }
        ),
        encoding="utf-8",
    )
    refreshed, status = series.ingest_comments_into_series(
        path,
        [_budget_comment("2026-10-30", 2.08, drainable_in=4, url="https://example.test/30")],
        write=True,
        updated_at="2026-10-30T99:00:00Z",
    )
    assert status.streak == 1
    assert refreshed["updated_at"] == "2026-10-30T99:00:00Z"
    assert json.loads(path.read_text(encoding="utf-8"))["updated_at"] == "2026-10-30T99:00:00Z"


def test_cli_ingest_rejects_non_list_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [{"date": "2026-10-30", "p50_minutes": 2.08}],
            }
        ),
        encoding="utf-8",
    )
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"body": "nope"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON array"):
        series.main([str(path), "--ingest-comments", str(bad)])


def test_cli_ingest_require_ready_exits_nonzero_while_streak_short(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [],
            }
        ),
        encoding="utf-8",
    )
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps(
            [_budget_comment("2026-10-30", 2.08, drainable_in=4, url="https://example.test/30")]
        ),
        encoding="utf-8",
    )
    assert series.main([str(path), "--ingest-comments", str(comments), "--require-ready"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ready_to_close"] is False
    assert report["streak"] == 1


def test_measurements_from_issue_comments_keeps_latest_per_day() -> None:
    comments = [
        _budget_comment(
            "2026-10-30",
            9.5,
            drainable_in=4,
            url="https://example.test/old",
        ),
        {"body": "unrelated keepalive note", "html_url": "https://example.test/noise"},
        _budget_comment(
            "2026-10-30",
            2.08,
            drainable_in=4,
            url="https://example.test/new",
        ),
        _budget_comment(
            "2026-10-29",
            2.08,
            drainable_in=5,
            url="https://example.test/29",
        ),
    ]
    parsed = series.measurements_from_issue_comments(comments)
    assert [item.date for item in parsed] == ["2026-10-29", "2026-10-30"]
    by_date = {item.date: item for item in parsed}
    assert by_date["2026-10-30"].p50_minutes == pytest.approx(2.08)
    assert by_date["2026-10-30"].comment_url == "https://example.test/new"


def test_ingest_comments_refuses_early_close_and_writes_series(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Closer path: sync live Health 85 comments; stay closed until streak hits 7."""

    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "issue": 1189,
                "source": "https://github.com/stranske/Counter_Risk/issues/1189",
                "notes": "preserve me",
                "target_minutes": 10.0,
                "required_consecutive_days": 7,
                "measurements": [],
            }
        ),
        encoding="utf-8",
    )
    comments_path = tmp_path / "comments.json"
    # Mirror official #1189 Health 85 posts through 2026-10-30 (streak 3/7).
    comments_path.write_text(
        json.dumps(
            [
                _budget_comment(
                    "2026-10-25",
                    19.97,
                    drainable_in=7,
                    url="https://example.test/25",
                ),
                _budget_comment(
                    "2026-10-26",
                    17.81,
                    drainable_in=7,
                    url="https://example.test/26",
                ),
                _budget_comment(
                    "2026-10-27",
                    17.29,
                    drainable_in=7,
                    url="https://example.test/27",
                ),
                _budget_comment(
                    "2026-10-28",
                    2.12,
                    drainable_in=6,
                    url="https://example.test/28",
                ),
                _budget_comment(
                    "2026-10-29",
                    2.08,
                    drainable_in=5,
                    url="https://example.test/29",
                ),
                _budget_comment(
                    "2026-10-30",
                    2.08,
                    drainable_in=4,
                    url="https://example.test/30",
                ),
            ]
        ),
        encoding="utf-8",
    )

    assert series.main([str(path), "--ingest-comments", str(comments_path), "--write"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["streak"] == 3
    assert report["ready_to_close"] is False
    assert report["remaining_days"] == 4
    assert report["wrote"] is True

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["issue"] == 1189
    assert written["notes"] == "preserve me"
    assert written["status"]["ready_to_close"] is False
    assert written["status"]["under_target_dates"] == [
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    ]
    assert written["updated_at"] == "2026-10-30T12:00:00Z"

    # Four more under-target days flip closure readiness for the dated series.
    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps(
            [
                _budget_comment("2026-10-31", 2.0, drainable_in=3, url="https://example.test/31"),
                _budget_comment("2026-11-01", 2.0, drainable_in=2, url="https://example.test/01"),
                _budget_comment("2026-11-02", 2.0, drainable_in=1, url="https://example.test/02"),
                _budget_comment("2026-11-03", 2.0, drainable_in=0, url="https://example.test/03"),
            ]
        ),
        encoding="utf-8",
    )
    assert series.main([str(path), "--ingest-comments", str(extra), "--write"]) == 0
    ready_report = json.loads(capsys.readouterr().out)
    assert ready_report["streak"] == 7
    assert ready_report["ready_to_close"] is True
    assert ready_report["remaining_days"] == 0
    assert series.main([str(path), "--require-ready"]) == 0


def test_issue_1189_evidence_matches_live_comment_ingest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Checked-in series must match a dry ingest of the recorded Health 85 URLs."""

    measurements, target, required, payload = series.load_series(EVIDENCE)
    comments = []
    for item in measurements:
        assert item.comment_url, item.date
        body = (
            f"CI budget {item.date}: p50={item.p50_minutes} min; "
            f"target={item.target_minutes} min; distance={item.distance}; "
            f"share={item.share}%; drainable_in={item.drainable_in}; "
            f"longest_job={item.longest_job}."
        )
        comments.append(
            {
                "body": body,
                "html_url": item.comment_url,
                "created_at": payload["updated_at"],
            }
        )

    comments_path = tmp_path / "comments.json"
    comments_path.write_text(json.dumps(comments), encoding="utf-8")
    empty = tmp_path / "empty-series.json"
    empty.write_text(
        json.dumps(
            {
                "issue": 1189,
                "target_minutes": target,
                "required_consecutive_days": required,
                "measurements": [],
            }
        ),
        encoding="utf-8",
    )

    assert series.main([str(empty), "--ingest-comments", str(comments_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready_to_close"] is False
    assert report["remaining_days"] == 4
    assert report["under_target_dates"] == [
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    ]
    assert report["wrote"] is False
