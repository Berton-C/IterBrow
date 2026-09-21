#!/bin/bash
LOG=/tmp/kill_all_metta.log
: > "$LOG"
echo "=== before ===" >> "$LOG"
pgrep -fl 'python.*metta_server\.py' >> "$LOG" 2>&1

for pid in $(pgrep -f 'python.*metta_server\.py'); do
  kill -TERM "$pid" 2>>"$LOG"
done
sleep 2
for pid in $(pgrep -f 'python.*metta_server\.py'); do
  kill -KILL "$pid" 2>>"$LOG"
done
sleep 1

echo "=== after ===" >> "$LOG"
pgrep -fl 'python.*metta_server\.py' >> "$LOG" 2>&1
echo "=== lock/socket files ===" >> "$LOG"
ls -la /tmp/iter-metta-bridge.sock* 2>&1 >> "$LOG"
rm -f /tmp/iter-metta-bridge.sock.lock 2>>"$LOG"
echo KILL_ALL_METTA_DONE >> "$LOG"
