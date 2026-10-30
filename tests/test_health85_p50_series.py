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
