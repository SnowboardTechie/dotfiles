import assert from "node:assert/strict";
import { execFile as execFileCallback } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { promisify } from "node:util";

import { WorktrunkGuardPlugin } from "../dot-config/opencode/plugins/worktrunk-guard.js";

const execFile = promisify(execFileCallback);

async function git(root, ...args) {
  return execFile("git", ["-C", root, ...args], { encoding: "utf8" });
}

async function createRepository() {
  const parent = await mkdtemp(path.join(os.tmpdir(), "worktrunk-guard-"));
  const repository = path.join(parent, "repo");
  await execFile("git", ["init", "--initial-branch=main", repository]);
  await git(repository, "config", "user.name", "Test User");
  await git(repository, "config", "user.email", "test@example.com");
  await git(repository, "commit", "--allow-empty", "-m", "Initial commit");
  return { parent, repository };
}

test("blocks mutating tools only in the primary checkout", async () => {
  const { parent, repository } = await createRepository();

  try {
    const primaryHooks = await WorktrunkGuardPlugin({ worktree: repository });
    await assert.rejects(
      primaryHooks["tool.execute.before"]({ tool: "bash" }),
      /blocked bash in the primary checkout/,
    );
    await primaryHooks["tool.execute.before"]({ tool: "read" });

    const linked = path.join(parent, "repo.feature");
    await git(repository, "worktree", "add", "-b", "feature", linked);
    const linkedHooks = await WorktrunkGuardPlugin({ worktree: linked });
    await linkedHooks["tool.execute.before"]({ tool: "bash" });
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});

test("creates a linked workspace through Worktrunk", async () => {
  const { parent, repository } = await createRepository();

  try {
    const hooks = await WorktrunkGuardPlugin({ worktree: repository });
    const result = await hooks.tool.worktrunk_workspace.execute(
      { branch: "feature-tool", create: true },
      { worktree: repository },
    );

    assert.match(result.output, /Worktree ready/);
    assert.equal(result.metadata.branch, "feature-tool");
    assert.ok(result.metadata.worktree_path);

    const linkedHooks = await WorktrunkGuardPlugin({
      worktree: result.metadata.worktree_path,
    });
    await linkedHooks["tool.execute.before"]({ tool: "bash" });
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});
