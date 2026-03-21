import os
import json
import logging
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

from agent_tools.orchestrators import (
    run_commit_workflow,
    run_sync_workflow,
    run_pr_create_workflow,
    run_pr_merge_workflow,
    run_release_workflow
)

# Set up logging to stderr for MCP compatibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-tools-mcp")

mcp = FastMCP("agent-tools")

def _with_cwd(func, repo_path: str, *args, **kwargs):
    """Context-aware wrapper to run code in a specific directory."""
    original_cwd = os.getcwd()
    try:
        if repo_path and os.path.isdir(repo_path):
            os.chdir(repo_path)
            logger.info(f"Changed working directory to: {repo_path}")
        else:
            logger.warning(f"Invalid repo_path: {repo_path}. Staying in {original_cwd}")
        
        return func(*args, **kwargs)
    finally:
        os.chdir(original_cwd)

# --- Git Commit Tools ---

@mcp.tool()
def git_commit_sense(repo_path: str) -> str:
    """
    Scans the repository for changes and returns project-specific commit rules.
    Use this as the first step of any commit workflow.
    """
    res = _with_cwd(run_commit_workflow, repo_path, mode="sense")
    return res.to_json()

@mcp.tool()
def git_commit_execute(repo_path: str, plan_json: str) -> str:
    """
    Executes a structured commit plan. 
    plan_json must be a JSON string like: {"commits": [{"files": ["path/a"], "message": "feat: ..."}]}
    """
    res = _with_cwd(run_commit_workflow, repo_path, mode="plan", plan_json_str=plan_json)
    return res.to_json()

# --- Git Sync Tools ---

@mcp.tool()
def git_sync(repo_path: str, point: str = "init") -> str:
    """
    Orchestrates a smart git sync (pull, rebase main, push).
    Points: 'init', 'current_rebase', 'rebase_main', 'push'
    """
    res = _with_cwd(run_sync_workflow, repo_path, mode="sync", point=point)
    return res.to_json()

@mcp.tool()
def git_sync_abort(repo_path: str) -> str:
    """Aborts an in-progress rebase during sync."""
    res = _with_cwd(run_sync_workflow, repo_path, mode="abort")
    return res.to_json()

# --- GitHub PR Tools ---

@mcp.tool()
def gh_pr_create_sense(repo_path: str) -> str:
    """Analyzes context for PR creation (branch, commits, diffs)."""
    res = _with_cwd(run_pr_create_workflow, repo_path, mode="sense")
    return res.to_json()

@mcp.tool()
def gh_pr_create_execute(repo_path: str, draft_json: str) -> str:
    """Creates a Pull Request based on the provided draft JSON (title, body)."""
    res = _with_cwd(run_pr_create_workflow, repo_path, mode="create", draft_json=draft_json)
    return res.to_json()

@mcp.tool()
def gh_pr_merge_sense(repo_path: str) -> str:
    """
    Stage 1: Analyzes PR, CI status, and reviews.
    Returns PR metadata and commit rules for synthesis.
    """
    res = _with_cwd(run_pr_merge_workflow, repo_path, mode="sense")
    return res.to_json()

@mcp.tool()
def gh_pr_merge_execute(repo_path: str, override_json: str) -> str:
    """
    Stage 2: Executes the PR merge with provided title and body.
    override_json: '{"title": "...", "body": "..."}'
    """
    res = _with_cwd(run_pr_merge_workflow, repo_path, mode="merge", data_json=override_json)
    return res.to_json()

# --- Git Release Tools ---

@mcp.tool()
def git_release_sense(repo_path: str) -> str:
    """
    Stage 1: Validates branch/purity and gathers release context (tags, commits).
    Use this to start a release analysis.
    """
    res = _with_cwd(run_release_workflow, repo_path, mode="sense")
    return res.to_json()

@mcp.tool()
def git_release_execute(repo_path: str, tag_json: str) -> str:
    """
    Stage 2: Creates an annotated tag and pushes to origin.
    REQUIRES a clean worktree (commit version bumps first via git_commit_flow).
    tag_json: '{"tag_name": "v1.2.3", "tag_message": "..."}'
    """
    res = _with_cwd(run_release_workflow, repo_path, mode="execute", tag_json=tag_json)
    return res.to_json()

# --- Prompts (Workflows) ---

@mcp.prompt()
def git_commit_flow() -> str:
    return """
Follow this industrial-grade commit protocol:
1. ALWAYS strictly follow the `instruction` field returned by `git_commit_sense`.
2. Use `details.rules_context` to ensure compliance with project-specific commit rules.
"""

@mcp.prompt()
def git_sync_flow() -> str:
    return """
Follow this linear rebase sync protocol:
1. ALWAYS strictly follow the dynamic `instruction` returned by the `git_sync` tool.
2. If the status is 'handoff', execute the specified recovery actions before resuming.
"""

@mcp.prompt()
def smart_pr_create_flow() -> str:
    return """
Follow this standard PR creation protocol:
1. ALWAYS strictly follow the `instruction` field returned by `gh_pr_create_sense`.
2. Use 'details.commits' to synthesize the PR content as instructed.
"""

@mcp.prompt()
def smart_pr_merge_flow() -> str:
    return """
Follow this professional PR merge protocol:
1. ALWAYS strictly follow the `instruction` returned by `gh_pr_merge_sense`.
2. Use 'details.commit_rules' to ensure the final squash message is perfectly compliant.
"""

@mcp.prompt()
def smart_release_flow() -> str:
    return """
Follow this industrial-grade automated release protocol:
1. ALWAYS strictly follow the dynamic `instruction` field returned by `git_release_sense`.
2. Use 'details' to navigate between version discovery, delegated commits, and final tagging.
"""

def main():
    # Ensure dependencies from src are discoverable if this script is run directly
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
