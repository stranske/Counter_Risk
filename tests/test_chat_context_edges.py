"""Run-context loading reports failures at the filesystem and table boundaries."""

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from counter_risk.chat import context


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_context_requires_a_run_directory(tmp_path: Path, kind: str) -> None:
    path = tmp_path / kind
    if kind == "file":
        path.write_text("not a directory", encoding="utf-8")
    with pytest.raises(context.RunContextError, match="does not exist or is not a directory"):
        context.load_run_context(path)


def test_manifest_requires_an_object(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("[]", encoding="utf-8")
    with pytest.raises(context.RunContextError, match="must contain a JSON object"):
        context.load_manifest(tmp_path)


@pytest.mark.parametrize(
    ("filename", "loader", "message"),
    [
        ("manifest.json", context.load_manifest, "Failed to read manifest.json"),
        ("cash.csv", context.discover_tables, "Failed to read CSV table"),
        ("chat_logs/chat.jsonl", context.load_chat_logs, "Failed to read chat log file"),
    ],
)
def test_context_wraps_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename, loader, message
) -> None:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    original_open = Path.open

    def fail_read(self, *args, **kwargs):
        if self == path:
            raise PermissionError("read denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_read)
    with pytest.raises(context.RunContextError, match=message) as caught:
        loader(tmp_path)
    assert isinstance(caught.value.__cause__, PermissionError)
    assert str(path) in str(caught.value)


def test_table_discovery_wraps_iteration_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_scan(self, pattern):
        yield tmp_path / "cash.csv"
        raise OSError("directory unavailable")

    monkeypatch.setattr(Path, "rglob", fail_scan)
    with pytest.raises(context.RunContextError, match="Failed while discovering tables") as caught:
        context.discover_tables(tmp_path)
    assert isinstance(caught.value.__cause__, OSError)


def test_csv_parse_errors_include_the_table_path(tmp_path: Path) -> None:
    path = tmp_path / "cash.csv"
    path.write_text("name,cash\n" + "x" * 20 + ",2\n", encoding="utf-8")
    previous_limit = csv.field_size_limit(10)
    try:
        with pytest.raises(context.RunContextError, match="Malformed CSV table") as caught:
            context.discover_tables(tmp_path)
    finally:
        csv.field_size_limit(previous_limit)
    assert isinstance(caught.value.__cause__, csv.Error)
    assert str(path) in str(caught.value)


def test_blank_chat_lines_and_malformed_delta_records_are_skipped(tmp_path: Path) -> None:
    chat_dir = tmp_path / "chat_logs"
    chat_dir.mkdir()
    (chat_dir / "a.jsonl").write_text('\n {"response": "first"}\n \n', encoding="utf-8")
    (chat_dir / "b.jsonl").write_text('{"response": "second"}\n', encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "warnings": "invalid",
                "top_changes_per_variant": {
                    "invalid": {},
                    "trend": [None, {"counterparty": "CIBC", "delta": 2}],
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = context.load_run_context(tmp_path)
    assert loaded.warnings == []
    assert loaded.deltas == {"trend": [{"counterparty": "CIBC", "delta": 2}]}
    assert loaded.chat_logs == [{"response": "first"}, {"response": "second"}]


def test_parquet_disk_failure_is_distinct_from_arrow_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ArrowError(OSError):
        pass

    def read_parquet(path):
        raise PermissionError("read denied")

    monkeypatch.setitem(sys.modules, "pandas", SimpleNamespace(read_parquet=read_parquet))
    monkeypatch.setattr(context, "_PYARROW_IO_ERROR_TYPES", (ArrowError,))
    with pytest.raises(
        context.RunContextError, match="Failed to access Parquet table on disk"
    ) as caught:
        context._load_parquet_table(tmp_path / "cash.parquet")
    assert isinstance(caught.value.__cause__, PermissionError)


def test_parquet_success_converts_to_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "cash.parquet"
    path.touch()

    def to_dict(*, orient):
        assert orient == "records"
        return [{"counterparty": "CIBC", "cash": 2.0}]

    def read_parquet(source):
        assert source == path
        return SimpleNamespace(to_dict=to_dict)

    monkeypatch.setitem(sys.modules, "pandas", SimpleNamespace(read_parquet=read_parquet))
    assert context.discover_tables(tmp_path) == {
        "cash.parquet": [{"counterparty": "CIBC", "cash": 2.0}]
    }
