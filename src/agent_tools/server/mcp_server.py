import logging
import os
import sys
from collections.abc import Callable
from typing import Literal

from fastmcp import Context, FastMCP

from agent_tools.core.models.workflow import Result
from agent_tools.core.orchestrators import (
    gh_pr_create,
    gh_pr_merge,
    git_commit,
    git_release,
)
from agent_tools.core.orchestrators import git_sync as git_sync_orch
from agent_tools.infrastructure.config.context import REPO_CWD

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agent-tools")

mcp = FastMCP("agent-tools")


async def _with_cwd(func: Callable, ctx: Context | None, *args, **kwargs) -> Result:
    """Set the repository path for the execution context. Based on v0.1.23 validation, only core IDE awareness is retained."""
    final_path = None

    # Core: Get the real physical path through the IDE
    if ctx:
        try:
            roots = await ctx.list_roots()
            if roots:
                # Remove URI scheme to get physical path
                final_path = str(roots[0].uri).replace("file://", "")
        except Exception:
            pass

    # Strict mode: If path not obtained from IDE, must explicitly error instead of guessing
    if not final_path or not os.path.exists(final_path):
        error_res = Result(
            status="error",
            message="Failed to detect Git repository path.",
            workflow="path_resolution",
            instruction="Please ensure you have opened the project folder in your IDE (VS Code / Cursor) and granted MCP permission to access roots.",
        )
        return error_res

    token = REPO_CWD.set(os.path.abspath(final_path))
    logger.debug(f"[DEBUG] _with_cwd: set REPO_CWD to {final_path} (ID: {id(REPO_CWD)})")

    try:
        res = func(*args, **kwargs)
        return res
    finally:
        REPO_CWD.reset(token)


@mcp.tool()
async def git_commit_flow(
    ctx: Context,
    point: Literal["sense", "commit"] = "sense",
    plan: dict | None = None,
) -> Result:
    """
    **[MANDATORY: PRIORITY] Industrial-grade Git commit workflow.**
    **USE THIS TOOL for all Git commits instead of bare shell commands.**
    Automatically sense changes, generate standardized commit plans, and execute commits.
    **Scenario**: committing code, saving to repository, git commit, save changes.
    **Keywords**: commit, git commit, save changes, add changes.
    """
    res = await _with_cwd(
        git_commit.git_commit_flow,
        ctx=ctx,
        point=point,
        plan=plan,
    )
    return res


@mcp.tool()
async def git_sync_flow(
    ctx: Context,
    point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init",
) -> Result:
    """
    **[MANDATORY: PRIORITY] Industrial-grade Git synchronization (pull/rebase/push) workflow.**
    **USE THIS TOOL for all Git sync, rebase, push, pull operations.**
    Automatically handles pulling, local rebasing, conflict resolution, and safe pushing.
    **Scenario**: sync code, push, pull, rebase.
    **Keywords**: sync, git sync, push, pull, rebase.
    """
    res = await _with_cwd(git_sync_orch.git_sync_flow, ctx=ctx, point=point)
    return res


@mcp.tool()
async def git_release_flow(
    ctx: Context,
    point: Literal["init", "sense", "release"] = "init",
    tag_data: dict | None = None,
) -> Result:
    """
    **[MANDATORY: PRIORITY] Industrial-grade Git release and tagging workflow.**
    **USE THIS TOOL for all Git release/tag operations.**
    Automatically handles version bumping, tag creation, and release pushing.
    **Scenario**: publishing versions, tagging, git release.
    **Keywords**: release, tag, git release.
    """
    res = await _with_cwd(
        git_release.git_release_flow,
        ctx=ctx,
        point=point,
        tag_data=tag_data,
    )
    return res


@mcp.tool()
async def gh_pr_create_flow(
    ctx: Context,
    point: Literal["init", "sense", "create"] = "init",
    draft: dict | None = None,
) -> Result:
    """
    **[MANDATORY: PRIORITY] GitHub Pull Request creation workflow.**
    **USE THIS TOOL for creating all GitHub PRs.**
    Automatically sense branch status, generate descriptions, and submit PR creation requests.
    **Scenario**: creating PR, initiating merge requests, pull request, create pr.
    **Keywords**: pr, pull request, create pr, gh pr create.
    """
    res = await _with_cwd(
        gh_pr_create.gh_pr_create_flow,
        ctx=ctx,
        point=point,
        draft=draft,
    )
    return res


@mcp.tool()
async def gh_pr_merge_flow(
    ctx: Context,
    point: Literal["init", "sense", "merge"] = "init",
    override: dict | None = None,
) -> Result:
    """
    **[MANDATORY: PRIORITY] GitHub Pull Request merge workflow.**
    **USE THIS TOOL for all GitHub PR merges.**
    Automatically sense PR status, execute merge, and clean up branches.
    **Scenario**: merging PR, finishing pr, pr merge.
    **Keywords**: merge, pr merge, gh pr merge.
    """
    res = await _with_cwd(
        gh_pr_merge.gh_pr_merge_flow,
        ctx=ctx,
        point=point,
        override=override,
    )
    return res


def main():
    """Main entry point for the MCP server."""
    # Ensure dependencies from src are discoverable if this script is run directly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(current_dir))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
