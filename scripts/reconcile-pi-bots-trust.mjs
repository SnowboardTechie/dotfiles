#!/usr/bin/env node
// Trust the bots' parent directory in Pi, so a Pi started in a bot's directory reads its
// `.pi/settings.json` (model, thinking level, extensions). Pi ignores a project's settings
// until the project is trusted; the bot service's own Pis pass --approve, but a desk Pi
// opened there (to look at or work on a bot) would otherwise ask, or silently skip them.
//
// Usage: reconcile-pi-bots-trust.mjs --check | --apply
//
// The bots' parent is $PI_BOTS_DIR, default ~/code/pi-bots/bots. The decision goes into
// Pi's own trust store through Pi's own ProjectTrustStore (same file, lock and path
// rules), found from the `pi` on PATH or $PI_PACKAGE_DIR. Skipped when the directory or
// Pi is missing. A saved "do not trust" for that directory is Bryan's and is left alone.
// Exit 0 when in place (or skipped), 1 on drift in --check, 2 on a usage error.

import { existsSync, readFileSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { delimiter, dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const PACKAGE_NAME = "@earendil-works/pi-coding-agent";

function usage() {
	console.error("Usage: reconcile-pi-bots-trust.mjs --check|--apply");
	process.exit(2);
}

const mode = process.argv[2];
if (process.argv.length !== 3 || (mode !== "--check" && mode !== "--apply")) usage();

function findPiPackage() {
	if (process.env.PI_PACKAGE_DIR) return process.env.PI_PACKAGE_DIR;
	for (const dir of (process.env.PATH ?? "").split(delimiter)) {
		if (!dir) continue;
		const candidate = join(dir, "pi");
		if (!existsSync(candidate)) continue;
		let current = dirname(realpathSync(candidate));
		while (true) {
			const manifest = join(current, "package.json");
			if (existsSync(manifest)) {
				try {
					if (JSON.parse(readFileSync(manifest, "utf8")).name === PACKAGE_NAME) return current;
				} catch {
					// not the package; keep walking up
				}
			}
			const parent = dirname(current);
			if (parent === current) break;
			current = parent;
		}
	}
	return undefined;
}

const botsDir = process.env.PI_BOTS_DIR || join(homedir(), "code", "pi-bots", "bots");
if (!existsSync(botsDir)) {
	console.log(`  Skipped (no bot directories at ${botsDir})`);
	process.exit(0);
}
const packageDir = findPiPackage();
if (packageDir === undefined) {
	console.log("  Skipped (Pi is not installed)");
	process.exit(0);
}

const pi = await import(pathToFileURL(join(packageDir, "dist", "index.js")).href);
if (typeof pi.ProjectTrustStore !== "function" || typeof pi.getAgentDir !== "function") {
	console.log(`  WARNING: Pi at ${packageDir} has no ProjectTrustStore; trust ${botsDir} with /trust instead`);
	process.exit(mode === "--check" ? 1 : 0);
}

const target = realpathSync(botsDir);
const store = new pi.ProjectTrustStore(pi.getAgentDir());
const entry = store.getEntry(target);
// Pi saves canonical paths, so the nearest decision is this directory's own when the keys match.
const exact = entry !== null && entry.path === target;

if (entry?.decision === true) {
	console.log(`  OK   Pi trusts ${target}${exact ? "" : ` (through ${entry.path})`}`);
	process.exit(0);
}
if (entry?.decision === false && exact) {
	console.log(`  WARNING: Pi has a saved "do not trust" for ${target}; leaving it`);
	process.exit(0);
}
if (mode === "--check") {
	const why = entry === null ? "no decision" : `inherits "do not trust" from ${entry.path}`;
	console.log(`  MISSING Pi trust for ${target} (${why})`);
	process.exit(1);
}
store.set(target, true);
console.log(`  Trusted ${target} in Pi${entry === null ? "" : ` (overriding "do not trust" saved for ${entry.path})`}`);
