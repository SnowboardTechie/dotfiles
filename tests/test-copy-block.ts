// Tests for dot-pi/agent/extensions/copy-block.ts (the /copy-block command).
// Run: node --test tests/test-copy-block.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { fencedBlocks, labels, recentBlocks } from "../dot-pi/agent/extensions/copy-block.ts";

const assistant = (content: unknown[]) => ({ type: "message", message: { role: "assistant", content } });
const user = (text: string) => ({ type: "message", message: { role: "user", content: [{ type: "text", text }] } });

test("a long command comes back as one line, exactly as written", () => {
	const command = "nix develop ~/code/nix-configs#simpler-grants -c pnpm --filter @common-grants/sdk run test:unit -- --reporter=verbose";
	assert.deepEqual(fencedBlocks(`Run:\n\n\`\`\`bash\n${command}\n\`\`\`\n`), [{ code: command, lang: "bash" }]);
});

test("multi-line blocks keep their newlines, continuations and heredocs", () => {
	const code = "curl -s https://x \\\n  -H 'a: b'\ncat > f <<'EOF'\nhello\nEOF";
	assert.deepEqual(fencedBlocks(`\`\`\`sh\n${code}\n\`\`\``), [{ code, lang: "sh" }]);
});

test("language tags with dashes, tilde fences and untagged fences all count", () => {
	const text = "```shell-session\n$ ls\n```\n~~~\nplain\n~~~\n```\nnone\n```";
	assert.deepEqual(fencedBlocks(text), [
		{ code: "$ ls", lang: "shell-session" },
		{ code: "plain", lang: "" },
		{ code: "none", lang: "" },
	]);
});

test("a longer outer fence holds an inner fence as content", () => {
	const text = "````md\nExample:\n```bash\nls\n```\n````";
	assert.deepEqual(fencedBlocks(text), [{ code: "Example:\n```bash\nls\n```", lang: "md" }]);
});

test("a fence under a list item loses the list indent", () => {
	assert.deepEqual(fencedBlocks("1. Run:\n   ```bash\n   git status\n     indented\n   ```"), [
		{ code: "git status\n  indented", lang: "bash" },
	]);
});

test("empty and unclosed fences give nothing", () => {
	assert.deepEqual(fencedBlocks("```bash\n\n```\n```bash\nnever closed"), []);
});

test("bash tool calls and fenced blocks, newest reply first, ten replies at most", () => {
	const branch = [
		assistant([{ type: "text", text: "```bash\nold\n```" }]),
		...Array.from({ length: 9 }, () => assistant([{ type: "text", text: "no code" }])),
		user("next"),
		assistant([
			{ type: "text", text: "```js\nx()\n```" },
			{ type: "toolCall", name: "bash", arguments: { command: "git status" } },
			{ type: "toolCall", name: "read", arguments: { path: "a" } },
		]),
	] as never;
	assert.deepEqual(recentBlocks(branch), [
		{ code: "x()", lang: "js", reply: 1 },
		{ code: "git status", lang: "bash", reply: 1 },
	]);
});

test("picker labels are unique and show the first line", () => {
	const block = { code: "echo hi\necho there", lang: "bash", reply: 2 };
	const shown = labels([block, block]);
	assert.equal(new Set(shown).size, 2);
	assert.equal(shown[0], "1. [reply 2, bash] echo hi (+1 lines)");
	assert.ok(labels([{ code: "x".repeat(200), lang: "", reply: 1 }])[0].endsWith("…"));
});
