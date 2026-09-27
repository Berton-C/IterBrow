#!/usr/bin/env bash
# Explicit, user-invoked update and uninstall transactions for source installs.
set -euo pipefail

LIFECYCLE_ACTION="${1:?Pass update or uninstall}"
LIFECYCLE_ROOT="$(cd "${2:?Pass the IterBrow root}" && pwd)"
LIFECYCLE_BRANCH="${3:-${ITERBROW_BRANCH:-TheWholeEnchilada}}"
LIFECYCLE_LAUNCH="${4:-1}"
LIFECYCLE_HELPER="$LIFECYCLE_ROOT/scripts/iterbrow_lifecycle.py"
LIFECYCLE_PARENT="$(dirname "$LIFECYCLE_ROOT")"
LIFECYCLE_NAME="$(basename "$LIFECYCLE_ROOT")"
LIFECYCLE_BACKUP_DIR="${ITERBROW_BACKUP_DIR:-$HOME/Library/Application Support/IterBrow Installer/backups}"
LIFECYCLE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"

life_ok() { printf "\033[1;32m   ✓ %s\033[0m\n" "$1"; }
life_warn() { printf "\033[1;33m   ! %s\033[0m\n" "$1"; }

case "$LIFECYCLE_ROOT" in
  /|"$HOME"|"$LIFECYCLE_PARENT")
    life_warn "Refusing an unsafe lifecycle target: $LIFECYCLE_ROOT"
    exit 1
    ;;
esac

if [[ ! -f "$LIFECYCLE_HELPER" || ! -f "$LIFECYCLE_ROOT/iter/state_manifest.json" ]]; then
  life_warn "This is not a complete IterBrow installation: $LIFECYCLE_ROOT"
  exit 1
fi
if [[ -d "$LIFECYCLE_ROOT/.git" ]]; then
  life_warn "Lifecycle replacement is for installed copies, not a Git development checkout."
  life_warn "Update this checkout with Git; use './install.sh repair' to repair its runtimes."
  exit 2
fi

PYTHON_BIN=""
for candidate in "$LIFECYCLE_ROOT/iter/.venv/bin/python3" python3.12 /opt/homebrew/bin/python3.12; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON_BIN="$candidate"; break; fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  life_warn "Python 3.12 is required for lifecycle state verification."
  exit 1
fi

mkdir -p "$LIFECYCLE_BACKUP_DIR"
chmod 700 "$LIFECYCLE_BACKUP_DIR"
STATE_ARCHIVE="$LIFECYCLE_BACKUP_DIR/state-$LIFECYCLE_STAMP.tar.gz"

"$PYTHON_BIN" "$LIFECYCLE_HELPER" prepare-offline --root "$LIFECYCLE_ROOT"
"$PYTHON_BIN" "$LIFECYCLE_HELPER" snapshot --root "$LIFECYCLE_ROOT" \
  --archive "$STATE_ARCHIVE" --include-tools
life_ok "State and secrets checkpointed at $STATE_ARCHIVE"

if [[ "$LIFECYCLE_ACTION" == "uninstall" ]]; then
  UNINSTALLING="$LIFECYCLE_PARENT/.$LIFECYCLE_NAME.uninstalling-$$"
  if [[ -e "$UNINSTALLING" ]]; then
    life_warn "Refusing to replace existing uninstall staging path: $UNINSTALLING"
    exit 1
  fi
  mv "$LIFECYCLE_ROOT" "$UNINSTALLING"
  rm -rf -- "$UNINSTALLING"
  life_ok "IterBrow program files removed; preserved state remains at $STATE_ARCHIVE"
  exit 0
fi

if [[ "$LIFECYCLE_ACTION" != "update" ]]; then
  life_warn "Unsupported lifecycle action: $LIFECYCLE_ACTION"
  exit 2
fi

