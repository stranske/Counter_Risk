"""Tests for PyInstaller release spec configuration."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def test_release_spec_defines_analysis_exe_and_collect() -> None:
    spec_path = Path(__file__).resolve().parents[1] / "release.spec"
    captures: dict[str, Any] = {}

    def _analysis(*args: object, **kwargs: object) -> SimpleNamespace:
        captures["analysis_args"] = args
        captures["analysis_kwargs"] = kwargs
        return SimpleNamespace(
            scripts=["fake-script"],
            pure=["fake-pure"],
            binaries=["fake-binary"],
            zipfiles=["fake-zip"],
            datas=["fake-data"],
        )

    def _pyz(*args: object, **kwargs: object) -> str:
        captures["pyz_args"] = args
        captures["pyz_kwargs"] = kwargs
        return "fake-pyz"

    def _exe(*args: object, **kwargs: object) -> str:
        captures["exe_args"] = args
        captures["exe_kwargs"] = kwargs
        return "fake-exe"

    def _collect(*args: object, **kwargs: object) -> str:
        captures["collect_args"] = args
        captures["collect_kwargs"] = kwargs
        return "fake-collect"

    namespace = {
        "__file__": str(spec_path),
        "Analysis": _analysis,
        "PYZ": _pyz,
        "EXE": _exe,
        "COLLECT": _collect,
    }

    exec(compile(spec_path.read_text(encoding="utf-8"), str(spec_path), "exec"), namespace)

    analysis_scripts = captures["analysis_args"][0]
    assert len(analysis_scripts) == 1
    assert analysis_scripts[0].endswith("src/counter_risk/cli.py")

    runtime_hooks = captures["analysis_kwargs"]["runtime_hooks"]
    assert len(runtime_hooks) == 1
    assert runtime_hooks[0].endswith("pyinstaller_runtime_hook.py")

    datas = captures["analysis_kwargs"]["datas"]
    bundled_targets = {target for _, target in datas}
    assert bundled_targets == {"templates", "config"}

    assert captures["exe_kwargs"]["name"] == "counter-risk"

    collect_args = captures["collect_args"]
    assert collect_args[0] == "fake-exe"
    assert collect_args[1] == ["fake-binary"]
    assert collect_args[2] == ["fake-zip"]
    assert collect_args[3] == ["fake-data"]
    assert captures["collect_kwargs"]["name"] == "counter-risk"


def test_release_spec_pyinstaller_build_outputs_expected_executable(
    tmp_path: Path,
) -> None:
    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller is None:
        pytest.skip("PyInstaller is not installed in this environment.")

    repo_root = Path(__file__).resolve().parents[1]
    temp_root = tmp_path / "project"
    shutil.copytree(repo_root / "src", temp_root / "src")
    shutil.copytree(repo_root / "config", temp_root / "config")
    shutil.copytree(repo_root / "templates", temp_root / "templates")
    shutil.copy2(repo_root / "release.spec", temp_root / "release.spec")
    shutil.copy2(
        repo_root / "pyinstaller_runtime_hook.py",
        temp_root / "pyinstaller_runtime_hook.py",
    )

    subprocess.run(
        [pyinstaller, "-y", "release.spec"],
        cwd=temp_root,
        text=True,
        capture_output=True,
        check=True,
    )

    expected_executable = (
        temp_root
        / "dist"
        / "counter-risk"
        / ("counter-risk.exe" if os.name == "nt" else "counter-risk")
    )
    assert expected_executable.is_file()
