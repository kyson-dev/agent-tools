---
name: gh_smart_pr_merge
description: Industrial-grade PR merge skill using a strict 4-stage L2-led protocol with identity-aware remediation.
---

# GitHub Smart PR Merge Skill

## Objective

Safely merge the current local branch's Pull Request by performing multi-stage validation (CI, Reviews, Conflicts) and automated cleanup. It identifies the PR automatically based on the active git branch.

## Constraints

1.  **L2 Dominance**: Deterministic logic (Git states, logic gates) MUST be handled by the L2 orchestrator (`pr_merge.py`).
2.  **Stateless L3**: L3 acts ONLY as an MCP gateway, data fetcher, and actuator for remediation.
3.  **Identity Boundary**: Proactive remediation (auto-sync/CI fix) is ONLY triggered if the user is the PR owner. Otherwise, it defaults to informative error reporting.
4.  **No Param Guessing**: L2 identifies the repo and branch. L3 MUST NOT manually override PR numbers or branch names.

## Steps

### Step 1: Sync local branch

Ensure the current branch is up to date and pushed to the remote.

// turbo
1. Execute the `git_smart_sync` skill.

### Step 2: Detect PR context

Locate the active PR associated with the current branch.

// turbo
2. Execute `agt gh merge`.
3. Follow the instruction to call `mcp_github_list_pull_requests`. 
4. Pass the result back: `agt gh merge --mode validate --data '<RAW_JSON>'`.

### Step 3: Validate metadata

L2 checks permissions and mergeability (conflicts/behind).

// turbo
5. Execute fetch instructions (e.g., `get_pull_request_status`, `get_pull_request_reviews`).
6. Pass combined data: `agt gh merge --mode verdict --data '{"status": ..., "reviews": ..., "pr": ...}'`.

### Step 4: Execute merge

Finalize the merge on GitHub.

// turbo
7. Execute `mcp_github_merge_pull_request` as instructed.
8. Confirm success: `agt gh merge --mode cleanup --data '{"merge_confirmed": true, "pr": ...}'`.

### Step 5: Cleanup resources

Finalize local branch deletion and remote branch cleanup.

// turbo
9. L2 will automatically attempt to delete the local branch if safe.
10. Follow the `remote_cleanup` instruction to call `mcp_github_delete_branch` on the correct `head_owner/head_repo`.

## Error Handling Matrix

- **Conflicts/Behind**: L2 will return `error`. Since Step 1 performs a sync, conflicts must be resolved manually if auto-sync fails.
- **Missing Approvals**: L2 returns `error`. User must nudge reviewers manually.
- **CI Failure**: L2 returns `error`. Author must fix test failures and retry.
- **Worktree Dirty**: L2 will preserve the local branch and skip deletion for safety.

## Error Handling Matrix

- **Conflicts/Behind**: L2 will block and (if owner) guide to `git_smart_sync`.
- **Missing Approvals**: L2 returns `error` with the specific reason. User must nudge manually.
- **CI Failure**: L2 blocks. If owner, L2 suggests sync/fix; if not, L2 reports closure.
- **Worktree Dirty**: L2 will preserve the local branch and skip deletion for safety.
