#!/bin/bash
set -x
set -o pipefail
LOG=/tmp/deploy_fixed_so.log
: > "$LOG"
{
SRC="/Users/bcb/Documents/ClarityOmega/IterBrow/hyperon-src-debug"
NEW_SO="$SRC/python/hyperonpy.cpython-312-darwin.so"
TARGET="/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/lib/python3.12/site-packages/hyperonpy.cpython-312-darwin.so"
DSYM_PERM="/Users/bcb/Documents/ClarityOmega/IterBrow/debug_symbols/hyperonpy.dSYM"

echo "=== regenerating dSYM ==="
rm -rf "$DSYM_PERM"
dsymutil "$NEW_SO" -o "$DSYM_PERM"
echo "dsymutil exit=$?"

echo "=== backing up currently-deployed .so ==="
cp "$TARGET" "${TARGET}.PRE_TRIEFIX_BACKUP"
echo "backup exit=$?"

echo "=== copying new .so into venv site-packages ==="
cp "$NEW_SO" "$TARGET"
echo "copy exit=$?"

echo "=== copying dSYM next to the venv .so for lldb auto-discovery ==="
rm -rf "${TARGET%.so}.dSYM"
cp -R "$DSYM_PERM" "${TARGET%.so}.dSYM"
echo "dsym copy exit=$?"

echo "=== re-signing (critical: avoids cs_mtime kernel kill) ==="
codesign --remove-signature "$TARGET"
codesign --force --sign - "$TARGET"
echo "codesign exit=$?"
codesign -dvvv "$TARGET" 2>&1 | head -10

echo "=== smoke test: import + basic run ==="
"/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/bin/python3" -c "
import time
t0 = time.time()
import hyperon
print('IMPORT_OK', time.time() - t0)
m = hyperon.MeTTa()
r = m.run('!(+ 1 2)')
print('RESULT:', r)
"
echo "smoke test exit=$?"
} >> "$LOG" 2>&1
echo DEPLOY_FIXED_SO_DONE >> "$LOG"
