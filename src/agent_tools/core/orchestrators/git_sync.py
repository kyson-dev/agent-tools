import logging
import os
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    get_branch_context,
    get_repo_context,
    run_git,
)
from agent_tools.infrastructure.config.manager import (
    get_allow_direct_actions_to_protected,
    get_protected_branches,
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_sync"


def _get_op_status() -> str | None:
    """Detect which git operation is currently in progress."""
    git_dir_res = run_git(["rev-parse", "--git-dir"])
    if not git_dir_res.ok:
        return None
    git_dir = git_dir_res.stdout.strip()
    if any(os.path.exists(os.path.join(git_dir, d)) for d in ("rebase-merge", "rebase-apply")):
        return "rebase"
    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        return "merge"
    return None


def _pause_for_conflict(current_point: str) -> Result:
    """Standardized recovery instruction for rebase conflicts."""
    conflicts_res = run_git(["diff", "--name-only", "--diff-filter=U"])
    files = conflicts_res.stdout.strip().splitlines()

    return Result(
        status="handoff",
        message="Conflicts detected.",
        workflow=WORKFLOW,
        next_step="RESOLVE_CONFLICTS",
        resume_point=current_point,
        instruction=(
            f"1. Resolve conflicts in: {', '.join(files)}\n"
            "2. Run 'git add <file>' for all resolved files.\n"
            f"3. Resume by calling 'git_sync_flow' with point='{current_point}'."
        ),
        constraints=[
            "Do NOT run 'git commit' during rebase.",
            "Do NOT run 'git rebase --continue' manually; the tool handles it.",
        ],
        details={"conflicted_files": files},
    )


def _handle_init() -> Result:
    """Stage 1: Pre-flight checks."""
    op = _get_op_status()
    if op == "rebase":
        res = run_git(["rebase", "--continue"])
        if not res.ok:
            return _pause_for_conflict("init")
    elif op == "merge":
        return Result(
            status="error",
            message="Merge in progress.",
            workflow=WORKFLOW,
            instruction="Please resolve merge manually or run 'git_sync_flow(point=\"abort\")'.",
        )

    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    if (
        branch_info.current_branch
        and branch_info.current_branch in get_protected_branches()
        and not get_allow_direct_actions_to_protected()
    ):
        return Result(
            status="error",
            message="Branch is protected.",
            workflow=WORKFLOW,
            instruction="Syncing to protected branches is restricted.",
        )

    if branch_info.is_dirty:
        return Result(
            status="handoff",
            message="Worktree is dirty.",
            workflow=WORKFLOW,
            resume_point="init",
            instruction="Please using 'git_commit_flow' to commit your changes before syncing.",
        )

    repo_info = get_repo_context(refresh=True)
    if not repo_info.primary_remote:
        return Result(status="error", message="No remote configured.", workflow=WORKFLOW)

    return _handle_current_rebase()


def _handle_current_rebase() -> Result:
    """Stage 2: Rebase against upstream."""
    if _get_op_status() == "rebase":
        res = run_git(["rebase", "--continue"])
        if not res.ok:
            return _pause_for_conflict("current_rebase")
    else:
        branch_info = get_branch_context()
        if branch_info.upstream and branch_info.behind > 0:
            res = run_git(["pull", "--rebase"])
            if not res.ok:
                return _pause_for_conflict("current_rebase")

    return _handle_rebase_main()


def _handle_rebase_main() -> Result:
    """Stage 3: Rebase onto default branch."""
    if _get_op_status() == "rebase":
        res = run_git(["rebase", "--continue"])
        if not res.ok:
            return _pause_for_conflict("rebase_main")
    else:
        branch_info = get_branch_context()
        repo_info = get_repo_context()

        if (
            repo_info.default_branch
            and repo_info.primary_remote
            and branch_info.current_branch
            and branch_info.current_branch != repo_info.default_branch
        ):
            target = f"{repo_info.primary_remote}/{repo_info.default_branch}"
            res = run_git(["rebase", target])
            if not res.ok:
                return _pause_for_conflict("rebase_main")

    return _handle_push()


def _handle_push() -> Result:
    """Stage 4: Safe push."""
    branch_info = get_branch_context()
    if not branch_info.current_branch:
        return Result(status="error", message="Unknown current branch.", workflow=WORKFLOW)

    repo_info = get_repo_context()
    remote = repo_info.primary_remote
    if not remote:
        return Result(status="error", message="No remote configured for push.", workflow=WORKFLOW)

    if branch_info.upstream:
        push_args = ["push", "--force-with-lease"]
    else:
        push_args = ["push", "-u", remote, branch_info.current_branch]

    res = run_git(push_args)
    if res.ok:
        return Result(
            status="success",
            message="Sync and push completed successfully.",
            workflow=WORKFLOW,
        )
    return Result(
        status="error",
        message=f"Push failed: {res.stderr}",
        workflow=WORKFLOW,
        instruction="Check for remote rejections or network issues.",
    )


def _handle_abort() -> Result:
    """Emergency abort."""
    op = _get_op_status()
    if not op:
        return Result(status="error", message="Nothing to abort.", workflow=WORKFLOW)

    res = run_git([op, "--abort"])
    return Result(
        status="success" if res.ok else "error",
        message=f"Abort {op} {'success' if res.ok else 'failed'}.",
        workflow=WORKFLOW,
    )


def git_sync_flow(
    point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init",
) -> Result:
    """Industrial-grade git sync flow orchestrator (pull | rebase | push)."""
    handlers = {
        "init": _handle_init,
        "current_rebase": _handle_current_rebase,
        "rebase_main": _handle_rebase_main,
        "push": _handle_push,
        "abort": _handle_abort,
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(status="error", message=f"Invalid point: {point}", workflow=WORKFLOW)
        return handler()
    except Exception as e:
        logger.exception("Sync workflow crash")
        return Result(status="error", message=f"Sync failed: {str(e)}", workflow=WORKFLOW)
