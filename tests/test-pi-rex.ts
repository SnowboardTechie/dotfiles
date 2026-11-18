// Tests for dot-pi/agent/extensions/pi-rex.ts (Rex briefing and pane/tab/session naming).
// Run: node --test tests/test-pi-rex.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import init, { applyNames, briefing, fileClaims, locate, ollamaNamer, renameRule, placeholder, requestText, rexCommand, shortSlug, slug, title, wordsNames, type Claims, type Namer, type Run, type Wanted } from "../dot-pi/agent/extensions/pi-rex.ts";

const S = "session:1";
const B = "block:2";
const W = "window:3";

function view(session: string, tab: string, pane: string, extraTabs = 0) {
	const windows: unknown[] = [{ window_id: W, label: tab, layers: [{ blocks: [{ block_id: "block:other", label: "shell" }, { block_id: B, label: pane }] }] }];
	for (let i = 0; i < extraTabs; i++) windows.push({ window_id: `window:x${i}`, label: "Other", layers: [{ blocks: [] }] });
	return { session_id: S, label: session, windows };
}

function fakeRex(v: unknown, fail: string[] = []) {
	const calls: string[][] = [];
	const run: Run = async (args) => {
		calls.push(args);
		if (args[1] === "inspect") return { code: 0, stdout: JSON.stringify(v) };
		if (args[0] === "__internal") return { code: 0, stdout: "You're running in a Rex terminal.\n\nUse the `rex` command.\n\nThe Rex setup for this agent is out of date. Suggest running `rex skill setup`\nto update it.\n" };
		return { code: fail.includes(args[0]) ? 1 : 0, stdout: "" };
	};
	return { run, calls, renames: () => calls.filter((c) => c[1] === "rename") };
}

function memoryClaims(taken: string[] = []): Claims {
	const set = new Set(taken);
	return { has: (id) => set.has(id), take: (id) => !set.has(id) && !!set.add(id), release: (id) => void set.delete(id) };
}

test("placeholders are Rex's generated labels and the /split launcher's names", () => {
	for (const l of ["dawn-canyon", "wandering-bay"]) assert.ok(placeholder.session(l), l);
	for (const l of ["Pi Durable", "Pi > Hermes", "PiRex", "Containerize Pi?", "planning-agents-vms", "work"]) assert.ok(!placeholder.session(l), l);
	assert.ok(placeholder.tab("Window 1bd453b0"));
	for (const l of ["Subscription Rename", "PiRex", "Window"]) assert.ok(!placeholder.tab(l), l);
	for (const l of ["shell", "split-ab12", "fork-0001"]) assert.ok(placeholder.pane(l), l);
	for (const l of ["w31-9", "relay-tests", "pi-next", "w31-9-review"]) assert.ok(!placeholder.pane(l), l);
});

test("names are cleaned for the level they go to", () => {
	assert.equal(slug("Rex Naming!"), "rex-naming");
	assert.equal(slug("w31-9-review"), "w31-9-review");
	assert.equal(slug("--"), "");
	assert.equal(title("  Pi  Rex\nNaming "), "Pi Rex Naming");
	assert.equal(title("--help"), "help");
	assert.ok(title("x".repeat(90)).length <= 40);
});

test("rex is found through REX_BIN_DIR when it is not on PATH", () => {
	assert.equal(rexCommand({ REX_BIN_DIR: "/r/MacOS" }), "/r/MacOS/rex");
	assert.equal(rexCommand({}), "rex");
});

test("a pane is located with its tab, session and tab count", () => {
	assert.deepEqual(locate(view("dawn-canyon", "Window 1bd453b0", "shell", 2), B), { session: "dawn-canyon", windowId: W, tab: "Window 1bd453b0", pane: "shell", tabs: 3 });
	assert.equal(locate(view("a", "b", "c"), "block:gone"), undefined);
	assert.equal(locate(undefined, B), undefined);
});

test("a fresh session gets all three names, in Rex's rename commands", async () => {
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	const report = await applyNames(rex.run, S, B, { pane: "Rex Naming", tab: "PiRex", session: "PiRex" }, memoryClaims());
	assert.deepEqual(rex.renames(), [
		["block", "rename", "-s", S, B, "rex-naming"],
		["window", "rename", "-s", S, W, "PiRex"],
		["session", "rename", S, "PiRex"],
	]);
	assert.deepEqual(report, ['pane: renamed to "rex-naming"', 'tab: renamed to "PiRex"', 'session: renamed to "PiRex"']);
});

