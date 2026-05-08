"""Validation tests for name registry maintainer documentation."""

from __future__ import annotations

from pathlib import Path


def test_name_registry_doc_contains_safe_maintainer_update_process() -> None:
    doc_path = Path(__file__).resolve().parents[1] / "docs" / "name_registry.md"
    assert doc_path.is_file()

    contents = doc_path.read_text(encoding="utf-8")

    assert "## Safe Update Process" in contents
    assert "Run the pipeline or mapping diff report first." in contents
    assert "Do not add aliases from memory." in contents
    assert "Keep `canonical_key` stable" in contents
    assert "series_included" in contents
    assert "NAME_RESOLUTIONS" in contents
    assert "config/name_registry.yml" in contents
    assert (
        "tests/test_name_registry.py tests/test_normalize.py tests/test_mapping_diff_report.py"
        in contents
    )
    assert "canonicalization helper" in contents
