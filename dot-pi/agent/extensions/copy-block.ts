// /copy-block: put a command or code block from Pi's recent replies on the clipboard,
// exactly as written. Mouse selection copies the rendered screen, where Pi has already
// wrapped long lines, so a wrapped command pastes as several lines. This reads the
// session instead. Same idea as the npm package @joelazar/pi-copy-block, rewritten here
// so nothing from npm runs in Pi; it uses only Pi's own exports. copyToClipboard is
// imported when the command runs, so the tests can load this file without Pi installed.
import type { ExtensionAPI, SessionEntry } from "@earendil-works/pi-coding-agent";

const RECENT_REPLIES = 10;
const LABEL_WIDTH = 80;

export type Block = { code: string; lang: string; reply: number };

/** Fenced blocks in Markdown: ``` or ~~~ fences of 3+ characters, closed by the same character at least as long. */
export function fencedBlocks(text: string): { code: string; lang: string }[] {
	const blocks: { code: string; lang: string }[] = [];
	let open: { char: string; length: number; lang: string; indent: number; lines: string[] } | undefined;
	for (const line of text.split("\n")) {
		if (!open) {
			const start = /^( {0,3})(`{3,}|~{3,})\s*([^\s`]*)/.exec(line);
			if (start) open = { char: start[2][0], length: start[2].length, lang: start[3], indent: start[1].length, lines: [] };
			continue;
		}
		const close = /^ {0,3}(`{3,}|~{3,})\s*$/.exec(line);
		if (close && close[1][0] === open.char && close[1].length >= open.length) {
			const code = open.lines.join("\n").replace(/^\n+|\s+$/g, "");
			if (code) blocks.push({ code, lang: open.lang });
			open = undefined;
			continue;
		}
		// A fence indented under a list item indents its body too; drop up to that much.
		open.lines.push(line.replace(new RegExp(`^ {0,${open.indent}}`), ""));
	}
	return blocks;
}

/** Blocks from the last RECENT_REPLIES assistant replies, newest reply first; within a reply, in order. */
export function recentBlocks(branch: SessionEntry[]): Block[] {
	const blocks: Block[] = [];
	let reply = 0;
	for (let i = branch.length - 1; i >= 0 && reply < RECENT_REPLIES; i--) {
		const entry = branch[i];
		if (entry?.type !== "message" || entry.message.role !== "assistant") continue;
		reply++;
		for (const part of entry.message.content) {
			if (part.type === "text") {
				for (const block of fencedBlocks(part.text)) blocks.push({ ...block, reply });
			} else if (part.type === "toolCall" && part.name === "bash" && typeof part.arguments?.command === "string") {
				blocks.push({ code: part.arguments.command, lang: "bash", reply });
			}
		}
	}
	return blocks;
}

/** One picker line per block, unique so the choice maps back to its block. */
export function labels(blocks: Block[]): string[] {
	return blocks.map((block, i) => {
		const lines = block.code.split("\n");
		const first = lines[0].length > LABEL_WIDTH ? `${lines[0].slice(0, LABEL_WIDTH - 1)}…` : lines[0];
		const more = lines.length > 1 ? ` (+${lines.length - 1} lines)` : "";
		return `${i + 1}. [reply ${block.reply}${block.lang ? `, ${block.lang}` : ""}] ${first}${more}`;
	});
}

export default function (pi: ExtensionAPI) {
	pi.registerCommand("copy-block", {
		description: `Copy a command or code block from the last ${RECENT_REPLIES} replies, as written`,
		handler: async (_args, ctx) => {
			const blocks = recentBlocks(ctx.sessionManager.getBranch());
			if (blocks.length === 0) {
				ctx.ui.notify(`No commands or code blocks in the last ${RECENT_REPLIES} replies`, "warning");
				return;
			}
			let block = blocks[0];
			if (blocks.length > 1) {
				const options = labels(blocks);
				const choice = await ctx.ui.select("Copy which block? (reply 1 is the latest)", options);
				if (choice === undefined) return;
				block = blocks[options.indexOf(choice)];
			}
			try {
				const { copyToClipboard } = await import("@earendil-works/pi-coding-agent");
				await copyToClipboard(block.code);
				ctx.ui.notify(`Copied ${block.code.split("\n").length} line(s) from reply ${block.reply}`, "info");
			} catch (err) {
				ctx.ui.notify(`Copy failed: ${err instanceof Error ? err.message : String(err)}`, "error");
			}
		},
	});
}
