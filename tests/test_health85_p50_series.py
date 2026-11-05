"""Health 85 trailing Gate p50 series parsing and closure readiness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import health85_p50_series as series

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "docs" / "evidence" / "issue-1189" / "health85-p50-series.json"
LIVE_COMMENTS = REPO_ROOT / "docs" / "evidence" / "issue-1189" / "health85-comments-api.json"


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
    assert series.next_required_dates(measurements) == (
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    )

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
    assert series.next_required_dates(seven) == ()


@pytest.mark.parametrize(
    "p50",
    [float("nan"), float("inf"), float("-inf"), -1.0, 10.01],
    ids=["nan", "infinity", "negative-infinity", "negative", "over-target"],
)
@pytest.mark.parametrize("invalid_index", [0, 3, 6], ids=["first", "middle", "latest"])
def test_cli_invalid_p50_breaks_streak_until_corrected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    p50: float,
    invalid_index: int,
) -> None:
    """A missing numeric p50 cannot establish an under-target daily measurement."""

    path = tmp_path / "series.json"
    measurements = [{"date": f"2026-10-{day}", "p50_minutes": 10.0} for day in range(24, 31)]
    measurements[invalid_index]["p50_minutes"] = p50
    payload = {"issue": 1189, "measurements": measurements}
    # Python's JSON loader accepts non-finite numbers; the closer must not count them.
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded, target, _, _ = series.load_series(path)
    table = series.format_dated_p50_series(loaded, target_minutes=target)
    assert f"| 2026-10-{24 + invalid_index} | {p50:.2f} | no |" in table

    for option in ("--require-ready", "--print-closure-comment"):
        assert series.main([str(path), option]) == 1
        output = capsys.readouterr().out
        report = json.loads(output)
        assert report["ready_to_close"] is False
        assert report["streak"] == 6 - invalid_index
        assert report["remaining_days"] == invalid_index + 1
        assert "Closing #" not in output

    # A corrected zero-minute value is valid, as are the six days exactly at target.
    measurements[invalid_index]["p50_minutes"] = 0.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert series.main([str(path), "--require-ready"]) == 0
    ready = json.loads(capsys.readouterr().out)
    assert ready["streak"] == 7
    assert ready["ready_to_close"] is True
    assert series.main([str(path), "--print-closure-comment"]) == 0
    closure = capsys.readouterr().out
    assert "Closing #1189" in closure
    assert f"| 2026-10-{24 + invalid_index} | 0.00 | yes |" in closure


def test_format_closure_comment_refuses_early_and_emits_dated_series() -> None:
    short = [
        series.Measurement(date="2026-10-28", p50_minutes=2.12),
        series.Measurement(date="2026-10-29", p50_minutes=2.08),
        series.Measurement(date="2026-10-30", p50_minutes=2.08),
    ]
    with pytest.raises(ValueError, match="not ready to close"):
        series.format_closure_comment(short)

    seven = [
        series.Measurement(date="2026-10-25", p50_minutes=19.97),
        series.Measurement(date="2026-10-26", p50_minutes=17.81),
        series.Measurement(date="2026-10-27", p50_minutes=17.29),
        series.Measurement(date="2026-10-28", p50_minutes=2.12),
        series.Measurement(date="2026-10-29", p50_minutes=2.08),
        series.Measurement(date="2026-10-30", p50_minutes=2.08),
        series.Measurement(date="2026-10-31", p50_minutes=2.00),
        series.Measurement(date="2026-11-01", p50_minutes=2.00),
        series.Measurement(date="2026-11-02", p50_minutes=2.00),
        series.Measurement(date="2026-11-03", p50_minutes=2.00),
    ]
    body = series.format_closure_comment(seven, issue=1189)
    assert "Closing #1189" in body
    assert "7 consecutive daily measurements" in body
    assert "Dated p50 series:" in body
    assert "| 2026-10-28 | 2.12 | yes |" in body
    assert "| 2026-11-03 | 2.00 | yes |" in body
    assert "| 2026-10-25 | 19.97 | no |" in body
    table = series.format_dated_p50_series(seven)
    assert table in body


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


def test_next_required_dates_after_over_target_newest_day() -> None:
    measurements = [
        series.Measurement(date="2026-10-28", p50_minutes=2.0),
        series.Measurement(date="2026-10-29", p50_minutes=2.0),
        series.Measurement(date="2026-10-30", p50_minutes=11.0),
    ]
    status = series.evaluate_series(measurements, target_minutes=10.0)
    assert status.streak == 0
    assert status.under_target_dates == ()
    assert series.next_required_dates(measurements) == (
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
    )
    assert series.next_required_dates([]) == ()


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
    expected_next = series.next_required_dates(
        measurements, target_minutes=target, required_consecutive_days=required
    )
    assert recorded["next_required_dates"] == list(expected_next)
    assert status.remaining_days == max(0, required - status.streak)

    by_date = {item.date: item for item in measurements}
    for day in status.under_target_dates:
        assert 0 <= by_date[day].p50_minutes <= target

    if status.ready_to_close:
        assert "Closing #1189" in series.format_closure_comment(
            measurements,
            issue=1189,
            target_minutes=target,
            required_consecutive_days=required,
        )
    else:
        with pytest.raises(ValueError, match="not ready to close"):
            series.format_closure_comment(
                measurements,
                issue=1189,
                target_minutes=target,
                required_consecutive_days=required,
            )


@pytest.mark.parametrize("target", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_nonfinite_or_negative_target_cannot_authorize_closure(
    tmp_path: Path, target: float
) -> None:
    path = tmp_path / "series.json"
    measurements = [{"date": f"2026-10-{day}", "p50_minutes": 10.0} for day in range(24, 31)]
    path.write_text(json.dumps({"target_minutes": target, "measurements": measurements}))
    with pytest.raises(ValueError, match="finite and nonnegative"):
        series.load_series(path)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        series.evaluate_series(
            [series.measurement_from_mapping(item) for item in measurements],
            target_minutes=target,
        )


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
    assert payload["next_required_dates"] == [
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert series.main([str(path), "--require-ready"]) == 1
    capsys.readouterr()  # drain require-ready JSON before the close-comment probe
    assert series.main([str(path), "--print-closure-comment"]) == 1
    blocked_out = capsys.readouterr().out
    blocked = json.loads(blocked_out)
    assert blocked["ready_to_close"] is False
    assert "Closing #" not in blocked_out


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
    assert written["status"]["next_required_dates"] == [
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert written["updated_at"] == "2026-10-30T12:00:00Z"
    assert report["status"] == written["status"]

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
    assert ready_report["next_required_dates"] == []
    ready_written = json.loads(path.read_text(encoding="utf-8"))
    assert ready_written["status"]["next_required_dates"] == []
    assert ready_written["status"]["ready_to_close"] is True
    assert series.main([str(path), "--require-ready"]) == 0
    assert series.main([str(path), "--print-closure-comment"]) == 0
    closure = capsys.readouterr().out
    assert "Closing #1189" in closure
    assert "Dated p50 series:" in closure
    assert "| 2026-10-28 | 2.12 | yes |" in closure
    assert "| 2026-11-03 | 2.00 | yes |" in closure


def test_cli_print_closure_comment_on_checked_in_evidence_exits_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Live #1189 evidence (streak 3/7) must not emit a close-comment body."""

    assert series.main([str(EVIDENCE), "--print-closure-comment"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ready_to_close"] is False
    assert report["remaining_days"] == 4
    assert report["next_required_dates"] == [
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]


def test_cli_ingest_print_closure_comment_blocks_then_emits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ingest+print-closure-comment stays blocked until the seventh under-target day."""

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
    short = tmp_path / "short.json"
    short.write_text(
        json.dumps(
            [_budget_comment("2026-10-30", 2.08, drainable_in=4, url="https://example.test/30")]
        ),
        encoding="utf-8",
    )
    assert (
        series.main(
            [str(path), "--ingest-comments", str(short), "--write", "--print-closure-comment"]
        )
        == 1
    )
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["ready_to_close"] is False
    assert blocked["streak"] == 1
    assert "Closing #" not in json.dumps(blocked)

    seven = tmp_path / "seven.json"
    seven.write_text(
        json.dumps(
            [
                _budget_comment("2026-10-28", 2.0, drainable_in=6, url="https://example.test/28"),
                _budget_comment("2026-10-29", 2.0, drainable_in=5, url="https://example.test/29"),
                _budget_comment("2026-10-30", 2.0, drainable_in=4, url="https://example.test/30"),
                _budget_comment("2026-10-31", 2.0, drainable_in=3, url="https://example.test/31"),
                _budget_comment("2026-11-01", 2.0, drainable_in=2, url="https://example.test/01"),
                _budget_comment("2026-11-02", 2.0, drainable_in=1, url="https://example.test/02"),
                _budget_comment("2026-11-03", 2.0, drainable_in=0, url="https://example.test/03"),
            ]
        ),
        encoding="utf-8",
    )
    assert (
        series.main(
            [str(path), "--ingest-comments", str(seven), "--write", "--print-closure-comment"]
        )
        == 0
    )
    closure = capsys.readouterr().out
    assert "Closing #1189" in closure
    assert "| 2026-11-03 | 2.00 | yes |" in closure


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
    assert report["next_required_dates"] == [
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert report["wrote"] is False
    assert report["status"]["next_required_dates"] == report["next_required_dates"]


def test_issue_1189_live_api_snapshot_ingest_blocks_closure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Real gh-api comment snapshot for #1189 must keep ready_to_close false (3/7).

    Closer path: ingest docs/evidence/issue-1189/health85-comments-api.json, then
    ``--print-closure-comment`` must exit 1 until Health 85 posts 2026-10-31..11-03.
    """

    assert LIVE_COMMENTS.is_file(), LIVE_COMMENTS
    live = json.loads(LIVE_COMMENTS.read_text(encoding="utf-8"))
    assert isinstance(live, list) and live
    budget_bodies = [
        comment["body"]
        for comment in live
        if series.parse_budget_comment(str(comment.get("body") or "")) is not None
    ]
    assert len(budget_bodies) == 6

    empty = tmp_path / "series.json"
    empty.write_text(
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

    assert (
        series.main(
            [
                str(empty),
                "--ingest-comments",
                str(LIVE_COMMENTS),
                "--write",
                "--print-closure-comment",
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ready_to_close"] is False
    assert report["streak"] == 3
    assert report["remaining_days"] == 4
    assert report["under_target_dates"] == [
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    ]
    assert report["next_required_dates"] == [
        "2026-10-31",
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]
    assert "Closing #" not in json.dumps(report)

    written = json.loads(empty.read_text(encoding="utf-8"))
    assert written["status"]["ready_to_close"] is False
    assert written["status"]["next_required_dates"] == report["next_required_dates"]

    # The current evidence must retain each historical snapshot measurement,
    # while allowing Health 85 to append newer calendar days.
    current, _, _, _ = series.load_series(EVIDENCE)
    by_date = {item.date: item for item in current}
    for item in series.measurements_from_issue_comments(live):
        assert by_date[item.date] == item
