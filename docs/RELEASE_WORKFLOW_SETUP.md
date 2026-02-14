# Release Workflow Setup

This repository uses `pyproject.toml` for dependency installation and
`python -m counter_risk.build.release --version-file VERSION --output-dir release --force`
for release bundle assembly.

A draft release workflow is provided at `docs/release.yml.draft`.

## Promote the Draft Workflow

1. Copy the draft into the workflow location:
   `cp docs/release.yml.draft .github/workflows/release.yml`
2. Commit and push the new workflow file.
3. Trigger it manually with `workflow_dispatch` and verify a `release/<version>/` artifact uploads.
   Recommended command: `scripts/verify_release_workflow_dispatch.sh release.yml <branch-or-tag>`

Before dispatching, you can run static checks locally:
`python scripts/validate_release_workflow_yaml.py docs/release.yml.draft`

## Optional Triggers

After validating manual runs, optionally add `push` and/or tag triggers in
`.github/workflows/release.yml`.
