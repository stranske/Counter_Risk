"""Reproduce serialized boundary proofs; restore all source bytes even on failure.

Run with the selected repository Python. Raw output/originals stay in a temporary
directory outside the checkout; public logs explicitly map raw to normalized hashes.
"""

from __future__ import annotations

import getpass
import hashlib
import html
import json
import os
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "f8871b2971d34b6d1b26df17fea1f9ef9cf079df"
PUBLIC = Path(__file__).resolve().parent
RAW = Path(tempfile.mkdtemp(prefix="counter-risk-1160-"))
PARSER = ROOT / "src/counter_risk/parsers/cprs_fcm.py"
PIPELINE = ROOT / "src/counter_risk/pipeline/run.py"
LIMITS = ROOT / "src/counter_risk/compute/limits.py"
TEST = "tests/compute/test_limits.py"
SOURCES = (PARSER, PIPELINE, LIMITS)
ORIGINALS = {path: path.read_bytes() for path in SOURCES}
MAPPING: list[dict[str, str]] = []
RESULTS: list[dict[str, object]] = []


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def publish(name: str, data: bytes) -> None:
    (RAW / name).write_bytes(data)
    text = data.decode()
    for local, portable in (
        (str(ROOT), "<REPO>"),
        (str(RAW), "<RAW>"),
        (sys.executable, "<PYTHON>"),
        (sys.prefix, "<PYTHON_ENV>"),
        (tempfile.gettempdir(), "<TMP>"),
        (str(Path.home()), "<HOME>"),
        (socket.gethostname(), "<HOST>"),
        (f"pytest-of-{getpass.getuser()}", "pytest-of-<USER>"),
    ):
        text = text.replace(local, portable)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    if name.endswith(".xml"):
        for token in (
            "<REPO>",
            "<RAW>",
            "<PYTHON>",
            "<PYTHON_ENV>",
            "<TMP>",
            "<HOME>",
            "<HOST>",
            "<USER>",
        ):
            text = text.replace(token, html.escape(token))
        ET.fromstring(text)
    normalized = text.encode()
    (PUBLIC / name).write_bytes(normalized)
    MAPPING.append(
        {"artifact": name, "raw_sha256": digest(data), "public_sha256": digest(normalized)}
    )


def run_suite(name: str, selection: str | None, failures: int, count: int) -> None:
    xml_path = RAW / f"{name}.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        TEST,
        "-q",
        "-m",
        "not slow",
        f"--junitxml={xml_path}",
    ]
    if selection:
        command += ["-k", selection]
    env = dict(os.environ, PYTHONPYCACHEPREFIX=str(RAW / f"cache-{name}"))
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=True)
        code, output = result.returncode, result.stdout + result.stderr
    except subprocess.CalledProcessError as exc:
        code, output = exc.returncode, exc.stdout + exc.stderr
    publish(f"{name}.log", output)
    publish(f"{name}.xml", xml_path.read_bytes())
    tree = ET.parse(xml_path)
    suites = list(tree.getroot().iter("testsuite"))
    assert sum(int(s.get("tests", "0")) for s in suites) == count
    assert sum(int(s.get("errors", "0")) for s in suites) == 0
    assert sum(int(s.get("skipped", "0")) for s in suites) == 0
    failed = list(tree.getroot().iter("failure"))
    assert len(failed) == failures, (name, code, len(failed))
    assert code == (1 if failures else 0), (name, code)
    assert all("AssertionError" in f.get("message", "") + (f.text or "") for f in failed)
    RESULTS.append(
        {"name": name, "command": command, "tests": count, "failures": failures, "exit": code}
    )


