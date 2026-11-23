// The Forgejo reader for pstack's pull request watcher: what it asks Forgejo and
// how it maps the answers. `tea` and `git` are replaced by a table of canned
// replies, so nothing here reaches a forge.
// Run: node --test tests/test-pstack-forgejo-reader.ts
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
	checkFromStatus,
	createForgejoReader,
	parseRemote,
	reviewDecision,
	rollupState,
	threadsFromComments,
} from "../dot-agents/pstack-forgejo/forgejo-reader.ts";

const HEAD = "a".repeat(40);
const BASE = "b".repeat(40);
const context = { owner: "bryan", repo: "widgets", number: 7 };

function pull(overrides: Record<string, unknown> = {}) {
	return {
		number: 7,
		state: "open",
		draft: false,
		mergeable: true,
		merged: false,
		merged_at: null,
		head: { ref: "feature", sha: HEAD, repo: { name: "widgets", owner: { login: "bryan" } } },
		base: { ref: "main", sha: BASE },
		...overrides,
	};
}

// Replies are keyed by the API path without its paging query, or by "git <subcommand>".
function reader(replies: Record<string, unknown>, mergeTreeExit = 0) {
	const calls: string[] = [];
	const run = async (argv: string[]) => {
		calls.push(argv.join(" "));
		if (argv[0] === "git") {
			if (argv[1] === "remote") return { code: 0, stdout: "ssh://forgejo@git.example.test:5518/bryan/widgets.git\n", stderr: "" };
			if (argv[1] === "branch") return { code: 0, stdout: "feature\n", stderr: "" };
			if (argv[1] === "merge-tree") return { code: mergeTreeExit, stdout: "", stderr: "" };
		}
		if (argv[1] === "logins")
			return { code: 0, stdout: JSON.stringify([{ name: "example", url: "https://git.example.test" }]), stderr: "" };
		const path = argv[argv.length - 1].replace(/[?&]limit=\d+&page=\d+$/, "");
		const page = Number(/page=(\d+)$/.exec(argv[argv.length - 1])?.[1] ?? 1);
		if (!(path in replies)) return { code: 1, stdout: "", stderr: `no reply for ${path}` };
		const reply = replies[path];
		return { code: 0, stdout: JSON.stringify(Array.isArray(reply) && page > 1 ? [] : reply), stderr: "" };
	};
	const fail = (failure: { detail: string }) => Object.assign(new Error(failure.detail), { failure });
	return { reader: createForgejoReader({ run, fail }), calls };
}
const R = "/repos/bryan/widgets";

test("a remote is read in ssh, scp and https form, with or without a port", () => {
	const expected = { host: "git.example.test", owner: "bryan", repo: "widgets" };
	assert.deepEqual(parseRemote("ssh://forgejo@git.example.test:5518/bryan/widgets.git"), expected);
	assert.deepEqual(parseRemote("forgejo@git.example.test:bryan/widgets.git"), expected);
	assert.deepEqual(parseRemote("https://git.example.test/bryan/widgets"), expected);
	assert.equal(parseRemote("https://git.example.test/bryan"), null);
});

test("a commit status maps to a check, and a warning counts as failed", () => {
	assert.equal(checkFromStatus({ context: "ci", status: "success" }).kind, "passed");
	assert.equal(checkFromStatus({ context: "ci", status: "pending" }).kind, "pending");
	assert.equal(checkFromStatus({ context: "ci", status: "skipped" }).kind, "skipped");
	assert.equal(checkFromStatus({ context: "ci", status: "failure" }).kind, "failed");
	assert.equal(checkFromStatus({ context: "ci", status: "warning" }).kind, "failed");
});

test("a commit with no status has no rollup state", () => {
	assert.equal(rollupState({ state: "", statuses: [] }), null);
	assert.equal(rollupState({ state: "success", statuses: [{}] }), "SUCCESS");
	assert.equal(rollupState({ state: "failure", statuses: [{}] }), "FAILURE");
});

