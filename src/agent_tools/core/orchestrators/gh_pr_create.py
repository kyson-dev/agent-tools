import json
import logging
from dataclasses import asdict
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    get_branch_context,
    get_commits_ahead,
    get_repo_context,
)
from agent_tools.infrastructure.clients.github.client import run_gh
from agent_tools.infrastructure.config.manager import get_full_commit_rules

logger = logging.getLogger(__name__)
WORKFLOW = "gh_pr_create"


def _check_safety_guards() -> Result | None:
    """Pre-conditions for PR creation."""
    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    repo_info = get_repo_context(refresh=True)
    if not repo_info.owner or not repo_info.repo:
        return Result(
            status="error",
            message="Cannot determine GitHub repository context.",
            workflow=WORKFLOW,
        )

    if not repo_info.default_branch:
        return Result(
            status="error",
            message="Default branch unknown. Push your branch first.",
            workflow=WORKFLOW,
        )

    commits = get_commits_ahead(repo_info.default_branch)
    if not commits:
        return Result(
            status="error",
            message=f"No commits ahead of '{repo_info.default_branch}'.",
            workflow=WORKFLOW,
        )

    return None


def _handle_init() -> Result:
    """Stage 0: Init and Sync."""
    return Result(
        status="handoff",
        message="PR creation initiated.",
        workflow=WORKFLOW,
        next_step="SYNC_BEFORE_PR",
        resume_point="sense",
        instruction=(
            "1. Run 'git_sync_flow' to ensure your branch is updated and pushed.\n"
            "2. After sync, call 'gh_pr_create_flow' with point='sense'."
        ),
    )


def _handle_sense() -> Result:
    """Stage 1: Context extraction and PR synthesis."""
    guard = _check_safety_guards()
    if guard:
        return guard

    repo_info = get_repo_context()
    branch_info = get_branch_context()
    base = repo_info.default_branch
    if not base:
        return Result(
            status="error", message="Default branch is required.", workflow=WORKFLOW
        )

    commits = get_commits_ahead(base)

    return Result(
        status="handoff",
        message="Context ready for PR synthesis.",
        workflow=WORKFLOW,
        next_step="SYNTHESIZE_PR_DESCRIPTION",
        resume_point="create",
        instruction=(
            "1. Review 'commits' in details.\n"
            "2. Synthesize a professional PR title and body (markdown).\n"
            "3. Call 'gh_pr_create_flow' with point='create' and your draft_json_str."
        ),
        constraints=[
            "Title MUST follow Conventional Commit style if applicable.",
            "Body MUST summarize technical changes clearly.",
        ],
        details={
            "owner": repo_info.owner,
            "repo": repo_info.repo,
            "head": branch_info.current_branch,
            "base": base,
            "commits": [asdict(c) for c in commits],
            "commit_rules": get_full_commit_rules(),
        },
    )


def _handle_create(draft_json_str: str) -> Result:
    """Stage 2: Execution via GitHub CLI."""
    try:
        data = json.loads(draft_json_str)
        title = data.get("title")
        body = data.get("body")
    except json.JSONDecodeError:
        return Result(
            status="error", message="Invalid JSON in draft_json_str.", workflow=WORKFLOW
        )

    if not title or not body:
        return Result(
            status="error",
            message="Both 'title' and 'body' are required.",
            workflow=WORKFLOW,
        )

    repo_info = get_repo_context()
    branch_info = get_branch_context()

    if not repo_info.default_branch or not branch_info.current_branch:
        return Result(
            status="error", message="Missing branch information.", workflow=WORKFLOW
        )

    args = [
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        repo_info.default_branch,
        "--head",
        branch_info.current_branch,
    ]

    res = run_gh(args)
    if res.returncode == 0:
        pr_url = res.stdout.strip()
        return Result(
            status="success",
            message=f"PR created successfully: {pr_url}",
            workflow=WORKFLOW,
            details={"pr_url": pr_url},
        )

    return Result(
        status="error",
        message=f"GitHub CLI error: {res.stderr}",
        workflow=WORKFLOW,
        instruction="Check if PR already exists or if you have permission to push.",
    )


def gh_pr_create_flow(
    point: Literal["init", "sense", "create"] = "init", draft_json_str: str = ""
) -> Result:
    """Industrial-grade GitHub PR creation flow orchestrator."""
    handlers = {
        "init": _handle_init,
        "sense": _handle_sense,
        "create": lambda: _handle_create(draft_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(
                status="error", message=f"Invalid point: {point}", workflow=WORKFLOW
            )
        return handler()
    except Exception as e:
        logger.exception("PR creation workflow crash")
        return Result(
            status="error", message=f"PR create failed: {str(e)}", workflow=WORKFLOW
        )
