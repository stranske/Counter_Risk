"""The mutation oracle must distinguish assertion messages from traceback text."""

import runpy
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


@pytest.mark.parametrize("actual_cash_failure", [False, True])
def test_cash_oracle_uses_junit_message(tmp_path: Path, actual_cash_failure: bool) -> None:
    verifier = (
        Path(__file__).resolve().parents[2] / "docs/evidence/issue-1159/verify_pipeline_break.py"
    )
    cash_failures = runpy.run_path(str(verifier))["cash_failures"]
    root = ET.Element("testsuites")
    case = ET.SubElement(ET.SubElement(root, "testsuite"), "testcase")
    message = (
        "AssertionError: exporter input disagrees with authoritative cash\nassert [0] == [1234567]"
        if actual_cash_failure
        else "AssertionError: workbook path is outside run directory"
    )
    failure = ET.SubElement(case, "failure", message=message)
    # Both tracebacks show the later assertion source; only one executed it.
    failure.text = (
        'assert cash == [cash_amount], "exporter input disagrees with authoritative cash"'
    )
    xml_path = tmp_path / "result.xml"
    ET.ElementTree(root).write(xml_path)
    assert bool(cash_failures(xml_path)) is actual_cash_failure
