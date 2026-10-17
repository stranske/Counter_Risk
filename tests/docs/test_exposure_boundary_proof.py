"""The bounded audit must reject an unverified source baseline before mutation."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("returncode", [1, 128], ids=["source-drift", "git-error"])
def test_dirty_source_gate_stops_before_proofs_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    script = Path(__file__).resolve().parents[2] / "docs/evidence/issue-1160/prove_boundary.py"
    raw = tmp_path / "raw"
    raw.mkdir()
    spec = importlib.util.spec_from_file_location("exposure_boundary_proof", script)
    assert spec is not None and spec.loader is not None
    proof = importlib.util.module_from_spec(spec)
    # Keep import-time temporary output local to the test. Importing snapshots
    # source bytes; main() must verify those bytes before producing evidence.
    with monkeypatch.context() as context:
        context.setattr(tempfile, "mkdtemp", lambda **kwargs: str(raw))
        spec.loader.exec_module(proof)

    command = ["git", "diff", "--exit-code", proof.BASELINE, "--", "src"]
    rejected_baseline = subprocess.CalledProcessError(returncode, command)
    git_run = Mock(side_effect=rejected_baseline)
    mutate = Mock()
    run_suite = Mock()
    publish = Mock()
    monkeypatch.setattr(proof.subprocess, "run", git_run)
    monkeypatch.setattr(proof, "mutate", mutate)
    monkeypatch.setattr(proof, "run_suite", run_suite)
    monkeypatch.setattr(proof, "publish", publish)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        proof.main()

    assert raised.value is rejected_baseline
    git_run.assert_called_once_with(command, cwd=proof.ROOT, capture_output=True, check=True)
    mutate.assert_not_called()
    run_suite.assert_not_called()
    publish.assert_not_called()
    assert list(raw.iterdir()) == [], "rejected source must not produce audit evidence"
    assert all(path.read_bytes() == original for path, original in proof.ORIGINALS.items())
