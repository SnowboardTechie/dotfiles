// Tests for dot-pi/agent/extensions/pi-split.ts (the /split and /split-fork commands).
// The Rex side is the next-session launcher, tested in tests/test-next-session-launch.py.
// Run: node --test tests/test-pi-split.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { launchArgs, launcherPath, paneName, seatFlag } from "../dot-pi/agent/extensions/pi-split.ts";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const extension = join(repo, "dot-pi", "agent", "extensions", "pi-split.ts");

test("the launcher is found through the ~/.pi symlink", () => {
	const home = mkdtempSync(join(tmpdir(), "pi-split-test-"));
	mkdirSync(join(home, "extensions"));
	const link = join(home, "extensions", "pi-split.ts");
	symlinkSync(extension, link);
	const found = launcherPath(link);
	assert.equal(found, join(repo, "dot-agents", "skills", "next-session", "scripts", "launch_next_session.py"));
	assert.ok(existsSync(found));
});

test("the seat follows this session's Claude config dir", () => {
	const home = "/Users/me";
	assert.deepEqual(seatFlag({ PI_CLAUDE_CODE_CONFIG_DIR: "/Users/me/.claude-personal/" }, home), ["--seat", "personal"]);
	assert.deepEqual(seatFlag({}, home), ["--seat", "work"]);
	assert.deepEqual(seatFlag({ CLAUDE_CONFIG_DIR: "/Users/me/.claude" }, home), ["--seat", "work"]);
	assert.deepEqual(seatFlag({ PI_CLAUDE_CODE_CONFIG_DIR: "/elsewhere" }, home), []);
});

test("a split carries the model, thinking level, seat and prompt", () => {
	const args = launchArgs({
		launcher: "/r/launch.py", name: "split-ab12", cwd: "/w",
		model: { provider: "claude-code", id: "claude-opus-5-5" }, thinking: "medium",
		promptFile: "/t/prompt.md", env: { PI_CLAUDE_CODE_CONFIG_DIR: "/h/.claude-personal" }, home: "/h",
	});
	assert.deepEqual(args, ["/r/launch.py", "launch", "--agent", "pi", "--name", "split-ab12", "--cwd", "/w",
		"--prompt-file", "/t/prompt.md", "--model", "claude-code/claude-opus-5-5", "--thinking", "medium",
		"--seat", "personal"]);
});

test("a fork without a prompt passes the session file and no prompt", () => {
	const args = launchArgs({ launcher: "/r/l.py", name: "fork-0001", cwd: "/w", forkFile: "/s/a.jsonl", env: {}, home: "/h" });
	assert.deepEqual(args, ["/r/l.py", "launch", "--agent", "pi", "--name", "fork-0001", "--cwd", "/w",
		"--fork", "/s/a.jsonl", "--seat", "work"]);
});

test("pane names satisfy the launcher's name rule", () => {
	for (const fork of [true, false]) assert.match(paneName(fork), /^[a-z][a-z0-9_-]{0,31}$/);
});

test("the extension registers /split and /split-fork", async () => {
	const { default: init } = await import("../dot-pi/agent/extensions/pi-split.ts");
	const names: string[] = [];
	init({ registerCommand: (name: string) => names.push(name) } as never);
	assert.deepEqual(names, ["split", "split-fork"]);
});
