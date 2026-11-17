// Keeps a Pi orchestrator attached to the background agents it starts (coding-agent-handoff-supervision).
//
// Pi's bash tool blocks until its command ends and has no background-with-notify mode, so a
// orchestrator that wants to answer Bryan while a background agent runs had no way to be woken
// when the background agent settled. Twice on 2026-11-16 orchestrators said as much ("nothing
// will wake me") and stopped, leaving finished background agents unread for hours.
//
// This extension gives Pi that wake-up and enforces it:
// - `watch_background_agent` starts the skill's rex_wait.sh in the background and returns at once. When the
//   wait ends (settled, no completion report, stalled or capped), its result arrives as a message that
//   starts a new turn, even if the orchestrator is idle.
// - Before a run settles, if it started or prompted a background agent (a bash call that opens a Rex pane
//   with `--session-id`, or types into one with `rex send`) and no watch is running, or a watch
//   ended without settling and was neither re-armed nor released, the run is continued once with
//   an instruction to arm one.
// Watches live in this Pi process; quitting Pi ends them.
import { spawn, type ChildProcess } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function waitScript(extensionFile: string): string {
	// <repo>/dot-pi/agent/extensions/background-agent-watch.ts -> <repo>/dot-agents/...
	const repo = resolve(dirname(realpathSync(extensionFile)), "..", "..", "..");
	return join(repo, "dot-agents", "skills", "coding-agent-handoff-supervision", "scripts", "rex_wait.sh");
}

