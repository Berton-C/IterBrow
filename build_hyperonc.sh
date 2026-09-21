#!/bin/bash
set -x
set -o pipefail

unset CC CXX
SRC="/Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug"
export CARGO_HOME="$SRC/cargo_home_debug"
export PATH="$SRC/cargo_home_debug/bin:$HOME/.cargo/bin:$PATH"
which cbindgen
which cargo
source "$SRC/build_venv/bin/activate"

BUILD_DIR="$SRC/c/build_debug"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 1

CMAKE_ARGS="-DBUILD_SHARED_LIBS=ON"
CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_INSTALL_PREFIX=$HOME/.local"
CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_BUILD_TYPE=Debug"
CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=$SRC/conan_provider.cmake"
echo "hyperonc CMake arguments: $CMAKE_ARGS"

cmake $CMAKE_ARGS ..
echo "CMAKE_CONFIGURE_EXIT=$?"

make -j 2>&1
echo "MAKE_EXIT=$?"

make install 2>&1
echo "MAKE_INSTALL_EXIT=$?"

echo "=== BUILD_HYPERONC_DONE ==="
find "$HOME/.local" -iname "*hyperonc*" 2>/dev/null
