#!/usr/bin/env bash

set -u

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <bundle_dir>" >&2
  exit 2
fi

BUNDLE_DIR="$1"
FAILURES=0

fail() {
  local message="$1"
  echo "[ERROR] ${message}" >&2
  FAILURES=$((FAILURES + 1))
}

check_file() {
  local path="$1"
  local description="$2"
  if [ ! -f "$path" ]; then
    fail "Missing ${description}: ${path}"
  fi
}

check_dir() {
  local path="$1"
  local description="$2"
  if [ ! -d "$path" ]; then
    fail "Missing ${description}: ${path}"
  fi
}

check_file "${BUNDLE_DIR}/VERSION" "VERSION file"
check_file "${BUNDLE_DIR}/manifest.json" "manifest file"
check_dir "${BUNDLE_DIR}/templates" "templates directory"
check_file "${BUNDLE_DIR}/config/fixture_replay.yml" "default config file"
check_file "${BUNDLE_DIR}/run_counter_risk.cmd" "runner command file"

readme_file=""
for candidate in "${BUNDLE_DIR}"/README*; do
  if [ -f "$candidate" ]; then
    readme_file="$candidate"
    break
  fi
done

if [ -z "$readme_file" ]; then
  fail "Missing README file in bundle root"
elif ! grep -q "How to run" "$readme_file"; then
  fail "README file does not contain required text 'How to run': ${readme_file}"
fi

platform="$(uname -s 2>/dev/null || echo unknown)"
case "$platform" in
  CYGWIN*|MINGW*|MSYS*)
    expected_executable="${BUNDLE_DIR}/bin/counter-risk.exe"
    ;;
  *)
    expected_executable="${BUNDLE_DIR}/bin/counter-risk"
    ;;
esac

check_file "$expected_executable" "built executable"

if [ "$FAILURES" -ne 0 ]; then
  echo "Bundle validation failed with ${FAILURES} issue(s)." >&2
  exit 1
fi

echo "Bundle validation passed for ${BUNDLE_DIR}."
