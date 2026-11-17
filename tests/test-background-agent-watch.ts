// Tests for dot-pi/agent/extensions/background-agent-watch.ts (keeping a Pi orchestrator attached to its
// background agents).
// Run: node --test tests/test-background-agent-watch.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { existsSync, mkdtempSync, mkdirSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import init, { startsOrPromptsBackgroundAgent, waitScript, type Spawn } from "../dot-pi/agent/extensions/background-agent-watch.ts";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const extension = join(repo, "dot-pi", "agent", "extensions", "background-agent-watch.ts");

// Commands as orchestrators actually ran them on 2026-11-16.
const START = `"$REX" window new -s "$REX_SESSION" "$(get tab_label)" --focus=false --keep-open -c "$W" --json -- env PI_PROGRAM_STATUS=0 pi --name x --session-id "$UUID" "@$S/prompt.md"`;
const SPLIT = `"$REX" split -s "$REX_SESSION" -b "$(get anchor)" --split=right --focus=false --keep-open --label x -c "$W" --json -- pi --session-id "$UUID"`;
const PROMPT = `"$REX" send -s "$REX_SESSION" -b $B "Read $S1/correction-1.md in full and carry out Correction 1 exactly as written there."`;
const QUIT = `"$REX" send -s "$REX_SESSION" -b block:1 "/quit"`;
const WAIT = `$SK/scripts/rex_wait.sh "$T" "$S/completion-report.md" 3300 "Correction 1"`;

function fakePi() {
	const handlers = new Map<string, Function[]>();
	const tools = new Map<string, any>();
	const sent: { message: any; options: any }[] = [];
	const pi = {
		on: (name: string, fn: Function) => handlers.set(name, [...(handlers.get(name) ?? []), fn]),
		registerTool: (t: any) => tools.set(t.name, t),
		sendMessage: (message: any, options: any) => sent.push({ message, options }),
	};
	const emit = async (name: string, event: any = {}) => {
		let last;
		for (const fn of handlers.get(name) ?? []) last = await fn(event, {});
		return last;
	};
	return { pi, tools, sent, emit };
}

function fakeSpawn() {
	const children: (EventEmitter & { stdout: EventEmitter; stderr: EventEmitter; kill: () => void; killed: boolean; args: string[] })[] = [];
	const spawn: Spawn = (_script, args) => {
		const c = Object.assign(new EventEmitter(), { stdout: new EventEmitter(), stderr: new EventEmitter(), killed: false, args, kill() { this.killed = true; this.emit("close", null, "SIGTERM"); } });
		children.push(c);
		return c as never;
	};
	return { spawn, children };
}

const bash = (command: string) => ({ toolName: "bash", input: { command } });
const settle = (emit: Function) => emit("agent_before_settle", { entries: [] });

function setup() {
	const p = fakePi();
	const s = fakeSpawn();
	init(p.pi as never, s.spawn);
	return { ...p, ...s, watch: (args: any) => p.tools.get("watch_background_agent").execute("id", args) };
}

test("the wait script is found through the ~/.pi symlink", () => {
	const home = mkdtempSync(join(tmpdir(), "background-agent-watch-test-"));
	mkdirSync(join(home, "extensions"));
	const link = join(home, "extensions", "background-agent-watch.ts");
	symlinkSync(extension, link);
	const found = waitScript(link);
	assert.equal(found, join(repo, "dot-agents", "skills", "coding-agent-handoff-supervision", "scripts", "rex_wait.sh"));
	assert.ok(existsSync(found));
});

test("background agent starts and typed turns are recognised; quitting and other rex calls are not", () => {
	for (const c of [START, SPLIT, PROMPT]) assert.ok(startsOrPromptsBackgroundAgent(c), c);
	for (const c of [QUIT, `"$REX" capture -s "$REX_SESSION" -b x --trim`, `"$REX" block close -s "$REX_SESSION" x`, "git push", `pi --session-id x`]) {
		assert.ok(!startsOrPromptsBackgroundAgent(c), c);
	}
});

