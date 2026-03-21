import os
import json
import logging
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

from orchestrators import (
    run_commit_workflow,
    run_sync_workflow,
    run_pr_create_workflow,
    run_pr_merge_workflow
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

# --- Prompts (Workflows) ---

@mcp.prompt()
def git_commit_flow() -> str:
    return """
Follow this industrial-grade commit workflow:
1. Scan changes: Call `git_commit_sense(repo_path=".")`.
2. Analyze the 'details' field: Identify logical groups of changes and check 'rules_context' (regex, limits).
3. Draft a Plan: Create a JSON object matching the required schema.
4. Execute: Call `git_commit_execute(repo_path=".", plan_json="...")` with your drafted plan.
"""

@mcp.prompt()
def git_sync_flow() -> str:
    return """
Follow this smart sync workflow:
1. Start sync: Call `git_sync(repo_path=".", point="init")`.
2. Handle handoffs: If status is 'handoff', follow the instruction and re-invoke with the specified 'resume_point'.
3. Verify: Ensure rebase completes and changes are pushed.
"""

@mcp.prompt()
def smart_pr_create_flow() -> str:
    return """
Follow this GitHub PR creation workflow:
1. Extract Context: Call `gh_pr_create_sense(repo_path=".")`.
2. Synthesize: Based on 'details.commits', draft a PR title (Conventional Commit) and body (Summary, Changes, Impact).
3. Execute: Call `gh_pr_create_execute(repo_path=".", draft_json='{"title": "...", "body": "..."}')`.
"""

@mcp.prompt()
def smart_pr_merge_flow() -> str:
    return """
Follow this industrial-grade PR merge workflow:
1. Sync: First, ensure the branch is updated by running the `git_sync_flow`.
2. Sense: Call `gh_pr_merge_sense(repo_path=".")`.
3. Synthesize & Merge: Based on 'details.pr' and 'details.commit_rules', generate a final squash commit `title` and `body` (following Conventional Commits), then immediately call `gh_pr_merge_execute(repo_path=".", override_json='{"title": "...", "body": "..."}')` without asking for user confirmation of the message.
4. Finalize: Report the PR URL and cleanup results.
"""

def main():
    # Ensure dependencies from src are discoverable if this script is run directly
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
