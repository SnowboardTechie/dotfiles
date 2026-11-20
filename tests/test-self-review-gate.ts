// Tests for dot-pi/agent/extensions/self-review-gate.ts (noticing a PR created without a passing
// pr-self-review check).
// Run: node --test tests/test-self-review-gate.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import init, { createsPullRequest, runsVerifier } from "../dot-pi/agent/extensions/self-review-gate.ts";

const VERIFY = `python3 ~/code/dotfiles/dot-agents/skills/pr-self-review/scripts/check_self_review.py --state-dir "$S" --worktree "$W" --base origin/main`;
const CREATE = `gh pr create --draft --base main --head bryan/x --title "Add x" --body-file "$S/pr-body.md"`;
const PASS = `{\n  "ok": true,\n  "identity": {},\n  "readiness": "Ready to publish",\n  "problems": []\n}`;
const FAIL = `{\n  "ok": false,\n  "problems": ["review-ponytail.md is missing."]\n}\n\nCommand exited with code 1`;

function fakePi() {
	const handlers = new Map<string, Function[]>();
	const pi = { on: (name: string, fn: Function) => handlers.set(name, [...(handlers.get(name) ?? []), fn]) };
	const emit = async (name: string, event: any = {}) => {
		let last;
		for (const fn of handlers.get(name) ?? []) last = await fn(event, {});
		return last;
	};
	init(pi as never);
	return emit;
}

const result = (command: string, exit = 0, output = "") => ({
	toolName: "bash",
	input: { command },
	content: [{ type: "text", text: output }],
	structuredContent: { output, exit_code: exit, truncated: false, wall_time_seconds: 1 },
	isError: exit !== 0,
});
const settle = (emit: Function) => emit("agent_before_settle", { entries: [] });

test("PR-creating commands are recognised at command position", () => {
	for (const c of [
		CREATE,
		`cd "$W" && gh pr create --draft`,
		`url=$(gh pr create --draft --fill)`,
		`url="$(tea pulls create --title x)"`,
		`tea pr create --title x`,
		`GH_HOST=example gh pr create`,
		`if true; then\n  gh pr create --fill\nfi`,
	]) assert.ok(createsPullRequest(c), c);
	for (const c of [
		`echo "next: gh pr create --draft"`,
		`# then gh pr create\ngit push`,
		`printf '%s\\n' 'gh pr create'`,
		`cat > notes.md <<'EOF'\ngh pr create --draft\nEOF`,
		`grep -n "gh pr create" SKILL.md`,
		`gh pr view 12`,
		`tea pulls list`,
	]) assert.ok(!createsPullRequest(c), c);
});

test("the verifier is recognised by its script name", () => {
	assert.ok(runsVerifier(VERIFY));
	assert.ok(!runsVerifier(`echo check_self_review.py`));
});

test("a PR created with no verifier run continues the run once", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(CREATE, 0, "https://example.invalid/pull/1"));
	const r: any = await settle(emit);
	assert.equal(r.continue, true);
	assert.equal(r.entries[0].display, false);
	assert.match(r.entries[0].content, /without a passing self-review check/);
	assert.match(r.entries[0].content, /pr-self-review/);
	assert.match(r.entries[0].content, /check_self_review\.py/);
	assert.equal(await settle(emit), undefined, "only once per run");
});

test("a verifier pass before the create keeps it quiet, also from an earlier run", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(VERIFY, 0, PASS));
	assert.equal(await settle(emit), undefined);
	await emit("before_agent_start");
	await emit("tool_result", result(CREATE));
	assert.equal(await settle(emit), undefined);
});

test("a verifier and create chained in one command count in order", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(`${VERIFY} && ${CREATE}`, 0, `${PASS}\nhttps://example.invalid/pull/1`));
	assert.equal(await settle(emit), undefined);
});

test("a verifier that ran but failed does not count", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(VERIFY, 1, FAIL));
	await emit("tool_result", result(CREATE));
	const r: any = await settle(emit);
	assert.equal(r.continue, true);
});

test("a verifier whose failure was masked to exit 0 does not count", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(`${VERIFY} || true`, 0, FAIL));
	await emit("tool_result", result(CREATE));
	assert.equal((await settle(emit) as any)?.continue, true);
});

test("a commit after the verifier passed makes it stale", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(VERIFY, 0, PASS));
	await emit("tool_result", result(`git add -A && git commit -m "Fix"`));
	await emit("tool_result", result(CREATE));
	assert.equal((await settle(emit) as any)?.continue, true);
});

test("a command that only mentions gh pr create stays quiet", async () => {
	const emit = fakePi();
	await emit("before_agent_start");
	await emit("tool_result", result(`echo "run gh pr create later" # gh pr create`));
	await emit("tool_result", { toolName: "read", input: { path: "gh pr create" }, content: [] });
	assert.equal(await settle(emit), undefined);
});

test("the gate never blocks or rewrites a tool call", async () => {
	const emit = fakePi();
	assert.equal(await emit("tool_call", { toolName: "bash", input: { command: CREATE } }), undefined);
	assert.equal(await emit("tool_result", result(CREATE)), undefined);
});
