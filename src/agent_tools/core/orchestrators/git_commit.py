import json
import logging
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    execute_commit_plan,
    get_branch_context,
    get_diff_summary,
)
from agent_tools.infrastructure.config.manager import (
    get_allow_direct_actions_to_protected,
    get_commit_body_wrap_length,
    get_commit_subject_regex,
    get_protected_branches,
    get_commit_grouping_signals,
    get_commit_max_groups,
    get_sensitive_patterns,
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_commit"


def _check_safety_guards() -> Result | None:
    """Pre-condition guards for commit operations."""
    branch_info = get_branch_context(refresh=True)

    if branch_info.is_detached:
        return Result(
            status="error",
            message="HEAD is detached.",
            workflow=WORKFLOW,
            instruction="Please checkout a branch (e.g., git checkout main) before committing.",
        )

    if (
        branch_info.current_branch
        and branch_info.current_branch in get_protected_branches()
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
    """Stage 1: Analyze workspace state without destructive side effects."""
    guard = _check_safety_guards()
    if guard:
        return guard

    # Capture current state before any 'add'
    diff_info = get_diff_summary()

    # Check for sensitive files (e.g., .env, secrets)
    sensitive_patterns = get_sensitive_patterns()
    risk_files = [
        f.filepath for f in diff_info.changed_files if any(p in f.filepath.lower() for p in sensitive_patterns)
    ]

    if not diff_info.changed_files:
        return Result(
            status="success",
            message="Working tree is clean.",
            workflow=WORKFLOW,
        )

    staged = [f.filepath for f in diff_info.changed_files if f.status_code[0] != " "]
    unstaged = [f.filepath for f in diff_info.changed_files if f.status_code[1] != " "]

    return Result(
        status="handoff",
        message="Workspace analyzed. Ready to build commit plan.",
        workflow=WORKFLOW,
        next_step="BUILD_COMMIT_PLAN",
        resume_point="commit",
        instruction=(
            "【STRICT PROTOCOL】You are in a controlled workflow. Direct commits or bypassing analysis is strictly prohibited.\n"
            "【ACTION】\n"
            "1. Review 'staged' vs 'unstaged' files in details.\n"
            "2. Group files into logical commits (max: 'details.max_groups') using these signals: 'details.grouping_signals'.\n"
            "3. Synthesize 'plan_json_str' following the 'details.json_format' layout, using these field specs for each entry in 'commits':\n"
            "   - 'files': Array of file paths to be committed together.\n"
            "   - 'message': A structured Git message. \n"
            "     * Subject (1st line): 【STRICT】MUST satisfy 'details.subject_regex'.\n"
            "     * Detail body (Add a blank line after the subject): "
            "        * The detailed body should explain the 'why' and 'how' (not just 'what'), especially for complex logic changes. 【STRICT】single line max `details.body_wrap_length` chars.\n"
            "4. Call 'git_commit_flow' with point='commit' and your 'plan_json_str'.\n"
            "【CONSTRAINTS】\n"
            "- Do NOT include files from 'risk_files' unless specifically authorized.\n"
        ),
        details={
            "staged_files": staged,
            "unstaged_files": unstaged,
            "risk_files": risk_files,
            "diff_summary": diff_info.diff_summary,
            "json_format": {
                "commits": [
                    {
                        "files": ["file1.py", "file2.py"],
                        "message": "feat(scope): short description\n\n- Detailed body...",
                    }
                ]
            },
            "subject_regex": get_commit_subject_regex(),
            "body_wrap_length": get_commit_body_wrap_length(),
            "grouping_signals": get_commit_grouping_signals(),
            "max_groups": get_commit_max_groups(),
        },
    )


def _handle_commit(plan_json_str: str) -> Result:
    """Stage 2: Execute the provided commit plan with validation."""
    try:
        plan = json.loads(plan_json_str)
    except json.JSONDecodeError:
        return Result(
            status="handoff",
            message="Invalid JSON format in plan.",
            workflow=WORKFLOW,
            resume_point="commit",
            instruction="Fix the JSON formatting error and resubmit the plan.",
        )

    # execute_commit_plan handles 'git add' for files specified in the plan
    commit_res = execute_commit_plan(plan)
    if not commit_res.ok:
        return Result(
            status="error",
            message=f"Commit execution failed: {commit_res.message}",
            workflow=WORKFLOW,
            instruction="Investigate the git error. You may need to manually resolve issues.",
        )

    return Result(
        status="success",
        message="Commit plan executed successfully.",
        workflow=WORKFLOW,
        details={"commits": commit_res.executed_commits},
    )


def git_commit_flow(point: Literal["sense", "commit"] = "sense", plan_json_str: str = "") -> Result:
    """Industrial-grade git commit flow orchestrator."""
    handlers = {
        "sense": _handle_sense,
        "commit": lambda: _handle_commit(plan_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(status="error", message=f"Invalid point: {point}", workflow=WORKFLOW)
        return handler()
    except Exception as e:
        logger.exception("Commit workflow crash")
        return Result(
            status="error",
            message=f"Git commit flow error: {str(e)}",
            workflow=WORKFLOW,
        )
