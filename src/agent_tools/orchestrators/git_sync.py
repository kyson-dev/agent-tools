"""
Smart Sync Orchestrator

Linear pipeline: Init → Pull/Rebase Upstream → Rebase Main → Push
Each stage can pause for conflicts, returning a Result with the current `point`
so L3 can resume after resolving.
"""

import os
from typing import Literal

from ...config import (
    get_allow_direct_actions_to_protected,
    get_protected_branches,
)
from ...git import (
    GitCommandError,
    get_branch_context,
    get_repo_context,
    run_git,
)
from ...protocol import Result

WORKFLOW = "git_sync"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_op_status() -> str | None:
    """Detect which git operation is currently in progress, if any.

    Returns: 'rebase', 'merge', 'cherry-pick', or None.
    """
    git_dir_res = run_git(["rev-parse", "--git-dir"])
    if not git_dir_res.ok:
        return None
    git_dir = git_dir_res.stdout.strip()
    if any(
        os.path.exists(os.path.join(git_dir, d))
        for d in ("rebase-merge", "rebase-apply")
    ):
        return "rebase"
    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        return "merge"
    if os.path.exists(os.path.join(git_dir, "CHERRY_PICK_HEAD")):
        return "cherry-pick"
    return None


def _pause_for_conflict(current_point: str) -> Result:
    """Return a standardized paused Result for rebase conflicts."""
    conflicts_res = run_git(["diff", "--name-only", "--diff-filter=U"])
    return Result(
        status="handoff",
        message="Conflicts detected during rebase.",
        workflow=WORKFLOW,
        next_step="resolve_conflicts",
        resume_point=current_point,
        instruction=f"1. Resolve conflicts in files listed in `details`. "
        f"2. Run `git add <file>` for each resolved file. "
        f'3. Resume the pipeline by calling `git_sync_flow(point="{current_point}")`.',
        details={
            "conflicted_files": conflicts_res.stdout.strip().splitlines(),
        },
    )


def _abort() -> Result:
    """Abort whichever git operation is currently in progress."""
    op = _get_op_status()
    if op is None:
        return Result(
            status="error",
            message="No operation in progress to abort.",
            workflow=WORKFLOW,
        )

    abort_cmd = {
        "rebase": ["rebase", "--abort"],
        "merge": ["merge", "--abort"],
        "cherry-pick": ["cherry-pick", "--abort"],
    }[op]

    res = run_git(abort_cmd)
    if res.ok:
        return Result(
            status="success",
            message=f"{op.capitalize()} aborted. Environment rolled back.",
            workflow=WORKFLOW,
        )
    return Result(
        status="error", message=f"Abort failed: {res.stderr}", workflow=WORKFLOW
    )


