"""Run folder safety at the filesystem ownership boundary."""

import multiprocessing
from datetime import date
from multiprocessing.synchronize import Barrier
from pathlib import Path

import pytest

from counter_risk.pipeline import run

AS_OF = date(2026, 2, 13)


def _claim_run_directory_in_process(
    repo_root: Path, run_date: date | None, barrier: Barrier, worker_index: int
) -> None:
    """Force separate allocators past the same stale existence check."""
    base_name = AS_OF.isoformat()
    if run_date is not None:
        base_name += f"__run_{run_date.isoformat()}"
    contested = repo_root / "runs" / base_name
    original_exists = Path.exists

    def synchronized_exists(path: Path) -> bool:
        exists = original_exists(path)
        if path == contested:
            barrier.wait(timeout=10)
        return exists

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(run, "_resolve_repo_root", lambda: repo_root)
        monkeypatch.setattr(Path, "exists", synchronized_exists)
        result = run._create_run_directory(as_of_date=AS_OF, run_date=run_date)

    (result / "manifest.json").write_text(str(worker_index), encoding="utf-8")
    (repo_root / f"claim-{worker_index}.txt").write_text(str(result), encoding="utf-8")


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


@pytest.mark.parametrize("run_date", [None, date(2026, 2, 14)], ids=["as-of", "run-date"])
def test_separate_processes_claim_distinct_run_directories(
    tmp_path: Path, run_date: date | None
) -> None:
    (tmp_path / "runs").mkdir()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    processes = [
        context.Process(
            target=_claim_run_directory_in_process,
            args=(tmp_path, run_date, barrier, index),
        )
        for index in range(2)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=20)
        assert [process.exitcode for process in processes] == [0, 0]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    results = [
        Path((tmp_path / f"claim-{index}.txt").read_text(encoding="utf-8")) for index in range(2)
    ]
    base_name = AS_OF.isoformat()
    if run_date is not None:
        base_name += f"__run_{run_date.isoformat()}"
    assert set(results) == {tmp_path / "runs" / base_name, tmp_path / "runs" / (base_name + "_1")}
    for index, result in enumerate(results):
        assert list(result.iterdir()) == [result / "manifest.json"]
        assert (result / "manifest.json").read_text(encoding="utf-8") == str(index)


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
