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

test("adopts a linked workspace and reroutes the current session", async () => {
  const { parent, repository } = await createRepository();

  try {
    const hooks = await WorktrunkGuardPlugin({ worktree: repository });
    const result = await hooks.tool.worktrunk_workspace.execute(
      { branch: "feature-tool", create: true },
      { sessionID: "session-a", worktree: repository },
    );

    assert.match(result.output, /Workspace adopted/);
    assert.equal(result.metadata.branch, "feature-tool");
    assert.ok(result.metadata.worktree_path);

    const bash = { workdir: repository };
    await hooks["tool.execute.before"](
      { tool: "bash", sessionID: "session-a" },
      { args: bash },
    );
    assert.equal(bash.workdir, result.metadata.worktree_path);

    const read = { filePath: path.join(repository, "README.md") };
    await hooks["tool.execute.before"](
      { tool: "read", sessionID: "session-a" },
      { args: read },
    );
    assert.equal(
      read.filePath,
      path.join(result.metadata.worktree_path, "README.md"),
    );

    const patch = {
      patchText: "*** Begin Patch\n*** Add File: nested/example.txt\n+test\n*** End Patch",
    };
    await hooks["tool.execute.before"](
      { tool: "apply_patch", sessionID: "session-a" },
      { args: patch },
    );
    assert.match(
      patch.patchText,
      new RegExp(`Add File: ${result.metadata.worktree_path}/nested/example\\.txt`),
    );

    await hooks.event({
      event: {
        type: "session.created",
        properties: {
          info: { id: "session-child", parentID: "session-a" },
        },
      },
    });
    const childBash = {};
    await hooks["tool.execute.before"](
      { tool: "bash", sessionID: "session-child" },
      { args: childBash },
    );
    assert.equal(childBash.workdir, result.metadata.worktree_path);

    await assert.rejects(
      hooks["tool.execute.before"](
        { tool: "bash", sessionID: "session-b" },
        { args: {} },
      ),
      /blocked bash in the primary checkout/,
    );
  } finally {
    await rm(parent, { recursive: true, force: true });
  }
});
