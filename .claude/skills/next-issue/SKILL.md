---
name: next-issue
description: Next Issue
user_invocable: true
allowed-tools: Bash(git *), Read, Grep, Glob, AskUserQuestion, mcp__github__search_issues, mcp__github__issue_read
argument-hint: "[#123 (parent/epic issue) or empty]"
---

# Next Issue

Pick the next unblocked GitHub issue assigned to you, create a branch and worktree for it, and get ready to work.

Argument: `<parent-issue-number or empty>`

## Step 1: Find the next issue

1. If `<parent-issue-number>` is provided, fetch its sub-issues:

```
mcp__github__issue_read(method: "get_sub_issues", owner, repo, issue_number: <parent-issue-number>)
```

Otherwise, list open issues assigned to "me":

```
mcp__github__search_issues(query: "repo:<owner>/<repo> is:issue is:open assignee:@me", sort: "created", order: "asc")
```

2. For each candidate issue, fetch it with `mcp__github__issue_read(method: "get", ...)` to read its body for blocker references. GitHub has no first-class "blocked by" relation, so blockers are expressed as text in the issue body (e.g., `Blocked by #123`, `Depends on #123`). Parse those mentions.

3. **Determine which issues are unblocked.** An issue is unblocked if:
   - It has no `Blocked by #N` / `Depends on #N` mentions in its body, OR
   - Every blocker issue is either closed, or there is a local branch `<username>/issue-<N>` for it (check with `git branch --list '<username>/issue-*'`).

4. If no unblocked issues are found, tell the user and stop.

5. If multiple unblocked issues exist, pick the one with the lowest issue number (earliest created). Present it to the user for confirmation before proceeding.

## Step 2: Determine the base branch

Ask the user: "Should I branch from the current branch (`<current-branch>`) or from another branch?"

If the user says the current branch, use it. If they specify another, use that.

If the current worktree is inside your worktrees directory (e.g., `~/code/worktrees/`), extract the current branch name from git automatically and suggest it as the default.

## Step 3: Create branch and worktree

1. Note the issue number (e.g., `123` from `#123`).
2. Create the worktree (replace `$WORKTREES_DIR` with your conventional worktrees directory):

```bash
git worktree add $WORKTREES_DIR/issue-<number> -b <username>/issue-<number> <base-branch>
```

3. **(Optional) Copy a workspace file** if your repo uses a multi-root editor workspace (e.g., a Cursor or VS Code `.code-workspace` file at the repo root):

```bash
cp <repo>/<repo>.code-workspace $WORKTREES_DIR/issue-<number>/<repo>.code-workspace
```

4. **Install dependencies** so the worktree is ready to use. If your repo is a monorepo with a root environment plus per-project environments, sync each one:

```bash
cd $WORKTREES_DIR/issue-<number> && <package-manager> sync
# For each sub-project that has its own environment:
cd $WORKTREES_DIR/issue-<number>/projects/<sub-project> && <package-manager> sync
```

5. **(Optional) Copy editor and type-checker config** from the main repo if they are gitignored (e.g., `.vscode/settings.json`, `pyrightconfig.json`). Each worktree needs its own copies because gitignored files are not carried over:

```bash
mkdir -p $WORKTREES_DIR/issue-<number>/.vscode
cp <repo>/.vscode/settings.json $WORKTREES_DIR/issue-<number>/.vscode/settings.json
# Repeat for pyrightconfig.json, sub-project .vscode dirs, etc., as needed.
```

6. Verify it was created:

```bash
cd $WORKTREES_DIR/issue-<number> && git log --oneline -3
```

## Step 4: Report

Print:
- The issue number, title, and URL
- The branch name and worktree path
- A brief summary of what the issue requires (from its title and first few lines of body)

## Rules

- Always confirm the issue with the user before creating the branch.
- If the branch `<username>/issue-<number>` already exists, tell the user and ask what to do (use existing, or pick a different issue).
- Do not start implementation. This skill only sets up the workspace.
- Do not use em-dashes. Use hyphens, commas, or parentheses instead.
