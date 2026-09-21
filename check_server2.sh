#!/bin/bash
LOG=/tmp/check_server2.log
: > "$LOG"
ps -p 38740,40571 -o pid,ppid,lstart,command >> "$LOG" 2>&1
echo "---dSYM check---" >> "$LOG"
SO=/Users/bcb/Documents/ClarityOmega/IterBrow/iter/.venv/lib/python3.12/site-packages/hyperonpy.cpython-312-darwin.so
ls -la "$SO" "$SO.dSYM" 2>&1 >> "$LOG"
codesign -dv "$SO" >> "$LOG" 2>&1
echo CHECK_SERVER2_DONE >> "$LOG"
