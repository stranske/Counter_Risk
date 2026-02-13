# Operator UX Decision: Monthly Counterparty Risk Runner

## Purpose

This document defines the operator experience for running the monthly counterparty risk process without CLI usage and without repository access. It compares two implementation approaches and records the implementation order, environmental constraints, and operating conventions.

## Monthly Operator Steps (No CLI)

1. Open the runner tool (Excel `Runner.xlsm` or Windows desktop app).
2. Select `As-Of Date` and optional variant (`All Programs`, `Ex Trend`, `Trend`).
3. Click `Run`.
4. Wait for completion and review run status summary.
5. Open the generated output folder from the provided link/button.
6. Verify expected outputs exist:
   - Updated historical workbooks
   - Updated monthly presentation outputs
   - Run manifest
   - Data quality summary
7. Escalate warnings according to operations policy if reconciliation gaps are reported.

## Approach A: Excel Runner (`Runner.xlsm`)

### Technical Requirements

- Microsoft Excel desktop installed on operator machines.
- Macro execution allowed for signed organizational macros.
- Access to the Python runtime/executable packaged for the runner backend, or access to a centrally hosted executable wrapper.
- Read/write access to required input/output shared drive folders.
- Stable mapped drive letter or UNC path configuration matching runner settings.

### User Workflow

1. Open `Runner.xlsm` from the approved shared location.
2. Enable macros (if organizational policy allows signed macro content).
3. Pick `As-Of Date` and variant.
4. Click `Run Monthly Process`.
5. Review completion message and warnings panel.
6. Click `Open Output Folder` to access produced artifacts.

## Approach B: Windows Desktop App

### Technical Requirements

- Windows 10/11 managed endpoint.
- Installed signed desktop application package (MSI or equivalent).
- Bundled runtime (no local Python requirement) preferred.
- Access to required input/output shared drive folders.
- Optional Office interop components if PPT/Excel automation uses local Office installation.

### User Workflow

1. Launch the `Counter Risk Runner` desktop application.
2. Choose `As-Of Date` and variant.
3. Confirm discovered inputs (or pick files when prompted by policy).
4. Click `Run`.
5. Review run status, warnings, and data quality summary.
6. Click `Open Output Folder` to view produced artifacts.

## Pros and Cons Comparison

| Approach | Pros | Cons |
| --- | --- | --- |
| A: Excel `Runner.xlsm` | Fast to deliver in Office-heavy environments; familiar UX for current operators; easy distribution as a single workbook | Depends on macro policy exceptions/signing; Excel-specific fragility; harder long-term maintainability/testability than app UI |
| B: Windows desktop app | Cleaner operator UX; stronger control over validation/logging/versioning; no macro dependency | Higher initial build/packaging effort; formal deployment process required; potentially more IT coordination for updates |

## Environmental and Technical Constraints

### Office Availability

- If local Office (Excel and PowerPoint desktop) is available and supported, both approaches can leverage COM automation for workbook/PPT update steps.
- If Office is unavailable or inconsistently installed, prefer an approach that can run with static output generation and documented fallback behavior.

### Macro Security Policies

- Approach A requires macro policy alignment:
  - Signed VBA project
  - Trusted publisher distribution
  - Execution permitted by group policy
- If macro execution is blocked by policy and no exception is available, Approach A is not viable for operators.

### Network Drive Paths and File Access

- Input and output locations must support both mapped drive and UNC path usage.
- Runner configuration must not assume a user-specific mapped letter only (for example, avoid hard-coding `Z:` without UNC fallback).
- Required permissions:
  - Read access to monthly input folder
  - Read/write access to output folder
  - Read access to historical templates/reference artifacts
- File locking and concurrent access must be handled with clear error messages for operators.

## Implementation Precedence (Order of Adoption)

1. Primary path: **Approach A (Excel `Runner.xlsm`)** for milestone-speed delivery where macro policy permits.
2. Secondary path: **Approach B (Windows desktop app)** as the strategic long-term replacement and/or mandatory fallback when macro policy blocks Approach A.

Decision rule:
- Start with Approach A for quickest operator enablement.
- Move to Approach B when deployment maturity and IT packaging support are available, or immediately if macro constraints make Approach A non-viable.

## Input Discovery Rules

### Standard Date-Based Discovery (Default)

- Given `as_of_date`, the runner searches the standard input root using the monthly folder convention (for example `YYYY-MM` then variant-specific file names).
- The run uses deterministic matching rules in this order:
  1. Exact `as_of_date` filename match
  2. Exact month-end date match within same month
  3. Policy-defined alias pattern match for known source naming variants
- If required files are missing, the run should fail with an operator-readable message listing missing inputs.

### File-Pick Rules (Exception Path)

- File picker is allowed only when date-based discovery fails or when explicitly enabled for backfill/correction runs.
- Selected files must pass schema/name validation before run start.
- The manifest must record that manual selection was used and include selected file paths.

## Output Folder Convention and Naming

- Standard output root: shared drive run-output directory managed by operations.
- Per-run folder name format:
  - `CounterRisk_<as_of_date:YYYY-MM-DD>_<variant>_<run_timestamp:YYYYMMDD_HHMMSS>`
- Required contents:
  - Updated historical workbooks
  - Updated monthly PPT outputs
  - `manifest.json`
  - `data_quality_summary.md` (or `.txt`)

Example:
- `CounterRisk_2026-01-31_AllPrograms_20260205_091530`

## Non-Repo Update Delivery Mechanism

- Operators receive releases from a shared drive `Releases` folder, not from GitHub.
- Each release is a versioned zip package:
  - `CounterRiskRunner_v<major>.<minor>.<patch>.zip`
- Package contents:
  - Runner executable/workbook
  - Required support files/templates
  - `CHANGELOG.md`
  - `README_Operator.md` (install/update instructions)
- Update process:
  1. Operator or IT downloads newest approved versioned zip.
  2. Extracts to approved installation location.
  3. Launches new version and confirms version string in the UI.
  4. Keeps prior version available for rollback until validation is complete.
