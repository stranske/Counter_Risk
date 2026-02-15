#!/usr/bin/env bash

set -u

BUNDLE_DIR=""
FAILURES=0
MISSING_GH_ERROR="Error: gh executable not found. The gh CLI is required for release validation. Please install it from https://cli.github.com/"

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

detect_platform() {
  local uname_output
  local os_env
  local msystem_env
  local ostype_env
  local cygwin_env
  local mingw_env

  uname_output="$(uname -s 2>/dev/null || true)"
  os_env="${OS-}"
  msystem_env="${MSYSTEM-}"
  ostype_env="${OSTYPE-}"
  cygwin_env="${CYGWIN-}"
  mingw_env="${MINGW-}"

  case "$uname_output" in
    CYGWIN*|MINGW*|MSYS*|Windows_NT)
      echo "windows"
      return 0
      ;;
  esac

  case "$os_env" in
    Windows_NT|CYGWIN*|MINGW*|MSYS*)
      echo "windows"
      return 0
      ;;
  esac

  case "$msystem_env" in
    CYGWIN*|MINGW*|MSYS*)
      echo "windows"
      return 0
      ;;
  esac

  case "$ostype_env" in
    cygwin*|msys*|mingw*|win32*)
      echo "windows"
      return 0
      ;;
  esac

  if [ -n "$cygwin_env" ] || [ "${CYGWIN+x}" = "x" ]; then
    echo "windows"
    return 0
  fi

  if [ -n "$mingw_env" ] || [ "${MINGW+x}" = "x" ]; then
    echo "windows"
    return 0
  fi

  echo "unix"
}

main() {
  local platform_type
  local expected_executable
  local readme_file

  if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <bundle_dir>" >&2
    return 2
  fi

  BUNDLE_DIR="$1"
  FAILURES=0

  if ! command -v gh >/dev/null 2>&1; then
    echo "${MISSING_GH_ERROR}" >&2
    return 1
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

  platform_type="$(detect_platform)"
  if [ "$platform_type" = "windows" ]; then
    expected_executable="${BUNDLE_DIR}/bin/counter-risk.exe"
  else
    expected_executable="${BUNDLE_DIR}/bin/counter-risk"
  fi

  check_file "$expected_executable" "built executable"

  if [ "$FAILURES" -ne 0 ]; then
    echo "Bundle validation failed with ${FAILURES} issue(s)." >&2
    return 1
  fi

  echo "Bundle validation passed for ${BUNDLE_DIR}."
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
