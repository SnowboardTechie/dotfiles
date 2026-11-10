// Records this Pi process's session file so scripts/rex-agent-sessions.py can resume it
// in the same Rex pane after a Rex server restart. Only runs inside Rex panes.
import { mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const dir = join(homedir(), ".pi/agent/runtime/rex-agent-sessions");
const file = join(dir, `${process.pid}.json`);

export default function (pi: ExtensionAPI) {
	if (!process.env.REX_SESSION) return;

	pi.on("session_start", async (_event, ctx) => {
		const sessionFile = ctx.sessionManager.getSessionFile();
		if (!sessionFile) return; // --no-session: nothing to resume
		try {
			mkdirSync(dir, { recursive: true, mode: 0o700 });
			const tmp = `${file}.tmp`;
			writeFileSync(
				tmp,
				JSON.stringify({ pid: process.pid, sessionFile, cwd: ctx.sessionManager.getCwd() }),
				{ mode: 0o600 },
			);
			renameSync(tmp, file);
		} catch {
			// Best effort: losing this only means the pane is not auto-resumed.
		}
	});

	pi.on("session_shutdown", async (event) => {
		// A quit ends the pane's session; switches (/new, /resume, fork) rewrite it on session_start.
		if (event.reason === "quit") rmSync(file, { force: true });
	});
}