test("names the user or a launcher set are kept", async () => {
	const rex = fakeRex(view("Pi > Hermes", "Subscription Rename", "w31-9"));
	const report = await applyNames(rex.run, S, B, { pane: "x", tab: "Y", session: "Z" }, memoryClaims());
	assert.deepEqual(rex.renames(), []);
	assert.deepEqual(report, ['pane: kept "w31-9" (already named)', 'tab: kept "Subscription Rename" (already named)', 'session: kept "Pi > Hermes" (already named)']);
});

test("only the first agent names the session", async () => {
	const claims = memoryClaims();
	const first = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	await applyNames(first.run, S, B, { session: "Pi Durable" }, claims);
	assert.deepEqual(first.renames(), [["session", "rename", S, "Pi Durable"]]);
	// The user then restores Rex's generated label; a second agent still stays out.
	const second = fakeRex(view("dawn-canyon", "Window 1bd453b0", "split-ab12"));
	const report = await applyNames(second.run, S, B, { pane: "review", tab: "Review", session: "Other" }, claims);
	assert.deepEqual(second.renames().map((c) => c[0]), ["block", "window"]);
	assert.match(report[2], /^session: kept "dawn-canyon" \(another agent already named/);
});

test("a refused session rename gives the claim back", async () => {
	const claims = memoryClaims();
	const rex = fakeRex(view("dawn-canyon", "T", "p"), ["session"]);
	const report = await applyNames(rex.run, S, B, { session: "Pi Durable" }, claims);
	assert.match(report[0], /Rex refused/);
	assert.equal(claims.has(S), false);
});

test("an unreachable or unfamiliar Rex renames nothing", async () => {
	const down: Run = async () => ({ code: 1, stdout: "" });
	assert.deepEqual(await applyNames(down, S, B, { pane: "x" }, memoryClaims()), ["Rex did not report this pane; nothing was renamed."]);
	const junk: Run = async () => ({ code: 0, stdout: "not json" });
	assert.deepEqual(await applyNames(junk, S, B, { pane: "x" }, memoryClaims()), ["Rex did not report this pane; nothing was renamed."]);
});

test("the claim marker can be taken once per Rex session", () => {
	const dir = mkdtempSync(join(tmpdir(), "pi-rex-test-"));
	const a = fileClaims(dir);
	const b = fileClaims(dir);
	assert.equal(a.has("session:01a1/../x"), false);
	assert.equal(a.take("session:01a1/../x", "One"), true);
	assert.equal(b.take("session:01a1/../x", "Two"), false);
	assert.equal(b.has("session:01a1/../x"), true);
	assert.equal(a.take("session:other", "Three"), true);
	a.release("session:01a1/../x");
	assert.equal(b.take("session:01a1/../x", "Two"), true);
});

test("Rex's briefing drops its out-of-date-setup advice", () => {
	assert.equal(briefing("One.\n\nThe Rex setup for this agent is out of date. Suggest running `rex skill setup`\nto update it.\n"), "One.");
});

// A minimal fake of Pi's extension API.
function fakePi(sessionName?: string) {
	const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
	const tools: any[] = [];
	let name = sessionName;
	const pi = {
		on: (event: string, handler: never) => void (handlers[event] = handler),
		registerTool: (tool: unknown) => void tools.push(tool),
		getSessionName: () => name,
		setSessionName: (next: string) => void (name = next),
	};
	return { pi: pi as never, handlers, tools, name: () => name };
}

test("outside Rex the extension registers nothing", () => {
	const fake = fakePi();
	init(fake.pi, fakeRex(view("a", "b", "c")).run, memoryClaims(), {});
	assert.deepEqual(Object.keys(fake.handlers), []);
});

test("a headless Pi in a Rex pane gets no tool, no briefing and renames nothing", async () => {
	const fake = fakePi("headless");
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "print" });
	const event = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(event, {});
	assert.deepEqual(fake.tools, []);
	assert.deepEqual(event.systemPromptOptions.sections, {});
	assert.deepEqual(rex.calls, []);
});

