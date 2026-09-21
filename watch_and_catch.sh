#!/bin/bash
# Continuously watches for the newest metta_server.py PID and attaches an
# lldb crash-catcher (in the background, non-blocking) to each new one as
# it appears, so whichever instance is actually serving live queries gets
# caught with debug symbols on its next natural SIGSEGV.
LOGDIR=/tmp/mettawatch
mkdir -p "$LOGDIR"
STATE=/tmp/mettawatch_last_pid.txt
: > "$LOGDIR/watcher.log"
echo "watcher started $(date)" >> "$LOGDIR/watcher.log"

LAST_PID=""
for i in $(seq 1 200); do
  NEWEST=$(pgrep -f 'python.*metta_server\.py' -n 2>/dev/null)
  if [ -n "$NEWEST" ] && [ "$NEWEST" != "$LAST_PID" ]; then
    echo "$(date) new pid detected: $NEWEST (prev: $LAST_PID)" >> "$LOGDIR/watcher.log"
    LOG="$LOGDIR/crash_${NEWEST}.log"
    (lldb -p "$NEWEST" \
      -o "process handle SIGSEGV --stop true --pass true --notify true" \
      -o "process handle SIGABRT --stop true --pass true --notify true" \
      -o "continue" \
      -o "bt all" \
      -o "register read" \
      -o "thread list" \
      -o "process status" \
      -o "memory region \$pc" \
      -o "detach" \
      -o "quit" > "$LOG" 2>&1 &)
    LAST_PID="$NEWEST"
  fi
  sleep 4
done
echo "watcher finished $(date)" >> "$LOGDIR/watcher.log"
