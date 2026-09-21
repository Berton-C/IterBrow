#!/bin/bash
LOG=/tmp/restart_after_fix.log
: > "$LOG"
echo "=== before ===" >> "$LOG"
pgrep -fl 'python.*metta_server\.py' >> "$LOG" 2>&1
kill -TERM 42492 2>>"$LOG"
sleep 2
kill -KILL 42492 2>>"$LOG"
sleep 1
echo "=== after kill ===" >> "$LOG"
pgrep -fl 'python.*metta_server\.py' >> "$LOG" 2>&1
echo RESTART_AFTER_FIX_DONE >> "$LOG"