test("the newest review of each reviewer decides, and stale reviews don't count", () => {
	const approve = { state: "APPROVED", user: { login: "ann" } };
	const reject = { state: "REQUEST_CHANGES", user: { login: "ann" } };
	assert.equal(reviewDecision([], 0), null);
	assert.equal(reviewDecision([], 1), "REVIEW_REQUIRED");
	assert.equal(reviewDecision([approve], 1), "APPROVED");
	assert.equal(reviewDecision([approve, reject], 0), "CHANGES_REQUESTED");
	assert.equal(reviewDecision([reject, approve], 0), "APPROVED");
	assert.equal(reviewDecision([{ ...reject, stale: true }], 0), null);
});

test("review comments on one line form one conversation, resolved by its first comment's resolver", () => {
	// Forgejo 16's Resolve button marks the conversation's first comment only;
	// replies keep a null resolver.
	const threads = threadsFromComments([
		{ path: "a.ts", position: 4, body: "reply", created_at: "2026-01-02", user: { login: "bo" }, resolver: null },
		{ path: "a.ts", position: 4, body: "first", created_at: "2026-01-01", user: { login: "ann" }, resolver: { login: "bo" } },
		{ path: "b.ts", position: 9, body: "open", created_at: "2026-01-03", user: { login: "ann" }, resolver: null },
		{ path: "b.ts", position: 9, body: "stray", created_at: "2026-01-04", user: { login: "bo" }, resolver: { login: "bo" } },
	]);
	assert.equal(threads.length, 2);
	assert.deepEqual([threads[0].resolved, threads[0].firstComment.body], [true, "first"]);
	assert.deepEqual([threads[1].resolved, threads[1].firstComment.body], [false, "open"]);
});

test("an open pull request Forgejo calls mergeable reads as clean", async () => {
	const { reader: forgejo } = reader({ [`${R}/pulls/7`]: pull(), [`${R}/pulls/7/reviews`]: [] });
	const facts = await forgejo.pullRequest(context);
	assert.deepEqual(
		[facts.state, facts.mergeable, facts.mergeStateStatus, facts.isDraft, facts.headRefOid, facts.baseRefOid, facts.baseRefName],
		["OPEN", "MERGEABLE", "CLEAN", false, HEAD, BASE, "main"],
	);
});

test("a draft that merges cleanly is a draft, not a conflict", async () => {
	const { reader: forgejo } = reader({ [`${R}/pulls/7`]: pull({ draft: true, mergeable: false }), [`${R}/pulls/7/reviews`]: [] }, 0);
	const facts = await forgejo.pullRequest(context);
	assert.deepEqual([facts.mergeable, facts.mergeStateStatus, facts.isDraft], ["MERGEABLE", "DRAFT", true]);
});

test("an unmergeable pull request is a conflict only when git finds one", async () => {
	const replies = { [`${R}/pulls/7`]: pull({ mergeable: false }), [`${R}/pulls/7/reviews`]: [] };
	const conflict = await reader(replies, 1).reader.pullRequest(context);
	assert.deepEqual([conflict.mergeable, conflict.mergeStateStatus], ["CONFLICTING", "DIRTY"]);
	// No conflict and not a draft: Forgejo is still checking, or the commits aren't local.
	for (const exit of [0, 128]) {
		const unknown = await reader(replies, exit).reader.pullRequest(context);
		assert.deepEqual([unknown.mergeable, unknown.mergeStateStatus], ["UNKNOWN", "UNKNOWN"]);
	}
});

test("a merged pull request reads as merged without asking for reviews", async () => {
	const { reader: forgejo, calls } = reader({ [`${R}/pulls/7`]: pull({ state: "closed", merged: true, merged_at: "2026-01-01T00:00:00Z" }) });
	const facts = await forgejo.pullRequest(context);
	assert.deepEqual([facts.state, facts.mergedAt], ["MERGED", "2026-01-01T00:00:00Z"]);
	assert.equal(calls.some((call) => call.includes("/reviews")), false);
});

test("a branch rule's required approvals make an unreviewed pull request wait for review", async () => {
	const { reader: forgejo } = reader({
		[`${R}/pulls/7`]: pull(),
		[`${R}/pulls/7/reviews`]: [],
		[`${R}/branch_protections/main`]: { required_approvals: 1 },
	});
	assert.equal((await forgejo.pullRequest(context)).reviewDecision, "REVIEW_REQUIRED");
});

