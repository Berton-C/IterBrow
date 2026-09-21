#!/bin/bash
LOG=/tmp/check_server.log
: > "$LOG"
pgrep -fl metta_server.py >> "$LOG" 2>&1
echo "---" >> "$LOG"
ls -la /tmp/iter-metta-bridge.sock >> "$LOG" 2>&1
echo CHECK_SERVER_DONE >> "$LOG"
