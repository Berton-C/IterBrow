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
#    6. Seed data + Godot 4.5 editor for this branch's extra features (COS CRM
#       + NodeQuest -- see "TheWholeEnchilada extras" step below; a no-op if
#       iter/crm/ isn't present, i.e. on the vanilla main branch). Godot is
#       only needed to EDIT iter/nodequest/godot/project/ -- playing the
#       already-compiled game (iter/nodequest/godot/export/) needs nothing
#       but a browser and never touches this download.
#
#  Usage:
#     git clone https://github.com/Berton-C/IterBrow.git                        # vanilla (main)
#     git clone -b TheWholeEnchilada https://github.com/Berton-C/IterBrow.git   # full version
#     cd IterBrow
#     ./install.sh
#
#  Safe to re-run -- every step checks for what's already installed and skips
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
  warn "janus_swi (real MeTTa evaluation) didn't import cleanly — this is"
  warn "expected if SWI-Prolog failed to install above. Everything else"
  warn "in Iter works fine without it."
else
  ok "janus_swi / MeTTa engine import OK."
fi
cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
step "5/6  Electron + npm dependencies"
npm install
ok "npm install complete."

# ------------------------------------------------------------------------------
# 6/6 -- TheWholeEnchilada extras (COS CRM + NodeQuest). No-op on the vanilla
# main branch, where iter/crm/ doesn't exist. These files are deliberately
# gitignored (personal contact/task data, local-only config) so a fresh clone
# never has them -- without this step, opening the CRM page or letting Iter
# call crm:write for the first time fails with a missing-directory error
# instead of the empty-state the page expects.
if [[ -d "$ROOT_DIR/iter/crm" ]]; then
  step "6/6  TheWholeEnchilada extras (COS CRM + NodeQuest)"

  CRM_DATA="$ROOT_DIR/iter/crm/data"
  mkdir -p "$CRM_DATA"
  for f in contacts tasks events captures; do
    if [[ ! -f "$CRM_DATA/$f.json" ]]; then
      echo '[]' > "$CRM_DATA/$f.json"
    fi
  done
  # schema.md is documentation (not personal data), but it lives inside the
  # same iter/crm/data/ path that's gitignored wholesale to keep contact/task
  # data private -- so it never ships in the clone either. Write it here from
  # the canonical copy so HANDOFF.md's references to it resolve on a fresh
  # install too.
  if [[ ! -f "$CRM_DATA/schema.md" ]]; then
    cat > "$CRM_DATA/schema.md" <<'SCHEMA_EOF'
# COS Command Center -- data schema (Phase 1)
# Location: crm/data/*.json -- pages read/write these; agent reads/writes directly. Disk is the API.