test("checks come from the head commit's statuses, and none is said plainly", async () => {
	const some = reader({
		[`${R}/pulls/7`]: pull(),
		[`${R}/commits/${HEAD}/status`]: { state: "pending", statuses: [{ context: "ci", status: "pending", target_url: "/runs/1" }] },
	}).reader;
	const fast = await some.checksFastPath(context);
	assert.equal(fast.kind, "checks");
	assert.deepEqual(fast.kind === "checks" && fast.checks.map((check) => [check.name, check.kind]), [["ci", "pending"]]);
	const none = reader({ [`${R}/pulls/7`]: pull(), [`${R}/commits/${HEAD}/status`]: { state: "", statuses: [] } }).reader;
	assert.equal((await none.checksFastPath(context)).kind, "none-reported");
	assert.equal((await none.checkRollupPage(context, null)).kind, "no-rollup");
});

test("commit rollups always include the head", async () => {
	const { reader: forgejo } = reader({
		[`${R}/pulls/7`]: pull(),
		[`${R}/pulls/7/commits`]: [{ sha: "c".repeat(40) }],
		[`${R}/commits/${"c".repeat(40)}/status`]: { state: "success", statuses: [{}] },
		[`${R}/commits/${HEAD}/status`]: { state: "", statuses: [] },
	});
	assert.deepEqual(await forgejo.commitRollups(context), [
		{ oid: "c".repeat(40), state: "SUCCESS" },
		{ oid: HEAD, state: null },
	]);
});

test("the current branch's pull request is found among the open ones", async () => {
	const { reader: forgejo } = reader({ [`${R}/pulls?state=open`]: [pull()] });
	assert.deepEqual(await forgejo.currentPr(null), context);
	assert.deepEqual(await forgejo.openPullRequests(context), [
		{ number: 7, headRepository: { owner: "bryan", repo: "widgets" }, headRefName: "feature", baseRefName: "main" },
	]);
});

test("a Forgejo error body printed with exit 0 is a failed query", async () => {
	const { reader: forgejo } = reader({ [`${R}/pulls/7`]: { message: "not found", url: "https://git.example.test/api/swagger" } });
	await assert.rejects(forgejo.pullRequest(context), /not found/);
});

test("tea is told which login to use, found from the origin's host", async () => {
	const { reader: forgejo, calls } = reader({ [R]: { default_branch: "main" } });
	assert.equal(await forgejo.defaultBranch(context), "main");
	assert.ok(calls.includes(`tea api --login example ${R}`));
	assert.equal(forgejo.webBase(), "https://git.example.test");
});

test("Forgejo has no check suites, so none is unsettled", async () => {
	const { reader: forgejo, calls } = reader({});
	assert.deepEqual(await forgejo.unsettledSuites(context, HEAD, "reported", ["azure-pipelines"]), {
		checks: [],
		queuedWithoutRuns: [],
	});
	assert.deepEqual(calls, []);
});

// pstack's watcher calls every method of its GitHubReader interface. When pstack
// adds one (0.9.153 added unsettledSuites), the watcher crashes on Forgejo until
// this reader has it too. Checked against PSTACK_WATCH_PR_DIR when set (point it
// at a checkout of a new pin before advancing it), else the installed pstack,
// where reconcile-pi-pstack.sh puts the pinned commit.
test("the reader has every method the installed pstack watcher calls", (t) => {
	const watchPr =
		process.env.PSTACK_WATCH_PR_DIR ||
		join(homedir(), ".pi/pstack/git/github.com/michael-denyer/pstack-claude/plugins/pstack/skills/poteto-mode/scripts/watch-pr");
	const types = join(watchPr, "types.ts");
	if (!existsSync(types)) return t.skip(`pstack's watcher is not at ${watchPr}`);
	const body = /export interface GitHubReader \{([\s\S]*?)\n\}/.exec(readFileSync(types, "utf8"))?.[1];
	assert.ok(body, "GitHubReader interface not found");
	const methods = [...body.matchAll(/^\s{2}(\w+)\(/gm)].map((match) => match[1]);
	assert.ok(methods.length >= 9, methods.join(","));
	const { reader: forgejo } = reader({});
	for (const method of methods) assert.equal(typeof (forgejo as Record<string, unknown>)[method], "function", method);
});
