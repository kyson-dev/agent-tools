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
            "【ACTION】\n"
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

    # 1. State check
    if pr_data.get("state") != "OPEN":
        return Result(
            status="error", message=f"PR #{number} is not OPEN.", workflow=WORKFLOW
        )

    # 2. Conflict check
    if pr_data.get("mergeable") == "CONFLICTING":
        return Result(
            status="error",
            message=f"PR #{number} has conflicts.",
            workflow=WORKFLOW,
            instruction="Resolve conflicts manually or via 'git_sync_flow'.",
        )

    # 3. CI/Status Checks
    checks = pr_data.get("statusCheckRollup", [])
    if checks:
        failing = [c for c in checks if c.get("conclusion") == "FAILURE"]
        pending = [c for c in checks if c.get("status") != "COMPLETED"]
        if failing:
            return Result(
                status="error",
                message=f"PR #{number} has {len(failing)} failing CI checks.",
                workflow=WORKFLOW,
                details={"failing": failing},
                instruction="Check 'gh pr checks' for details and fix the CI issues.",
            )
        if pending:
            return Result(
                status="handoff",
                message=f"PR #{number} has {len(pending)} pending CI checks.",
                workflow=WORKFLOW,
                next_step="WAIT_FOR_CI",
                resume_point="sense",
                instruction="Wait for CI to complete, then re-run 'gh_pr_merge_flow(point=\"sense\")'.",
            )

    # 4. Review check
    if pr_data.get("mergeStateStatus") == "BLOCKED":
        return Result(
            status="error",
            message=f"PR #{number} is BLOCKED (requires approval or specific checks).",
            workflow=WORKFLOW,
            instruction="Ensure the PR is approved and all mandatory checks pass.",
        )

    return Result(
        status="handoff",
        message=f"PR #{number} is ready for merge.",
        workflow=WORKFLOW,
        next_step="SYNTHESIZE_SQUASH_MESSAGE",
        resume_point="merge",
        instruction=(
            "【STRICT PROTOCOL / 严格协议】您当前处于受控工作流中。禁止跳过步骤、禁止执行任何未授权的裸命令。\n"
            "【ACTION】\n"
            "1. Review PR metadata in details.\n"
            "2. Synthesize a professional squash commit message following Conventional Commits.\n"
            "3. Call 'gh_pr_merge_flow' with point='merge' and your 'override_json_str', formatted according to 'details.json_format'."
        ),
        constraints=[
            "Commit title MUST follow 'type(scope): description'.",
        ],
        details={
            "pr": pr_data,
            "json_format": {
                "title": "feat(core): merge json format logic",
                "body": "Detailed summary of PR changes...",
            },
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
            status="error",
            message=f"Title '{title}' violates commit policy: {rules['message_regex']}",
            workflow=WORKFLOW,
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
            status="error",
            message=f"Merge failed: {res.stderr}",
            workflow=WORKFLOW,
            instruction="Investigate why the merge failed (e.g., branch protection rules).",
        )

    # Local Cleanup & Sync Feedback
    cleanup_msg = "Merged successfully."
    repo_info = get_repo_context()
    remote = repo_info.primary_remote

    if not branch_info.is_dirty:
        try:
            run_git(["checkout", base_branch])
            run_git(["branch", "-D", branch_info.current_branch])
            # Only attempt sync if a remote is available
            if remote:
                sync_res = run_git(["pull", remote, base_branch, "--rebase"])
                if sync_res.ok:
                    cleanup_msg += f" Local branch '{base_branch}' synchronized via '{remote}' and '{branch_info.current_branch}' cleaned up."
                else:
                    cleanup_msg += f" (Note: Switched to '{base_branch}', but auto-sync via '{remote}' failed: {sync_res.stderr}. You may need to resolve conflicts manually.)"
            else:
                cleanup_msg += f" (Note: Switched to '{base_branch}', but no remote found to sync.)"

        except Exception as e:
            cleanup_msg += f" (Note: Local environment sync or cleanup failed: {e})"
    else:
        cleanup_msg += f" (Note: Branch '{branch_info.current_branch}' was NOT deleted locally because it has uncommitted changes.)"

    return Result(status="success", message=cleanup_msg, workflow=WORKFLOW)


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
