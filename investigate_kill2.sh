#!/bin/bash
LOG=/tmp/logshow3.log
: > "$LOG"

cd /Users/bcb/Documents/ClarityOmega/IterBrow/iter || exit 1
SO=/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/lib/python3.12/site-packages/hyperonpy.cpython-312-darwin.so

echo "=== TEST A: raw ctypes dlopen ===" >> "$LOG"
./.venv/bin/python3 -u -c "
import ctypes
print('before dlopen')
lib = ctypes.CDLL('$SO')
print('after dlopen', lib)
" >> "$LOG" 2>&1
echo "TEST_A_EXIT=$?" >> "$LOG"

echo "=== TEST B: import hyperonpy directly (no hyperon wrapper) ===" >> "$LOG"
./.venv/bin/python3 -u -c "
print('before import hyperonpy')
import hyperonpy
print('after import hyperonpy', hyperonpy)
" >> "$LOG" 2>&1
echo "TEST_B_EXIT=$?" >> "$LOG"

echo "INVESTIGATE2_DONE" >> "$LOG"