test("a run that starts a background agent and stops without a watch is continued once", async () => {
	const { emit } = setup();
	await emit("before_agent_start");
	await emit("tool_call", bash(START));
	const r: any = await settle(emit);
	assert.equal(r.continue, true);
	assert.match(r.entries[0].content, /call watch_background_agent/);
	assert.equal(await settle(emit), undefined, "only once per run");
});

test("a running watch satisfies the check", async () => {
	const { emit, watch, children } = setup();
	await emit("before_agent_start");
	await emit("tool_call", bash(PROMPT));
	const res = await watch({ label: "docs-review", transcript: "/t.jsonl", completion_report: "/h.md", marker: "Correction 1" });
	assert.match(res.content[0].text, /Watching docs-review/);
	assert.deepEqual(children[0].args, ["/t.jsonl", "/h.md", "14400", "Correction 1"]);
	assert.equal(await settle(emit), undefined);
});

test("a foreground wait in the same command satisfies the check", async () => {
	const { emit } = setup();
	await emit("before_agent_start");
	await emit("tool_call", bash(`${PROMPT}\n${WAIT}`));
	assert.equal(await settle(emit), undefined);
});

test("runs that touch no background agent are left alone", async () => {
	const { emit } = setup();
	await emit("before_agent_start");
	await emit("tool_call", bash(QUIT));
	await emit("tool_call", { toolName: "read", input: { path: START } });
	assert.equal(await settle(emit), undefined);
});

test("a settled background agent wakes the session with its result", async () => {
	const { emit, watch, children, sent } = setup();
	await watch({ label: "core-docs", transcript: "/t.jsonl", completion_report: "/h.md" });
	children[0].stdout.emit("data", "SETTLED /h.md");
	children[0].emit("close", 0, null);
	assert.equal(sent.length, 1);
	assert.deepEqual(sent[0].options, { triggerTurn: true, deliverAs: "followUp" });
	assert.match(sent[0].message.content, /core-docs: settled/);
	assert.match(sent[0].message.content, /SETTLED \/h\.md/);
	await emit("before_agent_start");
	assert.equal(await settle(emit), undefined);
});

test("a wait that ends without settling must be re-armed or released", async () => {
	const { emit, watch, children, sent } = setup();
	await watch({ label: "core-docs", transcript: "/t.jsonl", completion_report: "/h.md" });
	children[0].emit("close", 2, null);
	assert.match(sent[0].message.content, /no finished completion report/);
	await emit("before_agent_start");
	const r: any = await settle(emit);
	assert.match(r.entries[0].content, /not re-armed or released: core-docs/);
	await emit("before_agent_start");
	await watch({ label: "core-docs", transcript: "/t.jsonl", completion_report: "/h.md" });
	assert.equal(await settle(emit), undefined, "re-armed");
	await watch({ label: "core-docs", transcript: "/t.jsonl", release: true });
	assert.equal(children[1].killed, true);
	assert.equal(await settle(emit), undefined, "released");
});

test("re-arming replaces the old wait without a stale wake-up", async () => {
	const { watch, children, sent } = setup();
	await watch({ label: "w", transcript: "/t.jsonl", completion_report: "/h.md" });
	await watch({ label: "w", transcript: "/t.jsonl", completion_report: "/h.md", marker: "Correction 1" });
	assert.equal(children[0].killed, true);
	children[0].emit("close", 0, null);
	assert.equal(sent.length, 0);
});

test("quitting Pi stops every wait", async () => {
	const { emit, watch, children } = setup();
	await watch({ label: "a", transcript: "/a", completion_report: "/ha" });
	await watch({ label: "b", transcript: "/b", completion_report: "/hb" });
	await emit("session_shutdown");
	assert.ok(children.every((c) => c.killed));
});
