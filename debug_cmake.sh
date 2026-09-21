#!/bin/bash
set -x
SRC="/Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug"
BUILD="$SRC/manual_build"
rm -rf "$BUILD"
mkdir -p "$BUILD"
source "$SRC/build_venv/bin/activate"
cd "$BUILD" || exit 1

echo "=== conan install ==="
conan install "$SRC/python" --output-folder=. --build=missing -s build_type=Debug

echo "=== cmake configure ==="
mkdir -p lib_out
cmake "$SRC/python" \
  -DCMAKE_TOOLCHAIN_FILE=./build/Debug/generators/conan_toolchain.cmake \
  -DCMAKE_LIBRARY_OUTPUT_DIRECTORY="$BUILD/lib_out/" \
  -DPython3_EXECUTABLE="$SRC/build_venv/bin/python3" \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_PREFIX_PATH=~/.local
CMAKE_CONFIGURE_EXIT=$?
echo "CMAKE_CONFIGURE_EXIT=$CMAKE_CONFIGURE_EXIT"

if [ "$CMAKE_CONFIGURE_EXIT" -eq 0 ]; then
  echo "=== cmake build ==="
  cmake --build .
  echo "CMAKE_BUILD_EXIT=$?"
fi
echo "DEBUG_CMAKE_SCRIPT_DONE"
