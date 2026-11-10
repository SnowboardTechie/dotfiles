// Shows which Claude subscription ("seat") pays for this Pi session's claude-code turns.
// The `pi` wrapper in dot-config/shell/aliases.sh sets PI_CLAUDE_CODE_CONFIG_DIR to the
// personal plan outside ~/code/sgg; pi-claude-code passes it on as CLAUDE_CONFIG_DIR.
// Unset means Claude Code's default login (the work seat).
//   footer: "seat: personal" / "seat: work"
//   /seat:  the seat plus the account Claude Code reports for it
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function seatConfigDir(env: NodeJS.ProcessEnv = process.env): string | undefined {
	return env.PI_CLAUDE_CODE_CONFIG_DIR || env.CLAUDE_CONFIG_DIR || undefined;
}

export function seatName(configDir: string | undefined, home = homedir()): string {
	if (!configDir || configDir.replace(/\/+$/, "") === join(home, ".claude")) return "work";
	if (configDir.replace(/\/+$/, "") === join(home, ".claude-personal")) return "personal";
	return configDir;
}

export default function (pi: ExtensionAPI) {
	const dir = seatConfigDir();
	const name = seatName(dir);

	pi.on("session_start", async (_event, ctx) => {
		// Hosts without the personal login have one seat; keep the footer quiet there.
		if (ctx.hasUI && existsSync(join(homedir(), ".claude-personal"))) ctx.ui.setStatus("seat", `seat: ${name}`);
	});

	pi.registerCommand("seat", {
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
			const line = `Seat: ${name} (${dir ?? "default login"}); ${account}`;
			if (ctx.hasUI) ctx.ui.notify(line, "info");
			else console.log(line);
		},
	});
}
