// Pi's counterpart to the SessionStart hook that `rex skill setup` installs for Claude and
// Codex (Rex reports hooks as unsupported for Pi). Inside a Rex pane, an interactive Pi:
//   - is told which Rex session and pane it runs in, with the text Rex itself prints for
//     agents (`rex __internal session-start`), so a Rex upgrade updates it;
//   - names its pane, its tab and the Rex session through the `rex_name` tool.
// Naming follows how the work is laid out: a session is one initiative ("Pi Durable"), a
// tab is one lane of it ("Lane A pi-bots"), a pane is one agent ("w31-9-review", the same
// slug as the Pi session name). Every level is named once, and only while it still carries
// a placeholder: Rex's generated label, or the /split launcher's `split-ab12`. A label set
// by hand or by a launcher is never replaced. The session has one more guard: the first Pi
// to name it leaves a marker, and no Pi names that session again.
// Headless Pi children (`pi -p`) inherit REX_BLOCK from their parent's pane, so everything
// here is limited to the TUI.
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export type Run = (args: string[]) => Promise<{ code: number; stdout: string }>;

export interface Location {
	session: string;
	windowId: string;
	tab: string;
	pane: string;
	tabs: number;
}

export interface Claims {
	has(sessionId: string): boolean;
	/** True when this call created the marker, so exactly one caller wins. */
	take(sessionId: string, label: string): boolean;
	release(sessionId: string): void;
}

export function rexCommand(env: NodeJS.ProcessEnv = process.env): string {
	// Rex's CLI is not on PATH in every pane; Rex exports its directory instead.
	return env.REX_BIN_DIR ? join(env.REX_BIN_DIR, "rex") : "rex";
}

export const placeholder = {
	// Rex generates two lowercase words, such as `dawn-canyon`. A hand-set label of the
	// same shape is indistinguishable; the names this extension writes never have it.
	session: (label: string) => /^[a-z]+-[a-z]+$/.test(label),
	tab: (label: string) => /^Window [0-9a-f]{8}$/.test(label),
	pane: (label: string) => label === "shell" || /^(split|fork)-[0-9a-f]{4}$/.test(label),
};

export function slug(text: string): string {
	return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32).replace(/-+$/, "");
}

export function title(text: string): string {
	// A leading dash would read as a flag to the rex CLI.
	return text.replace(/[\u0000-\u001f\u007f-\u009f]/g, " ").replace(/\s+/g, " ").trim().replace(/^-+\s*/, "").slice(0, 40).trim();
}

/** Find a pane in `rex session inspect --json` output. */
export function locate(view: any, blockId: string): Location | undefined {
	for (const window of view?.windows ?? []) {
		for (const layer of window.layers ?? []) {
			for (const block of layer.blocks ?? []) {
				if (block.block_id !== blockId) continue;
				return {
					session: String(view.label ?? ""),
					windowId: String(window.window_id),
					tab: String(window.label ?? ""),
					pane: String(block.label ?? ""),
					tabs: view.windows.length,
				};
			}
		}
	}
	return undefined;
}

/** Rex's own briefing for agents, minus its advice about a setup this extension replaces. */
export function briefing(text: string): string {
	return text.split(/\n{2,}/).filter((p) => p.trim() && !/^The Rex setup for this agent is out of date/.test(p.trim())).join("\n\n").trim();
}

export function namingNote(loc: Location, sessionClaimed: boolean): string {
	const open: string[] = [];
	const sessionOpen = placeholder.session(loc.session) && !sessionClaimed;
	if (placeholder.pane(loc.pane)) {
		open.push("`pane`: a lowercase hyphenated slug of one to three words for this agent's task, such as `w31-9-review`");
	}
	if (placeholder.tab(loc.tab)) {
		open.push("`tab`: a short Title Case name for the lane of work in this tab, such as `Lane A pi-bots`");
	}
	if (sessionOpen) {
		open.push("`session`: a short Title Case name for the whole initiative, such as `Pi Durable`");
	}
	const rule = "Don't rename the Rex session, tabs or panes with the rex CLI unless the user asks.";
	if (!open.length) return `This pane, its tab and the Rex session are already named. ${rule}`;
	const lines = [
		"Some Rex names here are still placeholders. Once the first request makes the work clear, call the `rex_name` tool once, without being asked, and pass only these:",
		...open.map((line) => `- ${line}`),
	];
	if (loc.tabs === 1 && sessionOpen && placeholder.tab(loc.tab)) {
		lines.push("This is the session's only tab, so give `tab` and `session` the same name.");
	}
	lines.push(`Names the user or a launcher already set are kept. ${rule}`);
	return lines.join("\n");
}

export interface Wanted {
	pane?: string;
	tab?: string;
	session?: string;
}

