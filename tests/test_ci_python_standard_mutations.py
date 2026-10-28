"""Exercise the runtime regression without writing protected workflow files."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests import test_ci_python_standard as standard


@pytest.fixture
def workflow_documents(monkeypatch: pytest.MonkeyPatch) -> dict[Path, str]:
    read_text = Path.read_text
    documents = {
        path: path.read_text(encoding="utf-8") for path in standard.WORKFLOWS.glob("*.yml")
    }

    def read_workflow(path: Path, *args, **kwargs) -> str:
        if path in documents:
            return documents[path]
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_workflow)
    return documents


@pytest.mark.parametrize("filename", ["ci.yml", "pr-00-gate.yml"])
def test_restored_old_matrix_fails_then_restored_standard_passes(
    workflow_documents: dict[Path, str], filename: str
) -> None:
    path = standard.WORKFLOWS / filename
    original = workflow_documents[path]
    original_bytes = path.read_bytes()
    matrix = '["3.13", "3.14"]'
    assert matrix in original  # ci.yml carries it once per job (python + slow shards)
    workflow_documents[path] = original.replace(matrix, '["3.12", "3.14"]')

    with pytest.raises(AssertionError, match="Python 3\\.12 runtime pins remain") as failure:
        standard.test_workflow_python_pins_follow_standard()
    assert f"{filename}.jobs." in str(failure.value)
    assert ".with.python-versions" in str(failure.value)

    workflow_documents[path] = original
    standard.test_workflow_python_pins_follow_standard()
    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "runtime_key",
    [
        "python-version",
        "python-versions",
        "primary-python-version",
        "coverage-python-version",
        "PYTHON_VERSION",
        "COVERAGE_REFERENCE_RUNTIME",
    ],
)
@pytest.mark.parametrize(
    "value",
    ["3.12", 3.12, "3.12.9", ["3.14", "3.12"], '["3.13", "3.12"]'],
    ids=["string", "number", "patch", "yaml-list", "json-list"],
)
def test_old_pins_are_rejected_in_other_workflows(
    workflow_documents: dict[Path, str], runtime_key: str, value: object
) -> None:
    path = next(
        path for path in workflow_documents if path.name not in {"ci.yml", "pr-00-gate.yml"}
    )
    workflow_documents[path] = yaml.safe_dump(
        {"jobs": {"probe": {"steps": [{"with": {runtime_key: value}}]}}}
    )

    with pytest.raises(AssertionError, match="Python 3\\.12 runtime pins remain") as failure:
        standard.test_workflow_python_pins_follow_standard()
    assert f"{path.name}.jobs.probe.steps[0].with.{runtime_key}" in str(failure.value)


@pytest.mark.parametrize("filename, job", [("ci.yml", "python"), ("pr-00-gate.yml", "python-ci")])
def test_python_matrix_cannot_be_optional(
    workflow_documents: dict[Path, str], filename: str, job: str
) -> None:
    path = standard.WORKFLOWS / filename
    workflow = yaml.safe_load(workflow_documents[path])
    workflow["jobs"][job]["continue-on-error"] = True
    workflow_documents[path] = yaml.safe_dump(workflow)

    with pytest.raises(AssertionError):
        standard.test_workflow_python_pins_follow_standard()