UPDATE_STAGE="$LIFECYCLE_PARENT/.$LIFECYCLE_NAME.update-$$"
UPDATE_ROLLBACK="$LIFECYCLE_PARENT/$LIFECYCLE_NAME.rollback-$LIFECYCLE_STAMP"
ACQUIRE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/iterbrow-update.XXXXXX")"
cleanup_update() {
  rm -rf -- "$ACQUIRE_TMP"
  if [[ -d "$UPDATE_STAGE" ]]; then rm -rf -- "$UPDATE_STAGE"; fi
}
trap cleanup_update EXIT

if [[ -n "${ITERBROW_UPDATE_SOURCE:-}" ]]; then
  SOURCE_DIR="$(cd "$ITERBROW_UPDATE_SOURCE" && pwd)"
  /usr/bin/ditto "$SOURCE_DIR" "$UPDATE_STAGE"
else
  ARCHIVE_URL="https://github.com/Berton-C/IterBrow/archive/refs/heads/$LIFECYCLE_BRANCH.tar.gz"
  curl -fL --progress-bar -o "$ACQUIRE_TMP/iterbrow.tar.gz" "$ARCHIVE_URL"
  tar -xzf "$ACQUIRE_TMP/iterbrow.tar.gz" -C "$ACQUIRE_TMP"
  SOURCE_DIR="$(find "$ACQUIRE_TMP" -mindepth 1 -maxdepth 1 -type d -name 'IterBrow-*' -print -quit)"
  if [[ -z "$SOURCE_DIR" || ! -f "$SOURCE_DIR/install.sh" ]]; then
    life_warn "The downloaded update is not a complete IterBrow source tree."
    exit 1
  fi
  /usr/bin/ditto "$SOURCE_DIR" "$UPDATE_STAGE"
fi

if [[ ! -f "$UPDATE_STAGE/package.json" || ! -f "$UPDATE_STAGE/iter/state_manifest.json" ]]; then
  life_warn "The staged update is incomplete; the current installation is unchanged."
  exit 1
fi

(cd "$UPDATE_STAGE" && /bin/bash ./install.sh install --no-launch)
"$PYTHON_BIN" "$LIFECYCLE_HELPER" restore --root "$UPDATE_STAGE" --archive "$STATE_ARCHIVE"

STAGE_PYTHON="$UPDATE_STAGE/iter/.venv/bin/python3"
if [[ ! -x "$STAGE_PYTHON" ]]; then STAGE_PYTHON="$PYTHON_BIN"; fi
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" "$LIFECYCLE_HELPER" validate-atomspace \
  --root "$UPDATE_STAGE" --python "$STAGE_PYTHON"
PYTHONDONTWRITEBYTECODE=1 "$STAGE_PYTHON" \
  "$UPDATE_STAGE/scripts/refresh_dashboard_projections.py" --root "$UPDATE_STAGE"
PYTHONDONTWRITEBYTECODE=1 "$STAGE_PYTHON" "$UPDATE_STAGE/scripts/iterbrow_readiness.py" \
  --app-root "$UPDATE_STAGE" --iter-dir "$UPDATE_STAGE/iter" \
  --python-bin "$STAGE_PYTHON" --require installed
life_ok "Staged code and restored state verified before replacement."

mv "$LIFECYCLE_ROOT" "$UPDATE_ROLLBACK"
if ! mv "$UPDATE_STAGE" "$LIFECYCLE_ROOT"; then
  mv "$UPDATE_ROLLBACK" "$LIFECYCLE_ROOT"
  life_warn "Update replacement failed; exact prior installation restored."
  exit 1
fi
trap - EXIT
rm -rf -- "$ACQUIRE_TMP"
life_ok "Update installed. Exact prior program retained at $UPDATE_ROLLBACK"

if [[ "$LIFECYCLE_LAUNCH" == "1" ]]; then
  cd "$LIFECYCLE_ROOT"
  nohup npm start >"${TMPDIR:-/tmp}/iterbrow-update-launch.log" 2>&1 &
  life_ok "IterBrow launch requested."
else
  life_ok "Launch skipped by --no-launch."
fi
