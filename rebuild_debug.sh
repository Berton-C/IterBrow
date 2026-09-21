#!/bin/bash
set -x
set -o pipefail

unset CC CXX
SRC="/Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug"
export PATH="$SRC/cargo_home_debug/bin:$PATH"
which cbindgen
source "$SRC/build_venv/bin/activate"
cd "$SRC/python" || exit 1
export DEBUG=1
python3 -m pip install --no-build-isolation -e ".[dev]" -v 2>&1 | tee "$SRC/build_output2.log"
echo "=== REBUILD_DONE marker below, exit=$? ==="
find "$SRC" -name "hyperonpy*.so" 2>/dev/null
