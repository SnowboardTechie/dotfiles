// Shows which Claude subscription pays for this Pi session's claude-code turns.
// The `pi` wrapper in dot-config/shell/aliases.sh sets PI_CLAUDE_CODE_CONFIG_DIR to the
// personal plan outside ~/code/sgg; pi-claude-code passes it on as CLAUDE_CONFIG_DIR.
// Unset means Claude Code's default login (the work subscription).
//   footer: "subscription: personal · 5h 12% ↻17:00 · week 15% ↻Fri 09:00 · sent 14:03:27"
//     The usage comes from the `claude-code.rate-limit` diagnostic pi-claude-code puts on each
//     assistant message (Claude Code's rate_limit_event, unifiedWindows), so it appears after the
//     first claude-code reply (or from the resumed history) and follows whichever plan answered. A plan without a five-hour
//     window (the personal one, 2026-11-17) shows only the week. "sent" is when the last user
//     message was sent, local time to the second.
//   /subscription:  the subscription plus the account Claude Code reports for it
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function subscriptionConfigDir(env: NodeJS.ProcessEnv = process.env): string | undefined {
	return env.PI_CLAUDE_CODE_CONFIG_DIR || env.CLAUDE_CONFIG_DIR || undefined;
}

export function subscriptionName(configDir: string | undefined, home = homedir()): string {
	if (!configDir || configDir.replace(/\/+$/, "") === join(home, ".claude")) return "work";
	if (configDir.replace(/\/+$/, "") === join(home, ".claude-personal")) return "personal";
	return configDir;
}

type Window = { utilization?: number; resetsAt?: number };
export type Usage = Record<string, Window>;

/** The rate-limit windows on an assistant message's claude-code diagnostic, if any. */
export function usageFromMessage(message: any): Usage | undefined {
	const diags = Array.isArray(message?.diagnostics) ? message.diagnostics : [];
	for (let i = diags.length - 1; i >= 0; i--) {
		const d = diags[i];
		if (d?.type !== "claude-code.rate-limit") continue;
		const w = d.details?.unifiedWindows;
		if (w && typeof w === "object") return w as Usage;
	}
	return undefined;
}

const pad = (n: number) => String(n).padStart(2, "0");
export function clock(ms: number): string {
	const d = new Date(ms);
	return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function resetLabel(sec: number, now: number): string {
	const d = new Date(sec * 1000);
	const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
	if (new Date(now).toDateString() === d.toDateString()) return hm;
	return `${d.toLocaleDateString("en-US", { weekday: "short" })} ${hm}`;
}

function windowLabel(label: string, w: Window | undefined, now: number): string | undefined {
	if (!w || typeof w.utilization !== "number") return undefined;
	const pct = `${label} ${Math.round(w.utilization * 100)}%`;
	return typeof w.resetsAt === "number" ? `${pct} ↻${resetLabel(w.resetsAt, now)}` : pct;
}

export function footerText(parts: { subscription?: string; usage?: Usage; sentAt?: number; now?: number }): string | undefined {
	const now = parts.now ?? Date.now();
	const out: string[] = [];
	if (parts.subscription) out.push(`subscription: ${parts.subscription}`);
	if (parts.usage) {
		for (const [key, label] of [["five_hour", "5h"], ["seven_day", "week"]] as const) {
			const text = windowLabel(label, parts.usage[key], now);
			if (text) out.push(text);
		}
	}
	if (parts.sentAt) out.push(`sent ${clock(parts.sentAt)}`);
	return out.length ? out.join(" · ") : undefined;
}

export default function (pi: ExtensionAPI) {
	const dir = subscriptionConfigDir();
	const name = subscriptionName(dir);
	// Machines without the personal login have one subscription; leave its name out there.
	const shown = existsSync(join(homedir(), ".claude-personal")) ? name : undefined;
	let usage: Usage | undefined;
	let sentAt: number | undefined;

	const render = (ctx: { hasUI: boolean; ui: { setStatus(key: string, text: string | undefined): void } }) => {
		if (ctx.hasUI) ctx.ui.setStatus("subscription", footerText({ subscription: shown, usage, sentAt }));
	};

	pi.on("session_start", async (_event, ctx) => {
		// A resumed session: the last user message's time and the last usage seen. The wrapper picks
		// the plan by directory, so a resume normally reaches the same plan; the next reply corrects it.
		usage = undefined;
		sentAt = undefined;
		for (const entry of ctx.sessionManager.getBranch() as any[]) {
			const m = entry?.type === "message" ? entry.message : undefined;
			if (m?.role === "user" && typeof m.timestamp === "number") sentAt = m.timestamp;
			if (m?.role === "assistant" && m.provider === "claude-code") usage = usageFromMessage(m) ?? usage;
		}
		render(ctx);
	});

	pi.on("message_start", async (event, ctx) => {
		const m = event.message as any;
		if (m?.role !== "user") return;
		sentAt = typeof m.timestamp === "number" ? m.timestamp : Date.now();
		render(ctx);
	});

	pi.on("message_end", async (event, ctx) => {
		const m = event.message as any;
		if (m?.role !== "assistant" || m.provider !== "claude-code") return;
		const next = usageFromMessage(m);
		if (!next) return;
		usage = next;
		render(ctx);
	});

	pi.registerCommand("subscription", {
		description: "Show which Claude subscription this session uses",
		handler: async (_args, ctx) => {
			const env = { ...process.env };
			if (dir) env.CLAUDE_CONFIG_DIR = dir;
			else delete env.CLAUDE_CONFIG_DIR;
			let account = "account unknown";
			try {
				const { execFileSync } = await import("node:child_process");
				const out = execFileSync("claude", ["auth", "status", "--json"], { env, timeout: 15000, encoding: "utf8" });
				const s = JSON.parse(out);
				if (s.loggedIn) {
					const org = s.orgName && !String(s.orgName).includes(s.email) ? s.orgName : undefined;
					account = [s.email, org, s.subscriptionType].filter(Boolean).join(", ");
				} else {
					account = "not logged in";
				}
			} catch (err) {
				account = `claude auth status failed: ${(err as Error).message.split("\n")[0]}`;
			}
			const line = `Subscription: ${name} (${dir ?? "default login"}); ${account}`;
			if (ctx.hasUI) ctx.ui.notify(line, "info");
			else console.log(line);
		},
	});
}
