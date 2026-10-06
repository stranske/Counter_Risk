"""Run folder safety at the filesystem ownership boundary."""

from datetime import date
from pathlib import Path

import pytest

from counter_risk.pipeline import run

AS_OF = date(2026, 2, 13)


def test_explicit_file_is_rejected_without_modifying_it(tmp_path: Path) -> None:
    output = tmp_path / "report.txt"
    output.write_text("existing report")
    with pytest.raises(ValueError, match="must be a directory"):
        run._create_run_directory(as_of_date=AS_OF, output_dir=output)
    assert output.read_text() == "existing report"


def test_unreadable_output_directory_retains_filesystem_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = PermissionError("directory inspection denied")

    def denied(_path: Path):
        raise error

    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(RuntimeError, match="Unable to inspect output_dir") as caught:
        run._create_run_directory(as_of_date=AS_OF, output_dir=tmp_path)
    assert caught.value.__cause__ is error


def test_existing_empty_output_directory_is_reused(tmp_path: Path) -> None:
    assert run._create_run_directory(as_of_date=AS_OF, output_dir=tmp_path) == tmp_path
    assert list(tmp_path.iterdir()) == []


def test_automatic_run_preserves_owned_folders_and_uses_next_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_resolve_repo_root", lambda: tmp_path)
    base = "2026-02-13__run_2026-02-14"
    for name in (base, base + "_1"):
        folder = tmp_path / "runs" / name
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(name)
    result = run._create_run_directory(as_of_date=AS_OF, run_date=date(2026, 2, 14))
    assert result == tmp_path / "runs" / (base + "_2")
    assert result.is_dir()
    assert list(result.iterdir()) == []
    for name in (base, base + "_1"):
        assert (tmp_path / "runs" / name / "manifest.json").read_text() == name


def test_concurrent_run_directory_claim_advances_without_reusing_other_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_resolve_repo_root", lambda: tmp_path)
    original_mkdir = Path.mkdir
    contested = tmp_path / "runs" / AS_OF.isoformat()
    claimed = False

    def claim_first(path: Path, *args, **kwargs) -> None:
        nonlocal claimed
        if path == contested and not claimed:
            claimed = True
            original_mkdir(path, parents=True)
            (path / "manifest.json").write_text("other run")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", claim_first)
    result = run._create_run_directory(as_of_date=AS_OF)
    assert result == tmp_path / "runs" / (AS_OF.isoformat() + "_1")
    assert result.is_dir()
    assert list(result.iterdir()) == []
    assert (contested / "manifest.json").read_text() == "other run"


def test_exhausted_run_names_fail_without_reusing_any_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(Path, "exists", lambda _path: True)
    with pytest.raises(RuntimeError, match="Unable to create unique run directory"):
        run._create_run_directory(as_of_date=AS_OF)


def test_automatic_run_does_not_swallow_noncollision_filesystem_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_resolve_repo_root", lambda: tmp_path)
    error = PermissionError("run root is read-only")

    def denied(_path: Path, *args, **kwargs) -> None:
        raise error

    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(PermissionError) as caught:
        run._create_run_directory(as_of_date=AS_OF)
    assert caught.value is error
