import json
import logging
import re
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    get_branch_context,
    get_repo_context,
    run_git,
)
from agent_tools.infrastructure.clients.github.client import run_gh
from agent_tools.infrastructure.config.manager import get_full_commit_rules

logger = logging.getLogger(__name__)
WORKFLOW = "gh_pr_merge"


def _check_safety_guards() -> Result | None:
    """Pre-conditions for PR merging."""
    repo_info = get_repo_context(refresh=True)
    if not repo_info.owner or not repo_info.repo:
        return Result(
            status="error", message="GitHub context unknown.", workflow=WORKFLOW
        )

    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    return None


def _handle_init() -> Result:
    """Stage 0: Init and Sync."""
    return Result(
        status="handoff",
        message="PR merge initiated.",
        workflow=WORKFLOW,
        next_step="SYNC_BEFORE_MERGE",
        resume_point="sense",
        instruction=(
            "1. Run 'git_sync_flow' to ensure your branch is updated and pushed.\n"
            "2. After sync, call 'gh_pr_merge_flow' with point='sense'."
        ),
    )


def _handle_sense() -> Result:
    """Stage 1: PR analysis and message synthesis."""
    guard = _check_safety_guards()
    if guard:
        return guard

    branch_info = get_branch_context()
    if not branch_info.current_branch:
        return Result(
            status="error", message="Unknown current branch.", workflow=WORKFLOW
        )

    view_res = run_gh(
        [
            "pr",
            "view",
            branch_info.current_branch,
            "--json",
            "number,title,body,state,mergeable,mergeStateStatus,statusCheckRollup,reviews,baseRefName",
        ]
    )

    if view_res.returncode != 0:
        return Result(
            status="error",
            message=f"PR not found: {view_res.stderr}",
            workflow=WORKFLOW,
        )

    pr_data = json.loads(view_res.stdout)
    number = pr_data.get("number")

    # Validation logic
    if pr_data.get("state") != "OPEN":
        return Result(
            status="error", message=f"PR #{number} is not OPEN.", workflow=WORKFLOW
        )

    if pr_data.get("mergeable") == "CONFLICTING":
        return Result(
            status="error",
            message=f"PR #{number} has conflicts.",
            workflow=WORKFLOW,
            instruction="Resolve conflicts manually or via git_sync_flow.",
        )

    if pr_data.get("mergeStateStatus") == "BLOCKED":
        return Result(
            status="error",
            message=f"PR #{number} is BLOCKED (approvals or CI).",
            workflow=WORKFLOW,
        )

    return Result(
        status="handoff",
        message=f"PR #{number} is ready for merge.",
        workflow=WORKFLOW,
        next_step="SYNTHESIZE_SQUASH_MESSAGE",
        resume_point="merge",
        instruction=(
            "1. Review PR metadata in details.\n"
            "2. Synthesize a squash commit title and body following Conventional Commits.\n"
            "3. Call 'gh_pr_merge_flow' with point='merge' and your override_json_str."
        ),
        constraints=[
            "Commit message MUST match the regex in details.",
        ],
        details={
            "pr": pr_data,
            "commit_rules": get_full_commit_rules(),
        },
    )


def _handle_merge(override_json_str: str) -> Result:
    """Stage 2: Execution and local cleanup."""
    try:
        data = json.loads(override_json_str)
        title = data.get("title")
        body = data.get("body")
    except json.JSONDecodeError:
        return Result(
            status="error",
            message="Invalid JSON in override_json_str.",
            workflow=WORKFLOW,
        )

    # Validate regex
    rules = get_full_commit_rules()
    if title and not re.match(rules["message_regex"], title):
        return Result(
            status="error", message="Title violates commit policy.", workflow=WORKFLOW
        )

    branch_info = get_branch_context()
    if not branch_info.current_branch:
        return Result(
            status="error", message="Unknown current branch.", workflow=WORKFLOW
        )

    view_res = run_gh(
        ["pr", "view", branch_info.current_branch, "--json", "number,baseRefName"]
    )
    if view_res.returncode != 0:
        return Result(
            status="error", message="Failed to fetch PR info.", workflow=WORKFLOW
        )

    pr_data = json.loads(view_res.stdout)
    number = pr_data.get("number")
    base_branch = pr_data.get("baseRefName")

    if not number or not base_branch:
        return Result(
            status="error", message="Incomplete PR information.", workflow=WORKFLOW
        )

    # Execute Merge
    args = ["pr", "merge", str(number), "--squash", "--delete-branch"]
    if title:
        args.extend(["--subject", title])
    if body:
        args.extend(["--body", body])

    res = run_gh(args)
    if res.returncode != 0:
        return Result(
            status="error", message=f"Merge failed: {res.stderr}", workflow=WORKFLOW
        )

    # Local Cleanup
    if not branch_info.is_dirty:
        try:
            run_git(["checkout", base_branch])
            run_git(["branch", "-D", branch_info.current_branch])
        except Exception as e:
            logger.warning(f"Local cleanup failed: {e}")

    return Result(
        status="success",
        message=f"PR #{number} merged and branch cleaned up.",
        workflow=WORKFLOW,
    )


def gh_pr_merge_flow(
    point: Literal["init", "sense", "merge"] = "init", override_json_str: str = ""
) -> Result:
    """Industrial-grade GitHub PR merging flow orchestrator."""
    handlers = {
        "init": _handle_init,
        "sense": _handle_sense,
        "merge": lambda: _handle_merge(override_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(
                status="error", message=f"Invalid point: {point}", workflow=WORKFLOW
            )
        return handler()
    except Exception as e:
        logger.exception("PR merge workflow crash")
        return Result(
            status="error", message=f"PR merge failed: {str(e)}", workflow=WORKFLOW
        )
