// Tests for dot-pi/agent/extensions/stream-rules.ts.
// Run: node --test tests/test-stream-rules.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import init, { broken as brokenRules, prose, RULES } from "../dot-pi/agent/extensions/stream-rules.ts";

const broken = (text: string) => brokenRules(text, new Set())[0]?.id;

test("each rule catches what Bryan keeps correcting", () => {
	assert.equal(broken("Fixed in #123."), "bare-issue-reference");
	assert.equal(broken("See (#45) for context"), "bare-issue-reference");
	assert.equal(broken("Lane A is still running"), "coined-label");
	assert.equal(broken("probe 3 failed"), "coined-label");
	assert.equal(broken("Open http://localhost:8080 to view it"), "local-web-link");
	assert.equal(broken("It's at file:///tmp/x.html"), "local-web-link");
	assert.equal(broken("Yes, it's done. One loose end: the cache."), "done-with-loose-ends");
	assert.equal(broken("**Yes.** Two things still open: x and y."), "done-with-loose-ends");
});

test("ordinary prose, links and code pass", () => {
	for (const ok of [
		"Fixed in [#123](https://git.example.com/r/issues/123), the login bug.",
		"The gateway address-ownership test passes.",
		"Run `git log #123` or see\n```\nlane A\nhttp://localhost:3000\n```",
		"Served at https://mac.tail1234.ts.net/demo/",
		"No. Two items are still open: the Omarchy run and the key.",
		"The C# compiler and color #fff are fine.",
		"A worker pool with 4 workers",
	]) assert.equal(broken(ok), undefined, ok);
});

test("prose drops code and link text", () => {
	assert.equal(prose("a `b` [c](d) e").replace(/\s+/g, " ").trim(), "a e");
});

test("a rule fires at most once per prompt", () => {
	const fired = new Set(["bare-issue-reference"]);
	assert.deepEqual(brokenRules("see #1", fired), []);
	assert.deepEqual(brokenRules("see #1 in lane B", fired).map((r) => r.id), ["coined-label"]);
});

test("every broken rule is reported together", () => {
	assert.deepEqual(brokenRules("Tracked in #77 and lane C picks it up.", new Set()).map((r) => r.id), ["bare-issue-reference", "coined-label"]);
});

function harness() {
	const handlers: Record<string, Function> = {};
	const notes: string[] = [];
	init({ on: (name: string, fn: Function) => (handlers[name] = fn) } as any);
	const ctx = { hasUI: true, ui: { notify: (m: string) => notes.push(m) } };
	const turnEnd = (text: string, extra: Partial<Record<string, unknown>> = {}) =>
		handlers.turn_end(
			{ outcome: "completed", toolResults: [], entries: [], messageEntryId: "m1", message: { role: "assistant", content: [{ type: "text", text }] }, ...extra },
			ctx,
		);
	return { handlers, notes, turnEnd };
}

test("a broken reply is withdrawn and asked for again, once per prompt", async () => {
	const h = harness();
	await h.handlers.before_agent_start({ messageType: "user" });
	const r = await h.turnEnd("Done in #12.");
	assert.equal(r.continue, true);
	assert.deepEqual(r.entries[0], { type: "context_edit", targetId: "m1", replacement: null });
	assert.equal(r.entries[1].type, "custom_message");
	assert.equal(r.entries[1].display, false);
	assert.match(r.entries[1].content, /bare issue or PR number/);
	assert.equal(h.notes.length, 1);
	assert.equal(await h.turnEnd("Done in #12."), undefined, "retry that still breaks it is kept");
	await h.handlers.before_agent_start({ messageType: "user" });
	const both = await h.turnEnd("Done in #12; lane C next.");
	assert.match(both.entries[1].content, /bare issue[\s\S]*labels of your own/);
	assert.deepEqual(both.entries[1].details, { rules: ["bare-issue-reference", "coined-label"] });
	assert.equal(await h.turnEnd("Done in #12; lane C next."), undefined, "one retry covers both");
	await h.handlers.before_agent_start({ messageType: "user" });
	assert.ok(await h.turnEnd("Done in #12."), "a new prompt resets");
});

test("replies with tool calls, errors and clean replies are left alone", async () => {
	const h = harness();
	assert.equal(await h.turnEnd("see #1", { toolResults: [{}] }), undefined);
	assert.equal(await h.turnEnd("see #1", { outcome: "aborted" }), undefined);
	assert.equal(
		await h.turnEnd("", { message: { role: "assistant", content: [{ type: "text", text: "see #1" }, { type: "toolCall" }] } }),
		undefined,
	);
	assert.equal(await h.turnEnd("All clear."), undefined);
	assert.equal(h.notes.length, 0);
});

test("every rule has an id, pattern and instruction", () => {
	const ids = new Set<string>();
	for (const r of RULES) {
		assert.ok(r.id && r.instruction && r.pattern instanceof RegExp);
		assert.ok(!ids.has(r.id));
		ids.add(r.id);
	}
});
