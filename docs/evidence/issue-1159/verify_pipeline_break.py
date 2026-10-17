"""Capture a fresh stale-cash mutation proof without rewriting historic evidence."""

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


def cash_failures(xml_path: Path) -> list[str]:
    """Inspect JUnit's reported assertion message, never traceback source lines."""
    return [
        failure.attrib["message"]
        for failure in ET.parse(xml_path).iter("failure")
        if failure.get("message", "").partition("\n")[0]
        == "AssertionError: exporter input disagrees with authoritative cash"
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent
        / ("review-proof-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")),
    )
    out = parser.parse_args().output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = root / "src/counter_risk/pipeline/run.py"
    original = source.read_bytes()
    needle = b"    for variant, workbook_path in workbook_paths.items():\n"
    broken = (
        b"    for variant, workbook_field in _CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT.items():\n"
        b"        workbook_path = getattr(config, workbook_field)\n"
        b"        if workbook_path is None:\n"
        b"            continue\n"
    )
    results = {}

    def run(phase: str) -> int:
        xml_path = out / (phase + ".xml")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/pipeline/test_run_pipeline.py",
            "-k",
            "screenshot and 1234567",
            "--junitxml=" + str(xml_path),
        ]
        record = {
            "argv": cmd,
            "cwd": str(root),
            "started_at": datetime.now(UTC).isoformat(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "test_sha256": hashlib.sha256(
                (root / "tests/pipeline/test_run_pipeline.py").read_bytes()
            ).hexdigest(),
        }
        (out / (phase + "-invocation.json")).write_text(json.dumps(record, indent=2) + "\n")
        with (out / (phase + ".log")).open("wb") as log:
            result = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        record.update(
            exit_code=result.returncode,
            finished_at=datetime.now(UTC).isoformat(),
            junit_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest(),
            log_sha256=hashlib.sha256((out / (phase + ".log")).read_bytes()).hexdigest(),
        )
        results[phase] = record
        print(phase, result.returncode, flush=True)
        return result.returncode

    try:
        assert original.count(needle) == 1
        source.write_bytes(original.replace(needle, broken))
        assert run("red-original-route") == 1
        messages = cash_failures(out / "red-original-route.xml")
        assert messages, "Mutation did not fail at the authoritative cash assertion"
        results["red-original-route"]["actual_cash_failure_messages"] = messages
    finally:
        source.write_bytes(original)
        (out / "proof.json").write_text(
            json.dumps(
                {"results": results, "byte_identical_restoration": source.read_bytes() == original},
                indent=2,
            )
            + "\n"
        )
    assert source.read_bytes() == original
    assert run("green-restored") == 0
    (out / "proof.json").write_text(
        json.dumps({"results": results, "byte_identical_restoration": True}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
