#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${REPO_ROOT}/scripts/validate_release_bundle.sh"
MISSING_GH_ERROR="Error: gh executable not found. The gh CLI is required for release validation. Please install it from https://cli.github.com/"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local context="$3"
  if [ "$expected" != "$actual" ]; then
    fail "${context}: expected '${expected}' but got '${actual}'"
  fi
}

assert_status_nonzero() {
  local status="$1"
  local context="$2"
  if [ "$status" -eq 0 ]; then
    fail "${context}: expected non-zero status"
  fi
}

make_fake_uname() {
  local bin_dir="$1"
  local uname_value="$2"
  cat >"${bin_dir}/uname" <<EOF
#!/usr/bin/env bash
echo "${uname_value}"
EOF
  chmod +x "${bin_dir}/uname"
}

make_fake_gh() {
  local bin_dir="$1"
  cat >"${bin_dir}/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "${bin_dir}/gh"
}

detect_with_env() {
  local bin_dir="$1"
  local uname_value="$2"
  local os_value="$3"
  local msystem_value="$4"
  local ostype_value="$5"

  make_fake_uname "${bin_dir}" "${uname_value}"

  PATH="${bin_dir}:${PATH}" \
    OS="${os_value}" \
    MSYSTEM="${msystem_value}" \
    OSTYPE="${ostype_value}" \
    /bin/bash -c "source '${SCRIPT_PATH}'; detect_platform"
}

test_detect_platform_linux_unix() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local result
  result="$(detect_with_env "${tmp_dir}" "Linux" "" "" "")"
  assert_eq "unix" "${result}" "Linux uname should map to unix"
  rm -rf "${tmp_dir}"
}

test_detect_platform_darwin_unix() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local result
  result="$(detect_with_env "${tmp_dir}" "Darwin" "" "" "")"
  assert_eq "unix" "${result}" "Darwin uname should map to unix"
  rm -rf "${tmp_dir}"
}

test_detect_platform_ostype_cygwin_windows() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local result
  result="$(detect_with_env "${tmp_dir}" "Linux" "" "" "cygwin")"
  assert_eq "windows" "${result}" "OSTYPE=cygwin should map to windows"
  rm -rf "${tmp_dir}"
}

test_detect_platform_msystem_mingw_windows() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local result
  result="$(detect_with_env "${tmp_dir}" "Linux" "" "MINGW64" "")"
  assert_eq "windows" "${result}" "MSYSTEM=MINGW64 should map to windows"
  rm -rf "${tmp_dir}"
}

test_detect_platform_msys_uname_windows() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local result
  result="$(detect_with_env "${tmp_dir}" "MSYS_NT-10.0" "" "" "")"
  assert_eq "windows" "${result}" "MSYS uname should map to windows"
  rm -rf "${tmp_dir}"
}

test_missing_gh_uses_standardized_error() {
  local tmp_dir
  local bundle_dir
  local output
  local status

  tmp_dir="$(mktemp -d)"
  bundle_dir="${tmp_dir}/release/1.2.3"
  mkdir -p "${bundle_dir}/config" "${bundle_dir}/templates" "${bundle_dir}/bin"
  cat >"${bundle_dir}/VERSION" <<'EOF'
1.2.3
EOF

  set +e
  output="$(PATH="${tmp_dir}" /bin/bash "${SCRIPT_PATH}" "${bundle_dir}" 2>&1)"
  status=$?
  set -e

  assert_status_nonzero "${status}" "missing gh should fail"
  assert_eq "${MISSING_GH_ERROR}" "${output}" "missing gh should use exact error message"
  rm -rf "${tmp_dir}"
}

test_detect_platform_linux_unix
test_detect_platform_darwin_unix
test_detect_platform_ostype_cygwin_windows
test_detect_platform_msystem_mingw_windows
test_detect_platform_msys_uname_windows
test_missing_gh_uses_standardized_error

echo "All validate_release_bundle shell tests passed."