test("an interactive Pi gets Rex's briefing and the naming note as one prompt section", async () => {
	const fake = fakePi();
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	assert.deepEqual(fake.tools, [], "no naming tool for the model");
	const event = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(event, {});
	const text = event.systemPromptOptions.sections.rex;
	assert.match(text, /^You're running in a Rex terminal\./);
	assert.doesNotMatch(text, /out of date/);
	assert.ok(text.endsWith(renameRule));
	assert.doesNotMatch(text, /rex_name/);
	assert.deepEqual(rex.calls[0], ["__internal", "session-start", "--agent", "pi", "--feature-session-naming=false"]);
	await fake.handlers.before_agent_start(event, {});
	assert.equal(rex.calls.filter((c) => c[0] === "__internal").length, 1, "Rex's text is fetched once");
});

test("the prompt section stays byte-identical after a rename, and later turns do not ask Rex", async () => {
	// A changed section reaches Claude as a mid-conversation system message. Through
	// pi-claude-code that message pushed requests past Anthropic's four cache breakpoints
	// ("Found 5"), and any change also costs a prompt-cache write. The tool result already
	// tells the model what was renamed, so the note is computed once per Pi process.
	const fake = fakePi();
	const current = { v: view("dawn-canyon", "Window 1bd453b0", "shell") };
	const calls: string[][] = [];
	const run: Run = async (args) => {
		calls.push(args);
		if (args[1] === "inspect") return { code: 0, stdout: JSON.stringify(current.v) };
		if (args[0] === "__internal") return { code: 0, stdout: "You're running in a Rex terminal.\n" };
		return { code: 0, stdout: "" };
	};
	init(fake.pi, run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	const first = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(first, {});
	assert.match(first.systemPromptOptions.sections.rex, /Rex terminal/);

	current.v = view("Pi Durable", "PiRex", "rex-naming");
	const before = calls.length;
	const second = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(second, {});
	assert.equal(second.systemPromptOptions.sections.rex, first.systemPromptOptions.sections.rex);
	assert.deepEqual(calls.slice(before), [], "no Rex calls after the first turn");
});

test("an unreachable Rex on the first turn is tried again on the next", async () => {
	const fake = fakePi();
	let up = false;
	const run: Run = async (args) => {
		if (!up) throw new Error("rex down");
		if (args[1] === "inspect") return { code: 0, stdout: JSON.stringify(view("Pi Durable", "PiRex", "w31-9")) };
		return { code: 0, stdout: "You're running in a Rex terminal.\n" };
	};
	init(fake.pi, run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	const first = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(first, {});
	assert.deepEqual(first.systemPromptOptions.sections, {});
	up = true;
	const second = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(second, {});
	assert.ok(second.systemPromptOptions.sections.rex.endsWith(renameRule));
});

test("a Pi session that already has a name labels its pane at start", async () => {
	const fake = fakePi("w31-9-review");
	const rex = fakeRex(view("Pi > Hermes", "Subscription Rename Background Agents", "split-ab12"));
	init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	assert.deepEqual(rex.renames(), [["block", "rename", "-s", S, B, "w31-9-review"]]);
});

// Naming from the first request, by a local model, with no naming work for the model the user talks to.
const ask = (prompt: string) => ({ messageType: "user", prompt, systemPromptOptions: { sections: {} as Record<string, string> } });

async function firstRequest(namer: Namer, v = view("dawn-canyon", "Window 1bd453b0", "shell"), claims = memoryClaims()) {
	const fake = fakePi();
	const rex = fakeRex(v);
	const ext = init(fake.pi, rex.run, claims, { REX_SESSION: S, REX_BLOCK: B }, namer) as any;
	await fake.handlers.session_start({}, { mode: "tui", cwd: "/Users/bryan/code/pi-durable" });
	await fake.handlers.before_agent_start(ask("It seems like Opus has stopped renaming the Rex panes"), {});
	await ext.naming();
	return { fake, rex, ext };
}

test("the first request names the pane, tab and an only-tab session", async () => {
	const seen: string[][] = [];
	const { fake, rex } = await firstRequest(async (r, d) => (seen.push([r, d]), { pane: "rex-naming-debug", tab: "Rex Pane Naming", session: "Pi Tooling" }));
	assert.deepEqual(seen, [["It seems like Opus has stopped renaming the Rex panes", "pi-durable"]]);
	assert.deepEqual(rex.renames(), [
		["block", "rename", "-s", S, B, "rex-naming-debug"],
		["window", "rename", "-s", S, W, "Rex Pane Naming"],
		["session", "rename", S, "Rex Pane Naming"],
	]);
	assert.equal(fake.name(), "rex-naming-debug");
});

test("a session with other tabs takes the namer's own session name", async () => {
	const { rex } = await firstRequest(async () => ({ pane: "a", tab: "B", session: "Pi Tooling" }), view("dawn-canyon", "Window 1bd453b0", "shell", 1));
	assert.deepEqual(rex.renames().at(-1), ["session", "rename", S, "Pi Tooling"]);
});

test("a session another Pi already named is left alone", async () => {
	const { rex } = await firstRequest(async () => ({ pane: "a", tab: "B", session: "C" }), undefined, memoryClaims([S]));
	assert.ok(!rex.renames().some((c) => c[0] === "session"));
});

test("names already set are left, and the namer isn't asked", async () => {
	let asked = 0;
	const { rex } = await firstRequest(async () => (asked++, { pane: "x", tab: "Y" }), view("Pi Durable", "Subscription Rename", "w31-9"));
	assert.equal(asked, 0);
	assert.deepEqual(rex.renames(), []);
});

test("only a placeholder level is renamed", async () => {
	const { rex } = await firstRequest(async () => ({ pane: "rex-naming", tab: "Rex Naming", session: "Pi" }), view("Pi Durable", "Subscription Rename", "split-ab12"));
	assert.deepEqual(rex.renames(), [["block", "rename", "-s", S, B, "rex-naming"]]);
});

test("without an answer from the namer, the request's first words name everything", async () => {
	const { rex } = await firstRequest(async () => undefined);
	assert.deepEqual(rex.renames().map((c) => c.at(-1)), ["it-seems-like", "It Seems Like Opus", "It Seems Like Opus"]);
});

test("naming happens once, for the first request only", async () => {
	let asked = 0;
	const { fake, ext } = await firstRequest(async () => (asked++, undefined));
	await fake.handlers.before_agent_start(ask("second request"), {});
	await ext.naming();
	assert.equal(asked, 1);
});

test("the run doesn't wait for a slow namer", async () => {
	const fake = fakePi();
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	let answer!: (w: Wanted) => void;
	const ext = init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B }, () => new Promise((r) => (answer = r))) as any;
	await fake.handlers.session_start({}, { mode: "tui", cwd: "/x" });
	const event = ask("hello");
	await fake.handlers.before_agent_start(event, {});
	assert.match(event.systemPromptOptions.sections.rex, /Rex terminal/, "the turn went ahead");
	assert.deepEqual(rex.renames(), []);
	answer({ pane: "p", tab: "T", session: "S" });
	await ext.naming();
	assert.equal(rex.renames().length, 3);
});

test("a headless Pi names nothing", async () => {
	const fake = fakePi("headless");
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	let asked = 0;
	const ext = init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B }, async () => (asked++, undefined)) as any;
	await fake.handlers.session_start({}, { mode: "print" });
	await fake.handlers.before_agent_start(ask("hi"), {});
	await ext.naming();
	assert.equal(asked, 0);
	assert.deepEqual(rex.calls, []);
});

