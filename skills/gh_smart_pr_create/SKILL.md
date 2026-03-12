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
- If `status` is `handoff` and `resume_point` is `create`:
    1. Proceed to Step 2.

### Step 2: Synthesize PR title and body

Using `details.commits` from Step 1, draft the PR content.

- **Title**: Follow Conventional Commits format (e.g., `feat: add user authentication`).
- **Body**: Write in three sections:
    - **Summary**: 2–3 sentences describing the overall change.
    - **Changes**: Bulleted list of the specific technical modifications.
    - **Impact**: Any side-effects or breaking changes.

### Step 3: Generate Create Plan

Send the synthesized description back to the orchestrator to generate a rigid execution plan.

// turbo
2. Execute `agt gh pr --create '{"title": "...", "body": "..."}'` using your synthesized content.

Check the JSON response:
- If `status` is `handoff`:
    1. Read the `instruction` field. It contains the exact `mcp_github_create_pull_request` call to make.
    2. Proceed to Step 4.

### Step 4: Execute the GitHub MCP Call

Invoke the GitHub MCP tool using the EXACT parameters provided in the Step 3 instruction.

3. Call `mcp_github_create_pull_request` as instructed.

## Acceptance Criteria

- Orchestrator return `status: "handoff"` with `resume_point: "create"`.
- The final PR is successfully created on GitHub via MCP.
- The PR body accurately reflects the branch changes.

## Error Handling

- **Detached HEAD**: Checkout a named branch first, then retry Step 1.
- **No commits ahead of base**: Run `git_smart_sync` to push your commits, then retry.
- **Remote not configured**: Ensure `origin` is set: `git remote add origin <url>`.
- **Branch out of date**: If the MCP tool rejects the PR because the branch is behind, run `git_smart_sync` and retry from Step 1.
- **Permission Denied**: Check write access to the repository. If unavailable, advise the user to create the PR manually.
