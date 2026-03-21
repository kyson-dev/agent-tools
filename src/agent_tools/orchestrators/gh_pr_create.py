from dataclasses import asdict

from agent_tools.protocol import Result
from agent_tools.git import (
    get_branch_context,
    get_repo_context,
    get_commits_ahead,
    GitCommandError,
)
from agent_tools.gh import run_gh
from agent_tools.config import get_full_commit_rules

WORKFLOW = "gh_pr_create"


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

        # Provide rules for message synthesis
        rules = get_full_commit_rules()

        return Result(
            status="handoff",
            message="Context extracted. Please synthesize PR title and body.",
            workflow=WORKFLOW,
            next_step="synthesize_description",
            resume_point="create",
            instruction=(
                "1. Analyze `commits` in `details`. "
                "2. VALIDATION REQUIRED: Synthesize a PR `title` following **Conventional Commits** and `details.commit_rules`. "
                "3. Call `gh_pr_create_execute(repo_path=\".\", draft_json='{\"title\": \"...\", \"body\": \"...\"}')`."
            ),
            details={
                "owner": repo_info.owner,
                "repo": repo_info.repo,
                "head": branch_info.current_branch,
                "base": base,
                "commits": [asdict(c) for c in commits],
                "commit_rules": rules
            },
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)
    except Exception as e:
        return Result(status="error", message=f"PR sense error: {str(e)}", workflow=WORKFLOW)


def create(title: str, body: str) -> Result:
    """Stage 2: Receive synthesis and execute PR creation via gh CLI."""
    if not title or not body:
        return Result(status="error", message="Title and body are required for PR creation.", workflow=WORKFLOW)

    repo_info = get_repo_context()
    branch_info = get_branch_context()
    base = repo_info.default_branch

    try:
        # Construct the gh pr create command
        args = [
            "pr", "create",
            "--title", title,
            "--body", body,
            "--base", base,
            "--head", branch_info.current_branch
        ]
        
        res = run_gh(args)
        
        if res.returncode != 0:
            return Result(
                status="error",
                message=f"GitHub PR creation failed: {res.stderr}",
                workflow=WORKFLOW,
                details={"stderr": res.stderr, "stdout": res.stdout}
            )

        pr_url = res.stdout.strip()
        return Result(
            status="success",
            message=f"Pull Request created successfully: {pr_url}",
            workflow=WORKFLOW,
            details={"pr_url": pr_url}
        )

    except Exception as e:
        return Result(status="error", message=f"Failed to execute gh pr create: {str(e)}", workflow=WORKFLOW)


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
