from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest


def _write_pin_file(path: Path, *, black_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"BLACK_VERSION={black_version}",
                "RUFF_VERSION=0.0.0",
                "MYPY_VERSION=0.0.0",
                "PYTEST_VERSION=0.0.0",
                "PYTEST_COV_VERSION=0.0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_pyproject(path: Path, *, black_version: str) -> None:
    path.write_text(
        "\n".join(
            [
                "[project]",
                'name = "counter-risk"',
                'version = "0.0.0"',
                "",
                "[project.optional-dependencies]",
                "dev = [",
                f'    "black=={black_version}",',
                '    "ruff==0.0.0",',
                '    "mypy==0.0.0",',
                '    "pytest==0.0.0",',
                '    "pytest-cov==0.0.0",',
                "]",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_sync_dev_dependencies_exits_nonzero_on_black_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pin_file = tmp_path / ".github/workflows/autofix-versions.env"
    pyproject = tmp_path / "pyproject.toml"

    _write_pin_file(pin_file, black_version="24.10.0")
    _write_pyproject(pyproject, black_version="24.1.0")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_dev_dependencies.py",
            "--check",
            "--pin-file",
            str(pin_file),
            "--pyproject",
            str(pyproject),
        ],
    )

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "sync_dev_dependencies.py"

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(script_path), run_name="__main__")

    captured = capsys.readouterr()
    combined = f"{captured.out}\n{captured.err}".lower()
    assert "black" in combined
    assert any(token in combined for token in ("drift", "mismatch", "out of sync", "formatting"))

    assert excinfo.value.code not in (0, None)
