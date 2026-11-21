// Pi's counterpart to the SessionStart hook that `rex skill setup` installs for Claude and
// Codex (Rex reports hooks as unsupported for Pi). Inside a Rex pane, an interactive Pi:
//   - is told which Rex session and pane it runs in, with the text Rex itself prints for
//     agents (`rex __internal session-start`), so a Rex upgrade updates it;
//   - names its pane, its tab and the Rex session when the first request arrives, in the
//     background. A local Ollama model reads the request and the working directory's name
//     and proposes the names; without it, the request's first words become them. The model
//     the user talks to has no naming tool and no naming note, so naming costs it no tokens.
//     A session whose only tab this is gets the tab's name. When the request names a pull
//     request or issue (a URL, "PR 1411", "issue 1389", "#123"), the pane and tab names start
//     with it ("PR 1411 Deps Bump Feedback", "pr-1411-feedback"); a GitHub one's title is read
//     with `gh` and given to the model, so the words after the number say what it is about.
// Naming follows how the work is laid out: a session is one initiative ("Pi Durable"), a
// tab is one workstream of it ("Subscription Rename"), a pane is one agent ("w31-9-review", the same
// slug as the Pi session name). Every level is named once, and only while it still carries
// a placeholder: Rex's generated label, or the /split launcher's `split-ab12`. A label set
// by hand or by a launcher is never replaced. The session has one more guard: the first Pi
// to name it leaves a marker, and no Pi names that session again.
// An interactive Pi in a Rex pane also sets PI_CLIPBOARD_OSC52=1, so its copies go out as OSC 52
// too and reach the clipboard of the Mac whose Rex app shows the pane, not only the server Mac's.
// It is set here, not only in a shell profile, because Pis that Rex starts directly (splits,
// launchers, resumes after a server restart) never run one. Pi reads it on every copy.
// Headless Pis (`pi -p`) a session starts inherit REX_BLOCK from its pane, so everything
// here is limited to the TUI.
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join } from "node:path";
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

/** Appended to Rex's briefing: the names are this extension's to give, not the model's. */
export const renameRule = "Don't rename the Rex session, tabs or panes with the rex CLI unless the user asks.";

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

/** The pull request or issue a request is about, when it names one. */
export interface Reference {
	/** How names start: "PR 1411", "Issue 1389", or "#123" when the kind is unknown. */
	label: string;
	/** Where its title can be read: GitHub's `owner/repo` and number. */
	github?: { repo: string; number: string };
	/** Its title, when it could be read. */
	title?: string;
}

