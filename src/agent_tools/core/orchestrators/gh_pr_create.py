import json
import logging
from dataclasses import asdict
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    get_branch_context,
    get_commits_ahead,
    get_repo_context,
    run_git,
)

from agent_tools.infrastructure.config.manager import (
    get_full_commit_rules,
)
from agent_tools.infrastructure.clients.github.client import run_gh

logger = logging.getLogger(__name__)
WORKFLOW = "gh_pr_create"


def _check_safety_guards() -> Result | None:
    """Pre-conditions for PR creation."""
    # 1. 必须有github上下文
    repo_info = get_repo_context(refresh=True)
    if not repo_info.owner or not repo_info.repo:
        return Result(status="error", message="GitHub context unknown.", workflow=WORKFLOW)

    # 2. 没有remote origin
    if not repo_info.primary_remote:
        return Result(status="error", message="No remote origin.", workflow=WORKFLOW)

    # 3. 不能是游离状态
    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    # 4. 当前分支必须存在
    if not branch_info.current_branch:
        return Result(status="error", message="Unknown current branch.", workflow=WORKFLOW)

    # 5. 默认分支必须存在
    if not repo_info.default_branch:
        return Result(status="error", message="Default branch is required.", workflow=WORKFLOW)

    # 6. 当前分支不能是默认分支
    if branch_info.current_branch == repo_info.default_branch:
        return Result(status="error", message="Current branch is default branch.", workflow=WORKFLOW)

    return None


def _current_branch_behind_remote_default_branch() -> bool:
    """确认当前分支是否落后于远程默认分支 (比如 origin/main)。"""
    repo_info = get_repo_context()

    remote_ref = f"{repo_info.primary_remote}/{repo_info.default_branch}"
    res = run_git(["merge-base", "--is-ancestor", remote_ref, "HEAD"])
    return not res.ok


def _handle_init() -> Result:
    """Stage 0: Init and Sync."""

    guard = _check_safety_guards()
    if guard:
        return guard

    branch_info = get_branch_context(refresh=True)

    # 严苛校验: 工作区不干净、有本地超前提交、或落后于远程默认分支
    if branch_info.is_dirty or branch_info.ahead > 0 or _current_branch_behind_remote_default_branch():
        return Result(
            status="handoff",
            message="PR creation initiated.",
            workflow=WORKFLOW,
            next_step="SYNC_BEFORE_PR",
            resume_point="sense",
            instruction=(
                "【ACTION】\n"
                "1. Run 'git_sync_flow' to ensure your branch is updated and pushed.\n"
                "2. After sync, call 'gh_pr_create_flow' with point='sense'."
            ),
        )
    return _handle_sense()


def _handle_sense() -> Result:
    """Stage 1: Context gathering and planning."""

    repo_info = get_repo_context(refresh=True)
    branch_info = get_branch_context(refresh=True)
    base = repo_info.default_branch
    if not base:
        return Result(status="error", message="Default branch unknown.", workflow=WORKFLOW)

    commits = get_commits_ahead(base)

    if not commits:
        return Result(
            status="error",
            message=f"No commits ahead of '{base}'.",
            workflow=WORKFLOW,
        )

    return Result(
        status="handoff",
        message="Context ready for PR synthesis.",
        workflow=WORKFLOW,
        next_step="SYNTHESIZE_PR_DESCRIPTION",
        resume_point="create",
        instruction=(
            "【STRICT PROTOCOL / 严格协议】您当前处于受控工作流中。禁止跳过步骤、禁止执行任何未授权的裸命令。\n"
            "【ACTION】\n"
            "1. Review 'commits' in details.\n"
            "2. Synthesize a professional PR title (Conventional Commit style) and a structured markdown body.\n"
            "3. Mention any relevant issue numbers if known.\n"
            "4. Call 'gh_pr_create_flow' with point='create' and your 'draft_json_str', formatted according to 'details.json_format'."
        ),
        constraints=[
            "Each commit message MUST follow Conventional Commits and `commit_rules`.",
        ],
        details={
            "owner": repo_info.owner,
            "repo": repo_info.repo,
            "head": branch_info.current_branch,
            "base": base,
            "commits": [asdict(c) for c in commits],
            "json_format": {
                "title": "feat(core): add JSON schema to results",
                "body": "## Summary\n- Added json_format to handoff details.\n\n## Test Plan\n- Verified via pytest.",
            },
            "commit_rules": get_full_commit_rules(),
        },
    )


def _handle_create(draft_json_str: str) -> Result:
    """Stage 2: Execution via GitHub CLI."""
    try:
        draft_data = json.loads(draft_json_str)
        title = draft_data.get("title")
        body = draft_data.get("body")
    except json.JSONDecodeError:
        return Result(status="error", message="Invalid JSON in draft_json_str.", workflow=WORKFLOW)

    if not title or not body:
        return Result(
            status="error",
            message="Both 'title' and 'body' are required.",
            workflow=WORKFLOW,
        )

    repo_info = get_repo_context()
    branch_info = get_branch_context()

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

    # Handle specific GH CLI errors
    if "already exists" in res.stderr.lower():
        return Result(
            status="handoff",
            message="A Pull Request for this branch already exists.",
            workflow=WORKFLOW,
            next_step="VIEW_EXISTING_PR",
            instruction="Run 'gh pr view --web' or 'gh pr list' to find the existing PR.",
        )

    return Result(
        status="error",
        message=f"GitHub CLI error: {res.stderr}",
        workflow=WORKFLOW,
        instruction="Verify your GitHub credentials and push permissions.",
    )


def gh_pr_create_flow(point: Literal["init", "sense", "create"] = "init", draft_json_str: str = "") -> Result:
    """Industrial-grade GitHub PR creation flow orchestrator."""
    handlers = {
        "init": _handle_init,
        "sense": _handle_sense,
        "create": lambda: _handle_create(draft_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(status="error", message=f"Invalid point: {point}", workflow=WORKFLOW)
        return handler()
    except Exception as e:
        logger.exception("PR creation workflow crash")
        return Result(status="error", message=f"PR create failed: {str(e)}", workflow=WORKFLOW)
