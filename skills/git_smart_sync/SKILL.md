---
name: git_smart_sync
description: Synchronizes local branch with upstream and main branches using a 4-stage linear rebase pipeline.
---

# Git Smart Sync Skill

## Objective

Safely align the current branch with its remote upstream and the project's default branch, resolving conflicts incrementally and pushing with safety guards.

## Constraints

1. Do NOT use `git pull`, `git rebase`, or `git push` directly. Use `agt git sync`.
2. Do NOT use the non-existent `--continue` flag. Use `--point <stage>` to resume.
3. NEVER force push to protected branches unless explicitly permitted by the orchestrator.
4. Use of `git add` is permitted ONLY for marking resolved conflict files during the rebase cycle.

## Steps

### Step 1: Initialize synchronization

Start the sync pipeline. The orchestrator will check for dirty trees, detached HEADs, and remote configurations.

// turbo
1. Execute `agt git sync --point init`.

### Step 2: Handle initialization halts

Check the JSON response from Step 1.
- If `status` is `success`: (Rare at this stage as it usually falls through) Continue.
- If `status` is `paused` and `message` says "Working tree is dirty":
    1. Stop this skill.
    2. Invoke the `git_smart_commit` skill to clear changes.
    3. Return to Step 1.
- If `status` is `paused` and `details.point` is `current_rebase`, `rebase_main`, or `push`: Proceed to the corresponding step below.

### Step 3: Resolve rebase conflicts

The orchestrator executes a linear pipeline: `current_rebase` (upstream) → `rebase_main` (default branch).
If a conflict occurs, the orchestrator will return `status: "paused"` with a `point` value.

2. If `status` is `paused` with a `point` (e.g., `current_rebase` or `rebase_main`):
    1. Read `details.conflicted_files`.
    2. Use file tools to resolve conflicts in those files.
    3. Run `git add <file>` for each resolved file.
    4. Resume the pipeline by running: `agt git sync --point <DETAILS_POINT_VALUE>`.
    5. Repeat if new conflicts arise at the same or next point.

### Step 4: Push the aligned branch

Once rebases are complete, the pipeline reaches the `push` stage.

3. If the orchestrator halts at `point: "push"` (e.g., for manual check), or automatically attempts push:
    - On `success`: Confirm to the user that the branch is aligned and pushed.
    - On `error`: Identify if the push was rejected (e.g., remote changes) and follow the error message instruction.

## Acceptance Criteria

- All local commits are rebased on top of the latest default branch.
- The branch is pushed to the remote with `force-with-lease`.
- The final orchestrator response is `status: "success"`.

## Error Handling

- **Abort Operation**: If conflicts are too complex or the user wants to stop, execute `agt git sync --abort`. This safely rolls back the environment.
- **Merge/Cherry-pick in progress**: If the orchestrator reports an existing merge or cherry-pick, advise the user to finish those operations or abort them before syncing.
- **Unrecognized Error**: For any terminal error, do NOT retry. Report the `message` and `stderr` to the user.
