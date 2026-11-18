// Rules that cost nothing until a reply breaks them, after oh-my-pi's "time-traveling
// stream rules". Each rule is a pattern for something Bryan keeps correcting in Pi's
// replies. When a finished reply to him matches one, the reply is dropped from the
// model's context, the rule is added in its place, and Pi asks for the reply again.
//
// Unlike oh-my-pi this checks the finished reply instead of aborting mid-stream: an
// aborted run in Pi is a hard stop with no continuation, and the turn_end boundary can
// replace a reply and continue in one step. The bad reply has already been shown, so
// Bryan sees it followed by the corrected one, with a note naming the rule.
//
// Only replies with no tool calls are checked: those are the answers Bryan reads, and
// dropping a reply that called tools would orphan its tool results. Code blocks, inline
// code and Markdown link text are ignored, so quoting a pattern never trips it. Every
// rule the reply breaks goes into one retry, since fixing one at a time let a later
// retry undo an earlier fix. Each rule fires at most once per prompt, so a reply that
// still matches after the retry is kept rather than looped on.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export interface Rule {
	id: string;
	pattern: RegExp;
	/** What the model is told when the rule fires. */
	instruction: string;
}

export const RULES: Rule[] = [
	{
		id: "bare-issue-reference",
		// #123 on its own; "[#123](url)" is removed before matching.
		pattern: /(^|[\s(,;:])#\d+\b/m,
		instruction:
			"Never leave a bare issue or PR number like #123. Link each one ([#123](url) or a full URL) and say in a few words what it is. If you don't know the URL, find it, or name the thing in plain words instead of the number.",
	},
	{
		id: "coined-label",
		// "lane A", "track B", "probe 3": labels of the agent's own making.
		pattern: /\b([Ll]ane|[Tt]rack|[Pp]robe|[Ww]orker)\s+([A-Z]|\d+)\b/,
		instruction:
			"Don't use labels of your own making such as \"track B\" or \"probe 3\". Call each work item, session or agent what it is in the project's own words.",
	},
	{
		id: "local-web-link",
		pattern: /\b(https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)\b|file:\/\/)/i,
		instruction:
			"Web views go to Bryan as a tailnet-only `tailscale serve` HTTPS URL on this Mac's ts.net name, never a localhost or file:// link. Serve it that way and check it loads before sharing.",
	},
	{
		id: "done-with-loose-ends",
		pattern: /^\s*(\*\*)?yes\b[\s\S]*\b(loose ends?|one (more )?(cleanup|thing)|still (open|pending))\b/i,
		instruction:
			"Never answer \"yes\" to whether work is done while part of the task is still open. If you can finish it, finish it now and then answer. Otherwise start with \"No\" and name only what needs Bryan, one line each.",
	},
];

/** The prose of a reply: code and link text removed, so only what Bryan reads as words is checked. */
export function prose(text: string): string {
	return text
		.replace(/```[\s\S]*?(```|$)/g, " ")
		.replace(/`[^`\n]*`/g, " ")
		.replace(/\[[^\]\n]*\]\([^)\n]*\)/g, " ");
}

/** Every rule the text breaks that hasn't fired yet for this prompt. */
export function broken(text: string, fired: Set<string>, rules: Rule[] = RULES): Rule[] {
	const p = prose(text);
	return rules.filter((r) => !fired.has(r.id) && r.pattern.test(p));
}

function replyText(message: any): string {
	if (!message || message.role !== "assistant") return "";
	const c = message.content;
	if (typeof c === "string") return c;
	if (!Array.isArray(c)) return "";
	return c.filter((x: any) => x?.type === "text").map((x: any) => x.text ?? "").join("\n");
}

function hasToolCalls(message: any): boolean {
	return Array.isArray(message?.content) && message.content.some((x: any) => x?.type === "toolCall");
}

export default function (pi: ExtensionAPI, rules: Rule[] = RULES) {
	let fired = new Set<string>();

	pi.on("before_agent_start", async (event) => {
		if (event.messageType === "user") fired = new Set();
	});

	pi.on("turn_end", async (event, ctx) => {
		if (event.outcome !== "completed" || event.toolResults.length > 0 || hasToolCalls(event.message)) return;
		const hit = broken(replyText(event.message), fired, rules);
		if (hit.length === 0) return;
		for (const r of hit) fired.add(r.id);
		const ids = hit.map((r) => r.id);
		if (ctx.hasUI) ctx.ui.notify(`Stream rules ${ids.join(", ")}: asking for the reply again`, "warning");
		const said = hit.length === 1 ? "a standing rule" : "standing rules";
		return {
			entries: [
				...event.entries,
				{ type: "context_edit", targetId: event.messageEntryId, replacement: null },
				{
					type: "custom_message",
					customType: "stream-rule",
					content: `Your last reply broke ${said} and was withdrawn.\n${hit.map((r) => `- ${r.instruction}`).join("\n")}\nWrite the whole reply again, following every rule above. Don't mention the rules or the withdrawn reply.`,
					display: false,
					details: { rules: ids },
				},
			],
			continue: true,
		};
	});
}
