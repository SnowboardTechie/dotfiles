#!/bin/sh
# Wait for a Rex-hosted Pi or Claude worker's turn to settle (references/rex-claude-handoff.md).
#
# usage: rex_wait.sh <transcript.jsonl> <handback.md> <cap seconds> [marker regex]
#
# The transcript is a Pi session file (~/.pi/agent/sessions/<cwd>/<time>_<session id>.jsonl) or a Claude one; both
# are read as the same two states. Turn ended: the last assistant message stopped without a tool call (Pi `stop`,
# `error` or `aborted`; Claude `end_turn`). Unanswered: the last message is the user's or a tool result.
#
# Settled: the turn ended, the handback ends with its `Divergence:` line and, when a marker is given (a correction
# turn's new section heading, e.g. "Correction 1"), the handback contains it. Exit 0 settled; 2 when the turn has
# stayed ended ~10 polls with no handback (a worker waiting on a question or stopped early: read the pane); 3 when
# the last record is unanswered and the transcript has been silent ~8 min: the turn halted without ending (a
# safety-filter stop leaves the pane idle at its prompt), so read the pane; 1 on the cap. A running tool shows an
# assistant tool call last, so a long foreground test never trips 3. Run it with terminal(background=true,
# notify=true). Use `test -f`, never `ls`, in such shells: an interactive alias can turn `ls` into another tool.
T=$1; H=$2; end=$(( $(date +%s) + $3 )); M=${4:-}; n=0; st=""
STALL=${REX_WAIT_STALL_SECONDS:-480}; POLL=${REX_WAIT_POLL_SECONDS:-60}; ENDED_POLLS=${REX_WAIT_ENDED_POLLS:-10}
while [ "$(date +%s)" -lt "$end" ]; do
  if [ -f "$T" ]; then
    st=$(tail -40 "$T" | python3 -c '
import json,sys
st=""
for l in sys.stdin:
    try: d=json.loads(l)
    except Exception: continue
    m=d.get("message") or {}
    if d.get("type")=="message":  # Pi
        role=m.get("role")
        if role=="assistant": st="working" if m.get("stopReason")=="toolUse" else "ended"
        elif role in ("user","toolResult"): st="unanswered"
    elif d.get("type")=="assistant":  # Claude
        st="ended" if m.get("stop_reason")=="end_turn" else "working"
    elif d.get("type")=="user":
        st="unanswered"
print(st)')
  fi
  if [ "$st" = ended ]; then
    # The handback's last paragraph starts with `Divergence:`; a long one wraps over several lines, so look at the
    # last non-blank paragraph rather than the last few lines.
    if [ -f "$H" ] && awk 'NF{p=(p==""||blank)?$0:p; blank=0; next} {blank=1} END{exit !(p ~ /^Divergence:/)}' "$H" && { [ -z "$M" ] || grep -q "$M" "$H"; }; then
      echo "SETTLED $H $(date)"; exit 0
    fi
    n=$((n+1)); [ $n -ge "$ENDED_POLLS" ] && { echo "ENDTURN-NO-HANDBACK $H $(date)"; exit 2; }
  else
    n=0
    if [ "$st" = unanswered ] && [ -f "$T" ] && [ $(( $(date +%s) - $(stat -f %m "$T" 2>/dev/null || stat -c %Y "$T") )) -ge "$STALL" ]; then
      echo "STALLED-NO-REPLY $T $(date)"; exit 3
    fi
  fi
  sleep "$POLL"
done
echo "TIMEOUT $H last=$st"; exit 1