def _sync(
    point: Literal["init", "current_rebase", "rebase_main", "push"] = "init",
) -> Result:
    """
    Linear Sync Pipeline.

    Stages:
        init           → environment & dirty-tree check
        current_rebase → pull --rebase against upstream
        rebase_main    → rebase onto primary_remote/default_branch
        push           → force-with-lease push

    Args:
        point: which stage to resume from (set by a previous paused Result).
    """
    try:
        # ====== Stage 1: Init ======
        if point == "init":
            # 1a. Pre-condition guard: detect any in-progress git operation.
            op = _get_op_status()
            if op == "rebase":
                # A leftover rebase — attempt to continue it.
                res = run_git(["rebase", "--continue"])
                if not res.ok:
                    return _pause_for_conflict("init")
            elif op == "merge":
                return Result(
                    status="error",
                    message="A merge is in progress. Resolve conflicts and run `git commit`, or abort with `sync --abort`.",
                    workflow=WORKFLOW,
                )
            elif op == "cherry-pick":
                return Result(
                    status="error",
                    message="A cherry-pick is in progress. Run `git cherry-pick --continue` to finish, or abort with `sync --abort`.",
                    workflow=WORKFLOW,
                )

            # 1b. Gather context (first and only time for the pipeline entry).
            branch_info = get_branch_context(refresh=True)

            # 1c. Guard: detached HEAD
            if branch_info.is_detached:
                return Result(
                    status="error",
                    message="HEAD is detached. Please checkout a branch before syncing.",
                    workflow=WORKFLOW,
                )

            # 1d. Guard: protected branch
            if (
                branch_info.current_branch in get_protected_branches()
                and not get_allow_direct_actions_to_protected()
            ):
                return Result(
                    status="error",
                    message=f"Branch '{branch_info.current_branch}' is protected.",
                    workflow=WORKFLOW,
                )

            # 1e. Guard: dirty working tree
            if branch_info.is_dirty:
                return Result(
                    status="handoff",
                    message="Working tree is dirty. Commit changes first.",
                    workflow=WORKFLOW,
                    next_step="clean_worktree",
                    resume_point="init",
                    instruction='Run the `git_commit_flow` prompt to clear changes, then re-run sync with `point="init"`.',
                )

            # 1f. Guard: no remote configured
            repo_info = get_repo_context(refresh=True)
            if not repo_info.primary_remote:
                return Result(
                    status="error",
                    message="No remote configured. Run `git remote add origin <url>` first.",
                    workflow=WORKFLOW,
                )

            point = "current_rebase"  # fall through

        # ====== Stage 2: Pull / Rebase Upstream ======
        if point == "current_rebase":
            if _get_op_status() == "rebase":
                # Resuming after conflict was resolved at this stage.
                res = run_git(["rebase", "--continue"])
                if not res.ok:
                    return _pause_for_conflict("current_rebase")
            else:
                branch_info = get_branch_context()
                if branch_info.upstream and branch_info.behind > 0:
                    res = run_git(["pull", "--rebase"])
                    if not res.ok:
                        return _pause_for_conflict("current_rebase")

            point = "rebase_main"  # fall through

        # ====== Stage 3: Rebase onto Default Branch ======
        if point == "rebase_main":
            if _get_op_status() == "rebase":
                # Resuming after conflict was resolved at this stage.
                res = run_git(["rebase", "--continue"])
                if not res.ok:
                    return _pause_for_conflict("rebase_main")
            else:
                branch_info = get_branch_context()
                repo_info = get_repo_context()

                # Skip if default branch is unknown (e.g. fresh remote with no branches yet)
                if not repo_info.default_branch or not repo_info.primary_remote:
                    pass
                # Skip if current branch is the default branch
                elif branch_info.current_branch == repo_info.default_branch:
                    pass
                # Rebase onto default branch
                else:
                    remote = repo_info.primary_remote
                    target = f"{remote}/{repo_info.default_branch}"
                    res = run_git(["rebase", target])
                    if not res.ok:
                        return _pause_for_conflict("rebase_main")

            point = "push"  # fall through

        # ====== Stage 4: Push ======
        if point == "push":
            branch_info = get_branch_context()
            if not branch_info.current_branch:
                return Result(
                    status="error",
                    message="Current branch is unknown. Please checkout a branch before syncing.",
                    workflow=WORKFLOW,
                )

            repo_info = get_repo_context()
            remote = repo_info.primary_remote or "origin"

            if branch_info.upstream:
                push_args = ["push", "--force-with-lease"]
            else:
                push_args = ["push", "-u", remote, branch_info.current_branch]

            res = run_git(push_args)
            if res.ok:
                return Result(
                    status="success",
                    message="Branch aligned and pushed successfully.",
                    workflow=WORKFLOW,
                )
            return Result(
                status="error",
                message=f"Push failed: {res.stderr}",
                workflow=WORKFLOW,
            )

        # If we somehow land here, the point value was unrecognised.
        return Result(
            status="error",
            message=f"Invalid pipeline point: '{point}'.",
            workflow=WORKFLOW,
        )

    except GitCommandError as e:
        return Result(
            status="error",
            message=str(e),
            workflow=WORKFLOW,
            details={"command": e.command, "stderr": e.stderr},
        )
    except Exception as e:
        # Catch-all boundary: any unexpected runtime error (TypeError,
        # AttributeError, KeyError from config, etc.) must return JSON
        # — never a raw traceback — because the caller is an LLM agent.
        return Result(
            status="error",
            message=f"Internal orchestrator error: {type(e).__name__}: {e}",
            workflow=WORKFLOW,
        )


def git_sync_flow(
    point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init",
) -> Result:
    try:
        if point == "abort":
            return _abort()
        else:
            return _sync(point)
    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)
    except Exception as e:
        return Result(
            status="error", message=f"Git sync error: {str(e)}", workflow=WORKFLOW
        )
