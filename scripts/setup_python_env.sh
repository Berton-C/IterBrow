#!/usr/bin/env bash
# One-time setup for the bundled iter/ Python agent.
#
# Usage:
#   scripts/setup_python_env.sh                     (default: this source checkout's iter/)
#   scripts/setup_python_env.sh /path/to/Iter\ Browser.app/Contents/Resources/app/iter
#       (use this second form if you're running the prebuilt .app from dist/
#       instead of `npm start` — point it at the iter/ folder inside the
#       .app bundle so the packaged app can find its own venv)
set -euo pipefail
TARGET="${1:-$(dirname "$0")/../iter}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$TARGET"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r "$ROOT_DIR/scripts/requirements.txt"
./.venv/bin/python3 -c "import hyperon"
bash "$ROOT_DIR/scripts/install_native_hyperon.sh" "$PWD/.venv/bin/python3"
echo "Done. main.js will automatically use $TARGET/.venv/bin/python3 once it exists."
echo "Hyperon native fidelity verified; the journaled AtomSpace service can start."
echo "Optional PeTTa/SWI compatibility dependencies live in scripts/requirements-optional-petta.txt."
