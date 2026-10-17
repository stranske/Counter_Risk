import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
source = root / "src/counter_risk/pipeline/run.py"
original = source.read_bytes()
out = root / "docs/evidence/issue-1159"
needle = b"    for variant, workbook_path in workbook_paths.items():\n"
broken = (
    b"    for variant, workbook_field in _CPRS_SCREENSHOT_WORKBOOK_FIELD_BY_VARIANT.items():\n"
    b"        workbook_path = getattr(config, workbook_field)\n"
    b"        if workbook_path is None:\n"
    b"            continue\n"
)
cmd = [
    sys.executable,
    "-m",
    "pytest",
    "tests/pipeline/test_run_pipeline.py",
    "-k",
    "screenshot and 1234567",
    "--junitxml=" + str(out / "pipeline-control.xml"),
]
results = {}


def run(phase):
    r = subprocess.run(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (phase + ".log")).write_bytes(r.stdout)
    (out / (phase + ".xml")).write_bytes((out / "pipeline-control.xml").read_bytes())
    results[phase] = {
        "exit_code": r.returncode,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    print(phase, r.returncode, flush=True)
    return r


try:
    assert original.count(needle) == 1
    source.write_bytes(original.replace(needle, broken))
    red = run("pipeline-red-original-route")
    assert red.returncode == 1
    assert b"exporter input disagrees with authoritative cash" in red.stdout
finally:
    source.write_bytes(original)
assert source.read_bytes() == original
assert run("pipeline-green-restored").returncode == 0
(out / "pipeline-control.xml").unlink()
(out / "pipeline-break-proof.json").write_text(
    json.dumps({"command": cmd, "results": results, "byte_identical_restoration": True}, indent=2)
    + "\n"
)
