#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 <workflow_file> <ref> [artifact_prefix]" >&2
  exit 2
fi

WORKFLOW_FILE="$1"
REF_NAME="$2"
ARTIFACT_PREFIX="${3:-release-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR_SCRIPT="${SCRIPT_DIR}/validate_release_workflow_yaml.py"

WORKFLOW_PATH="${WORKFLOW_FILE}"
if [ ! -f "${WORKFLOW_PATH}" ] && [ -f ".github/workflows/${WORKFLOW_FILE}" ]; then
  WORKFLOW_PATH=".github/workflows/${WORKFLOW_FILE}"
fi

if [ ! -f "${WORKFLOW_PATH}" ]; then
  echo "[ERROR] Workflow file not found: ${WORKFLOW_FILE}" >&2
  echo "[ERROR] Expected path: ${WORKFLOW_PATH}" >&2
  if [ -f "${REPO_ROOT}/docs/release.yml.draft" ]; then
    echo "[ERROR] Draft workflow exists at docs/release.yml.draft and must be promoted to .github/workflows/release.yml before dispatch verification." >&2
  fi
  exit 1
fi

if [[ "${WORKFLOW_PATH}" == *"/docs/release.yml.draft" ]] || [[ "${WORKFLOW_PATH}" == "docs/release.yml.draft" ]]; then
  echo "[ERROR] docs/release.yml.draft cannot be dispatched directly; copy it to .github/workflows/release.yml first." >&2
  exit 1
fi

if ! python "${VALIDATOR_SCRIPT}" "${WORKFLOW_PATH}"; then
  echo "[ERROR] Workflow validation failed for ${WORKFLOW_PATH}." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "[ERROR] GitHub CLI (gh) is required but was not found on PATH." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "[ERROR] GitHub CLI is not authenticated. Run: gh auth login" >&2
  exit 1
fi

echo "Triggering workflow '${WORKFLOW_FILE}' on ref '${REF_NAME}'..."
gh workflow run "${WORKFLOW_FILE}" --ref "${REF_NAME}"

echo "Resolving the latest workflow_dispatch run..."
run_json="$(
  gh run list \
    --workflow "${WORKFLOW_FILE}" \
    --branch "${REF_NAME}" \
    --event workflow_dispatch \
    --limit 1 \
    --json databaseId,status,conclusion,url
)"

run_id="$(
  python -c 'import json,sys; data=json.loads(sys.stdin.read() or "[]"); print(data[0].get("databaseId","") if data else "")' \
    <<<"${run_json}"
)"

if [ -z "${run_id}" ]; then
  echo "[ERROR] Could not find a workflow_dispatch run for ${WORKFLOW_FILE} on ${REF_NAME}." >&2
  exit 1
fi

echo "Watching run ${run_id} until completion..."
gh run watch "${run_id}" --exit-status

echo "Checking uploaded artifacts for run ${run_id}..."
view_json="$(gh run view "${run_id}" --json conclusion,artifacts,url)"
has_expected_artifact="$(
  ARTIFACT_PREFIX="${ARTIFACT_PREFIX}" python -c '
import json
import os
import sys

data = json.loads(sys.stdin.read() or "{}")
if data.get("conclusion") != "success":
    print("false")
    raise SystemExit

prefix = os.environ["ARTIFACT_PREFIX"]
artifacts = data.get("artifacts") or []
print("true" if any((item.get("name") or "").startswith(prefix) for item in artifacts) else "false")
' <<<"${view_json}"
)"

if [ "${has_expected_artifact}" != "true" ]; then
  echo "[ERROR] Run ${run_id} completed but no artifact matched prefix '${ARTIFACT_PREFIX}'." >&2
  exit 1
fi

echo "Workflow dispatch verified successfully for run ${run_id}."
