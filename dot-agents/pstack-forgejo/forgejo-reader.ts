// A Forgejo reader for pstack's pull request watcher.
//
// pstack's watcher (skills/poteto-mode/scripts/watch-pr in the pstack package)
// decides READY, BLOCKER and WAITING from a reader with nine methods, and ships
// one reader, for GitHub. This file is the same reader for Forgejo, through
// `tea api`. It declares the shapes it returns itself, so it has no import from
// the pstack package and its mapping can be tested without it; `watch-pr-forgejo`
// joins the two at run time.
//
// What Forgejo cannot say, and what this reader does about it:
// - `mergeable: false` means conflict, still checking, an error, or a draft
//   (Forgejo's "WIP: " title). A local `git merge-tree` of the base and head
//   tells a conflict from the rest; without those objects the answer is UNKNOWN.
// - There is no review-thread object. Review comments are grouped into a
//   conversation by file and position, and a conversation is resolved when every
//   comment in it has a resolver.
// - A commit status of `warning` is reported as failed.

export interface CommandResult {
	code: number;
	stdout: string;
	stderr: string;
}
export type Run = (argv: string[], cwd?: string) => Promise<CommandResult>;
export interface QueryFailure {
	kind: "command-exit" | "json-parse" | "missing-field" | "invalid-context-url";
	retryable: boolean;
	detail: string;
	code?: number;
	rawValue?: string;
}
export interface ReaderOptions {
	run: Run;
	// The watcher retries only errors of its own class, so the caller builds them.
	fail: (failure: QueryFailure) => Error;
	// tea's login name for the forge. Found from the remote's host when omitted.
	login?: string;
	// Where tea runs. A directory outside any repository keeps tea from reading
	// the checkout's Git config.
	teaCwd?: string;
	// The checkout, for `git remote` and `git merge-tree`.
	repoCwd?: string;
}
export interface Repository {
	owner: string;
	repo: string;
}
export interface PrContext extends Repository {
	number: number;
}
type Json = Record<string, unknown>;

const PAGE = 50;
const ROLLUP_COMMITS = 10;

export function parseRemote(value: string): (Repository & { host: string }) | null {
	let text = value.trim();
	const scp = /^[\w.-]+@([\w.-]+):(?!\d+\/)(.+)$/.exec(text);
	if (scp) text = `ssh://${scp[1]}/${scp[2]}`;
	let url: URL;
	try {
		url = new URL(text);
	} catch {
		return null;
	}
	const parts = url.pathname.replace(/\.git$/, "").split("/").filter(Boolean);
	if (parts.length !== 2) return null;
	return { host: url.hostname, owner: parts[0], repo: parts[1] };
}

export function checkFromStatus(status: Json) {
	const state = String(status.status ?? status.state ?? "").toLowerCase();
	const details = {
		name: String(status.context ?? ""),
		reportedState: state.toUpperCase(),
		description: String(status.description ?? ""),
		link: String(status.target_url ?? ""),
		workflow: "",
	};
	const kind =
		state === "success" ? "passed" : state === "skipped" ? "skipped" : state === "pending" ? "pending" : "failed";
	return { ...details, kind } as const;
}

export function rollupState(combined: Json): "SUCCESS" | "PENDING" | "FAILURE" | "ERROR" | null {
	const statuses = Array.isArray(combined.statuses) ? combined.statuses : [];
	if (statuses.length === 0) return null;
	const state = String(combined.state ?? "").toLowerCase();
	if (state === "success") return "SUCCESS";
	if (state === "pending") return "PENDING";
	if (state === "error") return "ERROR";
	return "FAILURE";
}

// The newest review of each reviewer that still counts decides.
export function reviewDecision(reviews: Json[], requiredApprovals: number) {
	const latest = new Map<string, string>();
	for (const review of reviews) {
		if (review.stale === true || review.dismissed === true) continue;
		const state = String(review.state ?? "");
		if (state !== "APPROVED" && state !== "REQUEST_CHANGES") continue;
		const user = (review.user ?? {}) as Json;
		latest.set(String(user.login ?? review.id), state);
	}
	const states = [...latest.values()];
	if (states.includes("REQUEST_CHANGES")) return "CHANGES_REQUESTED" as const;
	const approvals = states.filter((state) => state === "APPROVED").length;
	if (requiredApprovals > approvals) return "REVIEW_REQUIRED" as const;
	return approvals > 0 ? ("APPROVED" as const) : null;
}

