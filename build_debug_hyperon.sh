#!/bin/bash
set -x
set -o pipefail

BASE="/Users/bcb/Documents/ClarityOmega/IterBrow"
SRC="$BASE/hyperon-src-debug"

echo "=== STEP 1: Homebrew cmake ==="
if ! command -v cmake >/dev/null 2>&1; then
    brew install cmake
else
    echo "cmake already present: $(cmake --version | head -1)"
fi

echo "=== STEP 2: rustup update ==="
rustup update stable
rustc --version
cargo --version

echo "=== STEP 3: clone hyperon-experimental at v0.2.10 ==="
if [ -d "$SRC" ]; then
    echo "source dir already exists, leaving as-is"
else
    git clone https://github.com/trueagi-io/hyperon-experimental.git "$SRC"
fi
cd "$SRC" || exit 1
git fetch --tags
git checkout v0.2.10
git log -1 --oneline

echo "=== STEP 4: cbindgen ==="
cargo install --force cbindgen

echo "=== STEP 5: build venv (python3.12, matching iter's venv) ==="
BUILD_VENV="$SRC/build_venv"
if [ ! -d "$BUILD_VENV" ]; then
    /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv "$BUILD_VENV"
fi
source "$BUILD_VENV/bin/activate"
python3 -m pip install --upgrade pip
python3 -m pip install "conan" "cmake" pybind11

echo "=== STEP 6: conan profile ==="
conan profile detect --force || conan profile new default --detect

echo "=== STEP 7: build hyperonpy in DEBUG mode ==="
cd "$SRC/python" || exit 1
export DEBUG=1
python3 -m pip install -e ".[dev]" -v 2>&1 | tee "$SRC/build_output.log"

echo "=== BUILD_SCRIPT_DONE marker below ==="
echo "BUILD_SCRIPT_EXIT_CODE=$?"
