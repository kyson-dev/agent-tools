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
- If `status` is `success`: The branch is already up-to-date and pushed. Stop.
- If `status` is `handoff` and `next_step` is `clean_worktree`:
    1. Stop this skill.
    2. Invoke the `git_smart_commit` skill to clear changes.
    3. Return to Step 1.
- If `status` is `handoff` and `next_step` is `resolve_conflicts`: Proceed to Step 3.

### Step 3: Resolve rebase conflicts

If a conflict occurs, the orchestrator will return `status: "handoff"` with `next_step: "resolve_conflicts"`.

2. If `status` is `handoff` and `next_step` is `resolve_conflicts`:
    1. Read the `instruction` field for guidance.
    2. Read `details.conflicted_files`.
    3. Use file tools to resolve conflicts in those files.
    4. Run `git add <file>` for each resolved file.
    5. Resume the pipeline by running: `agt git sync --point` followed by the exact value provided in the `resume_point` field.
    6. Repeat if new conflicts arise.

### Step 4: Verify alignment and push

The orchestrator automatically attempts to push after all rebases are complete.

3. Check the final response:
    - On `status: "success"`: Confirm to the user that the branch is aligned and pushed.
    - On `status: "error"` and message mentions push failure: Identify the cause and report it to the user.

## Acceptance Criteria

- All local commits are rebased on top of the latest default branch.
- The branch is pushed to the remote with `force-with-lease`.
- The final orchestrator response is `status: "success"`.

## Error Handling

- **Abort Operation**: If conflicts are too complex, execute `agt git sync --abort`.
- **Merge/Cherry-pick in progress**: Finish those operations or abort them before syncing.
- **Unrecognized Error**: For any terminal error, do NOT retry. Report the `message` to the user.
