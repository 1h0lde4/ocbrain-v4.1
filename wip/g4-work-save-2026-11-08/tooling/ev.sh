#!/usr/bin/env bash
# usage: ev.sh ID 'command'   -> runs in /home/claude/ocbrain-v4.1, records command, UTC time, exit status, output
SP=/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a5
ID="$1"; shift
F="$SP/evidence/$ID.txt"
{
  echo "# evidence-id: $ID"
  echo "# started-utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)  (tz of user: Africa/Casablanca, UTC+00:00)"
  echo "# cwd: /home/claude/ocbrain-v4.1"
  echo "# command: $*"
  echo "# ---- output ----"
} > "$F"
( cd /home/claude/ocbrain-v4.1 && bash -c "$*" ) >> "$F" 2>&1
RC=$?
{ echo "# ---- end output ----"; echo "# exit-status: $RC"; echo "# finished-utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } >> "$F"
cat "$F"
