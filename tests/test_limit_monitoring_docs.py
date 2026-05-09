"""Validation tests for limit monitoring maintainer documentation."""

from __future__ import annotations

from pathlib import Path


def test_limit_monitoring_doc_contains_safe_maintainer_update_process() -> None:
    doc_path = Path(__file__).resolve().parents[1] / "docs" / "limit_monitoring.md"
    assert doc_path.is_file()

    contents = doc_path.read_text(encoding="utf-8")

    assert "## Safe Maintainer Update Process" in contents
    assert "config/limits.yml" in contents
    assert "`warning` or `fail`" in contents
    assert "enabled: false" in contents
    assert "strict_missing_entities: true" in contents
    assert (
        'pytest tests/test_limits_config.py tests/compute/test_limits.py -m "not slow"' in contents
    )
    assert "test_run_pipeline_writes_limit_breaches_csv_when_breaches_exist" in contents
    assert "test_run_pipeline_strict_missing_limit_entities_fails" in contents
    assert "duplicate limit keys are not allowed" in contents