def mutate(name: str, path: Path, before: str, after: str, selection: str, count: int) -> None:
    original = ORIGINALS[path]
    text = original.decode()
    assert text.count(before) == 1, name
    changed = text.replace(before, after).encode()
    publish(
        f"{name}-mutation.json",
        json.dumps(
            {
                "source": str(path.relative_to(ROOT)),
                "before": before,
                "after": after,
                "original_sha256": digest(original),
                "mutant_sha256": digest(changed),
            },
            indent=2,
        ).encode(),
    )
    try:
        path.write_bytes(changed)
        run_suite(f"{name}-red", selection, count, count)
    finally:
        path.write_bytes(original)
    assert path.read_bytes() == original
    run_suite(f"{name}-restored-green", selection, 0, count)


def main() -> None:
    # Restoration alone cannot prove the checkout started at the accepted source.
    subprocess.run(
        ["git", "diff", "--exit-code", BASELINE, "--", "src"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    for path, data in ORIGINALS.items():
        (RAW / path.name).write_bytes(data)
    checkout = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True, text=True
    ).stdout.strip()
    publish(
        "baseline.json",
        json.dumps(
            {
                "baseline_commit": BASELINE,
                "checkout_commit": checkout,
                "python": sys.executable,
                "python_version": sys.version,
                "sources": {
                    str(p.relative_to(ROOT)): digest(data) for p, data in ORIGINALS.items()
                },
                "test_sha256": digest((ROOT / TEST).read_bytes()),
            },
            indent=2,
        ).encode(),
    )
    run_suite("baseline-green", None, 0, 101)
    mutate(
        "parser-futures-identity",
        PARSER,
        '"fcm": fcm,\n                "clearing_house": clearing_house,',
        '"fcm": "Lost FCM",\n                "clearing_house": "Lost House",',
        "boundary_audit_alias_only",
        2,
    )
    mutate(
        "limit-alias-resolution",
        LIMITS,
        'if entity_type in {"counterparty", "fcm", "clearing_house"}:',
        'if entity_type == "counterparty":',
        "boundary_audit_alias_only",
        2,
    )
    # Restore the actual pre-#1170 builder, rather than an invented substitute.
    old_source = subprocess.run(
        [
            "git",
            "show",
            "c06f1cda48848a26e1e1a5c53421bea6a2728886^:src/counter_risk/pipeline/run.py",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    start = "def _build_limit_exposure_rows("
    end = "\ndef _compute_and_write_limit_breaches("
    old_builder = old_source[old_source.index(start) : old_source.index(end)]
    current = ORIGINALS[PIPELINE].decode()
    builder = current[current.index(start) : current.index(end)]
    mutate("original-overlap-builder", PIPELINE, builder, old_builder, "boundary_audit_overlap", 1)
    mutate(
        "parser-totals-identity",
        PARSER,
        '"counterparty": counterparty,\n                "TIPS":',
        '"counterparty": counterparty + " Lost",\n                "TIPS":',
        "boundary_audit_overlap or boundary_audit_partitioned",
        2,
    )
    start = "def _build_concentration_exposure_rows("
    end = "\ndef _compute_and_write_concentration_metrics("
    section = current[current.index(start) : current.index(end)]
    mutate(
        "concentration-partition",
        PIPELINE,
        section,
        section.replace('"variant": variant,', '"variant": "all_programs",'),
        "boundary_audit_partitioned",
        1,
    )
    run_suite("acceptance-green", None, 0, 101)
    assert all(p.read_bytes() == data for p, data in ORIGINALS.items())
    subprocess.run(
        ["git", "diff", "--exit-code", BASELINE, "--", "src"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    publish(
        "results.json",
        json.dumps(
            {
                "baseline_commit": BASELINE,
                "checkout_commit": checkout,
                "rounds": RESULTS,
                "restored_byte_identical": True,
                "production_matches_git_baseline": True,
                "source_hashes_after": {
                    str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in SOURCES
                },
            },
            indent=2,
        ).encode(),
    )
    (PUBLIC / "hash-mapping.json").write_text(json.dumps(MAPPING, indent=2) + "\n")
    print(f"Raw logs, JUnit and originals: {RAW}")


if __name__ == "__main__":
    try:
        main()
    finally:
        for source, content in ORIGINALS.items():
            source.write_bytes(content)
