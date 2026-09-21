#!/bin/bash
LOG=/tmp/logshow4.log
: > "$LOG"

cd /Users/bcb/Documents/ClarityOmega/IterBrow/iter || exit 1
SO=/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/lib/python3.12/site-packages/hyperonpy.cpython-312-darwin.so

START=$(date +"%Y-%m-%d %H:%M:%S")
./.venv/bin/python3 -u -c "
import ctypes, os
print('PID', os.getpid())
print('before dlopen')
lib = ctypes.CDLL('$SO')
print('after dlopen', lib)
" >> "$LOG" 2>&1
EXIT=$?
sleep 1
END=$(date +"%Y-%m-%d %H:%M:%S")
echo "EXIT=$EXIT START=$START END=$END" >> "$LOG"

echo "=== FULL LOG SHOW (unfiltered) ===" >> "$LOG"
log show --start "$START" --end "$END" >> "$LOG" 2>&1

echo "INVESTIGATE3_DONE" >> "$LOG"
