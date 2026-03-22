import argparse
import logging
import os
import sys
from collections.abc import Callable
from typing import Literal, cast

from fastmcp import Context, FastMCP

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


async def _with_cwd(func: Callable, ctx: Context | None, *args, **kwargs):
    """设置执行上下文的仓库路径。仅依赖环境变量 AGENT_TOOLS_REPO_PATH，不再进行主动探测。"""
    final_path = os.environ.get("AGENT_TOOLS_REPO_PATH") or os.getcwd()
    token = REPO_CWD.set(os.path.abspath(final_path))
    logger.debug(f"[DEBUG] _with_cwd: set REPO_CWD to {final_path}")
    try:
        return func(*args, **kwargs)
    finally:
        REPO_CWD.reset(token)


@mcp.tool()
async def git_commit_flow(
    ctx: Context,
    point: Literal["sense", "commit"] = "sense",
    plan_json_str: str = "",
) -> str:
    """Industrial-grade git commit flow orchestrator."""
    res = await _with_cwd(
        git_commit.git_commit_flow,
        ctx=ctx,
        point=point,
        plan_json_str=plan_json_str,
    )
    return cast(str, res.to_json())


@mcp.tool()
async def git_sync_flow(
    ctx: Context,
    point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init",
) -> str:
    """Industrial-grade git sync flow orchestrator (pull | rebase | push)."""
    res = await _with_cwd(git_sync_orch.git_sync_flow, ctx=ctx, point=point)
    return cast(str, res.to_json())


@mcp.tool()
async def git_release_flow(
    ctx: Context,
    point: Literal["init", "sense", "release"] = "init",
    tag_json_str: str = "",
) -> str:
    """Industrial-grade git release flow orchestrator (version bump | tag | push)."""
    res = await _with_cwd(
        git_release.git_release_flow,
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
) -> str:
    """Industrial-grade GitHub PR creation flow orchestrator."""
    res = await _with_cwd(
        gh_pr_create.gh_pr_create_flow,
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
) -> str:
    """Industrial-grade GitHub PR merging flow orchestrator."""
    res = await _with_cwd(
        gh_pr_merge.gh_pr_merge_flow,
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
