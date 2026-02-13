"""Assemble a versioned Counter Risk release bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

RELEASE_NAME_PREFIX = "counter-risk"
EXECUTABLE_BASENAME = "counter-risk"


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
        default=root / "release",
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
        if "__pycache__" in src_path.parts or src_path.suffix.lower() == ".pyc":
            continue
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
                'set "SCRIPT_DIR=%~dp0"',
                'set "EXE_PATH=%SCRIPT_DIR%bin\\counter-risk.exe"',
                'if exist "%EXE_PATH%" (',
                '  "%EXE_PATH%" %*',
                "  exit /b %ERRORLEVEL%",
                ")",
                'set "EXE_PATH=%SCRIPT_DIR%bin\\counter-risk"',
                '"%EXE_PATH%" %*',
                "exit /b %ERRORLEVEL%",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return runner_path


def _copy_templates(root: Path, bundle_dir: Path) -> list[Path]:
    template_sources = [root / "templates", root / "tests" / "fixtures"]
    template_candidates: dict[str, list[Path]] = {}

    for src_dir in template_sources:
        if not src_dir.exists():
            continue
        for src_path in sorted(path for path in src_dir.rglob("*.pptx") if path.is_file()):
            template_candidates.setdefault(src_path.name, []).append(src_path)

    duplicate_templates = {
        filename: paths
        for filename, paths in template_candidates.items()
        if len(paths) > 1
    }
    if duplicate_templates:
        conflict_lines = [
            "Template filename conflicts detected across template sources:",
        ]
        for filename in sorted(duplicate_templates):
            sources = ", ".join(str(path) for path in sorted(duplicate_templates[filename]))
            conflict_lines.append(f"- {filename}: {sources}")
        raise ValueError("\n".join(conflict_lines))

    copied: list[Path] = []
    destination = bundle_dir / "templates"
    destination.mkdir(parents=True, exist_ok=True)

    for filename in sorted(template_candidates):
        src_path = template_candidates[filename][0]
        dst_path = destination / filename
        shutil.copy2(src_path, dst_path)
        copied.append(dst_path)
    return copied


def _copy_fixture_artifacts(root: Path, bundle_dir: Path) -> list[Path]:
    fixtures_src = root / "tests" / "fixtures"
    fixture_suffixes = {".xlsx", ".pptx", ".csv", ".tsv", ".json", ".parquet"}
    return _copy_tree_filtered(fixtures_src, bundle_dir / "fixtures", suffixes=fixture_suffixes)


def _executable_filename(*, for_windows: bool | None = None) -> str:
    is_windows = for_windows if for_windows is not None else sys.platform.startswith("win")
    if is_windows:
        return f"{EXECUTABLE_BASENAME}.exe"
    return EXECUTABLE_BASENAME


def _expected_pyinstaller_output(root: Path, *, for_windows: bool | None = None) -> Path:
    return root / "dist" / RELEASE_NAME_PREFIX / _executable_filename(for_windows=for_windows)


def _run_pyinstaller(root: Path, spec_path: Path) -> None:
    result = subprocess.run(
        ["pyinstaller", "-y", str(spec_path)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        details = "\n".join(part for part in [stdout, stderr] if part)
        raise ValueError(
            f"PyInstaller failed with exit code {result.returncode} while building '{spec_path}'."
            + (f"\n{details}" if details else "")
        )


def _copy_bundled_executable(root: Path, bundle_dir: Path) -> Path:
    spec_path = root / "release.spec"
    if not spec_path.is_file():
        raise ValueError(f"Missing required PyInstaller spec file: '{spec_path}'.")

    _run_pyinstaller(root, spec_path)
    built_executable = _expected_pyinstaller_output(root)
    if not built_executable.is_file():
        raise ValueError(
            "PyInstaller build completed but expected executable was not found at "
            f"'{built_executable}'."
        )

    bundle_bin_dir = bundle_dir / "bin"
    bundle_bin_dir.mkdir(parents=True, exist_ok=True)
    destination = bundle_bin_dir / built_executable.name
    shutil.copy2(built_executable, destination)
    return destination


def _write_readme(bundle_dir: Path, version: str) -> Path:
    readme_path = bundle_dir / "README_HOW_TO_RUN.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Counter Risk Release - How to run",
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


def _validate_version_manifest_consistency(bundle_dir: Path) -> None:
    version_value = (bundle_dir / "VERSION").read_text(encoding="utf-8").strip()
    manifest_value = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))["version"]
    if version_value != manifest_value:
        raise ValueError(
            "Release metadata mismatch: VERSION file value "
            f"'{version_value}' does not match manifest version '{manifest_value}'."
        )


def assemble_release(version: str, output_dir: Path, *, force: bool = False) -> Path:
    """Create the versioned release bundle and return its path."""

    root = repository_root()
    bundle_dir = output_dir / version
    if bundle_dir.exists():
        if not force:
            raise ValueError(
                f"Release directory already exists: '{bundle_dir}'. Use --force to replace it."
            )
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied: dict[str, list[Path]] = {}
    copied["templates"] = _copy_templates(root, bundle_dir)
    copied["fixtures"] = _copy_fixture_artifacts(root, bundle_dir)

    config_src = root / "config"
    copied["config"] = _copy_tree_filtered(
        config_src,
        bundle_dir / "config",
        suffixes={".yml", ".yaml", ".json"},
    )
    copied["executable"] = [_copy_bundled_executable(root, bundle_dir)]

    version_file = bundle_dir / "VERSION"
    version_file.write_text(f"{version}\n", encoding="utf-8")
    copied["version"] = [version_file]

    runner_file = _create_runner_file(bundle_dir)
    copied["runner"] = [runner_file]

    readme_file = _write_readme(bundle_dir, version)
    copied["readme"] = [readme_file]

    manifest_file = _write_manifest(bundle_dir, version, copied)
    copied["manifest"] = [manifest_file]
    _validate_version_manifest_consistency(bundle_dir)

    return bundle_dir


def run_release(
    *,
    version: str | None = None,
    version_file: Path | None = None,
    output_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Assemble a release bundle using explicit runtime parameters."""

    root = repository_root()
    resolved_version_file = version_file or (root / "VERSION")
    resolved_output_dir = output_dir or (root / "release")
    resolved_version = read_version(version, resolved_version_file)
    return assemble_release(resolved_version, resolved_output_dir, force=force)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for release bundle assembly."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        bundle_dir = run_release(
            version=args.version,
            version_file=args.version_file,
            output_dir=args.output_dir,
            force=args.force,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Release bundle created at: {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
