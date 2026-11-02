#!/bin/sh
# Wait for a Rex-hosted Claude worker's turn to settle (references/rex-claude-handoff.md).
#
# usage: rex_wait.sh <transcript.jsonl> <handback.md> <cap seconds> [marker regex]
#
# Settled: the transcript's last assistant/user record is `assistant end_turn`, the handback ends with its
# `Divergence:` line and, when a marker is given (a correction turn's new section heading, e.g. "Correction 1"),
# the handback contains it. Exit 0 settled; 2 when end_turn has held ~10 polls with no handback (a worker waiting
# on a question or stopped early: read the pane); 1 on the cap. Run it with terminal(background=true,
# notify=true). Use `test -f`, never `ls`, in such shells: an interactive alias can turn `ls` into another tool.
T=$1; H=$2; end=$(( $(date +%s) + $3 )); M=${4:-}; n=0; st=""
while [ "$(date +%s)" -lt "$end" ]; do
  if [ -f "$T" ]; then
    st=$(tail -40 "$T" | python3 -c '
import json,sys
last=None
for l in sys.stdin:
    try: d=json.loads(l)
    except Exception: continue
    if d.get("type") in ("assistant","user"): last=d
m=(last or {}).get("message") or {}
print(last and last["type"], m.get("stop_reason"))')
  fi
  if [ "$st" = "assistant end_turn" ]; then
    if [ -f "$H" ] && tail -3 "$H" | grep -q '^Divergence:' && { [ -z "$M" ] || grep -q "$M" "$H"; }; then
      echo "SETTLED $H $(date)"; exit 0
    fi
    n=$((n+1)); [ $n -ge 10 ] && { echo "ENDTURN-NO-HANDBACK $H $(date)"; exit 2; }
  else n=0; fi
  sleep 60
done
echo "TIMEOUT $H last=$st"; exit 1