test("a run started by an extension message isn't taken as the first request", async () => {
	const fake = fakePi();
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	const seen: string[] = [];
	const ext = init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B }, async (r) => (seen.push(r), undefined)) as any;
	await fake.handlers.session_start({}, { mode: "tui", cwd: "/x" });
	await fake.handlers.before_agent_start({ messageType: "custom", systemPromptOptions: { sections: {} } }, {});
	await ext.naming();
	assert.deepEqual(seen, []);
	await fake.handlers.before_agent_start(ask("the real request"), {});
	await ext.naming();
	assert.deepEqual(seen, ["the real request"]);
});

test("request text and slugs are cut down for naming", () => {
	assert.equal(requestText("<file name=x>body</file>  and\n more"), "body and more");
	assert.equal(shortSlug("debug-rex-pane-renaming"), "debug-rex-pane");
	assert.deepEqual(wordsNames("<skill>x</skill> fix the pydantic errors"), { pane: "x-fix-the", tab: "X Fix The Pydantic", session: "X Fix The Pydantic" });
});

test("the Ollama namer asks for JSON with thinking off and cleans the answer", async () => {
	let sent: any;
	const fetchStub = (async (url: string, init: any) => {
		sent = { url, body: JSON.parse(init.body) };
		return { ok: true, json: async () => ({ message: { content: JSON.stringify({ pane: "Debug Rex Pane Renaming", tab: " Agent\nDebugging ", session: "Pi Tooling" }) } }) };
	}) as never;
	const names = await ollamaNamer({ PI_REX_NAMER_URL: "http://host:1/", PI_REX_NAMER_MODEL: "m" }, fetchStub)("hello", "pi-durable");
	assert.equal(sent.url, "http://host:1/api/chat");
	assert.equal(sent.body.model, "m");
	assert.equal(sent.body.think, false);
	assert.equal(sent.body.messages[1].content, "Directory: pi-durable\n\nhello");
	assert.deepEqual(sent.body.format.required, ["pane", "tab", "session"]);
	assert.deepEqual(names, { pane: "debug-rex-pane", tab: "Agent Debugging", session: "Pi Tooling" });
	const failing = ollamaNamer({}, (async () => { throw new Error("down"); }) as never);
	assert.equal(await failing("hello", "d"), undefined);
	const bad = ollamaNamer({}, (async () => ({ ok: true, json: async () => ({ message: { content: "not json" } }) })) as never);
	assert.equal(await bad("hello", "d"), undefined);
});
