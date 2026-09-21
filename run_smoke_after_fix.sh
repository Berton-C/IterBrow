#!/bin/bash
LOG=/tmp/smoke_after_fix.log
: > "$LOG"
cd /Users/bcb/Documents/ClarityOmega/IterBrow/iter || exit 1

echo "=== import hyperon ===" >> "$LOG"
./.venv/bin/python3 -u -c "
import hyperon
print('hyperon imported OK', hyperon.__file__)
" >> "$LOG" 2>&1
echo "IMPORT_EXIT=$?" >> "$LOG"

echo "=== full smoke test ===" >> "$LOG"
./.venv/bin/python3 -u /Users/bcb/Documents/ClarityOmega/IterBrow/smoke_test.py >> "$LOG" 2>&1
echo "SMOKE_EXIT=$?" >> "$LOG"

echo "SMOKE_AFTER_FIX_DONE" >> "$LOG"
