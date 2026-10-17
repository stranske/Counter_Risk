"""Publish the issue-1162 JUnit evidence without suite hostname metadata.

Original execution bindings remain intact; publication has its own digest.
This is specific to this repository's report-date review evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.parsers import expat

TRANSFORMATION = "remove-junit-suite-hostname-v1"
_START_TAG = re.compile(rb"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")
_ATTRIBUTE = re.compile(rb"\s+([\w:.-]+)\s*=\s*(?:\"[^\"]*\"|'[^']*')")


def remove_suite_hostnames(data: bytes) -> tuple[bytes, int]:
    """Remove only real suite hostname attributes, preserving every other byte."""
    parser = expat.ParserCreate()
    removals: list[tuple[int, int]] = []

    def start_element(name: str, attributes: dict[str, str]) -> None:
        if name not in {"testsuite", "testsuites"} or "hostname" not in attributes:
            return
        offset = parser.CurrentByteIndex
        tag = _START_TAG.match(data, offset)
        if tag is None:
            raise ValueError("Unable to locate JUnit suite start tag")
        attribute = next(
            (match for match in _ATTRIBUTE.finditer(tag.group()) if match[1] == b"hostname"),
            None,
        )
        if attribute is None:
            raise ValueError("Unable to locate JUnit suite hostname attribute")
        removals.append((offset + attribute.start(), offset + attribute.end()))

    def reject_doctype(*_args: object) -> None:
        raise ValueError("JUnit evidence must not contain a document type declaration")

    parser.StartElementHandler = start_element
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.Parse(data, True)
    published = data
    for start, end in reversed(removals):
        published = published[:start] + published[end:]
    return published, len(removals)


def publish_junit(path: Path) -> None:
    """Bind the raw and published hashes without rewriting execution provenance."""
    binding_path = path.with_suffix(".binding.json")
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    publication = binding.get("junit_publication")
    if publication is not None:
        if publication["published_sha256"] != raw_hash:
            raise ValueError(f"Published JUnit hash mismatch: {path}")
        return
    if binding["junit_sha256"] != raw_hash:
        raise ValueError(f"Original JUnit hash mismatch: {path}")
    published, count = remove_suite_hostnames(raw)
    binding["junit_publication"] = {
        "transformation": TRANSFORMATION,
        "original_sha256": raw_hash,
        "published_sha256": hashlib.sha256(published).hexdigest(),
        "removed_attributes": count,
    }
    path.write_bytes(published)
    binding_path.write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    evidence_dir = Path(__file__).resolve().parents[1] / "docs/evidence/issue-1162"
    for report in sorted(evidence_dir.glob("*.xml")):
        publish_junit(report)
