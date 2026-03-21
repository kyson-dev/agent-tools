import os
import json
import logging
from typing import Any, Dict, Optional, Literal
from mcp.server.fastmcp import FastMCP

from agent_tools.context import REPO_CWD
from agent_tools.orchestrators import (
    git_commit,
    git_sync as git_sync_orch,
    gh_pr_create,
    gh_pr_merge,
    git_release
)

# Set up logging to stderr for MCP compatibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-tools-mcp")

mcp = FastMCP("agent-tools")

def _with_cwd(func, repo_path: str, point: str, *args, **kwargs):
    """Context-aware wrapper to setup working directory safely using ContextVars."""
    if repo_path and os.path.isdir(repo_path):
        token = REPO_CWD.set(repo_path)
    else:
        logger.warning(f"Invalid repo_path: {repo_path}. Using current directory.")
        token = REPO_CWD.set(os.getcwd())
        
    try:
        return func(*args, **kwargs)
    finally:
        REPO_CWD.reset(token)

# --- Git Commit Tools ---

@mcp.tool()
def git_commit_flow(point: Literal["sense", "commit"] = "sense", plan_json_str: str = "") -> str:
    """
    Scans the repository for changes and returns project-specific commit rules.
    Use this as the first step of any commit workflow.
    """
    res = _with_cwd(git_commit.git_commit_flow, repo_path=".", point=point, plan_json_str=plan_json_str)
    return res.to_json()

# --- Git Sync Tools ---

@mcp.tool()
def git_sync_flow(point: Literal["init", "current_rebase", "rebase_main", "push", "abort"] = "init") -> str:
    """
    Orchestrates a smart git sync (pull, rebase main, push).
    Points: 'init', 'current_rebase', 'rebase_main', 'push'
    """
    res = _with_cwd(git_sync_orch.git_sync_flow, repo_path=".", point=point)
    return res.to_json()

# --- GitHub PR Tools ---

@mcp.tool()
def gh_pr_create_flow(point: Literal["init", "sense", "create"] = "init", draft_json_str: str = "") -> str:
    """Analyzes context for PR creation (branch, commits, diffs)."""
    res = _with_cwd(gh_pr_create.gh_pr_create_flow, repo_path=".", point=point, draft_json_str=draft_json_str)
    return res.to_json()

@mcp.tool()
def gh_pr_merge_flow(point: Literal["init", "sense", "merge"] = "init", override_json_str: str = "") -> str:
    """
    Stage 1: Analyzes PR, CI status, and reviews.
    Returns PR metadata and commit rules for synthesis.
    """
    res = _with_cwd(gh_pr_merge.gh_pr_merge_flow, repo_path=".", point=point, override_json_str=override_json_str)
    return res.to_json()

# --- Git Release Tools ---

@mcp.tool()
def git_release_flow(point: Literal["init", "sense", "release"] = "init", tag_json_str: str = "") -> str:
    """Stage 1: Analyzes commits/tags to determine next version. Use point='init' to start."""
    res = _with_cwd(git_release.git_release_flow, repo_path=".", point=point, tag_json_str=tag_json_str)
    return res.to_json()


# --- Prompts (Workflows) ---

@mcp.prompt()
def smart_commit_flow() -> str:
    return """
Follow this industrial-grade commit protocol:
1. Call `git_commit_flow(point="sense")`.
2. Use `details.commit_rules` to ensure compliance with project-specific commit rules.
"""

@mcp.prompt()
def smart_sync_flow() -> str:
    return """
Follow this linear rebase sync protocol:
1. Call `git_sync_flow(point="init")` tool.
2. If the status is 'handoff', execute the specified recovery actions before resuming.
"""

@mcp.prompt()
def smart_pr_create_flow() -> str:
    return """
Follow this standard PR creation protocol:
1. Call `gh_pr_create_flow(point="init")`.
2. Follow: ALWAYS strictly follow the dynamic `instruction` field returned by the tool.
"""

@mcp.prompt()
def smart_pr_merge_flow() -> str:
    return """
Follow this professional PR merge protocol:
1. Call `gh_pr_merge_flow(point="init")`.
2. Follow: ALWAYS strictly follow the dynamic `instruction` field returned by the tool.
"""

@mcp.prompt()
def smart_release_flow() -> str:
    return """
Follow this industrial-grade automated release protocol:
1. Call `git_release_flow(point="init")`.
2. Follow: ALWAYS strictly follow the dynamic `instruction` field returned by the tool.
"""

def main():
    # Ensure dependencies from src are discoverable if this script is run directly
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
