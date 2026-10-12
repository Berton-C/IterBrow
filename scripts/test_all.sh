#!/usr/bin/env bash
# One command runs every check that guards a change to IterBrow.
#
#   scripts/test_all.sh          unit + contract tests, then the end-to-end runs
#   scripts/test_all.sh --fast   unit + contract tests only (pre-push hook, quick loops)
#
# The end-to-end tests (tests/e2e) start the real iter.py loop, the real
# AtomSpace service and a scripted fake model in a throwaway ITER_DIR; they
# take a few minutes and need no API key or network.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/iter/.venv/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "iter/.venv is missing; run scripts/setup_python_env.sh first" >&2
  exit 2
fi
if ! "$PYTHON_BIN" -c "import pytest" 2>/dev/null; then
  echo "pytest is not installed in iter/.venv; run: iter/.venv/bin/python -m pip install pytest" >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/ib-test-pycache"

echo "[test_all] syntax check of main process and preload"
node -e "for (const f of ['main.js','preload.js']) new (require('vm').Script)(require('fs').readFileSync(f,'utf8'))"

echo "[test_all] unit and contract tests"
"$PYTHON_BIN" -m pytest tests --ignore=tests/e2e -q -p no:cacheprovider

if [[ "${1:-}" == "--fast" ]]; then
  echo "[test_all] fast mode: end-to-end runs skipped"
  exit 0
fi

echo "[test_all] end-to-end runs (real loop, real AtomSpace, fake model; ITERBROW_E2E_ALL=1 adds known-failing invariants)"
"$PYTHON_BIN" -m pytest tests/e2e -q -p no:cacheprovider -rx
echo "[test_all] all checks passed"
