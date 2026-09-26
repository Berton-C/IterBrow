#!/usr/bin/env bash
# Build the pinned native repair only when the installed engine fails fidelity.
# All build products remain in the system temporary directory, not the repo.
set -euo pipefail
NATIVE_PYTHON="${1:?Pass the target virtual environment Python}"
NATIVE_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
if "$NATIVE_PYTHON" "$NATIVE_SCRIPTS/native_engine.py"; then exit 0; fi
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Native repair requires a source build on this platform; no successful installation is claimed.' >&2
  exit 1
fi
NATIVE_BUILD="$(mktemp -d "${TMPDIR:-/tmp}/iterbrow-native.XXXXXX")"
echo "Building the repaired native engine in $NATIVE_BUILD"
brew install rust cbindgen protobuf openssl@3 pkg-config
"$NATIVE_PYTHON" -m pip install pybind11==2.13.6
git init "$NATIVE_BUILD/source"
git -C "$NATIVE_BUILD/source" remote add origin https://github.com/trueagi-io/hyperon-experimental.git
git -C "$NATIVE_BUILD/source" fetch --depth=1 origin 3f76dc460da6961f57f69f6c3e550c59c74ada83
git -C "$NATIVE_BUILD/source" checkout --detach FETCH_HEAD
git -C "$NATIVE_BUILD/source" apply "$NATIVE_SCRIPTS/patches/hyperon-0.2.10-trie-key.patch"
git clone --depth=1 --branch v3.5.0 https://github.com/martinmoene/optional-lite.git "$NATIVE_BUILD/optional-lite"
export OPENSSL_DIR="$(brew --prefix openssl@3)"
export CARGO_TARGET_DIR="$NATIVE_BUILD/target"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-13.0}"
cargo build --release --manifest-path "$NATIVE_BUILD/source/c/Cargo.toml" --features hyperon/git
mkdir -p "$NATIVE_BUILD/include/hyperon"
(cd "$NATIVE_BUILD/source/c" && cbindgen -c cbindgen.toml -o "$NATIVE_BUILD/include/hyperon/hyperon.h")
NATIVE_DESTINATION="$("$NATIVE_PYTHON" "$NATIVE_SCRIPTS/native_engine.py" --destination)"
read -r -a NATIVE_INCLUDES <<< "$("$NATIVE_PYTHON" -m pybind11 --includes)"
c++ -O2 -shared -std=c++17 -undefined dynamic_lookup "${NATIVE_INCLUDES[@]}" \
  -I"$NATIVE_BUILD/include" -I"$NATIVE_BUILD/optional-lite/include" \
  "$NATIVE_BUILD/source/python/hyperonpy.cpp" "$NATIVE_BUILD/target/release/libhyperonc.a" \
  -L"$OPENSSL_DIR/lib" -lssl -lcrypto -lz -liconv \
  -framework CoreFoundation -framework Security -o "$NATIVE_BUILD/$(basename "$NATIVE_DESTINATION")"
codesign --force --sign - "$NATIVE_BUILD/$(basename "$NATIVE_DESTINATION")"
cp "$NATIVE_DESTINATION" "$NATIVE_BUILD/before-native.so"
cp "$NATIVE_BUILD/$(basename "$NATIVE_DESTINATION")" "$NATIVE_DESTINATION.pending"
mv "$NATIVE_DESTINATION.pending" "$NATIVE_DESTINATION"
if ! "$NATIVE_PYTHON" "$NATIVE_SCRIPTS/native_engine.py"; then
  cp "$NATIVE_BUILD/before-native.so" "$NATIVE_DESTINATION"
  echo "Native verification failed; previous binary restored. Build retained at $NATIVE_BUILD" >&2
  exit 1
fi
rm -rf "$NATIVE_BUILD"
echo 'Native engine repair installed and verified.'
