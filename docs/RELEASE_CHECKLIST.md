# Release Checklist

## Prerequisites

- Run all steps on **Windows** if producing an operator bundle — PyInstaller
  produces a platform-native binary. A Windows build is required for the
  work PC deployment.
- Ensure `assets/templates/counter_risk_template.xlsm` is present and up to
  date. The release assembler builds `counter_risk_runner.xlsm` from this
  template automatically.

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

This creates `release/<version>/...` including:
- The bundled executable
- `counter_risk_runner.xlsm` built from `assets/templates/counter_risk_template.xlsm`
  with version metadata injected
- Remote trigger scripts and documentation
- Config, templates, fixtures, and metadata files

## Validate bundle contents

```bash
VERSION="$(cat VERSION | tr -d '\n\r')"
BUNDLE_DIR="release/${VERSION}"
test -f "${BUNDLE_DIR}/VERSION"
test -f "${BUNDLE_DIR}/manifest.json"
test -d "${BUNDLE_DIR}/templates"
test -f "${BUNDLE_DIR}/config/fixture_replay.yml"
test -f "${BUNDLE_DIR}/run_counter_risk.cmd"
test -f "${BUNDLE_DIR}/counter_risk_runner.xlsm"
test -f "${BUNDLE_DIR}/request_counter_risk_remote.cmd"
test -f "${BUNDLE_DIR}/process_counter_risk_remote.cmd"
test -f "${BUNDLE_DIR}/remote_trigger_testing.md"
test -f "${BUNDLE_DIR}/README_HOW_TO_RUN.md"
test -f "${BUNDLE_DIR}/bin/counter-risk" || test -f "${BUNDLE_DIR}/bin/counter-risk.exe"
```

## Update config paths for the target environment

The config YAML files (`config/all_programs.yml`, `config/ex_trend.yml`,
`config/trend.yml`) contain paths to source data files. Before deploying to
the work PC, update these to point to the actual data location:

```yaml
# Example — replace with real paths for the operator's machine
mosers_all_programs_xlsx: "N:\\Data\\MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx"
output_root: "C:\\CounterRisk\\runs\\all_programs"
```

Config files can be edited directly in `release/<version>/config/` after
assembly without rebuilding.

## Validate Runner XLSM macros manually (Windows Excel)

Use the manual checklist in [runner_xlsm_macro_manual_verification.md](runner_xlsm_macro_manual_verification.md).

Minimum required release validation:

1. Inspect the built workbook in the bundle:
   ```
   release/<version>/counter_risk_runner.xlsm
   ```
2. Follow the **Manual Macro/Button Check** section and record results.
3. To test a version bump, build a fresh workbook explicitly:
   ```bash
   python -m counter_risk.build.xlsm \
     --template-path assets/templates/counter_risk_template.xlsm \
     --output-path dist/counter_risk_runner.vnext.xlsm \
     --version 1.2.4
   ```
4. Follow the **Version Bump Regression Check** section and record results.

## Confirm macro trust on the work PC

Before the first run on the operator machine, confirm one of:
- The bundle folder is added to Excel's **Trusted Locations**, or
- The workbook is signed with a trusted code-signing certificate, or
- The operator is prompted and clicks **Enable Content** on first open

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
- `counter_risk_runner.xlsm` — operator Excel entrypoint (versioned)
- `run_counter_risk.cmd` — fallback CLI launcher
- `request_counter_risk_remote.cmd` — remote request submission script
- `process_counter_risk_remote.cmd` — remote request worker script
- `remote_trigger_testing.md` — remote trigger flow documentation
- `templates/` — PPT and XLSM output templates
- `config/` — workflow YAML configs (update paths before deployment)
- `fixtures/` — test fixture artifacts
- `VERSION`
- `manifest.json`
- `README_HOW_TO_RUN.md`