/** A bash command that starts a background agent in a Rex pane or types a turn into one. */
export function startsOrPromptsBackgroundAgent(command: string): boolean {
	const rex = /(\brex\b|\$\{?REX\}?)/.test(command);
	if (!rex) return false;
	const opensPane = /--session-id\b/.test(command) && /\b(window new|split)\b/.test(command);
	const types = /\bsend\s+-s\b/.test(command) && !/\bsend\s+-s\s+\S+\s+-b\s+\S+\s+["']?\/(quit|exit)\b/.test(command);
	return opensPane || types;
}

export const OUTCOMES: Record<number, string> = {
	0: "settled: the turn ended and the completion report ends with its Divergence: line. Read the completion report and the changes now.",
	1: "reached its cap without settling. Read the background agent's pane and decide; arm a new watch if it is still working.",
	2: "the turn ended with no finished completion report for ten minutes: the background agent is asking something or stopped early. Read its pane.",
	3: "the turn halted without ending (unanswered for eight minutes, often a safety-filter stop). Read its pane and send one short continuation.",
};

export interface WatchRequest {
	label: string;
	transcript: string;
	completion_report: string;
	marker?: string;
	cap_seconds?: number;
}

export type Spawn = (script: string, args: string[]) => ChildProcess;

export default function (pi: ExtensionAPI, spawnWait: Spawn = (s, a) => spawn(s, a, { stdio: ["ignore", "pipe", "pipe"] })) {
	const script = waitScript(fileURLToPath(import.meta.url));
	const running = new Map<string, ChildProcess>(); // transcript -> waiter
	const unsettled = new Map<string, string>(); // transcript -> label, ended without settling
	let promptedThisRun = false;
	let nudgedThisRun = false;

	const release = (transcript: string) => {
		running.get(transcript)?.kill();
		running.delete(transcript);
		unsettled.delete(transcript);
	};

	pi.on("session_shutdown", async () => {
		for (const child of running.values()) child.kill();
		running.clear();
	});

	pi.on("before_agent_start", async () => {
		promptedThisRun = false;
		nudgedThisRun = false;
	});

	pi.on("tool_call", async (event) => {
		const command = (event as any).toolName === "bash" ? String((event as any).input?.command ?? "") : "";
		if (!command) return;
		if (startsOrPromptsBackgroundAgent(command)) promptedThisRun = true;
		// A foreground wait in the same or a later call stays attached to the background agent until it returns.
		if (/\b(rex_wait|wait[-_][\w-]*)\.sh\b/.test(command)) promptedThisRun = false;
	});

	pi.on("agent_before_settle", async (event) => {
		if (nudgedThisRun) return;
		const needs: string[] = [];
		if (promptedThisRun && running.size === 0) needs.push("This run started or prompted a background agent, and no watch_background_agent is running.");
		if (unsettled.size > 0) needs.push(`A watch ended without the background agent settling and was not re-armed or released: ${[...unsettled.values()].join(", ")}.`);
		if (needs.length === 0) return;
		nudgedThisRun = true;
		return {
			entries: [
				...event.entries,
				{
					type: "custom_message",
					customType: "background-agent-watch",
					content: `${needs.join(" ")}\nBefore you stop, call watch_background_agent for every background agent with a turn in flight (one call each: its transcript, its completion report path and, for a correction, the correction's heading as marker). It returns at once and wakes you when the background agent settles, so you can still reply to Bryan. For a background agent that is closed or settled and accepted, call watch_background_agent with release: true. Never tell Bryan nothing will wake you.`,
					display: false,
				},
			],
			continue: true,
		};
	});

	pi.registerTool({
		name: "watch_background_agent",
		label: "Watch background agent",
		description:
			"Watch a visible background agent you started (coding-agent-handoff-supervision) until its turn settles, without blocking. Returns at once; when the background agent settles, ends without a completion report, stalls or hits the cap, a message wakes this session with the result. Call it after every background agent start and every turn you type into a background agent. With release: true, stop watching a background agent that is closed or accepted.",
		promptSnippet: "Wake this session when a Rex background agent's turn settles (background rex_wait.sh)",
		promptGuidelines: [
			"After starting a background agent or typing a turn into one, call watch_background_agent for it before ending your turn; Pi's bash has no background notify, and this is the wake-up.",
		],
		parameters: {
			type: "object",
			properties: {
				label: { type: "string", description: "The background agent's name, as in its identity record." },
				transcript: { type: "string", description: "The background agent's transcript path (background_agent_transcript in its identity record)." },
				completion_report: { type: "string", description: "The completion report file its assignment names." },
				marker: { type: "string", description: "For a correction or later turn: the new section's heading, such as \"Correction 1\"." },
				cap_seconds: { type: "number", description: "Give up after this many seconds (default 14400, four hours)." },
				release: { type: "boolean", description: "Stop watching this transcript: the background agent is closed, or settled and accepted." },
			},
			required: ["label", "transcript"],
			additionalProperties: false,
		} as never,
		async execute(_id, params: WatchRequest & { release?: boolean }) {
			const text = (t: string) => ({ content: [{ type: "text" as const, text: t }], details: undefined });
			if (params.release) {
				release(params.transcript);
				return text(`Released ${params.label}.`);
			}
			if (!params.completion_report) return text("completion_report is required to watch a background agent.");
			release(params.transcript); // a re-arm replaces the old wait
			const args = [params.transcript, params.completion_report, String(params.cap_seconds ?? 14400)];
			if (params.marker) args.push(params.marker);
			const child = spawnWait(script, args);
			running.set(params.transcript, child);
			let out = "";
			child.stdout?.on("data", (d) => (out += d));
			child.stderr?.on("data", (d) => (out += d));
			child.on("close", (code, signal) => {
				if (running.get(params.transcript) !== child) return; // released or re-armed
				running.delete(params.transcript);
				if (signal) return;
				const exit = code ?? 1;
				if (exit === 0) unsettled.delete(params.transcript);
				else unsettled.set(params.transcript, params.label);
				const outcome = OUTCOMES[exit] ?? `exited ${exit}.`;
				pi.sendMessage(
					{
						customType: "background-agent-watch",
						content: `Background agent ${params.label}: ${outcome}\nCompletion report: ${params.completion_report}\nTranscript: ${params.transcript}\n${out.trim()}`,
						display: true,
						details: { label: params.label, exit },
					},
					{ triggerTurn: true, deliverAs: "followUp" },
				);
			});
			return text(`Watching ${params.label}. This session will be woken when it settles; you may end your turn.`);
		},
	});
}
