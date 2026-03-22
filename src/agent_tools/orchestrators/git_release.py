import logging
import re
from dataclasses import asdict
from typing import Literal

from ...config import (
    get_full_commit_rules,
    get_release_tag_regex,
)
from ...git import (
    GitCommandError,
    get_branch_context,
    get_commits_ahead,
    get_latest_tag,
    get_repo_context,
    run_git,
)
from ...protocol import Result

logger = logging.getLogger(__name__)
WORKFLOW = "git_release"


def _check_safety_guards() -> Result | None:
    """Strict pre-conditions (Branch check, Dirty check, Sync check)."""
    try:
        repo_info = get_repo_context()
        branch_info = get_branch_context(refresh=True)

        # Guard 1: Must be on default branch
        if branch_info.current_branch != repo_info.default_branch:
            return Result(
                status="error",
                message=f"Release must be cut from the default branch ('{repo_info.default_branch}'). Current: '{branch_info.current_branch}'",
                workflow=WORKFLOW,
            )

        # Guard 2: Working tree must be clean
        if branch_info.is_dirty:
            return Result(
                status="error",
                message="Working tree remains dirty. Please commit or stash changes before releasing.",
                workflow=WORKFLOW,
            )

        return None
    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)


def _init_sync() -> Result:
    return Result(
        status="handoff",
        message="git release initiated. Ensuring local branch is synchronized.",
        workflow=WORKFLOW,
        next_step="sync_branch",
        resume_point="create",
        instruction='\
                1. **SYNC**: Run `git_sync_flow` to ensure your branch is updated and pushed. \
                2. **RESUME**: Call `git_release_flow(point="sense")` after sync completes.',
    )


def _sense() -> Result:
    """Stage 1: Gather release context and handoff to AI."""
    guard = _check_safety_guards()
    if guard:
        return guard

    try:
        latest_tag = get_latest_tag()
        if latest_tag:
            commits = get_commits_ahead(latest_tag)
        else:
            res = run_git(["rev-list", "--max-parents=0", "HEAD"])
            first_commit = res.stdout.strip()
            commits = get_commits_ahead(f"{first_commit}^!") if first_commit else []

        return Result(
            status="handoff",
            message="Ready to analyze release.",
            workflow=WORKFLOW,
            next_step="plan_bump",
            details={
                "latest_tag": latest_tag,
                "commits": [asdict(c) for c in commits],
                "tag_regex": get_release_tag_regex(),
                "commit_rules": get_full_commit_rules(),
                "branch_info": asdict(get_branch_context()),
            },
            instruction=(
                "1. All message MUST following **Conventional Commits** and `details.commit_rules`. Tag MUST following `details.tag_regex`. "
                "2. **ANALYZE**: Determine next SemVer based on `commits`. **AUTONOMOUS DISCOVERY**: Search for versioning indicators (e.g., `pyproject.toml`, `package.json`, `setup.py`, `VERSION` file) in common locations using your file-system tools. If the project HAS NO internal version field, propose a **Tag-Only Release** (skipping file mutation). "
                "3. **SANITY CHECK**: Cross-reference `details.latest_tag` with any found file-based version. If versions are inconsistent across multiple files, or if a manual out-of-sync bump is detected, you MUST propose a unification strategy following SemVer policy. "
                "4. **EXPLICIT HANDOFF (STOP)**: Present the full release draft (`tag_name`, Release Notes, and found version files) to the user. AWAIT explicit authorization before proceeding. "
                "5. **MUTATE & COMMIT**: Based on authorization, use `replace_file_content` to unify/apply version increments, then use `git_commit_flow` to commit. Skip if state is already compliant or it's a Tag-Only release. "
                '6. **FINALIZE**: Call `git_release_flow(point="release", tag_json_str=\'{"tag_name": "...", "tag_message": "..."}\')` to tag and push locally. Handle any tag-exists or push-rejected errors by suggesting resolutions.'
            ),
        )
    except Exception as e:
        return Result(
            status="error", message=f"Sense failed: {str(e)}", workflow=WORKFLOW
        )


def _release(tag_json_str: str) -> Result:
    """Stage 2: Tag, and Push atomically. REQUIRES clean worktree."""
    import json

    try:
        data = json.loads(tag_json_str)
        tag_name = data.get("tag_name")
        tag_message = data.get("tag_message")
    except json.JSONDecodeError:
        return Result(
            status="error", message="Invalid tag_json_str format.", workflow=WORKFLOW
        )

    # Check regex locally first
    tag_regex = get_release_tag_regex()
    if not re.match(tag_regex, tag_name):
        return Result(
            status="error",
            message=f"Tag name '{tag_name}' does not match policy: {tag_regex}",
            workflow=WORKFLOW,
        )

    guard = _check_safety_guards()
    if guard:
        return guard

    try:
        # 1. Create Annotated Tag
        tag_cmd = ["tag", "-a", tag_name, "-m", tag_message]
        run_git(tag_cmd).raise_on_error(f"Failed to create tag {tag_name}")

        # 2. Push main and tags
        run_git(["push", "origin", "--atomic", "HEAD", tag_name]).raise_on_error(
            "Push failed"
        )

        return Result(
            status="success",
            message=f"Release {tag_name} successfully published.",
            workflow=WORKFLOW,
            details={"tag": tag_name},
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)


def git_release_flow(
    point: Literal["init", "sense", "release"] = "init", tag_json_str=""
) -> Result:
    try:
        if point == "init":
            return _init_sync()
        elif point == "sense":
            return _sense()
        elif point == "release":
            return _release(tag_json_str)
    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)
    except Exception as e:
        return Result(
            status="error", message=f"Git release error: {str(e)}", workflow=WORKFLOW
        )
