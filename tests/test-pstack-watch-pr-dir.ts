// Where pstack's pull request watcher looks for the pstack package.
// Run: node --test tests/test-pstack-watch-pr-dir.ts
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { findWatchPrDir, watchPrCandidates } from "../dot-agents/pstack-forgejo/watch-pr-dir.ts";

const PACKAGE =
	"git/github.com/michael-denyer/pstack-claude/plugins/pstack/skills/poteto-mode/scripts/watch-pr";
const WATCHER = join(import.meta.dirname, "..", "dot-agents", "pstack-forgejo", "watch-pr-forgejo");

function scratch(t: { after: (fn: () => void) => void }) {
	const root = mkdtempSync(join(tmpdir(), "watch-pr-dir-"));
	t.after(() => rmSync(root, { recursive: true, force: true }));
	return root;
}

function install(dir: string) {
	mkdirSync(dir, { recursive: true });
	writeFileSync(join(dir, "cli.ts"), "");
	return dir;
}

test("PSTACK_WATCH_PR_DIR wins over every other place", (t) => {
	const root = scratch(t);
	const explicit = install(join(root, "explicit"));
	const agentDir = join(root, "agent");
	install(join(agentDir, PACKAGE));
	install(join(root, "home", ".pi", "pstack", PACKAGE));
	install(join(root, "home", ".pi", "agent", PACKAGE));
	const env = { PSTACK_WATCH_PR_DIR: explicit, PI_CODING_AGENT_DIR: agentDir };
	assert.deepEqual(findWatchPrDir(env, join(root, "home")), { dir: explicit });
});

test("PI_CODING_AGENT_DIR wins over both default homes", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	const fromEnv = install(join(root, "agent", PACKAGE));
	install(join(home, ".pi", "pstack", PACKAGE));
	install(join(home, ".pi", "agent", PACKAGE));
	assert.deepEqual(findWatchPrDir({ PI_CODING_AGENT_DIR: join(root, "agent") }, home), { dir: fromEnv });
});

test("~/.pi/pstack wins over ~/.pi/agent", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	const pstack = install(join(home, ".pi", "pstack", PACKAGE));
	install(join(home, ".pi", "agent", PACKAGE));
	assert.deepEqual(findWatchPrDir({}, home), { dir: pstack });
});

test("~/.pi/agent is the last place", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	const agent = install(join(home, ".pi", "agent", PACKAGE));
	assert.deepEqual(findWatchPrDir({}, home), { dir: agent });
});

test("a set variable whose directory has no cli.ts falls through", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	mkdirSync(join(root, "explicit"), { recursive: true });
	mkdirSync(join(root, "agent", PACKAGE), { recursive: true });
	const pstack = install(join(home, ".pi", "pstack", PACKAGE));
	const env = { PSTACK_WATCH_PR_DIR: join(root, "explicit"), PI_CODING_AGENT_DIR: join(root, "agent") };
	assert.deepEqual(findWatchPrDir(env, home), { dir: pstack });
});

test("empty variables count as unset", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	const agent = install(join(home, ".pi", "agent", PACKAGE));
	assert.deepEqual(findWatchPrDir({ PSTACK_WATCH_PR_DIR: "", PI_CODING_AGENT_DIR: "" }, home), { dir: agent });
});

test("with nothing installed it lists every place tried, in order", (t) => {
	const root = scratch(t);
	const home = join(root, "home");
	assert.deepEqual(findWatchPrDir({}, home), {
		tried: [join(home, ".pi", "pstack", PACKAGE), join(home, ".pi", "agent", PACKAGE)],
	});
	const env = { PSTACK_WATCH_PR_DIR: join(root, "explicit"), PI_CODING_AGENT_DIR: join(root, "agent") };
	assert.deepEqual(findWatchPrDir(env, home), { tried: watchPrCandidates(env, home) });
	assert.deepEqual(watchPrCandidates(env, home), [
		join(root, "explicit"),
		join(root, "agent", PACKAGE),
		join(home, ".pi", "pstack", PACKAGE),
		join(home, ".pi", "agent", PACKAGE),
	]);
});

test("the watcher exits 64 and lists the places it tried", (t) => {
	const bun = spawnSync("bun", ["--version"]);
	if (bun.error || bun.status !== 0) return t.skip("bun is not on PATH");
	const home = scratch(t);
	const env = { ...process.env, HOME: home };
	delete env.PI_CODING_AGENT_DIR;
	delete env.PSTACK_WATCH_PR_DIR;
	const run = spawnSync("bun", [WATCHER, "--help"], { env, encoding: "utf8" });
	assert.equal(run.status, 64);
	const first = run.stderr.indexOf(join(home, ".pi", "pstack", PACKAGE));
	const second = run.stderr.indexOf(join(home, ".pi", "agent", PACKAGE));
	assert.ok(first >= 0 && second > first, run.stderr);
	assert.match(run.stderr, /PSTACK_WATCH_PR_DIR/);
});
