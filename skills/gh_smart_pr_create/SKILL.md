---
name: gh_smart_pr_create
description: Senses PR creation context via the pr_create orchestrator, then creates a Pull Request using native GitHub MCP tools.
---

# GitHub Smart PR Create Skill

## Objective

Collect local repository context (owner, repo, branch, commits) via the L2 orchestrator, synthesize a structured PR description, and create a Pull Request on GitHub using native MCP tools.

## Constraints

1. Do NOT gather repository metadata manually (e.g., do NOT call `git remote get-url` or `git log` yourself). Use `agt gh pr` to extract context.
2. NEVER use `gh` CLI commands. Use `mcp_github_*` tools exclusively.
3. Do NOT push directly to `main` or `master`. This skill creates a PR — not a direct push.
4. Do NOT dump raw commit hashes or diffs into the PR body. Synthesize a human-readable description from the `commits` list.

## Prerequisites

- Local branch has been synchronized and pushed using `git_smart_sync`.

## Steps

### Step 1: Extract PR context from the orchestrator

Run the L2 orchestrator to perform pre-condition checks and gather all required context.

// turbo
1. Execute `agt gh pr`.

Check the JSON response:
- If `status` is `error`: Read the `message` and resolve the issue.
- If `status` is `handoff` and `next_step` is `create_mcp_pr`:
    1. Note that `resume_point` is empty because this workflow hands off to external tools.
    2. Read the `instruction` field for the recommended next steps.
    3. Proceed to Step 2.

### Step 2: Synthesize PR title and body

Using `details.commits` from Step 1, draft the PR content.

- **Title**: Follow Conventional Commits format (e.g., `feat: add user authentication`).
- **Body**: Write in three sections:
    - **Summary**: 2–3 sentences describing the overall change.
    - **Changes**: Bulleted list of the specific technical modifications, derived from each commit's `subject` and `body`.
    - **Impact**: Any side-effects, deployment steps, or breaking changes to be aware of.

### Step 3: Create the Pull Request

Invoke the GitHub MCP tool using the context from `details`.

2. Call `mcp_github_create_pull_request` with `owner`, `repo`, `head`, and `base` from `details`, plus your synthesized `title` and `body`.

## Acceptance Criteria

- Orchestrator returns `status: "handoff"` with a non-empty `commits` list.
- The PR is successfully created on GitHub via MCP.
- The PR body accurately reflects the branch changes.

## Error Handling

- **Detached HEAD**: Checkout a named branch first, then retry Step 1.
- **No commits ahead of base**: Run `git_smart_sync` to push your commits, then retry.
- **Remote not configured**: Ensure `origin` is set: `git remote add origin <url>`.
- **Branch out of date**: If the MCP tool rejects the PR because the branch is behind, run `git_smart_sync` and retry from Step 1.
- **Permission Denied**: Check write access to the repository. If unavailable, advise the user to create the PR manually.
