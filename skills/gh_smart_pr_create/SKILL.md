---
name: gh_smart_pr_create
description: Senses PR creation context via the pr_create orchestrator, then creates a Pull Request using native GitHub MCP tools.
---

# GitHub Smart PR Create Skill

## Objective

Collect local repository context (owner, repo, branch, commits) via the L2 orchestrator, synthesize a structured PR description, and create a Pull Request on GitHub using native MCP tools.

## Constraints

1. Do NOT gather repository metadata manually (e.g., do NOT call `git remote get-url` or `git log` yourself). Use `agt gh pr` to extract context through L2.
2. NEVER use `gh` CLI commands. Use `mcp_github_*` tools exclusively for GitHub operations.
3. Do NOT push directly to `main` or `master`. This skill creates a PR — not a direct push.
4. Do NOT dump raw commit hashes or diffs into the PR body. Synthesize a human-readable description from the `commits` list.

## Prerequisites

- Local branch has been synchronized and pushed to the remote repository using `git_smart_sync`.

## Steps

### Step 1: Extract PR context from the orchestrator

Run the L2 orchestrator to perform pre-condition checks and gather all required context.

// turbo
1. Execute `agt gh pr`.

Check the JSON response:
- If `status` is `error`: Read the `message`. Common causes: detached HEAD, no remote configured, no commits ahead of base. Resolve the issue and retry.
- If `status` is `paused`: Extract `details` and proceed to Step 2.

### Step 2: Synthesize PR title and body

Using `details.commits` from Step 1, draft the PR content. Do NOT call any tools in this step.

- **Title**: Follow Conventional Commits format using the most significant change (e.g., `feat: add user authentication`).
- **Body**: Write in three sections:
    - **Summary**: 2–3 sentences describing the overall change.
    - **Changes**: Bulleted list of the specific technical modifications, derived from each commit's `subject` and `body`.
    - **Impact**: Any side-effects, deployment steps, or breaking changes to be aware of.

### Step 3: Create the Pull Request

Invoke the GitHub MCP tool using the context from `details`.

2. Call `mcp_github_create_pull_request` with:
    - `owner`: from `details.owner`
    - `repo`: from `details.repo`
    - `head`: from `details.head`
    - `base`: from `details.base`
    - `title`: synthesized in Step 2
    - `body`: synthesized in Step 2

## Acceptance Criteria

- `agt gh pr` returns `status: "paused"` with a non-empty `commits` list.
- The PR is successfully created on GitHub (MCP tool returns a PR URL or number).
- The PR body is human-readable and accurately reflects the branch changes.

## Error Handling

- **Detached HEAD**: Checkout a named branch first, then retry Step 1.
- **No commits ahead of base**: Run `git_smart_sync` to push your commits, then retry.
- **Remote not configured**: Ensure `origin` is set: `git remote add origin <url>`.
- **Branch out of date**: If the MCP tool rejects the PR because the branch is behind, run `git_smart_sync` and retry from Step 1.
- **Permission Denied**: Check write access to the repository. If unavailable, advise the user to create the PR manually.
