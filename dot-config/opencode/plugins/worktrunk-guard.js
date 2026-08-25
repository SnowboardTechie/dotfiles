import { execFile as execFileCallback } from "node:child_process";
import { realpath } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { tool } from "@opencode-ai/plugin";

const execFile = promisify(execFileCallback);
const BLOCKED_PRIMARY_TOOLS = new Set([
  "apply_patch",
  "bash",
  "edit",
  "patch",
  "write",
]);
const PATH_ARGUMENTS = new Map([
  ["bash", "workdir"],
  ["edit", "filePath"],
  ["glob", "path"],
  ["grep", "path"],
  ["lsp", "filePath"],
  ["patch", "filePath"],
  ["read", "filePath"],
  ["write", "filePath"],
]);

async function gitPath(root, argument) {
  const { stdout } = await execFile(
    "git",
    ["-C", root, "rev-parse", "--path-format=absolute", argument],
    { encoding: "utf8" },
  );
  return realpath(stdout.trim());
}

async function isPrimaryCheckout(root) {
  try {
    const { stdout: bare } = await execFile(
      "git",
      ["-C", root, "rev-parse", "--is-bare-repository"],
      { encoding: "utf8" },
    );
    if (bare.trim() === "true") {
      return false;
    }

    const [gitDirectory, commonDirectory] = await Promise.all([
      gitPath(root, "--git-dir"),
      gitPath(root, "--git-common-dir"),
    ]);
    return gitDirectory === commonDirectory;
  } catch {
    return false;
  }
}

function parseWorktreePath(output, branch) {
  const branchRef = `refs/heads/${branch}`;

  for (const block of output.trim().split(/\n\s*\n/)) {
    const fields = new Map(
      block.split("\n").map((line) => {
        const separator = line.indexOf(" ");
        return separator === -1
          ? [line, ""]
          : [line.slice(0, separator), line.slice(separator + 1)];
      }),
    );
    if (fields.get("branch") === branchRef) {
      return fields.get("worktree");
    }
  }

  return undefined;
}

async function findWorktreePath(root, branch) {
  const { stdout } = await execFile(
    "git",
    ["-C", root, "worktree", "list", "--porcelain"],
    { encoding: "utf8" },
  );
  return parseWorktreePath(stdout, branch);
}

async function prepareWorktree(root, { branch, create, base }) {
  const args = ["-C", root, "switch", "--format=json", "--no-cd"];
  if (create) {
    args.push("--create");
  }
  if (base) {
    args.push("--base", base);
  }
  args.push(branch);

  let warning;
  try {
    await execFile("wt", args, {
      encoding: "utf8",
      env: process.env,
    });
  } catch (error) {
    warning = (error.stderr || error.message || String(error)).trim();
  }

  const path = await findWorktreePath(root, branch);
  if (!path || (await isPrimaryCheckout(path))) {
    throw new Error(
      warning || `Worktrunk did not create or locate a linked worktree for ${branch}`,
    );
  }

  return { path, warning };
}

function reroutePath(value, primaryRoot, worktreeRoot) {
  if (!value) {
    return worktreeRoot;
  }
  if (!path.isAbsolute(value)) {
    return path.resolve(worktreeRoot, value);
  }

  const relative = path.relative(primaryRoot, value);
  if (relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== "..")) {
    return path.resolve(worktreeRoot, relative);
  }
  return value;
}

function rerouteTool(toolName, args, primaryRoot, worktreeRoot) {
  const pathArgument = PATH_ARGUMENTS.get(toolName);
  if (pathArgument && (args[pathArgument] || ["bash", "glob", "grep"].includes(toolName))) {
    args[pathArgument] = reroutePath(
      args[pathArgument],
      primaryRoot,
      worktreeRoot,
    );
  }

  if (toolName === "apply_patch" && args.patchText) {
    args.patchText = args.patchText.replace(
      /^(\*\*\* (?:Add File|Delete File|Update File|Move to): )(.+)$/gm,
      (_line, prefix, filePath) =>
        `${prefix}${reroutePath(filePath, primaryRoot, worktreeRoot)}`,
    );
  }
}

export const WorktrunkGuardPlugin = async ({ worktree }) => {
  const primaryCheckout = await isPrimaryCheckout(worktree);
  const adoptedWorktrees = new Map();

  return {
    event: async ({ event }) => {
      const info = event.properties?.info;
      if (event.type === "session.created" && info?.parentID) {
        const adoptedWorktree = adoptedWorktrees.get(info.parentID);
        const sessionID = event.properties.sessionID || info.id;
        if (adoptedWorktree && sessionID) {
          adoptedWorktrees.set(sessionID, adoptedWorktree);
        }
      }
      if (event.type === "session.deleted") {
        adoptedWorktrees.delete(event.properties?.sessionID || info?.id);
      }
    },
    tool: {
      worktrunk_workspace: tool({
        description:
          "Create or locate an isolated feature worktree with Worktrunk. Use this before repository mutations when the session started in a primary checkout.",
        args: {
          branch: tool.schema
            .string()
            .min(1)
            .describe("Feature branch name or existing branch to open"),
          create: tool.schema
            .boolean()
            .default(true)
            .describe("Create a new branch; set false to open an existing branch"),
          base: tool.schema
            .string()
            .optional()
            .describe("Optional base branch when creating a new branch"),
        },
        async execute(args, context) {
          if (args.base && !args.create) {
            throw new Error("base is only valid when create is true");
          }

          const result = await prepareWorktree(context.worktree, args);
          adoptedWorktrees.set(context.sessionID, result.path);
          const warning = result.warning
            ? `\n\nWorktrunk warning:\n${result.warning}`
            : "";
          return {
            output:
              `Workspace adopted at ${result.path}. ` +
              `Subsequent tools in this session will run from the linked worktree.${warning}`,
            metadata: {
              branch: args.branch,
              worktree_path: result.path,
              warning: result.warning,
            },
          };
        },
      }),
    },
    "experimental.chat.system.transform": async (input, output) => {
      if (!primaryCheckout || adoptedWorktrees.has(input.sessionID)) {
        return;
      }
      output.system.push(
        "WORKTRUNK GUARD: This session is running in the repository's primary checkout. It is read-only. Use worktrunk_workspace to create or locate and adopt a linked feature worktree before any repository mutation.",
      );
    },
    "tool.execute.before": async (input, output) => {
      const adoptedWorktree = adoptedWorktrees.get(input.sessionID);
      if (adoptedWorktree) {
        rerouteTool(input.tool, output.args, worktree, adoptedWorktree);
        return;
      }
      if (primaryCheckout && BLOCKED_PRIMARY_TOOLS.has(input.tool)) {
        throw new Error(
          `Worktrunk guard blocked ${input.tool} in the primary checkout. ` +
            "Use worktrunk_workspace to adopt a linked worktree in this session.",
        );
      }
    },
  };
};
