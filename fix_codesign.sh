#!/bin/bash
LOG=/tmp/fix_codesign.log
: > "$LOG"
SO=/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/lib/python3.12/site-packages/hyperonpy.cpython-312-darwin.so

echo "=== before ===" >> "$LOG"
codesign -dv "$SO" >> "$LOG" 2>&1
stat -f "mtime=%m" "$SO" >> "$LOG" 2>&1

echo "=== removing existing signature ===" >> "$LOG"
codesign --remove-signature "$SO" >> "$LOG" 2>&1
echo "remove_exit=$?" >> "$LOG"

echo "=== re-signing ad-hoc ===" >> "$LOG"
codesign --force --sign - "$SO" >> "$LOG" 2>&1
echo "sign_exit=$?" >> "$LOG"

echo "=== after ===" >> "$LOG"
codesign -dv "$SO" >> "$LOG" 2>&1
stat -f "mtime=%m" "$SO" >> "$LOG" 2>&1

echo "=== smoke test: dlopen ===" >> "$LOG"
cd /Users/bcb/Documents/ClarityOmega/IterBrow/iter
./.venv/bin/python3 -u -c "
import ctypes
print('before dlopen')
lib = ctypes.CDLL('$SO')
print('after dlopen', lib)
" >> "$LOG" 2>&1
echo "DLOPEN_EXIT=$?" >> "$LOG"

echo "FIX_CODESIGN_DONE" >> "$LOG"
