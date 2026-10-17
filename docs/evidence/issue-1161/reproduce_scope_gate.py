"""Serialize original-scope RED and byte-identical restore GREEN for #1161.

Run from the repository root with the selected Python interpreter. Artifacts are
written beside this script. No assertions or guards are removed from the tests.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

BASE = "4c4a11d36b7a368524b26eee30d120efe3cb591b"
SOURCE = Path("src/counter_risk/pipeline/run.py")
TEST = Path("tests/compute/test_limits.py")
OUT = Path(__file__).resolve().parent
NODE = str(TEST) + "::test_all_programs_absolute_cap_ignores_overlapping_variants"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(name: str, args: list[str], expected_rc: int) -> dict[str, object]:
    xml = OUT / f"{name}.xml"
    argv = [sys.executable, "-m", "pytest", "-vv", *args, f"--junitxml={xml}"]
    source_before, test_before = SOURCE.read_bytes(), TEST.read_bytes()
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    (OUT / f"{name}.log").write_bytes(result.stdout)
    root = ET.parse(xml).getroot()
    cases = root.findall(".//testcase")
    failures = root.findall(".//failure")
    errors = root.findall(".//error")
    record: dict[str, object] = {
        "argv": argv,
        "started_at": started,
        "exit_code": result.returncode,
        "source_sha256": sha(source_before),
        "test_sha256": sha(test_before),
        "pipeline_test_sha256": sha(Path("tests/pipeline/test_run_pipeline.py").read_bytes()),
        "junit_sha256": sha(xml.read_bytes()),
        "console_sha256": sha(result.stdout),
        "tests": len(cases),
        "failures": len(failures),
        "errors": len(errors),
    }
    (OUT / f"{name}.binding.json").write_text(json.dumps(record, indent=2) + "\n")
    assert SOURCE.read_bytes() == source_before
    assert TEST.read_bytes() == test_before
    assert result.returncode == expected_rc, result.stdout.decode()
    assert len(cases) > 0 and not errors
    if expected_rc:
        assert len(cases) == len(failures) == 2
        assert b"350000000.0" in result.stdout
        assert b"450000000.0" in result.stdout
    else:
        assert not failures
    return record


def main() -> None:
    restored = SOURCE.read_bytes()
    test_bytes = TEST.read_bytes()
    original = subprocess.check_output(["git", "show", f"{BASE}:{SOURCE}"])
    start = b"def _build_limit_exposure_rows("
    end = b"def _compute_and_write_limit_breaches("
    broken = (
        restored[: restored.index(start)]
        + original[original.index(start) : original.index(end)]
        + restored[restored.index(end) :]
    )
    # The only production change is the scope-selection builder. This is the
    # original implementation, with original alias/canonicalization code intact.
    assert broken == original
    records = [run("green-before", [NODE], 0)]
    try:
        SOURCE.write_bytes(broken)
        (OUT / "original-builder.txt").write_bytes(
            original[original.index(start) : original.index(end)]
        )
        records.append(run("original-scope-red", [NODE], 1))
    finally:
        SOURCE.write_bytes(restored)
    assert SOURCE.read_bytes() == restored
    assert TEST.read_bytes() == test_bytes
    records.append(run("restored-green", [NODE], 0))
    records.append(
        run(
            "acceptance",
            [
                str(TEST),
                "tests/pipeline/test_run_pipeline.py",
                "-k",
                "all_programs_ and not apply_daily and not daily_holdings and not generates_all_programs",
            ],
            0,
        )
    )
    (OUT / "proof.json").write_text(
        json.dumps(
            {
                "base_commit": BASE,
                "restored_byte_identical": True,
                "test_byte_identical": True,
                "restore_sha256": sha(restored),
                "original_source_sha256": sha(original),
                "runs": records,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
