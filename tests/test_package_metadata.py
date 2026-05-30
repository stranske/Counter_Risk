"""Packaging metadata should not expose template bootstrap placeholders."""

from __future__ import annotations

import tomllib
from pathlib import Path

from setuptools import find_packages

REPO_ROOT = Path(__file__).resolve().parents[1]


def _project_metadata() -> dict[str, object]:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]


def test_project_metadata_is_counter_risk_specific() -> None:
    project = _project_metadata()

    assert project["name"] == "counter-risk"
    assert project["name"] != "my-project"
    assert "Counterparty" in str(project["description"])

    authors = project["authors"]
    assert isinstance(authors, list)
    assert authors
    serialized = repr(authors)
    assert "Your Name" not in serialized
    assert "your.email@example.com" not in serialized

    urls = project["urls"]
    assert isinstance(urls, dict)
    assert urls["Repository"] == "https://github.com/stranske/Counter_Risk"
    assert "stranske/Template" not in repr(urls)


def test_placeholder_package_is_not_shipped() -> None:
    packages = find_packages(where=str(REPO_ROOT / "src"))

    assert "counter_risk" in packages
    assert "my_project" not in packages
    assert not (REPO_ROOT / "src" / "my_project").exists()
