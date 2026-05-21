#!/usr/bin/env node
// Reads Claude Code's native statusLine JSON from stdin and renders a compact HUD.
//
// Available native fields (per Claude Code statusLine docs):
//   rate_limits.{five_hour,seven_day}.{used_percentage,resets_at}   (Pro/Max only, after 1st API resp)
//   context_window.used_percentage
//   cost.{total_cost_usd,total_duration_ms}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (input += chunk));
process.stdin.on("end", () => {
  let data;
  try {
    data = JSON.parse(input);
  } catch {
    process.stdout.write("\n");
    return;
  }

  const dim = (s) => `\x1b[2m${s}\x1b[0m`;
  const colorPct = (pct) => {
    const code = pct >= 80 ? 31 : pct >= 50 ? 33 : 32; // red / yellow / green
    return `\x1b[${code}m${pct}%\x1b[0m`;
  };

  const fmtRemaining = (resetsAt) => {
    const sec = Math.max(0, resetsAt - Math.floor(Date.now() / 1000));
    if (sec >= 86400) return `${Math.floor(sec / 86400)}d${Math.floor((sec % 86400) / 3600)}h`;
    if (sec >= 3600) return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
    if (sec >= 60) return `${Math.floor(sec / 60)}m`;
    return `${sec}s`;
  };

  const fmtDuration = (ms) => {
    const sec = Math.floor(ms / 1000);
    if (sec >= 3600) return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
    if (sec >= 60) return `${Math.floor(sec / 60)}m`;
    return `${sec}s`;
  };

  const parts = [];

  const fh = data.rate_limits?.five_hour;
  if (fh?.used_percentage != null) {
    let s = `5h:${colorPct(Math.round(fh.used_percentage))}`;
    if (fh.resets_at) s += dim(`(${fmtRemaining(fh.resets_at)})`);
    parts.push(s);
  }

  const wk = data.rate_limits?.seven_day;
  if (wk?.used_percentage != null) {
    let s = `wk:${colorPct(Math.round(wk.used_percentage))}`;
    if (wk.resets_at) s += dim(`(${fmtRemaining(wk.resets_at)})`);
    parts.push(s);
  }

  const ctx = data.context_window?.used_percentage;
  if (ctx != null) parts.push(`ctx:${colorPct(Math.round(ctx))}`);

  const dur = data.cost?.total_duration_ms;
  if (dur != null) parts.push(dim("session:") + fmtDuration(dur));

  const cost = data.cost?.total_cost_usd;
  if (cost != null && cost > 0) parts.push(dim("$") + cost.toFixed(2));

  process.stdout.write(parts.join(dim(" | ")) + "\n");
});
