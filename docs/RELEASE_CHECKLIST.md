# Release Checklist

## Build the executable with PyInstaller

```bash
pyinstaller -y release.spec
```

Expected output:

- Linux/macOS: `dist/counter-risk/counter-risk`
- Windows: `dist/counter-risk/counter-risk.exe`

## Assemble the versioned release bundle

```bash
python -m counter_risk.build.release --version-file VERSION --output-dir release --force
```

This creates `release/<version>/...` including the bundled executable and metadata files.

## Validate bundle contents

```bash
VERSION="$(cat VERSION | tr -d '\n\r')"
BUNDLE_DIR="release/${VERSION}"
test -f "${BUNDLE_DIR}/VERSION"
test -f "${BUNDLE_DIR}/manifest.json"
test -d "${BUNDLE_DIR}/templates"
test -f "${BUNDLE_DIR}/config/fixture_replay.yml"
test -f "${BUNDLE_DIR}/run_counter_risk.cmd"
test -f "${BUNDLE_DIR}/README_HOW_TO_RUN.md"
test -f "${BUNDLE_DIR}/bin/counter-risk" || test -f "${BUNDLE_DIR}/bin/counter-risk.exe"
```

## Run the release workflow in CI

Trigger from GitHub CLI:

```bash
gh workflow run release.yml --ref <branch-or-tag>
```

Check status and logs:

```bash
gh run list --workflow release.yml
gh run watch
```

Or use the helper script to trigger, wait, and verify the release artifact:

```bash
scripts/verify_release_workflow_dispatch.sh release.yml <branch-or-tag>
```

## Expected bundle contents

- `bin/counter-risk` (or `bin/counter-risk.exe` on Windows)
- `run_counter_risk.cmd`
- `templates/`
- `config/fixture_replay.yml` (default config file)
- `VERSION`
- `manifest.json`
- `README_HOW_TO_RUN.md` (title includes `How to run`)
