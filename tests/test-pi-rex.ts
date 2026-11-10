// Tests for dot-pi/agent/extensions/pi-rex.ts (Rex briefing and pane/tab/session naming).
// Run: node --test tests/test-pi-rex.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import init, { applyNames, briefing, fileClaims, locate, namingNote, placeholder, rexCommand, slug, title, type Claims, type Run } from "../dot-pi/agent/extensions/pi-rex.ts";

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
	for (const l of ["Lane A pi-bots", "PiRex", "Window"]) assert.ok(!placeholder.tab(l), l);
	for (const l of ["shell", "split-ab12", "fork-0001"]) assert.ok(placeholder.pane(l), l);
	for (const l of ["w31-9", "lane-b", "pi-next", "w31-9-review"]) assert.ok(!placeholder.pane(l), l);
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
	const rex = fakeRex(view("Pi > Hermes", "Lane A pi-bots", "w31-9"));
	const report = await applyNames(rex.run, S, B, { pane: "x", tab: "Y", session: "Z" }, memoryClaims());
	assert.deepEqual(rex.renames(), []);
	assert.deepEqual(report, ['pane: kept "w31-9" (already named)', 'tab: kept "Lane A pi-bots" (already named)', 'session: kept "Pi > Hermes" (already named)']);
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

test("the note asks only for the levels that are still placeholders", () => {
	const fresh = namingNote({ session: "dawn-canyon", windowId: W, tab: "Window 1bd453b0", pane: "shell", tabs: 1 }, false);
	assert.match(fresh, /`pane`/);
	assert.match(fresh, /`tab`/);
	assert.match(fresh, /`session`/);
	assert.match(fresh, /same name/);
	const lane = namingNote({ session: "Pi > Hermes", windowId: W, tab: "Window 1bd453b0", pane: "split-ab12", tabs: 4 }, false);
	assert.match(lane, /`pane`/);
	assert.match(lane, /`tab`/);
	assert.doesNotMatch(lane, /`session`:/);
	assert.doesNotMatch(lane, /same name/);
	const claimed = namingNote({ session: "dawn-canyon", windowId: W, tab: "PiRex", pane: "shell", tabs: 1 }, true);
	assert.doesNotMatch(claimed, /`session`:/);
	const named = namingNote({ session: "Pi > Hermes", windowId: W, tab: "Lane A pi-bots", pane: "w31-9", tabs: 4 }, false);
	assert.match(named, /already named/);
	assert.doesNotMatch(named, /rex_name/);
});

test("Rex's briefing drops its out-of-date-setup advice", () => {
	assert.equal(briefing("One.\n\nThe Rex setup for this agent is out of date. Suggest running `rex skill setup`\nto update it.\n"), "One.");
});

// A minimal stand-in for Pi's extension API.
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
	const fake = fakePi("child");
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
	assert.deepEqual(fake.tools.map((t) => t.name), ["rex_name"]);
	const event = { systemPromptOptions: { sections: {} as Record<string, string> } };
	await fake.handlers.before_agent_start(event, {});
	const text = event.systemPromptOptions.sections.rex;
	assert.match(text, /^You're running in a Rex terminal\./);
	assert.doesNotMatch(text, /out of date/);
	assert.match(text, /rex_name/);
	assert.deepEqual(rex.calls[0], ["__internal", "session-start", "--agent", "pi", "--feature-session-naming=false"]);
	await fake.handlers.before_agent_start(event, {});
	assert.equal(rex.calls.filter((c) => c[0] === "__internal").length, 1, "Rex's text is fetched once");
});

test("the tool names the pane and gives an unnamed Pi session the same slug", async () => {
	const fake = fakePi();
	const rex = fakeRex(view("dawn-canyon", "Window 1bd453b0", "shell"));
	init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	const result = await fake.tools[0].execute("id", { pane: "Rex Naming", tab: "PiRex", session: "PiRex" });
	assert.equal(rex.renames().length, 3);
	assert.equal(fake.name(), "rex-naming");
	assert.match(result.content[0].text, /pane: renamed to "rex-naming"/);
});

test("a Pi session that already has a name labels its pane at start", async () => {
	const fake = fakePi("w31-9-review");
	const rex = fakeRex(view("Pi > Hermes", "Lane A pi-bots Sub Agents", "split-ab12"));
	init(fake.pi, rex.run, memoryClaims(), { REX_SESSION: S, REX_BLOCK: B });
	await fake.handlers.session_start({}, { mode: "tui" });
	assert.deepEqual(rex.renames(), [["block", "rename", "-s", S, B, "w31-9-review"]]);
});
