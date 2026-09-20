#!/usr/bin/env bash
# ==============================================================================
#  IterBrow one-shot installer (macOS)
# ------------------------------------------------------------------------------
#  Sets up everything Iter Browser needs on a brand-new Mac:
#    1. Homebrew            (package manager, if missing)
#    2. nvm + Node 20.11.1  (Electron's JS runtime)
#    3. SWI-Prolog          (optional — powers real MeTTa reasoning)
#    4. Python 3.12 venv    (Iter agent's own process, with pinned deps)
#    5. npm install         (Electron + its native deps)
#
#  Usage:
#     git clone https://github.com/Berton-C/IterBrow.git
#     cd IterBrow
#     ./install.sh
#
#  Safe to re-run — every step checks for what's already installed and skips
#  it. Nothing here touches your accumulated memory/chat data (there isn't
#  any yet on a fresh clone); if you were handed a separate memory snapshot
#  file, see the README's "Restoring a memory snapshot" section AFTER this
#  script finishes, not before.
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
step() { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }
ok()   { printf "\033[1;32m   ✓ %s\033[0m\n" "$1"; }
warn() { printf "\033[1;33m   ! %s\033[0m\n" "$1"; }

if [[ "$(uname -s)" != "Darwin" ]]; then
  warn "This script targets macOS. On Linux, install Node 18+, Python 3.12,"
  warn "and (optionally) SWI-Prolog with your distro's package manager, then"
  warn "run: npm install && bash scripts/setup_python_env.sh"
  exit 1
fi

bold "IterBrow installer — this will take a few minutes on a clean machine."

# ------------------------------------------------------------------------------
step "1/5  Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew not found — installing it now (you may be prompted for your password)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
else
  ok "Homebrew already installed ($(brew --version | head -1))."
fi

# ------------------------------------------------------------------------------
step "2/5  Node.js (via nvm)"
export NVM_DIR="$HOME/.nvm"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  warn "nvm not found — installing it now."
  brew install nvm
  mkdir -p "$NVM_DIR"
fi
# shellcheck disable=SC1091
source "$(brew --prefix nvm)/nvm.sh" 2>/dev/null || source "$NVM_DIR/nvm.sh" 2>/dev/null || true

if command -v nvm >/dev/null 2>&1 || [[ -s "$NVM_DIR/nvm.sh" ]]; then
  nvm install 20.11.1
  nvm use 20.11.1
  ok "Node $(node --version) ready via nvm."
else
  # Fallback: plain Homebrew node if nvm wiring didn't load in this shell
  if ! command -v node >/dev/null 2>&1; then
    brew install node@20
    brew link --overwrite node@20
  fi
  ok "Node $(node --version) ready (Homebrew fallback)."
fi

# ------------------------------------------------------------------------------
step "3/5  SWI-Prolog (optional — enables real MeTTa reasoning)"
if brew list --versions swi-prolog >/dev/null 2>&1; then
  ok "SWI-Prolog already installed ($(brew list --versions swi-prolog))."
else
  warn "Installing SWI-Prolog (needed for tools/metta.py's real MeTTa engine)."
  if brew install swi-prolog; then
    ok "SWI-Prolog installed."
  else
    warn "SWI-Prolog install failed — Iter will still run fine, only its MeTTa"
    warn "reasoning tool (tools/metta.py) will be unavailable. Re-run"
    warn "'brew install swi-prolog' any time to add it later."
  fi
fi

# ------------------------------------------------------------------------------
step "4/5  Python 3.12 virtual environment for the Iter agent"
PYBIN=""
for cand in python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
  if command -v "$cand" >/dev/null 2>&1; then PYBIN="$cand"; break; fi
done
if [[ -z "$PYBIN" ]]; then
  warn "Python 3.12 not found — installing via Homebrew."
  brew install python@3.12
  PYBIN="$(brew --prefix python@3.12)/bin/python3.12"
fi
ok "Using $PYBIN ($($PYBIN --version))."

cd "$ROOT_DIR/iter"
if [[ ! -d .venv ]]; then
  "$PYBIN" -m venv .venv
fi
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r "$ROOT_DIR/scripts/requirements.txt"
ok "Python dependencies installed into iter/.venv."

if ! ./.venv/bin/python3 -c "import janus_swi" >/dev/null 2>&1; then
  warn "janus_swi didn't import cleanly (only used by an older, unused code"
  warn "path) — harmless, safe to ignore."
fi

if ! ./.venv/bin/python3 -c "import hyperon" >/dev/null 2>&1; then
  warn "hyperon (the real MeTTa engine behind iter/metta_server.py) didn't"
  warn "import cleanly. It should have installed from requirements.txt above"
  warn "— if this persists, run: ./.venv/bin/pip install hyperon==0.2.10"
  warn "and re-check. Everything else in Iter works fine without it; only"
  warn "the persistent MeTTa/NACE reasoning server won't start."
else
  ok "hyperon / MeTTa engine import OK."
fi
cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
step "5/5  Electron + npm dependencies"
npm install
ok "npm install complete."

# ------------------------------------------------------------------------------
printf "\n\033[1;32m======================================================\033[0m\n"
printf "\033[1;32m  IterBrow is installed.\033[0m\n"
printf "\033[1;32m======================================================\033[0m\n\n"
echo "Next steps:"
echo "  1. Run:  npm start"
echo "  2. In the app's Settings drawer, choose the OpenRouter provider and"
echo "     paste in your own OpenRouter API key (sign up free at"
echo "     https://openrouter.ai/keys — never share or commit this key)."
echo "  3. Press Start, then type in the chat box to talk to Iter."
echo
echo "If you were given a separate iterbrow_state.tar.gz (or .zip) memory"
echo "snapshot, see README.md -> 'Restoring a memory snapshot' before you"
echo "start chatting, so Iter comes up already primed with that memory."
echo