contacts.json: [{
  "id":"c_<ts>","name":"","role":"","org":"","tier":"influencer|vc|dev|partner|internal",
  "warmth":0-100,"channels":[{"type":"email|telegram|x|linkedin","value":""}],
  "tags":[],"last_touch":"","next_step":"","next_step_due":"",
  "history":[{"ts":"","note":"","by":"her|iter"}],"notes":""
}]
tasks.json: [{
  "id":"t_<ts>","title":"","kind":"followup|talk|roundtable|meetup|cast|admin",
  "who":"contact_id|","due":"","status":"open|doing|done|dropped",
  "next_step":"","priority":1-3,"notes":"","created_by":"her|iter"
}]
events.json: [{
  "id":"e_<ts>","title":"","type":"meetup|talk|roundtable|cast|call|other",
  "when":"","where":"","prep_status":"topic|outline|slides|recorded|published",
  "linked_contacts":[],"notes":""
}]
captures.json: [{"ts":"","raw":"","parsed":true}]
SCHEMA_EOF
  fi
  ok "CRM data files + schema seeded empty at iter/crm/data/."

  # PWQ (Pending Work Queue) runtime data is deliberately gitignored too --
  # it is Iter's live, per-user negotiation state (real proposals, real user
  # answers), not shippable content. Without any seed at all, a fresh clone's
  # PWQ tab just renders an empty "Queue is clear" state and never
  # demonstrates the actual click-to-negotiate mechanism. iter/pwq_seed.json
  # (tracked, generic, no personal data) fixes that: pwq.html's load()
  # already falls back to it when .runtime/pwq.json doesn't exist yet, so no
  # copy is even required here -- this just documents the mechanism inline.
  PWQ_RUNTIME_DIR="$ROOT_DIR/iter/.runtime"
  mkdir -p "$PWQ_RUNTIME_DIR"
  if [[ ! -f "$PWQ_RUNTIME_DIR/pwq.json" && -f "$ROOT_DIR/iter/pwq_seed.json" ]]; then
    ok "PWQ tab will show generic example content (iter/pwq_seed.json) until"
    ok "your own Iter curates real proposals into iter/.runtime/pwq.json."
  fi

  mkdir -p "$ROOT_DIR/private/crm"
  ok "private/crm/ ready for connector config (Mattermost token, Gmail OAuth client --"
  ok "see iter/crm/HANDOFF.md section 7, 'First Session Quickstart', for exact steps)."

  if [[ -d "$ROOT_DIR/iter/nodequest/godot/export" ]]; then
    ok "NodeQuest text quests: open iter/nodequest/index.html directly, no server needed."
    warn "NodeQuest Ch1 (compiled Godot scene) won't load over a plain file:// tab --"
    warn "browsers block the wasm/pck fetches it needs. Serve it locally instead:"
    warn "   cd iter/nodequest/godot/export && python3 -m http.server 8765"
    warn "then open http://localhost:8765/index.html in a tab."
  fi

  # Godot 4.5 editor -- only needed if you want to open/edit/rebuild
  # iter/nodequest/godot/project/ and evolve NodeQuest or build more games
  # (this is meant as an ongoing learning environment, not a one-off game).
  # Playing the already-compiled export above needs none of this. Pinned to
  # the exact 4.5-stable macOS universal build (arm64 + x86_64) with an
  # official SHA-512 check against godotengine/godot-builds' own release
  # manifest, so a corrupted or tampered download is refused rather than
  # silently installed.
  GODOT_DIR="$ROOT_DIR/tools"
  GODOT_APP="$GODOT_DIR/Godot.app"
  GODOT_ZIP_URL="https://github.com/godotengine/godot-builds/releases/download/4.5-stable/Godot_v4.5-stable_macos.universal.zip"
  GODOT_SHA512="59d195d1876210fa0f8c36bc10b147339fc8e076c684b74111533992f1a1dcdc0f760461f4cadad627e5b11e74468b54b9355fc6ea0c507c52533dfa7aa0c617"

  if [[ -d "$GODOT_APP" ]]; then
    ok "Godot editor already installed at tools/Godot.app -- skipping download."
  else
    warn "Downloading Godot 4.5 editor (~160MB, macOS universal) -- this can take a few minutes."
    mkdir -p "$GODOT_DIR"
    GODOT_TMPDIR="$(mktemp -d)"
    GODOT_ZIP="$GODOT_TMPDIR/godot.zip"
    if curl -fL --progress-bar -o "$GODOT_ZIP" "$GODOT_ZIP_URL"; then
      ACTUAL_SHA512="$(shasum -a 512 "$GODOT_ZIP" | awk '{print $1}')"
      if [[ "$ACTUAL_SHA512" == "$GODOT_SHA512" ]]; then
        unzip -q -o "$GODOT_ZIP" -d "$GODOT_DIR"
        if [[ -d "$GODOT_APP" ]]; then
          xattr -dr com.apple.quarantine "$GODOT_APP" 2>/dev/null || true
          if "$GODOT_APP/Contents/MacOS/Godot" --version >/dev/null 2>&1; then
            ok "Godot $("$GODOT_APP/Contents/MacOS/Godot" --version) installed and verified at tools/Godot.app."
          else
            warn "Godot.app unzipped but didn't run cleanly (--version check failed)."
            warn "Check System Settings -> Privacy & Security if macOS blocked it, then"
            warn "open tools/Godot.app once manually to approve it."
          fi
        else
          warn "Godot zip extracted but tools/Godot.app wasn't found afterward --"
          warn "the release asset layout may have changed. NodeQuest's shipped build"
          warn "still plays fine without this; download manually from"
          warn "https://godotengine.org/download/macos/ (pick 4.5-stable) if needed."
        fi
      else
        warn "Godot download failed checksum verification (expected $GODOT_SHA512,"
        warn "got $ACTUAL_SHA512) -- refusing to install a corrupted/tampered copy."
        warn "Playing the shipped NodeQuest build still works with zero Godot install --"
        warn "only editing iter/nodequest/godot/project/ needs the editor. Re-run"
        warn "install.sh to retry the download."
      fi
    else
      warn "Godot download failed (network issue?) -- continuing without it."
      warn "Playing the shipped NodeQuest build still works with zero Godot install."
      warn "Re-run install.sh any time to retry."
    fi
    rm -rf "$GODOT_TMPDIR"
  fi
else
  ok "Vanilla branch -- no CRM/NodeQuest extras to seed."
fi

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
