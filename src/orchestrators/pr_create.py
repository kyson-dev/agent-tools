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
    """Stage 1: Extract context and hand off for description synthesis."""
    try:
        branch_info = get_branch_context(refresh=True)

        if branch_info.is_detached:
            return Result(
                status="error",
                message="HEAD is detached. Please checkout a branch before creating a PR.",
                workflow=WORKFLOW,
            )

        repo_info = get_repo_context(refresh=True)

        if not repo_info.owner or not repo_info.repo:
            return Result(
                status="error",
                message="Cannot determine repository owner/name from remote URL.",
                workflow=WORKFLOW,
            )

        base = repo_info.default_branch
        if not base:
            return Result(
                status="error",
                message="Unable to determine the base branch. Push your branch first.",
                workflow=WORKFLOW,
            )

        commits = get_commits_ahead(base)
        if not commits:
            return Result(
                status="error",
                message=f"No commits found ahead of '{base}'.",
                workflow=WORKFLOW,
            )

        return Result(
            status="handoff",
            message="Context extracted. Please synthesize PR title and body.",
            workflow=WORKFLOW,
            next_step="synthesize_description",
            resume_point="create",
            instruction="1. Analyze the `commits` in `details`. 2. Synthesize a concise PR 'title' and 'body'. 3. Call `agt gh pr --create '{\"title\": \"...\", \"body\": \"...\"}'`.",
            details={
                "owner": repo_info.owner,
                "repo": repo_info.repo,
                "head": branch_info.current_branch,
                "base": base,
                "commits": [asdict(c) for c in commits],
            },
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)
    except Exception as e:
        return Result(status="error", message=f"PR sense error: {str(e)}", workflow=WORKFLOW)


def create(title: str, body: str) -> Result:
    """Stage 3: Receive synthesis and provide rigid MCP command."""
    if not title or not body:
        return Result(status="error", message="Title and body are required for PR creation.", workflow=WORKFLOW)

    # Re-verify context before issuing the command
    repo_info = get_repo_context()
    branch_info = get_branch_context()

    return Result(
        status="handoff",
        message="Description received. Ready to create PR.",
        workflow=WORKFLOW,
        next_step="execute_mcp_call",
        resume_point="", # Final handoff to MCP
        instruction=(
            "Call `mcp_github_create_pull_request` with the following parameters exactly:\n"
            f"- owner: {repo_info.owner}\n"
            f"- repo: {repo_info.repo}\n"
            f"- title: {title}\n"
            f"- body: {body}\n"
            f"- head: {branch_info.current_branch}\n"
            f"- base: {repo_info.default_branch}"
        ),
        details={
            "owner": repo_info.owner,
            "repo": repo_info.repo,
            "title": title,
            "body": body,
            "head": branch_info.current_branch,
            "base": repo_info.default_branch,
        }
    )


def run_pr_create_workflow(mode: str, draft_json: str = None) -> Result:
    if mode == "sense":
        return sense()
    elif mode == "create":
        if not draft_json:
            return Result(status="error", message="mode='create' requires draft_json.", workflow=WORKFLOW)
        import json
        try:
            data = json.loads(draft_json)
            return create(title=data.get("title"), body=data.get("body"))
        except json.JSONDecodeError:
            return Result(status="error", message="Invalid draft_json format.", workflow=WORKFLOW)
    return Result(status="error", message=f"Invalid mode: '{mode}'.", workflow=WORKFLOW)
