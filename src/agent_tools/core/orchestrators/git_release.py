import json
import logging
import re
from dataclasses import asdict
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    GitCommandError,
    get_branch_context,
    get_commits_ahead,
    get_latest_tag,
    get_repo_context,
    run_git,
)
from agent_tools.infrastructure.config.manager import (
    get_full_commit_rules,
    get_release_tag_regex,
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_release"


def _check_safety_guards() -> Result | None:
    """Strict pre-conditions for releasing."""
    repo_info = get_repo_context()
    branch_info = get_branch_context(refresh=True)

    if branch_info.current_branch != repo_info.default_branch:
        return Result(
            status="error",
            message=f"Releases must be cut from the default branch ('{repo_info.default_branch}').",
            workflow=WORKFLOW,
            instruction=f"Switch to '{repo_info.default_branch}' and sync before releasing.",
        )

    if branch_info.is_dirty:
        return Result(
            status="error",
            message="Working tree is dirty.",
            workflow=WORKFLOW,
            instruction="Commit or stash changes before starting the release flow.",
        )

    return None


def _handle_init() -> Result:
    """Stage 0: Initialization and Sync."""
    return Result(
        status="handoff",
        message="Release initialized.",
        workflow=WORKFLOW,
        next_step="SYNC_BEFORE_RELEASE",
        resume_point="sense",
        instruction=(
            "1. Run 'git_sync_flow' to ensure your branch is updated and pushed.\n"
            "2. After sync, call 'git_release_flow' with point='sense'."
        ),
    )


def _handle_sense() -> Result:
    """Stage 1: Context gathering and planning."""
    guard = _check_safety_guards()
    if guard:
        return guard

    latest_tag = get_latest_tag()
    if latest_tag:
        commits = get_commits_ahead(latest_tag)
    else:
        res = run_git(["rev-list", "--max-parents=0", "HEAD"])
        first_commit = res.stdout.strip()
        commits = get_commits_ahead(f"{first_commit}^!") if first_commit else []

    return Result(
        status="handoff",
        message="Ready to plan release.",
        workflow=WORKFLOW,
        next_step="PLAN_VERSION_BUMP",
        resume_point="release",
        instruction=(
            "1. Analyze 'commits' in details to determine the next SemVer.\n"
            "2. Search for version files (pyproject.toml, package.json, etc.) and propose increments.\n"
            "3. Present the release draft to the user and await authorization.\n"
            "4. After approval, update version files and commit.\n"
            "5. Finally, call 'git_release_flow' with point='release' and your tag_json_str."
        ),
        constraints=[
            "Tag MUST match the regex in details.",
            "Do NOT bypass user authorization for version bumps.",
        ],
        details={
            "latest_tag": latest_tag,
            "commits": [asdict(c) for c in commits],
            "tag_regex": get_release_tag_regex(),
            "commit_rules": get_full_commit_rules(),
            "branch_info": asdict(get_branch_context()),
        },
    )


def _handle_release(tag_json_str: str) -> Result:
    """Stage 2: Physical tagging and atomic push."""
    try:
        data = json.loads(tag_json_str)
        tag_name = data.get("tag_name")
        tag_message = data.get("tag_message", f"Release {tag_name}")
    except json.JSONDecodeError:
        return Result(
            status="error",
            message="Invalid JSON in tag_json_str.",
            workflow=WORKFLOW,
            instruction="Fix the JSON format and retry.",
        )

    if not tag_name:
        return Result(status="error", message="Missing 'tag_name'.", workflow=WORKFLOW)

    tag_regex = get_release_tag_regex()
    if not re.match(tag_regex, tag_name):
        return Result(
            status="error",
            message=f"Tag '{tag_name}' violates policy: {tag_regex}",
            workflow=WORKFLOW,
        )

    guard = _check_safety_guards()
    if guard:
        return guard

    try:
        # Create Annotated Tag
        run_git(["tag", "-a", tag_name, "-m", tag_message]).raise_on_error(
            "Tag creation failed"
        )
        # Atomic Push
        run_git(["push", "origin", "--atomic", "HEAD", tag_name]).raise_on_error(
            "Atomic push failed"
        )

        return Result(
            status="success",
            message=f"Release {tag_name} published successfully.",
            workflow=WORKFLOW,
            details={"tag": tag_name},
        )
    except GitCommandError as e:
        return Result(
            status="error",
            message=f"Git error during release: {e.stderr}",
            workflow=WORKFLOW,
            instruction="Resolve the git issue (e.g., tag already exists) and retry.",
        )


def git_release_flow(
    point: Literal["init", "sense", "release"] = "init", tag_json_str: str = ""
) -> Result:
    """Industrial-grade git release flow orchestrator."""
    handlers = {
        "init": _handle_init,
        "sense": _handle_sense,
        "release": lambda: _handle_release(tag_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(
                status="error", message=f"Invalid point: {point}", workflow=WORKFLOW
            )
        return handler()
    except Exception as e:
        logger.exception("Release workflow crash")
        return Result(
            status="error", message=f"Release failed: {str(e)}", workflow=WORKFLOW
        )
