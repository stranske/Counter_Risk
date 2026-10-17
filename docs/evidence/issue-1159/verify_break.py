"""Serialized issue-1159 causal regression proof; run with the selected Python."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
source = root / "src/counter_risk/pipeline/run.py"
original = source.read_bytes()
needle = b"    for variant, workbook_path in workbook_paths.items():\n"
broken_route = (
    b"    for variant, workbook_field in _CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT.items():\n"
    b"        workbook_path = getattr(config, workbook_field)\n"
    b"        if workbook_path is None:\n"
    b"            continue\n"
)
assert original.count(needle) == 1
command = [
    sys.executable,
    "-m",
    "pytest",
    "tests/pipeline/test_cprs_screenshot_generation.py",
    "-k",
    "adjusted",
    "--junitxml=" + str(evidence / "gate.xml"),
]
results = {}


def run(phase: str) -> int:
    result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (evidence / f"{phase}.log").write_bytes(result.stdout)
    shutil.copyfile(evidence / "gate.xml", evidence / f"{phase}.xml")
    results[phase] = {
        "exit_code": result.returncode,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    print(phase, result.returncode, flush=True)
    return result.returncode


try:
    assert run("green-before") == 0
    source.write_bytes(original.replace(needle, broken_route))
    assert run("red-original-route") == 1
    red = (evidence / "red-original-route.log").read_text()
    assert "exporter must read adjusted CIBC cash" in red
finally:
    source.write_bytes(original)
    assert source.read_bytes() == original
assert run("green-restored") == 0
(evidence / "gate.xml").unlink()
(evidence / "break-proof.json").write_text(
    json.dumps(
        {
            "command": command,
            "mutation": "Restore original configured workbook route at the exporter boundary",
            "byte_identical_restoration": source.read_bytes() == original,
            "results": results,
            "test_sha256": hashlib.sha256(
                (root / "tests/pipeline/test_cprs_screenshot_generation.py").read_bytes()
            ).hexdigest(),
        },
        indent=2,
    )
    + "\n"
)
