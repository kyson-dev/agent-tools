"""
Smart Sync Orchestrator

Linear pipeline: Init → Pull/Rebase Upstream → Rebase Main → Push
Each stage can pause for conflicts, returning a Result with the current `point`
so L3 can resume after resolving.
"""
import os
from typing import Literal, Optional

from protocol import Result
from git import run_git, get_branch_context, get_repo_context, GitCommandError
from config import get_protected_branches, get_allow_direct_actions_to_protected

WORKFLOW = "smart_sync"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_op_status() -> Optional[str]:
    """Detect which git operation is currently in progress, if any.
    
    Returns: 'rebase', 'merge', 'cherry-pick', or None.
    """
    git_dir_res = run_git(["rev-parse", "--git-dir"])
    if not git_dir_res.ok:
        return None
    git_dir = git_dir_res.stdout.strip()
    if any(os.path.exists(os.path.join(git_dir, d)) for d in ("rebase-merge", "rebase-apply")):
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
        status="paused",
        message="Conflicts detected during rebase.",
        workflow=WORKFLOW,
        details={
            "conflicted_files": conflicts_res.stdout.strip().splitlines(),
            "point": current_point,
            "instruction": (
                f"Resolve conflicts, `git add`, then re-run with point='{current_point}'."
            ),
        },
    )


def _handle_abort() -> Result:
    """Abort whichever git operation is currently in progress."""
    op = _get_op_status()
    if op is None:
        return Result(status="error", message="No operation in progress to abort.", workflow=WORKFLOW)

    abort_cmd = {
        "rebase": ["rebase", "--abort"],
        "merge": ["merge", "--abort"],
        "cherry-pick": ["cherry-pick", "--abort"],
    }[op]

    res = run_git(abort_cmd)
    if res.ok:
        return Result(status="success", message=f"{op.capitalize()} aborted. Environment rolled back.", workflow=WORKFLOW)
    return Result(status="error", message=f"Abort failed: {res.stderr}", workflow=WORKFLOW)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_sync_workflow(
    mode: Literal["sync", "abort"] = "sync",
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
        mode:  "sync" to run the pipeline, "abort" to cancel an in-progress rebase.
        point: which stage to resume from (set by a previous paused Result).
    """
    try:
        # ------ Abort (independent of the pipeline) ------
        # Kept inside the try block so any unexpected crash in _handle_abort
        # is captured and returned as a JSON error, not a raw traceback.
        if mode == "abort":
            return _handle_abort()
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
                    status="paused",
                    message="Working tree is dirty. Commit changes first.",
                    workflow=WORKFLOW,
                    details={
                        "point": "init",
                        "instruction": "Run the commit skill, then re-run sync.",
                    },
                )

            # 1f. Guard: no remote configured
            repo_info = get_repo_context()
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
                # current branch is same default branch
                branch_info = get_branch_context()
                repo_info = get_repo_context()
                if branch_info.current_branch != repo_info.default_branch:
                    remote = repo_info.primary_remote or "origin"
                    target = f"{remote}/{repo_info.default_branch}"
                    res = run_git(["rebase", target])
                    if not res.ok:
                        return _pause_for_conflict("rebase_main")
                
            point = "push"  # fall through

        # ====== Stage 4: Push ======
        if point == "push":
            branch_info = get_branch_context()
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
