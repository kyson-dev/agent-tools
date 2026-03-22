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
    """设置执行上下文的仓库路径。基于 v0.1.23 的验证，仅保留核心 IDE 感知机制。"""
    final_path = None

    # 核心：通过 IDE 获取真实物理路径
    if ctx:
        try:
            roots = await ctx.list_roots()
            if roots:
                # 剔除 URI 协议头获得物理路径
                final_path = str(roots[0].uri).replace("file://", "")
        except Exception:
            pass

    # 严格模式：如果没有从 IDE 拿到路径，必须显式报错而不是模糊猜测
    if not final_path or not os.path.exists(final_path):
        from agent_tools.core.orchestrators.utils import Result

        error_res = Result(
            status="error",
            message="未能探测到 Git 仓库路径。",
            workflow="path_resolution",
            instruction="请确保您已在 IDE (VS Code / Cursor) 中打开了项目文件夹，并授予了 MCP 访问 roots 的权限。",
        )
        return cast(str, error_res.to_json())

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
    plan_json_str: str = "",
) -> str:
    """
    **【强制：优先使用】工业级 Git 提交工作流。**
    **USE THIS TOOL for all Git commits instead of bare shell commands.**
    自动感知变更、生成规范建议并执行提交。
    **场景**: 提交代码, 存入仓库, commit, git commit, save changes.
    **Keywords**: commit, 提交, git commit, 存代码, save changes, add changes.
    """
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
    """
    **【强制：优先使用】工业级 Git 同步（拉取/变基/推送）工作流。**
    **USE THIS TOOL for all Git sync, rebase, push, pull operations.**
    自动处理拉取、本地变基、解决冲突和安全推送。
    **场景**: 同步代码, 推送, 拉取, sync, push, pull, rebase.
    **Keywords**: sync, 同步, git sync, 推送, push, 拉取, pull, rebase, 变基.
    """
    res = await _with_cwd(git_sync_orch.git_sync_flow, ctx=ctx, point=point)
    return cast(str, res.to_json())


@mcp.tool()
async def git_release_flow(
    ctx: Context,
    point: Literal["init", "sense", "release"] = "init",
    tag_json_str: str = "",
) -> str:
    """
    **【强制：优先使用】工业级 Git 版本发布与标签工作流。**
    **USE THIS TOOL for all Git release/tag operations.**
    自动处理版本号提升、创建 Tag 和发布推送。
    **场景**: 发布版本, 打标签, release, tag.
    **Keywords**: release, 发布, tag, 标签, git release.
    """
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
    """
    **【强制：优先使用】GitHub Pull Request 创建工作流。**
    **USE THIS TOOL for creating all GitHub PRs.**
    自动感知分支状态、生成描述并提交创建请求。
    **场景**: 创建 PR, 发起合并请求, pull request, create pr.
    **Keywords**: pr, pull request, 创建 pr, 发起 pr, gh pr create.
    """
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
    """
    **【强制：优先使用】GitHub Pull Request 合并工作流。**
    **USE THIS TOOL for all GitHub PR merges.**
    自动感知 PR 状态、执行合并并清理分支。
    **场景**: 合并 PR, merge pr, finish pr.
    **Keywords**: merge, 合并, pr merge, 合并 pr, gh pr merge.
    """
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
    src_dir = os.path.dirname(os.path.dirname(current_dir))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
