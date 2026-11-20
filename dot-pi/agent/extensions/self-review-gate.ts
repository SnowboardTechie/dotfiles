// Notices a pull request created without a passing pr-self-review check, and sends the run back once.
//
// On 2026-11-20 an orchestrator opened a draft PR for issue work and reported it to Bryan without
// running pr-self-review: it read the diff, reran tests and called that acceptance. Every skill on
// the path already required the review, so this extension makes the skip visible to the run itself.
//
// A bash call that runs pr-self-review's scripts/check_self_review.py with exit code 0 and `"ok": true`
// in its output records a pass for this session. A later commit makes the pass stale. A bash call that
// creates a PR (`gh pr create`, `tea pr create`, `tea pulls create` at command position) with no current
// pass marks the run; before the run settles it is continued once with a hidden instruction to review
// the exact head now. It never blocks or rewrites a tool call.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// The script as the program, or as the script argument of python/uv.
const VERIFIER = /^(?:\w+=\S*\s+)*(?:(?:\S*\/)?(?:python3?|uv\s+run(?:\s+python3?)?)\s+(?:-\S+\s+)*)?\S*check_self_review\.py\b/;
const CREATE = /^(?:\w+=\S*\s+)*(?:gh\s+pr\s+create|tea\s+(?:pr|pulls?)\s+create)\b/;
const COMMIT = /^(?:\w+=\S*\s+)*git\s+(?:-\S+\s+(?:\S+\s+)?)*commit\b/;

/** The command's segments at command position, with heredoc bodies, comments and plain quoted text removed. */
export function commandSegments(command: string): string[] {
	const stripped = command
		.replace(/<<-?\s*(['"]?)(\w+)\1[^\n]*\n[\s\S]*?\n\s*\2\s*(?=\n|$)/g, "") // heredoc bodies
		.replace(/'[^']*'/g, "''") // single-quoted text never runs
		.replace(/"(?:[^"\\$`]|\\.)*"/g, '""') // double-quoted text without a substitution never runs
		.replace(/(^|\s)#[^\n]*/g, "$1"); // comments
	return stripped
		.split(/\$\(|`|&&|\|\||[;|&\n(){}]|\b(?:then|do|else)\b/)
		.map((s) => s.replace(/^[\s"!]+/, "").trim())
		.filter(Boolean);
}

export function createsPullRequest(command: string): boolean {
	return commandSegments(command).some((s) => CREATE.test(s));
}

export function runsVerifier(command: string): boolean {
	return commandSegments(command).some((s) => VERIFIER.test(s));
}

function commits(command: string): boolean {
	return commandSegments(command).some((s) => COMMIT.test(s));
}

function output(event: any): string {
	const structured = event.structuredContent?.output;
	if (typeof structured === "string") return structured;
	return (event.content ?? []).map((c: any) => (c?.type === "text" ? c.text : "")).join("\n");
}

function exitCode(event: any): number | undefined {
	const code = event.structuredContent?.exit_code;
	if (typeof code === "number") return code;
	return event.isError ? 1 : undefined;
}

export default function (pi: ExtensionAPI) {
	let passed = false; // a current verifier pass in this session
	let createdUnchecked = false;
	let nudgedThisRun = false;

	pi.on("before_agent_start", async () => {
		createdUnchecked = false;
		nudgedThisRun = false;
	});

	// tool_result carries the exit code; returning nothing leaves the result untouched.
	pi.on("tool_result", async (event) => {
		const e = event as any;
		if (e.toolName !== "bash") return;
		const command = String(e.input?.command ?? "");
		if (!command) return;
		const verifierPassed = runsVerifier(command) && exitCode(e) === 0 && /"ok":\s*true/.test(output(e));
		if (commits(command)) passed = false;
		if (verifierPassed) passed = true;
		if (createsPullRequest(command) && !passed) createdUnchecked = true;
	});

	pi.on("agent_before_settle", async (event) => {
		if (nudgedThisRun || !createdUnchecked) return;
		nudgedThisRun = true;
		return {
			entries: [
				...event.entries,
				{
					type: "custom_message",
					customType: "self-review-gate",
					content:
						"This run created a pull request without a passing self-review check: no bash call ran pr-self-review's scripts/check_self_review.py with exit 0 on the current head before the PR was created. Load the pr-self-review skill and read it in full, run it on the exact head of that PR now (a diff read, a passing build or a reviewer given a hand-written brief is not that review), then run check_self_review.py with the state directory, worktree and base. Do not tell Bryan the PR is ready to look at until the verifier exits 0, and when you report, quote its readiness line.",
					display: false,
				},
			],
			continue: true,
		};
	});
}
