#!/bin/bash
LOG=/tmp/logshow2.log
: > "$LOG"

cd /Users/bcb/Documents/ClarityOmega/IterBrow/iter || exit 1

date +"%Y-%m-%d %H:%M:%S" >> "$LOG"
echo "--- launching ---" >> "$LOG"
START=$(date +"%Y-%m-%d %H:%M:%S")

./.venv/bin/python3 -u -c "import hyperon; print(1)" >> "$LOG" 2>&1
EXIT=$?
END=$(date +"%Y-%m-%d %H:%M:%S")
echo "EXIT=$EXIT" >> "$LOG"
echo "START=$START END=$END" >> "$LOG"

echo "--- log show ---" >> "$LOG"
log show --start "$START" --end "$END" --predicate 'eventMessage contains "hyperonpy" or eventMessage contains "python3" or eventMessage contains "AMFI" or eventMessage contains "Gatekeeper" or eventMessage contains "sandboxd" or eventMessage contains "TCC" or eventMessage contains "ReportCrash"' >> "$LOG" 2>&1

echo "INVESTIGATE_DONE" >> "$LOG"
