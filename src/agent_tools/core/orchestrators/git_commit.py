import json
import logging
from dataclasses import asdict
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    GitCommandError,
    execute_commit_plan,
    get_branch_context,
    get_diff_summary,
    get_repo_context,
    run_git,
)
from agent_tools.infrastructure.config.manager import (
    get_allow_direct_actions_to_protected,
    get_full_commit_rules,
    get_protected_branches,
    get_separation_rules,
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_commit"


def _check_preconditions() -> Result | None:
    """Pre-condition guards for commit operations."""
    branch_info = get_branch_context()

    if branch_info.is_detached:
        return Result(
            status="error",
            message="HEAD is detached.",
            workflow=WORKFLOW,
            instruction="Please checkout a branch (e.g., git checkout main) before committing.",
        )

    if (
        branch_info.current_branch in get_protected_branches()
        and not get_allow_direct_actions_to_protected()
    ):
        return Result(
            status="error",
            message=f"Branch '{branch_info.current_branch}' is protected.",
            workflow=WORKFLOW,
            instruction="Direct commits are restricted. Please create a feature branch.",
        )

    return None


def _handle_sense() -> Result:
    """Stage 1: Analyze changes and rules."""
    guard = _check_preconditions()
    if guard:
        return guard

    # Stage changes
    add_res = run_git(["add", "."])
    if not add_res.ok:
        return Result(
            status="error",
            message="Failed to stage files.",
            workflow=WORKFLOW,
            details={"stderr": add_res.stderr},
            instruction="Please check for file locks or permissions and try again.",
        )

    diff_info = get_diff_summary()
    if not diff_info.changed_files:
        return Result(
            status="success",
            message="Working tree is clean.",
            workflow=WORKFLOW,
        )

    return Result(
        status="handoff",
        message="Ready to build commit plan.",
        workflow=WORKFLOW,
        next_step="BUILD_COMMIT_PLAN",
        resume_point="commit",
        instruction=(
            "1. Review the 'changed_files' and 'diff_summary' in details.\n"
            "2. Group changes logically based on 'separation_rules'.\n"
            "3. Draft commit messages following **Conventional Commits** and 'commit_rules'.\n"
            "4. Call 'git_commit_flow' with point='commit' and your plan_json_str."
        ),
        constraints=[
            "Do NOT combine unrelated changes into a single commit.",
            "Do NOT bypass Conventional Commit formatting.",
        ],
        details={
            "changed_files": [asdict(f) for f in diff_info.changed_files],
            "diff_summary": diff_info.diff_summary,
            "commit_rules": get_full_commit_rules(),
            "separation_rules": get_separation_rules(),
            "branch_info": asdict(get_branch_context()),
            "repo_info": asdict(get_repo_context()),
        },
    )


def _handle_commit(plan_json_str: str) -> Result:
    """Stage 2: Execute the provided commit plan."""
    guard = _check_preconditions()
    if guard:
        return guard

    try:
        plan = json.loads(plan_json_str)
    except json.JSONDecodeError:
        return Result(
            status="handoff",
            message="Invalid JSON format in plan.",
            workflow=WORKFLOW,
            resume_point="commit",
            instruction="Fix the JSON formatting error and resubmit the plan.",
            details={"received_str": plan_json_str},
        )

    try:
        commit_res = execute_commit_plan(plan)
        if not commit_res.ok:
            return Result(
                status="error",
                message=f"Commit execution failed: {commit_res.message}",
                workflow=WORKFLOW,
                instruction="Investigate the git error above. You may need to manually fix conflicts or configuration.",
            )

        return Result(
            status="success",
            message="Commit plan executed successfully.",
            workflow=WORKFLOW,
            details={"commits": commit_res.executed_commits},
        )
    except GitCommandError as e:
        return Result(
            status="error",
            message=f"Git error: {e.stderr}",
            workflow=WORKFLOW,
            instruction="Fix the underlying git issue and restart the commit flow.",
        )


def git_commit_flow(
    point: Literal["sense", "commit"] = "sense", plan_json_str: str = ""
) -> Result:
    """Industrial-grade git commit flow orchestrator."""
    try:
        if point == "sense":
            return _handle_sense()
        if point == "commit":
            return _handle_commit(plan_json_str)
        return Result(
            status="error",
            message=f"Unknown resume point: {point}",
            workflow=WORKFLOW,
        )
    except Exception as e:
        logger.exception("Unexpected error in git_commit_flow")
        return Result(
            status="error",
            message=f"Unexpected error: {str(e)}",
            workflow=WORKFLOW,
            instruction="Please report this bug to the developer.",
        )
