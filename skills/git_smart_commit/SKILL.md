---
name: git_smart_commit
description: Senses changes and executes atomic, multi-staged commits via the smart_commit orchestrator.
---

# Git Smart Commit Skill

## Objective

Identify semantic changes in the working tree and execute one or more structured, valid commits following project rules.

## Constraints

1. Do NOT use `git commit` directly. Do NOT use `git add` unless explicitly instructed by the orchestrator's `instruction` field. The orchestrator handles staging internally.
2. Do NOT bypass the plan-execute two-phase process.
3. Commit messages MUST strictly follow the `message_regex` and `subject_max_length` provided in the sense response.

## Steps

### Step 1: Sense working tree changes

Run the orchestrator in sense mode to scan the repository and retrieve configuration rules.

// turbo
1. Execute `agt git commit --sense`.

### Step 2: Parse and build commit plan

Analyze the JSON response from Step 1.
- If `status` is `success` and `changed_files` is empty: Report "No changes to commit" and stop.
- If `status` is `paused`:
    1. Extract `details.rules_context` (allowed types, regex, length constraints).
    2. Extract `details.diff_summary`.
    3. Group changed files into atomic logical units based on the `grouping_signals`.
    4. Draft commit messages for each group that satisfy the regex and length rules.
    5. Construct a JSON plan in the format: `{"commits": [{"files": ["path/a", "path/b"], "message": "feat: description"}]}`.

### Step 3: Execute the commit plan

Transmit the drafted plan back to the orchestrator for atomic execution.

2. Execute `agt git commit --plan '<YOUR_PLAN_JSON_STRING>'`.

### Step 4: Verify execution result

Check the final output of the execution.
- If `status` is `success`: Summarize the successfully created commits to the user.
- If `status` is `error`: Read the `message` and `details`, fix the plan or resolve terminal issues, and retry from Step 3 if appropriate.

## Acceptance Criteria

- All successfully committed changes appear in `git log`.
- Commits are atomic and follow the conventional commit format defined in `rules.yaml`.
- The orchestrator returns `status: "success"`.

## Error Handling

- **Branch Protected**: If the sense result reports the branch is protected, do NOT attempt to commit. Advise the user to create a feature branch.
- **Detached HEAD**: If the sense result reports a detached HEAD, advise the user to checkout a branch first.
- **Invalid JSON Plan**: If Step 3 returns a JSON parsing error, verify your JSON escaping (especially for nested quotes in commit messages) and retry.
