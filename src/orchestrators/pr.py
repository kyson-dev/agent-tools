from dataclasses import asdict

from protocol import Result
from git import (
    get_branch_context,
    get_repo_context,
    get_commits_ahead,
    GitCommandError,
)

WORKFLOW = "pr_create"


def sense() -> Result:
    """Extract all local context needed for PR creation.

    Guards (fail-fast, in order):
      1. Detached HEAD
      2. Owner/repo not parseable from remote URL
      3. No commits ahead of the default branch

    On success, returns `status='handoff'` with all context needed for L3 to
    synthesize a PR description and invoke mcp_github_create_pull_request.
    """
    try:
        branch_info = get_branch_context(refresh=True)

        # Guard 1: Detached HEAD
        if branch_info.is_detached:
            return Result(
                status="error",
                message="HEAD is detached. Please checkout a branch before creating a PR.",
                workflow=WORKFLOW,
            )

        repo_info = get_repo_context(refresh=True)

        # Guard 2: Remote not configured / owner+repo not parseable
        if not repo_info.owner or not repo_info.repo:
            return Result(
                status="error",
                message="Cannot determine repository owner/name from remote URL. "
                        "Ensure a remote named 'origin' is configured.",
                workflow=WORKFLOW,
                details={"remote_url": repo_info.remote_url},
            )

        base = repo_info.default_branch

        # Guard 3: Base branch unknown
        if not base:
            return Result(
                status="error",
                message=(
                    "Unable to determine the base branch. "
                    "Run `git_smart_sync` to push your branch and set up tracking, "
                    "then retry."
                ),
                workflow=WORKFLOW,
                details={"head": branch_info.current_branch},
            )

        # Guard 4: No commits ahead of base
        commits = get_commits_ahead(base)
        if not commits:
            return Result(
                status="error",
                message=f"No commits found ahead of '{base}'. "
                        "Push your changes before creating a PR.",
                workflow=WORKFLOW,
                details={"base": base, "head": branch_info.current_branch},
            )

        return Result(
            status="handoff",
            message="PR context extracted. Synthesize a description and call mcp_github_create_pull_request.",
            workflow=WORKFLOW,
            next_step="create_mcp_pr",
            resume_point="",  # No resume point for orchestrator; hand off to external tool
            instruction="1. Read `commits` in `details` and synthesize a concise PR title and body. "
                    "2. Call the external `mcp_github_create_pull_request` tool using the "
                    "`owner`, `repo`, `head`, and `base` fields from `details`.",
            details={
                "owner": repo_info.owner,
                "repo": repo_info.repo,
                "head": branch_info.current_branch,
                "base": base,
                "commits": [asdict(c) for c in commits],
            },
        )

    except GitCommandError as e:
        return Result(
            status="error",
            message=str(e),
            workflow=WORKFLOW,
            details={"command": e.command, "stderr": e.stderr},
        )
    except Exception as e:
        return Result(status="error", message=f"PR sense error: {str(e)}", workflow=WORKFLOW)


def run_pr_workflow(mode: str) -> Result:
    if mode == "sense":
        return sense()
    return Result(
        status="error",
        message=f"Invalid mode: '{mode}'. Expected 'sense'.",
        workflow=WORKFLOW,
    )
