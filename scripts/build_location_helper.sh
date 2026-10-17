#!/usr/bin/env bash
# Build the native location helper for Map Station (docs/milestones/M11_browser_track.md A4).
#
#   scripts/build_location_helper.sh           compile scripts/location/iter_location.swift into
#                                              $ITER_DIR/.runtime/bin/iter_location (needs swiftc)
#   scripts/build_location_helper.sh --check   report which location route exists; builds nothing
#
# Best-effort by design: without swiftc it says so and exits 0 (Homebrew's CoreLocationCLI is the
# other route). install.sh calls it on install and repair and never fails because of it.
# The --check path uses only shell builtins so it runs anywhere.
set -u
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
[[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ITER_DIR="${ITER_DIR:-$ROOT_DIR/iter}"
SOURCE="$ROOT_DIR/scripts/location/iter_location.swift"
OUTPUT="$ITER_DIR/.runtime/bin/iter_location"
BREW_HINT="brew install corelocationcli"

find_swiftc() {
  # On macOS /usr/bin/swiftc is a shim that offers to install the Command Line Tools, so look for a
  # real toolchain instead of trusting PATH.
  local candidate
  for candidate in /Library/Developer/CommandLineTools/usr/bin/swiftc \
                   /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swiftc; do
    [[ -x "$candidate" ]] && { printf '%s' "$candidate"; return 0; }
  done
  return 1
}

if [[ "${1:-}" == "--check" ]]; then
  if [[ -n "${ITERBROW_LOCATION_HELPER:-}" && -x "${ITERBROW_LOCATION_HELPER}" ]]; then
    printf 'location helper (ITERBROW_LOCATION_HELPER): %s\n' "$ITERBROW_LOCATION_HELPER"
  fi
  if [[ -x "$OUTPUT" ]]; then printf 'built helper: %s\n' "$OUTPUT"; else printf 'built helper: missing\n'; fi
  found_brew=""
  for candidate in /opt/homebrew/bin/CoreLocationCLI /usr/local/bin/CoreLocationCLI; do
    [[ -x "$candidate" ]] && { found_brew="$candidate"; break; }
  done
  if [[ -n "$found_brew" ]]; then printf 'CoreLocationCLI: %s\n' "$found_brew"; else printf 'CoreLocationCLI: missing (%s)\n' "$BREW_HINT"; fi
  if swiftc_path="$(find_swiftc)"; then printf 'swiftc: %s\n' "$swiftc_path"; else printf 'swiftc: missing\n'; fi
  exit 0
fi

if ! SWIFTC="$(find_swiftc)"; then
  printf 'no swiftc; %s works too\n' "$BREW_HINT"
  exit 0
fi

mkdir -p "${OUTPUT%/*}"
if "$SWIFTC" -O -o "$OUTPUT.tmp" "$SOURCE" -framework CoreLocation; then
  chmod 755 "$OUTPUT.tmp"
  mv -f "$OUTPUT.tmp" "$OUTPUT"
  printf '%s\n' "$OUTPUT"
else
  rm -f "$OUTPUT.tmp"
  printf 'swiftc could not build the location helper; %s works too\n' "$BREW_HINT" >&2
  exit 1
fi
