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
cd "$TARGET"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install openai
echo "Done. main.js will automatically use $TARGET/.venv/bin/python3 once it exists."
echo

# pymetta (real MeTTa evaluation for tools/metta.py) links against a
# system-level SWI-Prolog install at pip-install time, so it can fail here if
# SWI-Prolog 9.3+ isn't on this machine yet. Don't let that abort setup --
# every other tool works fine without it.
if ./.venv/bin/pip install 'pymetta[engine]'; then
  echo "pymetta installed -- tools/metta.py has real MeTTa evaluation."
else
  echo "WARNING: pymetta install failed (see above). tools/metta.py will not"
  echo "work until you install SWI-Prolog 9.3+ and re-run this script:"
  echo "  macOS:   brew install swi-prolog"
  echo "  Linux:   sudo apt install swi-prolog   (or the swi-prolog/stable PPA for 9.3+)"
  echo "  Windows: winget install SWI-Prolog.SWI-Prolog"
  echo "Every other tool still works; only the metta tool (and the 'metta'"
  echo "eval self-test) are affected."
fi
