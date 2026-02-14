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

if ! command -v gh >/dev/null 2>&1; then
  echo "[ERROR] gh is required but not found on PATH. Please install gh." >&2
  exit 1
fi

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

# Multi-signal platform detection: uname plus Windows-adjacent env vars.
# These env vars vary by shell/runtime:
# - Git Bash / MSYS2: OS=Windows_NT and/or MSYSTEM=MINGW64|MSYS
# - Cygwin: uname CYGWIN* and CYGWIN is often set (value may not contain "CYGWIN")
# - WSL: WSL_DISTRO_NAME is set, but userspace is Linux so we keep non-.exe expectation
platform="$(uname -s 2>/dev/null || true)"
if [ -z "$platform" ]; then
  platform="unknown"
fi

os_env="${OS-}"
msystem_env="${MSYSTEM-}"
cygwin_env="${CYGWIN-}"
mingw_env="${MINGW-}"
wsl_distro_env="${WSL_DISTRO_NAME-}"
ostype_env="${OSTYPE-}"

is_windows=0
case "$platform" in
  CYGWIN*|MINGW*|MSYS*|Windows_NT)
    is_windows=1
    ;;
esac

if [ "$is_windows" -eq 0 ]; then
  # Prefer explicit env signal checks over fuzzy matching because some variables
  # (for example CYGWIN) can have values that do not include the variable name.
  if [ "$os_env" = "Windows_NT" ] || [ -n "$msystem_env" ] || [ -n "$mingw_env" ]; then
    is_windows=1
  elif [ "${CYGWIN+x}" = "x" ] || [ "${MINGW+x}" = "x" ]; then
    is_windows=1
  else
    case "$ostype_env" in
      cygwin*|msys*|mingw*|win32*)
        is_windows=1
        ;;
    esac
  fi
fi

if [ "$is_windows" -eq 1 ]; then
    expected_executable="${BUNDLE_DIR}/bin/counter-risk.exe"
else
  expected_executable="${BUNDLE_DIR}/bin/counter-risk"
fi

check_file "$expected_executable" "built executable"

if [ "$FAILURES" -ne 0 ]; then
  echo "Bundle validation failed with ${FAILURES} issue(s)." >&2
  exit 1
fi

echo "Bundle validation passed for ${BUNDLE_DIR}."
