"""Regression gates for the PyInstaller availability guard in the release tests.

Two release tests decide whether PyInstaller is usable before invoking it. They used
to do that by comparing resolved interpreter directories::

    if Path(pyinstaller).resolve().parent != Path(sys.executable).resolve().parent:
        pytest.skip("PyInstaller is not installed in the active test environment.")

``Path.resolve()`` follows symlinks, and a virtualenv's ``bin/python`` is a symlink to
the base interpreter, so both operands collapse onto the base interpreter's ``bin``
directory and the comparison is equal no matter what is installed in the active
environment. The skip therefore never fired, the tests invoked a foreign PyInstaller
against the active environment's code, and the failure surfaced as an opaque
``CalledProcessError`` naming ``release.spec`` -- misdirecting exactly the person most
likely to hit it, someone setting the repository up for the first time.

The guard now asks the question its own skip message claims to ask: is ``PyInstaller``
importable in the running interpreter?
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

_GUARD_FILES = (
    _REPO_ROOT / "tests" / "test_release_spec.py",
    _REPO_ROOT / "tests" / "integration" / "test_packaged_executable_assets.py",
)

# The distinctive half of the defective comparison. Whitespace is stripped from both
# needle and haystack before searching, so reformatting the call across lines cannot
# hide a resurrected guard -- and no legitimate use of this expression exists in
# either file.
_DEFECTIVE_FRAGMENT = "Path(sys.executable).resolve().parent"

_RELEASE_NODE_ID = (
    "tests/test_release_spec.py::test_release_spec_pyinstaller_build_outputs_expected_executable"
)

_EXPECTED_SKIP_REASON = "PyInstaller is not installed in the active test environment."

# Imported into the subprocess before collection. It makes PyInstaller unimportable and
# points `shutil.which` at a path inside the RESOLVED interpreter directory -- which is
# precisely the collapse that defeated the old guard, so the old guard would decline to
# skip and the test would go on to invoke a binary that is not there.
_FORCING_PLUGIN = """
import importlib.util
import shutil
import sys
from pathlib import Path

_ABSENT = Path(sys.executable).resolve().parent / "pyinstaller-absent-for-guard-test"
_real_find_spec = importlib.util.find_spec
_real_which = shutil.which


def _find_spec(name, package=None):
    if name == "PyInstaller" or name.startswith("PyInstaller."):
        return None
    return _real_find_spec(name, package)


def _which(cmd, *args, **kwargs):
    if cmd == "pyinstaller":
        return str(_ABSENT)
    return _real_which(cmd, *args, **kwargs)


importlib.util.find_spec = _find_spec
shutil.which = _which
"""


def test_pyinstaller_guard_does_not_compare_resolved_parents() -> None:
    needle = "".join(_DEFECTIVE_FRAGMENT.split())
    offenders = []
    for path in _GUARD_FILES:
        haystack = "".join(path.read_text(encoding="utf-8").split())
        if needle in haystack:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert not offenders, (
        "the symlink-blind PyInstaller guard is back in: "
        + ", ".join(offenders)
        + f" -- {_DEFECTIVE_FRAGMENT} collapses onto the base interpreter's bin "
        "directory inside a virtualenv, so the skip never fires. Ask "
        'importlib.util.find_spec("PyInstaller") instead.'
    )


@pytest.mark.skipif(
    os.environ.get("COUNTER_RISK_GUARD_SUBPROCESS") == "1",
    reason="guard subprocess re-entry",
)
def test_release_tests_skip_when_pyinstaller_unimportable(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "forcing"
    plugin_dir.mkdir()
    (plugin_dir / "_force_pyinstaller_absent.py").write_text(_FORCING_PLUGIN, encoding="utf-8")

    env = os.environ.copy()
    env["COUNTER_RISK_GUARD_SUBPROCESS"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(plugin_dir), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            _RELEASE_NODE_ID,
            "-p",
            "_force_pyinstaller_absent",
            "-p",
            "no:cacheprovider",
            "-rs",
            "-q",
            "--no-header",
            "--tb=no",
        ],
        cwd=_REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = completed.stdout + completed.stderr

    # The observable outcome is the whole assertion: SKIPPED, not FAILED. Re-deriving
    # the defective predicate here and comparing it against importability would be a
    # defect detector rather than a regression gate -- it would fail identically
    # whether or not the production guard is fixed.
    assert "1 skipped" in report, report
    assert completed.returncode == 0, report
    # Naming the reason pins WHICH guard skipped: `shutil.which` is forced to return a
    # path, so the earlier `pyinstaller is None` guard cannot be the one that fired.
    assert _EXPECTED_SKIP_REASON in report, report
