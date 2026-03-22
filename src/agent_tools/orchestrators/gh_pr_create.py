from dataclasses import asdict
from typing import Literal

from ..config import get_full_commit_rules
from ..gh import run_gh
from ..git import (
    GitCommandError,
    get_branch_context,
    get_commits_ahead,
    get_repo_context,
)
from ..protocol import Result

WORKFLOW = "gh_pr_create"


def _init_sync() -> Result:
    return Result(
        status="handoff",
        message="PR creation initiated. Ensuring branch is synchronized.",
        workflow=WORKFLOW,
        next_step="sync_branch",
        resume_point="create",
        instruction='\
                    1. **SYNC**: Run `git_sync_flow` to ensure your branch is pushed and aligned. \
                    2. **RESUME**: Call `gh_pr_create_flow(point="sense")` after sync completes.',
    )


def _check_safety_guards() -> Result | None:
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

    return None


def _sense() -> Result:

    res = _check_safety_guards()
    if res:
        return res

    repo_info = get_repo_context()
    branch_info = get_branch_context()
    base = repo_info.default_branch or "main"
    # Provide rules for message synthesis
    rules = get_full_commit_rules()
    commits = get_commits_ahead(base)

    return Result(
        status="handoff",
        message="Context extracted. Please synthesize PR title and body.",
        workflow=WORKFLOW,
        next_step="synthesize_description",
        resume_point="create",
        instruction=(
            "1. All message MUST following **Conventional Commits** and `details.commit_rules`. "
            "2. Analyze `commits` in `details`. "
            '3. Call `gh_pr_create_flow(point="create", draft_json_str=\'{"title": "...", "body": "..."}\')`.'
        ),
        details={
            "owner": repo_info.owner,
            "repo": repo_info.repo,
            "head": branch_info.current_branch,
            "base": base,
            "commits": [asdict(c) for c in commits],
            "commit_rules": rules,
        },
    )


def _create(draft_json_str: str) -> Result:
    """Stage 2: Receive synthesis and execute PR creation via gh CLI."""
    import json

    try:
        data = json.loads(draft_json_str)
        title = data.get("title")
        body = data.get("body")
    except json.JSONDecodeError:
        return Result(
            status="error", message="Invalid draft_json_str format.", workflow=WORKFLOW
        )

    if not title or not body:
        return Result(
            status="error",
            message="Title and body are required for PR creation.",
            workflow=WORKFLOW,
        )

    repo_info = get_repo_context()
    branch_info = get_branch_context()
    base = repo_info.default_branch

    try:
        # Construct the gh pr create command
        args = [
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--base",
            base,
            "--head",
            branch_info.current_branch,
        ]

        res = run_gh(args)

        if res.returncode != 0:
            return Result(
                status="error",
                message=f"GitHub PR creation failed: {res.stderr}",
                workflow=WORKFLOW,
                details={"stderr": res.stderr, "stdout": res.stdout},
            )

        pr_url = res.stdout.strip()
        return Result(
            status="success",
            message=f"Pull Request created successfully: {pr_url}",
            workflow=WORKFLOW,
            details={"pr_url": pr_url},
        )

    except Exception as e:
        return Result(
            status="error",
            message=f"Failed to execute gh pr create: {str(e)}",
            workflow=WORKFLOW,
        )


def gh_pr_create_flow(
    point: Literal["init", "sense", "create"] = "init", draft_json_str: str = ""
) -> Result:
    try:
        if point == "init":
            return _init_sync()
        elif point == "sense":
            return _sense()
        elif point == "create":
            return _create(draft_json_str)

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)
    except Exception as e:
        return Result(
            status="error", message=f"PR create error: {str(e)}", workflow=WORKFLOW
        )
