#!/bin/sh
# Wait for a Rex-hosted Claude worker's turn to settle (references/rex-claude-handoff.md).
#
# usage: rex_wait.sh <transcript.jsonl> <handback.md> <cap seconds> [marker regex]
#
# Settled: the transcript's last assistant/user record is `assistant end_turn`, the handback ends with its
# `Divergence:` line and, when a marker is given (a correction turn's new section heading, e.g. "Correction 1"),
# the handback contains it. Exit 0 settled; 2 when end_turn has held ~10 polls with no handback (a worker waiting
# on a question or stopped early: read the pane); 3 when the last record is a `user` one (a prompt or tool
# result the model never answered) and the transcript has been silent ~8 min: the turn halted without end_turn
# (a safety-filter stop leaves the pane idle at its prompt), so read the pane; 1 on the cap. A running tool shows
# `assistant tool_use` last, so a long foreground test never trips 3. Run it with terminal(background=true,
# notify=true). Use `test -f`, never `ls`, in such shells: an interactive alias can turn `ls` into another tool.
T=$1; H=$2; end=$(( $(date +%s) + $3 )); M=${4:-}; n=0; st=""; STALL=${REX_WAIT_STALL_SECONDS:-480}
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
    # The handback's last paragraph starts with `Divergence:`; a long one wraps over several lines, so look at the
    # last non-blank paragraph rather than the last few lines.
    if [ -f "$H" ] && awk 'NF{p=(p==""||blank)?$0:p; blank=0; next} {blank=1} END{exit !(p ~ /^Divergence:/)}' "$H" && { [ -z "$M" ] || grep -q "$M" "$H"; }; then
      echo "SETTLED $H $(date)"; exit 0
    fi
    n=$((n+1)); [ $n -ge 10 ] && { echo "ENDTURN-NO-HANDBACK $H $(date)"; exit 2; }
  else
    n=0
    if [ "$st" = "user None" ] && [ -f "$T" ] && [ $(( $(date +%s) - $(stat -f %m "$T" 2>/dev/null || stat -c %Y "$T") )) -ge "$STALL" ]; then
      echo "STALLED-NO-REPLY $T $(date)"; exit 3
    fi
  fi
  sleep 60
done
echo "TIMEOUT $H last=$st"; exit 1
