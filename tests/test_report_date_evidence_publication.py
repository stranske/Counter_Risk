"""Publication must preserve the truth of the original report-date test evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from tools.publish_report_date_evidence import (
    TRANSFORMATION,
    publish_junit,
    remove_suite_hostnames,
)

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "docs/evidence/issue-1162"


def test_transformation_removes_only_suite_hostname_attributes() -> None:
    original = (
        b'<?xml version="1.0"?>\n<testsuites hostname="outer" name="a &gt; b">'
        b'<!-- <testsuite hostname="comment"/> -->'
        b"<testsuite name='suite hostname=\"keep\"' hostname = 'inner' tests='1'>"
        b'<testcase hostname="keep" name="test">'
        b'<failure><![CDATA[<testsuite hostname="diagnostic"/>]]></failure>'
        b"</testcase></testsuite></testsuites>\n"
    )
    expected = original.replace(b' hostname="outer"', b"").replace(b" hostname = 'inner'", b"")
    published, count = remove_suite_hostnames(original)
    assert published == expected
    assert count == 2
    assert remove_suite_hostnames(published) == (published, 0)


def test_publication_retains_actual_execution_binding_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "test.xml"
    original = b'<testsuites><testsuite hostname="runner" tests="1"/></testsuites>'
    binding = {
        "argv": ["/actual/python", "-m", "pytest", "--junitxml=test.xml"],
        "cwd": "/actual/working/directory",
        "started_at": "2026-10-17T03:08:03+00:00",
        "source_bindings": {"src/counter_risk/dates.py": "source-digest"},
        "exit_code": 0,
        "console_sha256": "console-digest",
        "junit_sha256": hashlib.sha256(original).hexdigest(),
    }
    path.write_bytes(original)
    binding_path = path.with_suffix(".binding.json")
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    publish_junit(path)

    result = json.loads(binding_path.read_text(encoding="utf-8"))
    publication = result.pop("junit_publication")
    assert result == binding
    assert publication == {
        "transformation": TRANSFORMATION,
        "original_sha256": binding["junit_sha256"],
        "published_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "removed_attributes": 1,
    }
    binding_bytes = binding_path.read_bytes()
    report_bytes = path.read_bytes()
    publish_junit(path)
    assert binding_path.read_bytes() == binding_bytes
    assert path.read_bytes() == report_bytes


@pytest.mark.parametrize("already_published", [False, True])
def test_publication_rejects_hash_mismatch_without_mutation(
    tmp_path: Path, already_published: bool
) -> None:
    path = tmp_path / "test.xml"
    path.write_bytes(b'<testsuite hostname="runner"/>')
    binding = {"junit_sha256": "incorrect"}
    if already_published:
        binding["junit_publication"] = {"published_sha256": "incorrect"}
    binding_path = path.with_suffix(".binding.json")
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    report_bytes, binding_bytes = path.read_bytes(), binding_path.read_bytes()
    with pytest.raises(ValueError, match="JUnit hash mismatch"):
        publish_junit(path)
    assert path.read_bytes() == report_bytes
    assert binding_path.read_bytes() == binding_bytes


@pytest.mark.parametrize("name", ["scope-red", "scope-green", "acceptance-final", "compatibility"])
def test_published_report_date_evidence_hashes_and_original_provenance(name: str) -> None:
    binding = json.loads((EVIDENCE_DIR / f"{name}.binding.json").read_text(encoding="utf-8"))
    report = (EVIDENCE_DIR / f"{name}.xml").read_bytes()
    publication = binding["junit_publication"]
    assert publication["transformation"] == TRANSFORMATION
    assert publication["original_sha256"] == binding["junit_sha256"]
    assert publication["published_sha256"] == hashlib.sha256(report).hexdigest()
    assert publication["removed_attributes"] == 1
    assert (
        binding["console_sha256"]
        == hashlib.sha256((EVIDENCE_DIR / f"{name}.log").read_bytes()).hexdigest()
    )
    assert binding["argv"][0] == "/opt/anaconda3/bin/python3"
    assert binding["cwd"] == (
        "/Users/teacher/.codex/orchestrator/worktrees/stranske__Counter_Risk__1162__opener"
    )
    root = ElementTree.fromstring(report)
    suites = list(root.iter("testsuite"))
    assert all("hostname" not in suite.attrib for suite in suites)
    expected = json.loads((EVIDENCE_DIR / "verification.json").read_text())["gates"][name]
    for field in ("tests", "failures", "errors", "skipped"):
        assert sum(int(suite.attrib[field]) for suite in suites) == expected[field]
