"""Focused pipeline orchestration coverage for coverage-autopilot issue #1214."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from counter_risk.pipeline import run as run_module


def test_run_pipeline_with_config_forwards_report_date_override(
    monkeypatch, tmp_path: Path
) -> None:
    """In-memory config execution must preserve an approved report-date override."""

    config_dir = tmp_path / "config"
    captured: dict[str, object] = {}

    def fake_run_pipeline(config_path: Path, **kwargs: object) -> Path:
        captured["config_path"] = config_path
        captured["kwargs"] = kwargs
        return tmp_path / "run"

    monkeypatch.setattr(run_module, "run_pipeline", fake_run_pipeline)
    result = run_module.run_pipeline_with_config(
        _config(),
        config_dir=config_dir,
        output_dir=tmp_path / "run",
        formatting_profile="accounting",
        report_date_override="source-date-confirmed",
    )

    assert result == tmp_path / "run"
    assert isinstance(captured["config_path"], Path)
    assert captured["config_path"].parent.name == "counter-risk-runtime"
    assert captured["kwargs"] == {
        "output_dir": tmp_path / "run",
        "formatting_profile": "accounting",
        "report_date_override": "source-date-confirmed",
    }
    assert not captured["config_path"].exists()


def test_fleet_artifact_excludes_external_output_paths_and_captures_environment(
    monkeypatch, tmp_path: Path
) -> None:
    """Fleet evidence references only artifacts contained in the run directory."""

    captured: dict[str, object] = {}

    def fake_build_fleet_records(**kwargs: object) -> list[dict[str, str]]:
        captured.update(kwargs)
        return [{"status": "ok"}]

    expected_path = tmp_path / "langsmith-fleet.json"
    monkeypatch.setattr(run_module, "build_fleet_records", fake_build_fleet_records)
    monkeypatch.setattr(run_module, "write_fleet_records", lambda path, records: expected_path)
    monkeypatch.setenv("LANGSMITH_TRACE_LATENCY_MS", " 123 ")
    monkeypatch.setenv("PIPELINE_ERROR_CATEGORY", " input ")

    result = run_module._write_langsmith_fleet_artifact(
        run_dir=tmp_path,
        as_of_date=date(2025, 12, 31),
        output_paths=[tmp_path / "manifest.json", tmp_path.parent / "outside.csv"],
        warnings=[],
        concentration_metrics_records=[{"counterparty": "A"}],
        risk_proxy_summary={"available": True},
        limit_breach_summary={"warning_breach_count": 1},
        workflow_trace_events=[{"stage": "parse"}],
    )

    assert result == expected_path
    assert captured["report_artifacts"] == ["artifact:manifest.json"]
    assert captured["risk_proxy_status"] == "success"
    assert captured["data_quality_status"] == "warning"
    assert captured["limit_max_severity"] == "warning"
    context = captured["context"]
    assert context.latency_ms == 123
    assert context.error_category == "input"


def test_limit_summary_and_failure_message_cover_invalid_and_fail_values(tmp_path: Path) -> None:
    """Limit policy must not turn malformed counts into a false failure."""

    no_breach = run_module.LimitBreachEvaluation(csv_path=None, breach_count=0)
    summary = run_module._build_limit_breach_summary(run_dir=tmp_path, limit_breaches=no_breach)
    assert summary["has_breaches"] is False
    assert summary["warning_banner"] is None
    run_module._raise_for_fail_limit_breaches(
        {"fail_breach_count": "not-a-number"}, run_dir=tmp_path
    )

    csv_path = tmp_path / "limit_breaches.csv"
    csv_path.write_text("severity\nfail\nfail\n", encoding="utf-8")
    banner = run_module._build_limit_warning_banner_for_run_dir(tmp_path)
    assert banner is not None
    assert banner.title == "Limit Breaches Detected (2)"

    fail_summary = {
        "fail_breach_count": 2,
        "report_path": "limit_breaches.csv",
    }
    try:
        run_module._raise_for_fail_limit_breaches(fail_summary, run_dir=tmp_path)
    except RuntimeError as exc:
        assert "Fail-severity limit breaches detected: 2" in str(exc)
        assert str(csv_path.resolve()) in str(exc)
    else:
        raise AssertionError("fail-severity limits must stop the pipeline")


def _config():
    from counter_risk.config import WorkflowConfig

    return WorkflowConfig(
        as_of_date="2025-12-31",
        mosers_all_programs_xlsx=Path("all.xlsx"),
        mosers_ex_trend_xlsx=Path("ex.xlsx"),
        mosers_trend_xlsx=Path("trend.xlsx"),
        hist_all_programs_3yr_xlsx=Path("hist-all.xlsx"),
        hist_ex_llc_3yr_xlsx=Path("hist-ex.xlsx"),
        hist_llc_3yr_xlsx=Path("hist-trend.xlsx"),
        monthly_pptx=Path("report.pptx"),
        output_root=Path("runs"),
    )
