import json
from dataclasses import asdict
from typing import Optional

from agent_tools.protocol import Result
from agent_tools.git import (
    run_git,
    get_branch_context,
    get_repo_context,
    get_diff_summary,
    execute_commit_plan,
    GitCommandError
)
from agent_tools.config import (
    get_protected_branches,
    get_allow_direct_actions_to_protected,
    get_full_commit_rules
)

WORKFLOW = "git_commit"


def _check_preconditions() -> Optional[Result]:
    """Shared pre-condition guards for both sense and execute.
    
    Returns a Result if a guard fails, otherwise None (all clear).
    """
    branch_info = get_branch_context()

    # Guard: detached HEAD
    if branch_info.is_detached:
        return Result(
            status="error",
            message="HEAD is detached. Please checkout a branch before committing.",
            workflow=WORKFLOW,
        )

    # Guard: protected branch
    if branch_info.current_branch in get_protected_branches() and not get_allow_direct_actions_to_protected():
        return Result(
            status="error",
            message=f"Branch '{branch_info.current_branch}' is protected. Direct commits are restricted.",
            workflow=WORKFLOW,
            details={"is_protected": True},
        )

    return None


def sense() -> Result:
    try:
        guard = _check_preconditions()
        if guard:
            return guard

        repo_info = get_repo_context()
        branch_info = get_branch_context()

        # Stage all changes — must succeed before we proceed
        add_res = run_git(["add", "."])
        if not add_res.ok:
            return Result(
                status="error",
                message=f"Failed to stage files: {add_res.stderr}",
                workflow=WORKFLOW,
            )

        diff_info = get_diff_summary()
        changed_files = diff_info.changed_files

        if not changed_files:
            return Result(
                status="success",
                message="Working tree is clean.",
                workflow=WORKFLOW,
                details={"changed_files": []},
            )

        rules_context = get_full_commit_rules()

        return Result(
            status="handoff",
            message="Ready to build commit plan.",
            workflow=WORKFLOW,
            next_step="build_plan",
            resume_point="plan",
            instruction=(
                "1. Analyze `changed_files` and `commit_rules` (regex, types, limits) in `details`. "
                "2. VALIDATION REQUIRED: All commit messages MUST strictly follow **Conventional Commits** and `details.commit_rules`. "
                "3. Execute `git_commit_execute(repo_path=\".\", plan_json='...')` with your grouping strategy."
            ),
            details={
                "changed_files": [asdict(f) for f in changed_files],
                "diff_summary": diff_info.diff_summary,
                "branch_info": asdict(branch_info),
                "repo_context": asdict(repo_info),
                "commit_rules": rules_context,
            },
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW, details={"command": e.command, "stderr": e.stderr})
    except Exception as e:
        return Result(status="error", message=f"Sense error: {str(e)}", workflow=WORKFLOW)


def execute(plan_json_str: str) -> Result:
    try:
        # Guard: pre-conditions before executing any git writes
        guard = _check_preconditions()
        if guard:
            return guard

        plan = json.loads(plan_json_str)
    except json.JSONDecodeError:
        return Result(status="error", message="Invalid plan: expected a JSON string.", workflow=WORKFLOW)
    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW, details={"command": e.command, "stderr": e.stderr})
    except Exception as e:
        return Result(status="error", message=f"Execute setup error: {str(e)}", workflow=WORKFLOW)

    try:
        commit_res = execute_commit_plan(plan)

        if not commit_res.ok:
            return Result(
                status="error",
                message=f"Commit failed: {commit_res.message}",
                workflow=WORKFLOW,
                details={"git_output": commit_res.message},
            )

        return Result(
            status="success",
            message="Commit plan executed successfully.",
            workflow=WORKFLOW,
            details={"commits": commit_res.executed_commits},
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW, details={"command": e.command, "stderr": e.stderr})
    except Exception as e:
        return Result(status="error", message=f"Execute error: {str(e)}", workflow=WORKFLOW)


def run_commit_workflow(mode: str, plan_json_str: str = None) -> Result:
    if mode == "sense":
        return sense()
    elif mode == "plan":
        if not plan_json_str:
            return Result(status="error", message="mode='plan' requires a plan_json_str argument.", workflow=WORKFLOW)
        return execute(plan_json_str)
    else:
        return Result(status="error", message=f"Invalid mode: '{mode}'. Expected 'sense' or 'plan'.", workflow=WORKFLOW)
