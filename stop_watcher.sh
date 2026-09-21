#!/bin/bash
LOG=/tmp/stop_watcher.log
: > "$LOG"

echo "=== before ===" >> "$LOG"
pgrep -fl watch_and_catch.sh >> "$LOG" 2>&1
echo "---lldb count---" >> "$LOG"
pgrep -fl "lldb -p" >> "$LOG" 2>&1

echo "=== killing ===" >> "$LOG"
pkill -9 -f watch_and_catch.sh >> "$LOG" 2>&1
echo "pkill1_exit=$?" >> "$LOG"
pkill -9 -f "lldb -p" >> "$LOG" 2>&1
echo "pkill2_exit=$?" >> "$LOG"

sleep 1
echo "=== after ===" >> "$LOG"
pgrep -fl watch_and_catch.sh >> "$LOG" 2>&1
pgrep -fl "lldb -p" >> "$LOG" 2>&1

echo "=== metta_server.py still alive (sanity - should NOT be affected) ===" >> "$LOG"
pgrep -fl "python.*metta_server.py" | grep -v bash >> "$LOG" 2>&1

echo STOP_WATCHER_DONE >> "$LOG"