// What a reference looks like in a request, earliest match first: a GitHub or Forgejo URL,
// "PR 1411" / "PR1411" / "pull request #12", "issue 1196", or a bare "#123".
const referencePatterns: [RegExp, (m: RegExpExecArray) => Reference][] = [
	[/https?:\/\/([^/\s]+)\/([\w.-]+\/[\w.-]+)\/(pull|pulls|issues)\/(\d+)/i, (m) => ({
		label: `${/^pull/i.test(m[3]) ? "PR" : "Issue"} ${m[4]}`,
		...(m[1].toLowerCase() === "github.com" ? { github: { repo: m[2], number: m[4] } } : {}),
	})],
	[/\b(?:PR|pull request)\s*#?(\d+)\b/i, (m) => ({ label: `PR ${m[1]}` })],
	[/\bissue\s*#?(\d+)\b/i, (m) => ({ label: `Issue ${m[1]}` })],
	[/(?:^|[\s(])#(\d+)\b/, (m) => ({ label: `#${m[1]}` })],
];

/** The first pull request or issue the request names, if any. */
export function findReference(request: string): Reference | undefined {
	let best: { at: number; ref: Reference } | undefined;
	for (const [pattern, make] of referencePatterns) {
		const m = pattern.exec(request);
		if (m && (!best || m.index < best.at)) best = { at: m.index, ref: make(m) };
	}
	return best?.ref;
}

/** Reads a GitHub issue or pull request title with `gh`; undefined when it can't. */
export type TitleReader = (repo: string, number: string) => Promise<string | undefined>;

export function ghTitle(command = "gh"): TitleReader {
	return (repo, number) =>
		new Promise((done) =>
			execFile(command, ["api", `repos/${repo}/issues/${number}`, "--jq", ".title"], { timeout: 5000 }, (err, stdout) =>
				done(err ? undefined : String(stdout ?? "").trim().slice(0, 200) || undefined)),
		);
}

/** Start each name with the reference: "PR 1411 Deps Bump Feedback", "pr-1411-feedback". */
export function withReference(want: Wanted, ref: Reference | undefined): Wanted {
	if (!ref) return want;
	const prefix = slug(ref.label);
	const strip = (text: string, pattern: RegExp) => text.replace(pattern, "").trim();
	const num = ref.label.replace(/\D/g, "");
	const rest = strip(want.tab ?? "", new RegExp(`^(?:(?:PR|Issue|Pull Request)\\s*)?#?${num}\\b[\\s:·-]*`, "i"));
	const paneRest = slug(want.pane ?? "").split("-").filter((w) => w && w !== num && w !== "pr" && w !== "issue").slice(0, 2).join("-");
	return {
		...want,
		tab: title(rest ? `${ref.label} ${rest}` : ref.label),
		pane: slug(paneRest ? `${prefix}-${paneRest}` : prefix),
	};
}

/** Proposes names for a first request made in the named directory; undefined when it can't. */
export type Namer = (request: string, directory: string, ref?: Reference) => Promise<Wanted | undefined>;

/** Strip pasted markup and keep a request short enough for a naming prompt. */
export function requestText(request: string): string {
	return request.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 2000);
}

/** A pane slug of at most three words. */
export function shortSlug(text: string): string {
	return slug(slug(text).split("-").filter(Boolean).slice(0, 3).join("-"));
}

/** Names from the request's own first words, for when no model answers. */
export function wordsNames(request: string): Wanted {
	const words = requestText(request).replace(/https?:\/\/\S+/g, " ").split(" ").filter((w) => /[a-z0-9]/i.test(w)).slice(0, 4).join(" ");
	const tab = title(words.replace(/\b\w/g, (c) => c.toUpperCase()));
	return { pane: shortSlug(words), tab, session: tab };
}

// A local model through Ollama's chat API. Thinking off and a JSON schema keep the answer to
// three short strings (about 1.5 s warm, about 20 s when the model must load first). keep_alive
// unloads it a minute later, so a 28 GB model doesn't sit in memory for pane names.
export const namerPrompt = [
	"Name a terminal pane after the task in the user's first message to a coding agent, working in the named directory. Reply with JSON only.",
	"Name the specific subject of the work, never just the activity: 'Pydantic Error Cleanup', not 'Code Changes'; 'Search Filter Feedback', not 'Review Feedback' or 'PR Review Fixes'.",
	"pane: a lowercase hyphenated slug of one to three words for the task.",
	"tab: a Title Case name of two to five words for the workstream.",
	"session: a short Title Case name for the wider initiative or project the work belongs to, never a PR or issue number.",
	"When the message gives a Reference line, the work is that pull request or issue: tab is the reference followed by two to four words on its subject and what is being done, taken from its title and the request, and pane is the reference slug followed by one or two words.",
	"Formats with a reference: tab 'PR 1520 Search Filter Feedback', pane 'pr-1520-feedback'; tab 'Issue 1530 Award Schema Docs', pane 'issue-1530-docs'; tab 'PR 1540 Auth Refactor Answers', pane 'pr-1540-answers'.",
	"Formats without one: tab 'Pydantic Error Cleanup', pane 'pydantic-errors'; tab 'Laptop Backup Research', pane 'backup-research'.",
].join(" ");

export function ollamaNamer(env: NodeJS.ProcessEnv = process.env, request: typeof fetch = fetch): Namer {
	const url = (env.PI_REX_NAMER_URL ?? "http://127.0.0.1:11434").replace(/\/+$/, "");
	const model = env.PI_REX_NAMER_MODEL ?? "qwen3.8-pi:27b-q8";
	return async (text, directory, ref) => {
		const reference = ref ? `Reference: ${ref.label}${ref.title ? ` — ${ref.title}` : ""}\n` : "";
		try {
			const response = await request(`${url}/api/chat`, {
				method: "POST",
				headers: { "content-type": "application/json" },
				signal: AbortSignal.timeout(90_000),
				body: JSON.stringify({
					model,
					stream: false,
					think: false,
					keep_alive: "1m",
					format: {
						type: "object",
						properties: { pane: { type: "string" }, tab: { type: "string" }, session: { type: "string" } },
						required: ["pane", "tab", "session"],
					},
					messages: [
						{
							role: "system",
							content: namerPrompt,
						},
						{ role: "user", content: `Directory: ${directory}\n${reference}\n${requestText(text)}` },
					],
				}),
			});
			if (!response.ok) return undefined;
			const answer = JSON.parse(((await response.json()) as { message?: { content?: string } }).message?.content ?? "");
			const pane = shortSlug(String(answer.pane ?? ""));
			const tab = title(String(answer.tab ?? ""));
			const session = title(String(answer.session ?? ""));
			return pane && tab ? { pane, tab, session: session || tab } : undefined;
		} catch {
			return undefined;
		}
	};
}

export default function (
	pi: ExtensionAPI,
	run: Run = rexRunner(rexCommand()),
	claims: Claims = fileClaims(),
	env: NodeJS.ProcessEnv = process.env,
	namer: Namer = ollamaNamer(env),
	readTitle: TitleReader = ghTitle(),
) {
	const sessionId = env.REX_SESSION;
	const blockId = env.REX_BLOCK;
	if (!sessionId || !blockId) return;

	let interactive = false;
	let directory = "";
	// The whole `rex` section, built once per Pi process. A changed section reaches Claude as a
	// mid-conversation system message, which costs a prompt-cache write and, through
	// pi-claude-code, pushed requests past Anthropic's four cache breakpoints ("Found 5").
	let section: string | undefined;
	let namingStarted = false;
	/** The naming of the first request, exposed so tests can wait for it. */
	let naming: Promise<void> = Promise.resolve();

	// A Pi session that already has a name (`pi --name`, /name, a resumed session) labels
	// its pane without asking a model.
	const labelPaneFromSessionName = async () => {
		const name = pi.getSessionName();
		if (interactive && name) await applyNames(run, sessionId, blockId, { pane: name }, claims).catch(() => {});
	};

	pi.on("session_start", async (_event, ctx) => {
		interactive = ctx.mode === "tui";
		if (!interactive) return;
		env.PI_CLIPBOARD_OSC52 = "1";
		directory = basename(ctx.cwd ?? process.cwd());
		await labelPaneFromSessionName();
	});

	pi.on("session_info_changed", labelPaneFromSessionName);

	// Names whatever still has a placeholder, from the first request. When the request names a
	// pull request or issue, every name but the session's starts with it, whatever the namer said.
	// A session whose only tab this is takes the tab's name, unless that name is a reference;
	// otherwise it takes the namer's own session name. The claim marker still lets only one Pi
	// name a session.
	const nameFromFirstRequest = async (request: string) => {
		const view = await run(["session", "inspect", sessionId, "--json"]);
		const loc = view.code === 0 ? locate(JSON.parse(view.stdout), blockId) : undefined;
		if (!loc) return;
		const paneOpen = placeholder.pane(loc.pane);
		const tabOpen = placeholder.tab(loc.tab);
		const sessionOpen = placeholder.session(loc.session) && !claims.has(sessionId);
		if (!paneOpen && !tabOpen && !sessionOpen) return;
		const ref = findReference(requestText(request));
		if (ref?.github) ref.title = await readTitle(ref.github.repo, ref.github.number).catch(() => undefined);
		const proposed = withReference((await namer(request, directory, ref)) ?? wordsNames(request), ref);
		const want: Wanted = {};
		if (paneOpen && proposed.pane) want.pane = proposed.pane;
		if (tabOpen && proposed.tab) want.tab = proposed.tab;
		const sessionName = loc.tabs === 1 && tabOpen && !ref ? proposed.tab : proposed.session;
		if (sessionOpen && sessionName) want.session = sessionName;
		await applyNames(run, sessionId, blockId, want, claims);
		if (want.pane && !pi.getSessionName()) pi.setSessionName(slug(want.pane));
	};

	pi.on("before_agent_start", async (event: any) => {
		if (!interactive) return;
		if (!namingStarted && event.messageType !== "custom" && typeof event.prompt === "string" && event.prompt.trim()) {
			namingStarted = true;
			// Not awaited: a cold model takes about 20 s, and the run must not wait for it.
			naming = nameFromFirstRequest(event.prompt).catch(() => {});
		}
		if (section === undefined) {
			try {
				const out = await run(["__internal", "session-start", "--agent", "pi", "--feature-session-naming=false"]);
				const rexText = out.code === 0 ? briefing(out.stdout) : "";
				// Keep only a complete result; an unreachable Rex is asked again next turn.
				if (rexText) section = `${rexText}\n\n${renameRule}`;
			} catch {
				// Rex being unreachable must never block a turn.
			}
		}
		if (section) (event.systemPromptOptions.sections ??= {}).rex = section;
	});
	return { naming: () => naming };
}
