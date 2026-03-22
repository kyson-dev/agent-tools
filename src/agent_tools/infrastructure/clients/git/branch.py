from .client import run_git
from .git_types import BranchContext


def get_branch_context(refresh: bool = False) -> BranchContext:
    """Returns the current git branch context.

    Raises:
        GitCommandError: if any required git command fails (fail-fast).
    """
    # Fail-fast: must be inside a valid work-tree.
    res = run_git(["rev-parse", "--is-inside-work-tree"])
    res.raise_on_error("Not inside a git work-tree")

    if refresh:
        remotes_res = run_git(["remote"])
        if remotes_res.stdout.strip():
            run_git(["fetch", "--all", "--quiet"])

    # --- Current branch / detached HEAD detection ---
    current_branch_res = run_git(["branch", "--show-current"])
    current_branch_res.raise_on_error("Failed to determine current branch")
    current_branch = current_branch_res.stdout.strip()
    is_detached = False

    if not current_branch:
        # Empty output from --show-current means detached HEAD.
        rev_res = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        rev_res.raise_on_error("Failed to resolve HEAD reference")
        head_ref = rev_res.stdout.strip()
        if head_ref == "HEAD":
            is_detached = True
            short_hash_res = run_git(["rev-parse", "--short", "HEAD"])
            short_hash_res.raise_on_error("Failed to resolve HEAD short hash")
            current_branch = short_hash_res.stdout.strip()
        else:
            current_branch = head_ref

    # --- Upstream / ahead-behind ---
    # NOTE: @{u} exits with code 128 when no upstream is set; that is NORMAL
    # (any new branch that hasn't been pushed yet). We must NOT raise here.
    upstream_res = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    upstream = upstream_res.stdout.strip() if upstream_res.ok else None

    ahead = 0
    behind = 0
    if upstream:
        count_res = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
        count_res.raise_on_error("Failed to count commits ahead/behind upstream")
        count_str = count_res.stdout.strip()
        if count_str:
            parts = count_str.split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])

    # --- Dirty-tree check ---
    is_dirty_res = run_git(["status", "--porcelain"])
    is_dirty_res.raise_on_error("Failed to check working tree status")

    return BranchContext(
        current_branch=current_branch or None,
        is_detached=is_detached,
        upstream=upstream or None,
        ahead=ahead,
        behind=behind,
        is_dirty=is_dirty_res.stdout.strip() != "",
    )
