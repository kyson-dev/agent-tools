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


def _check_safety_guards() -> Result | None:
    # 1. 游离分支
    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    # 2. 没有remote origin
    repo_info = get_repo_context(refresh=True)
    if not repo_info.primary_remote:
        return Result(status="error", message="No remote origin.", workflow=WORKFLOW)

    # 3. 有当前分支和默认分支存在
    if not branch_info.current_branch or not repo_info.default_branch:
        return Result(status="error", message="Missing branch information.", workflow=WORKFLOW)

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
            "【ACTION】\n"
            f"1. Resolve conflicts in: {', '.join(files)}\n"
            "2. Run 'git add <file>' for all resolved files.\n"
            f"3. Resume by calling 'git_sync_flow' with point='{current_point}'.\n"
            "【CONSTRAINTS】\n"
            "- Do NOT run 'git commit' during rebase."
            "- Do NOT run 'git rebase --continue' manually; the tool handles it."
        ),
        details={"conflicted_files": files},
    )


def _is_protected_branch(refresh: bool = False) -> bool:
    branch_info = get_branch_context(refresh=refresh)
    if not branch_info.current_branch:
        # If current branch is unknown, it cannot be a protected branch.
        # This case should ideally be caught by _check_safety_guards,
        # but this provides an additional safeguard.
        return False
    if branch_info.current_branch in get_protected_branches() and not get_allow_direct_actions_to_protected():
        return True
    return False


def _handle_init() -> Result:
    """Stage 1: Pre-flight checks."""

    safety_guard_res = _check_safety_guards()
    if safety_guard_res:
        return safety_guard_res

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

    is_protected = _is_protected_branch()
    branch_info = get_branch_context()

    if branch_info.is_dirty:
        if is_protected:
            return Result(
                status="error",
                message="Branch is protected.",
                workflow=WORKFLOW,
                instruction="Worktree is dirty and branch is protected, please commit your changes for new branch.",
            )
        return Result(
            status="handoff",
            message="Worktree is dirty.",
            workflow=WORKFLOW,
            resume_point="init",
            instruction="Please using 'git_commit_flow' to commit your changes before syncing.",
        )

    return _handle_current_rebase()


def _handle_current_rebase() -> Result:
    """Stage 2: Rebase against upstream."""
    if _get_op_status() == "rebase":
        res = run_git(["rebase", "--continue"])
        if not res.ok:
            return _pause_for_conflict("current_rebase")
    else:
        branch_info = get_branch_context(refresh=True)
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
        branch_info = get_branch_context(refresh=True)
        repo_info = get_repo_context(refresh=True)

        if not repo_info.default_branch:
            return Result(status="error", message="Default branch unknown.", workflow=WORKFLOW)

        if branch_info.current_branch != repo_info.default_branch:
            target = f"{repo_info.primary_remote}/{repo_info.default_branch}"
            res = run_git(["rebase", target])
            if not res.ok:
                return _pause_for_conflict("rebase_main")

    return _handle_push()


def _handle_push() -> Result:
    """Stage 4: Safe push."""
    branch_info = get_branch_context(refresh=True)
    is_protected = _is_protected_branch(refresh=True)

    if branch_info.ahead == 0:
        return Result(
            status="success",
            message="Local branch is already up-to-date with remote.",
            workflow=WORKFLOW,
        )

    if branch_info.upstream:
        # 这里保护分支本地领先不能提交，如果是相同的话提示成功，如果落后的话不应该存在返回错误吧
        if is_protected:
            return Result(
                status="error",
                message="Branch is protected.",
                workflow=WORKFLOW,
                instruction="branch is protected",
            )

        push_args = ["push", "--force-with-lease"]
    else:
        # 这里是保护分支是肯定不能提交的
        if is_protected:
            return Result(
                status="error",
                message="Branch is protected.",
                workflow=WORKFLOW,
                instruction="branch is protected",
            )

        repo_info = get_repo_context()
        remote = repo_info.primary_remote
        if not remote or not branch_info.current_branch:
            return Result(status="error", message="Missing remote or branch info.", workflow=WORKFLOW)

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
