"""Assemble a versioned Counter Risk release bundle."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

RELEASE_NAME_PREFIX = "counter-risk"


def repository_root() -> Path:
    """Return the repository root from this module location."""

    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for release assembly."""

    root = repository_root()
    parser = argparse.ArgumentParser(prog="counter-risk-release")
    parser.add_argument(
        "--version",
        help="Release version override. If omitted, reads from --version-file.",
    )
    parser.add_argument(
        "--version-file",
        type=Path,
        default=root / "VERSION",
        help="Path to VERSION file used when --version is not provided.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "dist",
        help="Directory where the versioned release folder will be created.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing release directory if it already exists.",
    )
    return parser


def read_version(version_override: str | None, version_file: Path) -> str:
    """Resolve release version from CLI override or VERSION file."""

    if version_override is not None:
        version = version_override.strip()
        if version:
            return version
        raise ValueError("Version override cannot be empty.")

    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(
            f"Unable to read VERSION file '{version_file}'. Pass --version or provide VERSION."
        ) from exc

    if not version:
        raise ValueError(f"VERSION file '{version_file}' is empty.")
    return version


def _copy_tree_filtered(
    src_dir: Path, dst_dir: Path, *, suffixes: set[str] | None = None
) -> list[Path]:
    copied: list[Path] = []
    if not src_dir.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        return copied

    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_path in sorted(path for path in src_dir.rglob("*") if path.is_file()):
        if suffixes is not None and src_path.suffix.lower() not in suffixes:
            continue
        relative = src_path.relative_to(src_dir)
        dst_path = dst_dir / relative
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        copied.append(dst_path)
    return copied


def _create_runner_file(bundle_dir: Path) -> Path:
    runner_path = bundle_dir / "run_counter_risk.cmd"
    runner_path.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal",
                "set SCRIPT_DIR=%~dp0",
                "python \"%SCRIPT_DIR%\\pipeline\\counter_risk_cli.py\" %*",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return runner_path


def _write_readme(bundle_dir: Path, version: str) -> Path:
    readme_path = bundle_dir / "README_HOW_TO_RUN.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Counter Risk Release",
                "",
                f"Version: {version}",
                "",
                "## How to run",
                "1. Copy this entire folder to a working location.",
                "2. Update YAML files in config/ if input paths changed.",
                "3. Double-click run_counter_risk.cmd.",
                "",
                "This bundle was assembled for non-technical operator use.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return readme_path


def _write_manifest(bundle_dir: Path, version: str, copied: dict[str, list[Path]]) -> Path:
    manifest_path = bundle_dir / "manifest.json"
    payload = {
        "release_name": bundle_dir.name,
        "version": version,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "artifacts": {
            key: [str(path.relative_to(bundle_dir)) for path in paths]
            for key, paths in copied.items()
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def assemble_release(version: str, output_dir: Path, *, force: bool = False) -> Path:
    """Create the versioned release bundle and return its path."""

    root = repository_root()
    bundle_dir = output_dir / f"{RELEASE_NAME_PREFIX}-{version}"
    if bundle_dir.exists():
        if not force:
            raise ValueError(
                f"Release directory already exists: '{bundle_dir}'. Use --force to replace it."
            )
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied: dict[str, list[Path]] = {}
    templates_src = root / "templates"
    copied["templates"] = _copy_tree_filtered(
        templates_src,
        bundle_dir / "templates",
        suffixes={".pptx"},
    )

    config_src = root / "config"
    copied["config"] = _copy_tree_filtered(
        config_src,
        bundle_dir / "config",
        suffixes={".yml", ".yaml", ".json"},
    )

    version_file = bundle_dir / "VERSION"
    version_file.write_text(f"{version}\n", encoding="utf-8")
    copied["version"] = [version_file]

    runner_file = _create_runner_file(bundle_dir)
    copied["runner"] = [runner_file]

    readme_file = _write_readme(bundle_dir, version)
    copied["readme"] = [readme_file]

    manifest_file = _write_manifest(bundle_dir, version, copied)
    copied["manifest"] = [manifest_file]

    return bundle_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for release bundle assembly."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        version = read_version(args.version, args.version_file)
        bundle_dir = assemble_release(version, args.output_dir, force=args.force)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Release bundle created at: {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