export function threadsFromComments(comments: Json[]) {
	const groups = new Map<string, Json[]>();
	for (const comment of comments) {
		const position = comment.position || comment.original_position || 0;
		const key = `${String(comment.path ?? "")}:${String(position)}`;
		groups.set(key, [...(groups.get(key) ?? []), comment]);
	}
	return [...groups.entries()].map(([id, group]) => {
		const sorted = [...group].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
		const first = sorted[0];
		const user = (first.user ?? {}) as Json;
		return {
			id,
			firstComment: {
				authorLogin: typeof user.login === "string" ? user.login : null,
				body: String(first.body ?? ""),
				path: typeof first.path === "string" && first.path ? first.path : null,
				line: null,
				createdAt: String(first.created_at ?? ""),
			},
			resolved: group.every((comment) => comment.resolver != null),
		};
	});
}

export function createForgejoReader(options: ReaderOptions) {
	const { run, fail } = options;
	let login = options.login;
	let webBase = "";

	async function git(args: string[]): Promise<CommandResult> {
		return run(["git", ...args], options.repoCwd);
	}
	async function remote() {
		const result = await git(["remote", "get-url", "origin"]);
		return result.code === 0 ? parseRemote(result.stdout) : null;
	}
	async function resolveLogin(): Promise<string> {
		if (login) return login;
		const origin = await remote();
		const listed = await run(["tea", "logins", "list", "--output", "json"], options.teaCwd);
		if (listed.code !== 0)
			throw fail({ kind: "command-exit", retryable: false, code: listed.code, detail: "tea logins list failed" });
		const logins = JSON.parse(listed.stdout) as Json[];
		const match = logins.find((entry) => {
			try {
				return origin !== null && new URL(String(entry.url)).hostname === origin.host;
			} catch {
				return false;
			}
		});
		if (!match)
			throw fail({
				kind: "invalid-context-url",
				retryable: false,
				detail: `no tea login matches the origin host ${origin?.host ?? "(no origin)"}`,
			});
		login = String(match.name);
		webBase = String(match.url).replace(/\/$/, "");
		return login;
	}
	async function api(path: string): Promise<unknown> {
		const name = await resolveLogin();
		const result = await run(["tea", "api", "--login", name, path], options.teaCwd);
		if (result.code !== 0)
			throw fail({
				kind: "command-exit",
				retryable: true,
				code: result.code,
				detail: (result.stderr.trim().split("\n")[0] || `tea api ${path} exited ${result.code}`).slice(0, 240),
			});
		let value: unknown;
		try {
			value = JSON.parse(result.stdout);
		} catch (error) {
			throw fail({ kind: "json-parse", retryable: true, detail: `${path}: ${String(error)}` });
		}
		// tea prints a Forgejo error body with exit 0.
		if (value !== null && !Array.isArray(value) && typeof value === "object") {
			const body = value as Json;
			if (typeof body.message === "string" && typeof body.url === "string" && Object.keys(body).length <= 3)
				throw fail({ kind: "command-exit", retryable: true, code: 0, detail: `${path}: ${body.message}` });
		}
		return value;
	}
	async function pages(path: string): Promise<Json[]> {
		const items: Json[] = [];
		for (let page = 1; ; page += 1) {
			const batch = (await api(`${path}${path.includes("?") ? "&" : "?"}limit=${PAGE}&page=${page}`)) as Json[];
			if (!Array.isArray(batch)) throw fail({ kind: "missing-field", retryable: true, detail: `${path} is not a list` });
			items.push(...batch);
			if (batch.length < PAGE) return items;
		}
	}
	const repoPath = (repository: Repository) => `/repos/${repository.owner}/${repository.repo}`;
	const pull = async (context: PrContext) => (await api(`${repoPath(context)}/pulls/${context.number}`)) as Json;
	const combined = async (repository: Repository, sha: string) =>
		(await api(`${repoPath(repository)}/commits/${sha}/status`)) as Json;

	async function conflicts(base: string, head: string): Promise<boolean | null> {
		const result = await git(["merge-tree", "--write-tree", "--quiet", base, head]);
		return result.code === 0 ? false : result.code === 1 ? true : null;
	}
	async function requiredApprovals(repository: Repository, branch: string): Promise<number> {
		try {
			const rule = (await api(`${repoPath(repository)}/branch_protections/${encodeURIComponent(branch)}`)) as Json;
			return typeof rule.required_approvals === "number" ? rule.required_approvals : 0;
		} catch {
			return 0;
		}
	}

	return {
		webBase: () => webBase,
		async originRepo(): Promise<Repository | null> {
			const origin = await remote();
			return origin === null ? null : { owner: origin.owner, repo: origin.repo };
		},
		async currentPr(pr: number | null): Promise<PrContext> {
			const origin = await remote();
			if (origin === null)
				throw fail({ kind: "invalid-context-url", retryable: false, detail: "the checkout has no origin remote" });
			if (pr !== null) return { owner: origin.owner, repo: origin.repo, number: pr };
			const branch = (await git(["branch", "--show-current"])).stdout.trim();
			const open = await pages(`${repoPath(origin)}/pulls?state=open`);
			const match = open.find((item) => ((item.head ?? {}) as Json).ref === branch);
			if (!match)
				throw fail({
					kind: "invalid-context-url",
					retryable: false,
					detail: `no open pull request for branch ${branch}; pass --pr`,
				});
			return { owner: origin.owner, repo: origin.repo, number: Number(match.number) };
		},
		async pullRequest(context: PrContext) {
			const item = await pull(context);
			const head = (item.head ?? {}) as Json;
			const base = (item.base ?? {}) as Json;
			const merged = item.merged === true;
			const state = merged ? "MERGED" : item.state === "closed" ? "CLOSED" : "OPEN";
			const draft = item.draft === true;
			let mergeable: "MERGEABLE" | "CONFLICTING" | "UNKNOWN" = "MERGEABLE";
			if (state === "OPEN" && item.mergeable !== true) {
				const conflict = await conflicts(String(base.sha), String(head.sha));
				mergeable = conflict === true ? "CONFLICTING" : conflict === false && draft ? "MERGEABLE" : "UNKNOWN";
			}
			const reviews =
				state === "OPEN" ? await pages(`${repoPath(context)}/pulls/${context.number}/reviews`) : [];
			const required = state === "OPEN" ? await requiredApprovals(context, String(base.ref)) : 0;
			return {
				context,
				mergeable,
				mergeStateStatus: draft ? "DRAFT" : mergeable === "CONFLICTING" ? "DIRTY" : mergeable === "UNKNOWN" ? "UNKNOWN" : "CLEAN",
				reviewDecision: reviewDecision(reviews, required),
				headRefOid: typeof head.sha === "string" ? head.sha : null,
				baseRefOid: typeof base.sha === "string" ? base.sha : null,
				headRefName: String(head.ref ?? ""),
				baseRefName: String(base.ref ?? ""),
				state,
				mergedAt: typeof item.merged_at === "string" ? item.merged_at : null,
				isDraft: draft,
			};
		},
		async openPullRequests(repository: Repository) {
			return (await pages(`${repoPath(repository)}/pulls?state=open`)).map((item) => {
				const head = (item.head ?? {}) as Json;
				const base = (item.base ?? {}) as Json;
				const headRepo = head.repo as Json | null | undefined;
				const owner = headRepo ? ((headRepo.owner ?? {}) as Json).login : null;
				return {
					number: Number(item.number),
					headRepository:
						headRepo && typeof owner === "string" ? { owner, repo: String(headRepo.name) } : null,
					headRefName: String(head.ref ?? ""),
					baseRefName: String(base.ref ?? ""),
				};
			});
		},
		async defaultBranch(repository: Repository): Promise<string> {
			return String(((await api(repoPath(repository))) as Json).default_branch);
		},
		async checksFastPath(context: PrContext) {
			const head = ((await pull(context)).head ?? {}) as Json;
			const status = await combined(context, String(head.sha));
			const statuses = Array.isArray(status.statuses) ? (status.statuses as Json[]) : [];
			return statuses.length === 0
				? ({ kind: "none-reported" } as const)
				: ({ kind: "checks", checks: statuses.map(checkFromStatus) } as const);
		},
		// The watcher reads this only when the fast path found no check. Forgejo has
		// one source of checks, so it answers the same question again.
		async checkRollupPage(context: PrContext, _after: string | null) {
			const head = ((await pull(context)).head ?? {}) as Json;
			const status = await combined(context, String(head.sha));
			const statuses = Array.isArray(status.statuses) ? (status.statuses as Json[]) : [];
			return statuses.length === 0
				? ({ kind: "no-rollup" } as const)
				: ({ kind: "contexts", checks: statuses.map(checkFromStatus), endCursor: null } as const);
		},
		async reviewThreadPage(context: PrContext, _after: string | null) {
			const reviews = await pages(`${repoPath(context)}/pulls/${context.number}/reviews`);
			const comments: Json[] = [];
			for (const review of reviews) {
				if (review.state === "PENDING" || !review.comments_count) continue;
				comments.push(...(await pages(`${repoPath(context)}/pulls/${context.number}/reviews/${String(review.id)}/comments`)));
			}
			return { threads: threadsFromComments(comments), endCursor: null };
		},
		// Forgejo has no one call for every commit's status, so this reads the
		// newest commits only. The head is always among them.
		async commitRollups(context: PrContext) {
			const commits = await pages(`${repoPath(context)}/pulls/${context.number}/commits`);
			const head = String((((await pull(context)).head ?? {}) as Json).sha);
			const shas = [...new Set([...commits.map((commit) => String(commit.sha)).slice(-ROLLUP_COMMITS), head])];
			const rollups = [];
			for (const oid of shas) rollups.push({ oid, state: rollupState(await combined(context, oid)) });
			return rollups;
		},
	};
}
