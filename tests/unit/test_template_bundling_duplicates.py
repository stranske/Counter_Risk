from __future__ import annotations

from pathlib import Path

import pytest

from counter_risk.build import release


def _write_template(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def test_copy_templates_raises_with_all_duplicate_filenames_and_source_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    bundle_dir = tmp_path / "bundle"

    first_duplicate = "collision-one.pptx"
    second_duplicate = "collision-two.pptx"

    template_dir = repo_root / "templates"
    fixture_dir = repo_root / "tests" / "fixtures"

    _write_template(template_dir / first_duplicate, b"template-one")
    _write_template(fixture_dir / first_duplicate, b"fixture-one")
    _write_template(template_dir / second_duplicate, b"template-two")
    _write_template(fixture_dir / second_duplicate, b"fixture-two")

    with pytest.raises(ValueError) as exc_info:
        release._copy_templates(repo_root, bundle_dir)

    message = str(exc_info.value)
    assert "Template filename conflicts detected across template sources" in message

    expected_conflicts = {
        first_duplicate: [template_dir / first_duplicate, fixture_dir / first_duplicate],
        second_duplicate: [template_dir / second_duplicate, fixture_dir / second_duplicate],
    }
    for filename, paths in expected_conflicts.items():
        assert filename in message
        for path in paths:
            assert str(path) in message
