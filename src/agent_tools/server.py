import argparse
import logging
import os
import sys
from collections.abc import Callable
from typing import Literal, cast

from fastmcp import Context, FastMCP

from .context import REPO_CWD
from .orchestrators import gh_pr_create, gh_pr_merge, git_commit, git_release
from .orchestrators import git_sync as git_sync_orch

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agent-tools")

mcp = FastMCP("agent-tools")


async def _with_cwd(
    func: Callable, repo_path: str, ctx: Context | None, *args, **kwargs
):
    """Context-aware wrapper to setup working directory.

    Priority:
    1. Explicit repo_path (if it exists and is not ".")
    2. AGENT_TOOLS_REPO_PATH environment variable
    3. MCP Session Roots (provided by the IDE)
    4. Search upwards for .git from current process CWD
    """
    env_path = os.environ.get("AGENT_TOOLS_REPO_PATH")
    final_path = None

    # Priority 1: Use explicit repo_path if it's an absolute directory
    if repo_path and repo_path != "." and os.path.isdir(repo_path):
        final_path = os.path.abspath(repo_path)
    # Priority 2: Use Environment Variable
    elif env_path and os.path.exists(env_path):
        final_path = os.path.abspath(env_path)
    else:
        # Priority 3: Try to probe MCP session roots (Modern/Smart)
        if ctx:
            try:
                roots = await ctx.list_roots()
                if roots:
                    # Use the first root provided by IDE, stripping file://
                    root_uri = str(roots[0].uri)
                    root_path = root_uri.replace("file://", "")
                    if os.path.exists(root_path):
                        final_path = root_path
            except Exception as e:
                logger.debug(f"Could not list roots from context: {e}")

        # Final Fallback: Resolve '.' relative to CWD and search upward for .git
        if not final_path:
            final_path = os.path.abspath(repo_path or os.getcwd())
            current = final_path
            while current != os.path.dirname(current):
                if os.path.isdir(os.path.join(current, ".git")):
                    final_path = current
                    break
                current = os.path.dirname(current)

    token = REPO_CWD.set(final_path)
    logger.debug(
        f"[DEBUG] _with_cwd: set REPO_CWD to {final_path} (ID: {id(REPO_CWD)})"
    )
    try:
        # Orchestrators are sync, we run them directly
        res = func(*args, **kwargs)
        logger.debug(
            f"[DEBUG] _with_cwd: func returned (status: {getattr(res, 'status', 'N/A')})"
        )
        return res
    finally:
        REPO_CWD.reset(token)


@mcp.tool()
async def git_commit_flow(
    ctx: Context,
    point: Literal["sense", "commit"] = "sense",
    plan_json_str: str = "",
    repo_path: str = ".",
) -> str:
    """Industrial-grade git commit flow orchestrator."""
    res = await _with_cwd(
        git_commit.git_commit_flow,
        repo_path=repo_path,
        ctx=ctx,
        point=point,
        plan_json_str=plan_json_str,
    )
    return cast(str, res.to_json())


@mcp.tool()
async def git_sync_flow(
    ctx: Context,
    point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init",
    repo_path: str = ".",
) -> str:
    """Industrial-grade git sync flow orchestrator (pull | rebase | push)."""
    res = await _with_cwd(
        git_sync_orch.git_sync_flow, repo_path=repo_path, ctx=ctx, point=point
    )
    return cast(str, res.to_json())


@mcp.tool()
async def git_release_flow(
    ctx: Context,
    point: Literal["init", "sense", "release"] = "init",
    tag_json_str: str = "",
    repo_path: str = ".",
) -> str:
    """Industrial-grade git release flow orchestrator (version bump | tag | push)."""
    res = await _with_cwd(
        git_release.git_release_flow,
        repo_path=repo_path,
        ctx=ctx,
        point=point,
        tag_json_str=tag_json_str,
    )
    return cast(str, res.to_json())


@mcp.tool()
async def gh_pr_create_flow(
    ctx: Context,
    point: Literal["init", "sense", "create"] = "init",
    draft_json_str: str = "",
    repo_path: str = ".",
) -> str:
    """Industrial-grade GitHub PR creation flow orchestrator."""
    res = await _with_cwd(
        gh_pr_create.gh_pr_create_flow,
        repo_path=repo_path,
        ctx=ctx,
        point=point,
        draft_json_str=draft_json_str,
    )
    return cast(str, res.to_json())


@mcp.tool()
async def gh_pr_merge_flow(
    ctx: Context,
    point: Literal["init", "sense", "merge"] = "init",
    override_json_str: str = "",
    repo_path: str = ".",
) -> str:
    """Industrial-grade GitHub PR merging flow orchestrator."""
    res = await _with_cwd(
        gh_pr_merge.gh_pr_merge_flow,
        repo_path=repo_path,
        ctx=ctx,
        point=point,
        override_json_str=override_json_str,
    )
    return cast(str, res.to_json())


def main():
    """Main entry point for the MCP server."""
    # Ensure dependencies from src are discoverable if this script is run directly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    parser = argparse.ArgumentParser(
        description="Industrial-grade Agent Git Workflow Tools"
    )
    parser.add_argument(
        "--repository",
        "-r",
        help="Path to the git repository (overrides AGENT_TOOLS_REPO_PATH)",
    )
    # Use parse_known_args to avoid conflicts with FastMCP's own arguments if any
    args, _ = parser.parse_known_args()

    if args.repository:
        # Resolve to absolute path immediately
        os.environ["AGENT_TOOLS_REPO_PATH"] = os.path.abspath(args.repository)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
