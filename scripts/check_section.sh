#!/usr/bin/env bash
# Check one milestone section: its own tests, then the guard tests every section must keep green.
#
#   scripts/check_section.sh M14-B          the section's unit tests + e2e tests + guards
#   scripts/check_section.sh M14-B --no-e2e  skip the section's end-to-end tests (minutes each)
#   scripts/check_section.sh M14            every section of the milestone
#
# A test belongs to a section when its file names the item (`@pending("M14-B2")` or a `"""M14-B2"""`
# docstring). The script also says how many `@pending` markers for the section are left: a section is
# done when that count is 0 and everything here passes. See CLAUDE.md.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SECTION="${1:-}"
if [[ ! "$SECTION" =~ ^M[0-9]+(-[A-Z])?$ ]]; then
  echo "usage: scripts/check_section.sh M14-B [--no-e2e]" >&2
  exit 2
fi
E2E=1
[[ "${2:-}" == "--no-e2e" ]] && E2E=0

PYTHON_BIN="$ROOT_DIR/iter/.venv/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "iter/.venv is missing; run scripts/setup_python_env.sh first" >&2
  exit 2
fi
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/ib-test-pycache"

# Every milestone's guards: the rules that must never regress (NACE untouched, gate advisory, the tool
# cap, the builder's hands and eyes, apps and briefs). Add a milestone's own files here once it ships.
GUARDS=(tests/test_m12_untie.py tests/test_m12_files.py tests/test_m12_guidance.py
        tests/test_m13_reading.py tests/test_m13_actions.py tests/test_m13_targets.py tests/test_m13_guidance.py
        tests/test_m14_vault.py tests/test_m14_scaffold.py tests/test_m14_cycling.py tests/test_m14_loop.py
        tests/test_m10_apps.py tests/test_m7_brief.py tests/test_tool_cap.py tests/test_governance_gate.py)

# An item: M14-B2 (one section) or any M14-<letter><n> (the whole milestone).
if [[ "$SECTION" == *-* ]]; then ITEM="${SECTION}[0-9]*"; else ITEM="${SECTION}-[A-Z][0-9]*"; fi
NAMES="[\"']${ITEM}[\"']|\"\"\"${ITEM}"
# Plain loops, not mapfile: macOS ships bash 3.2.
UNIT=(); E2E_FILES=()
while IFS= read -r f; do UNIT+=("$f"); done < <(grep -rlE "$NAMES" tests --include='test_*.py' --exclude-dir=e2e | sort)
while IFS= read -r f; do E2E_FILES+=("$f"); done < <(grep -rlE "$NAMES" tests/e2e --include='test_*.py' | sort)

echo "[check] $SECTION: node syntax check"
node -e "for (const f of ['main.js','preload.js']) new (require('vm').Script)(require('fs').readFileSync(f,'utf8'))"
for f in bridge/*.js; do node --check "$f"; done

if [[ ${#UNIT[@]} -eq 0 && ${#E2E_FILES[@]} -eq 0 ]]; then
  echo "[check] no tests name $SECTION" >&2
  exit 2
fi

# Guards not already in the section's own list, so nothing runs twice.
RUN=(${UNIT[@]+"${UNIT[@]}"})
for g in "${GUARDS[@]}"; do
  [[ -f "$g" ]] || continue
  [[ " ${RUN[*]} " == *" $g "* ]] || RUN+=("$g")
done
echo "[check] $SECTION: ${#UNIT[@]} section file(s) + guards"
"$PYTHON_BIN" -m pytest "${RUN[@]}" -q -p no:cacheprovider -rxX

if [[ $E2E -eq 1 && ${#E2E_FILES[@]} -gt 0 ]]; then
  echo "[check] $SECTION: end-to-end ${E2E_FILES[*]}"
  "$PYTHON_BIN" -m pytest "${E2E_FILES[@]}" -q -p no:cacheprovider -rxX
fi

LEFT=$( (grep -rhoE "@pending\(\"${ITEM}\"\)" tests || true) | wc -l | tr -d ' ')
echo "[check] $SECTION: $LEFT @pending marker(s) left"
if [[ "$LEFT" != "0" ]]; then
  grep -rnE "@pending\(\"${ITEM}\"\)" tests | sed 's/^/  /'
fi