/** Rename whatever still has a placeholder. Returns one report line per requested level. */
export async function applyNames(run: Run, sessionId: string, blockId: string, want: Wanted, claims: Claims): Promise<string[]> {
	const inspected = await run(["session", "inspect", sessionId, "--json"]);
	let loc: Location | undefined;
	try {
		loc = inspected.code === 0 ? locate(JSON.parse(inspected.stdout), blockId) : undefined;
	} catch {
		loc = undefined;
	}
	if (!loc) return ["Rex did not report this pane; nothing was renamed."];

	const report: string[] = [];
	const rename = async (level: string, current: string, next: string, free: boolean, args: string[], why: string) => {
		if (!next) return void report.push(`${level}: no usable name given`);
		if (!free) return void report.push(`${level}: kept "${current}" (${why})`);
		const result = await run([...args, next]);
		report.push(result.code === 0 ? `${level}: renamed to "${next}"` : `${level}: Rex refused the rename, still "${current}"`);
		return result.code === 0;
	};

	if (want.pane !== undefined) {
		await rename("pane", loc.pane, slug(want.pane), placeholder.pane(loc.pane), ["block", "rename", "-s", sessionId, blockId], "already named");
	}
	if (want.tab !== undefined) {
		await rename("tab", loc.tab, title(want.tab), placeholder.tab(loc.tab), ["window", "rename", "-s", sessionId, loc.windowId], "already named");
	}
	if (want.session !== undefined) {
		const next = title(want.session);
		if (!placeholder.session(loc.session)) {
			report.push(`session: kept "${loc.session}" (already named)`);
		} else if (!next) {
			report.push("session: no usable name given");
		} else if (!claims.take(sessionId, next)) {
			report.push(`session: kept "${loc.session}" (another agent already named this session once)`);
		} else if (!(await rename("session", loc.session, next, true, ["session", "rename", sessionId], ""))) {
			claims.release(sessionId);
		}
	}
	return report;
}

export function fileClaims(dir = join(homedir(), ".pi/agent/runtime/pi-rex/sessions")): Claims {
	const file = (sessionId: string) => join(dir, `${sessionId.replace(/[^\w.-]/g, "_")}.json`);
	return {
		has: (sessionId) => existsSync(file(sessionId)),
		take(sessionId, label) {
			try {
				mkdirSync(dir, { recursive: true, mode: 0o700 });
				// "wx" fails if the marker exists, so two agents cannot both take it.
				writeFileSync(file(sessionId), JSON.stringify({ label, pid: process.pid, at: new Date().toISOString() }), { flag: "wx", mode: 0o600 });
				return true;
			} catch {
				return false;
			}
		},
		release: (sessionId) => rmSync(file(sessionId), { force: true }),
	};
}

function rexRunner(command: string): Run {
	// Never start a server, and never let a hung one stall Pi.
	return (args) =>
		new Promise((done) =>
			execFile(command, ["--autostart=false", "--timeout", "2s", ...args], { timeout: 2500, maxBuffer: 4 * 1024 * 1024 }, (err, stdout) =>
				done({ code: err ? 1 : 0, stdout: String(stdout ?? "") })),
		);
}

export default function (pi: ExtensionAPI, run: Run = rexRunner(rexCommand()), claims: Claims = fileClaims(), env: NodeJS.ProcessEnv = process.env) {
	const sessionId = env.REX_SESSION;
	const blockId = env.REX_BLOCK;
	if (!sessionId || !blockId) return;

	let interactive = false;
	let rexText: string | undefined;

	// A Pi session that already has a name (`pi --name`, /name, a resumed session) labels
	// its pane without asking the model.
	const labelPaneFromSessionName = async () => {
		const name = pi.getSessionName();
		if (interactive && name) await applyNames(run, sessionId, blockId, { pane: name }, claims).catch(() => {});
	};

	pi.on("session_start", async (_event, ctx) => {
		interactive = ctx.mode === "tui";
		if (!interactive) return;
		pi.registerTool({
			name: "rex_name",
			label: "Name Rex pane",
			description:
				"Name this agent's Rex pane, its tab, and the Rex session after the work. Each is renamed only while it still has a placeholder name; names the user set are kept, and the result says which were applied.",
			parameters: {
				type: "object",
				properties: {
					pane: { type: "string", description: "Lowercase hyphenated slug for this agent's task, one to three words." },
					tab: { type: "string", description: "Short Title Case name for the lane of work in this tab." },
					session: { type: "string", description: "Short Title Case name for the whole initiative." },
				},
				additionalProperties: false,
			} as never,
			async execute(_id, params: Wanted) {
				const report = await applyNames(run, sessionId, blockId, params, claims);
				// The pane label and the Pi session name are the same slug in this setup.
				if (params.pane && slug(params.pane) && !pi.getSessionName()) pi.setSessionName(slug(params.pane));
				return { content: [{ type: "text", text: report.join("\n") || "Nothing to name." }], details: undefined };
			},
		});
		await labelPaneFromSessionName();
	});

	pi.on("session_info_changed", labelPaneFromSessionName);

	pi.on("before_agent_start", async (event) => {
		if (!interactive) return;
		try {
			if (rexText === undefined) {
				const out = await run(["__internal", "session-start", "--agent", "pi", "--feature-session-naming=false"]);
				rexText = out.code === 0 ? briefing(out.stdout) : "";
			}
			const view = await run(["session", "inspect", sessionId, "--json"]);
			const loc = view.code === 0 ? locate(JSON.parse(view.stdout), blockId) : undefined;
			const text = [rexText, loc ? namingNote(loc, claims.has(sessionId)) : ""].filter(Boolean).join("\n\n");
			// Pi diffs sections and patches only what changed, so the prompt cache survives.
			if (text) (event.systemPromptOptions.sections ??= {}).rex = text;
		} catch {
			// Rex being unreachable must never block a turn.
		}
	});
}
