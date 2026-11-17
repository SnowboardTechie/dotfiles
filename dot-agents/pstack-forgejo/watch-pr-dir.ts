import { existsSync } from "node:fs";
import { join } from "node:path";

const PACKAGE =
	"git/github.com/michael-denyer/pstack-claude/plugins/pstack/skills/poteto-mode/scripts/watch-pr";

// An unset and an empty variable both count as absent, so a blank export in a
// shell profile can't hide the defaults.
export function watchPrCandidates(env: Record<string, string | undefined>, home: string): string[] {
	const candidates: string[] = [];
	if (env.PSTACK_WATCH_PR_DIR) candidates.push(env.PSTACK_WATCH_PR_DIR);
	if (env.PI_CODING_AGENT_DIR) candidates.push(join(env.PI_CODING_AGENT_DIR, PACKAGE));
	candidates.push(join(home, ".pi", "pstack", PACKAGE), join(home, ".pi", "agent", PACKAGE));
	return candidates;
}

export function findWatchPrDir(
	env: Record<string, string | undefined>,
	home: string,
	exists: (dir: string) => boolean = (dir) => existsSync(join(dir, "cli.ts")),
): { dir: string } | { tried: string[] } {
	const tried = watchPrCandidates(env, home);
	const dir = tried.find(exists);
	return dir === undefined ? { tried } : { dir };
}
