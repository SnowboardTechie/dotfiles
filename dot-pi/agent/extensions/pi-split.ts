// Opens a second Pi in a Rex pane to the right of this one, adapted from
// split-fork.ts in mitsuhiko/agent-stuff (Ghostty AppleScript swapped for Rex).
//   /split [prompt]       a fresh Pi
//   /split-fork [prompt]  a Pi on a copy of this conversation (`pi --fork`)
// The new Pi runs on this session's model, thinking level and Claude seat; the
// prompt, if any, is its first message. Focus stays here.
// The Rex work (split, typed command, wait for Pi to start) is done by the
// next-session launcher, dot-agents/skills/next-session/scripts/launch_next_session.py,
// found relative to this file's real path in the repository.
import { mkdtempSync, realpathSync, writeFileSync, existsSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";
import { execFile } from "node:child_process";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function launcherPath(extensionFile: string): string {
	// <repo>/dot-pi/agent/extensions/pi-split.ts -> <repo>/dot-agents/...
	const repo = resolve(dirname(realpathSync(extensionFile)), "..", "..", "..");
	return join(repo, "dot-agents", "skills", "next-session", "scripts", "launch_next_session.py");
}

export function seatFlag(env: NodeJS.ProcessEnv = process.env, home = homedir()): string[] {
	const dir = (env.PI_CLAUDE_CODE_CONFIG_DIR || env.CLAUDE_CONFIG_DIR || "").replace(/\/+$/, "");
	if (!dir || dir === join(home, ".claude")) return ["--seat", "work"];
	if (dir === join(home, ".claude-personal")) return ["--seat", "personal"];
	return []; // an unfamiliar config dir: leave it to the new pane's shell
}

export interface SplitRequest {
	launcher: string;
	name: string;
	cwd: string;
	model?: { provider: string; id: string };
	thinking?: string;
	promptFile?: string;
	forkFile?: string;
	env?: NodeJS.ProcessEnv;
	home?: string;
}

export function launchArgs(r: SplitRequest): string[] {
	const args = [r.launcher, "launch", "--agent", "pi", "--name", r.name, "--cwd", r.cwd];
	if (r.promptFile) args.push("--prompt-file", r.promptFile);
	if (r.forkFile) args.push("--fork", r.forkFile);
	if (r.model) args.push("--model", `${r.model.provider}/${r.model.id}`);
	if (r.thinking) args.push("--thinking", r.thinking);
	args.push(...seatFlag(r.env, r.home));
	return args;
}

export function paneName(fork: boolean): string {
	return `${fork ? "fork" : "split"}-${randomBytes(2).toString("hex")}`;
}

export default function (pi: ExtensionAPI) {
	const launcher = launcherPath(fileURLToPath(import.meta.url));

	const register = (command: string, fork: boolean, description: string) =>
		pi.registerCommand(command, {
			description,
			handler: async (args, ctx) => {
				const say = (msg: string, level: "info" | "warning" | "error") =>
					ctx.hasUI ? ctx.ui.notify(msg, level) : console.log(msg);
				if (!process.env.REX_BLOCK || !process.env.REX_SESSION) {
					say(`/${command} needs a Pi running in a Rex pane.`, "warning");
					return;
				}
				let forkFile: string | undefined;
				if (fork) {
					forkFile = ctx.sessionManager.getSessionFile();
					if (!forkFile || !existsSync(forkFile)) {
						say(`/${command}: this session has nothing saved to fork yet.`, "warning");
						return;
					}
				}
				const prompt = args.trim();
				let promptFile: string | undefined;
				if (prompt) {
					promptFile = join(mkdtempSync(join(tmpdir(), "pi-split-")), "prompt.md");
					writeFileSync(promptFile, `${prompt}\n`, "utf8");
				}
				const name = paneName(fork);
				const argv = launchArgs({
					launcher,
					name,
					cwd: ctx.cwd,
					model: ctx.model ? { provider: ctx.model.provider, id: ctx.model.id } : undefined,
					thinking: pi.getThinkingLevel(),
					promptFile,
					forkFile,
				});
				// Pi sets PI_SESSION_ID only for its tools' children, and pi.exec takes no env,
				// so the launcher gets this session's id explicitly.
				const env = { ...process.env, PI_SESSION_ID: ctx.sessionManager.getSessionId() };
				delete env.HERMES_SESSION_ID;
				const result = await new Promise<{ code: number; stdout: string; stderr: string }>((done) =>
					execFile("python3", argv, { env, timeout: 120_000 }, (err, stdout, stderr) =>
						done({ code: err ? (typeof err.code === "number" ? err.code : 1) : 0, stdout, stderr })),
				);
				let out: { ok?: boolean; reason?: string; pane?: string; manual?: string } = {};
				try {
					out = JSON.parse(result.stdout);
				} catch {
					out = { ok: false, reason: (result.stderr || result.stdout || "no output").trim().slice(-400) };
				}
				if (result.code === 0 && out.ok) {
					say(`Opened ${name} in Rex pane ${out.pane}${prompt ? " with the prompt" : ""}.`, "info");
				} else {
					say(`/${command} failed: ${out.reason ?? "unknown error"}${out.manual ? `; run: ${out.manual}` : ""}`, "error");
				}
			},
		});

	register("split", false, "Open a fresh Pi in a Rex pane to the right, same model and seat. Usage: /split [prompt]");
	register("split-fork", true, "Open a Pi on a copy of this conversation in a Rex pane to the right. Usage: /split-fork [prompt]");
}
