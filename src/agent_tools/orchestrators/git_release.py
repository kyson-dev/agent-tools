import json
import logging
from dataclasses import asdict
from typing import Optional, List

from agent_tools.protocol import Result
from agent_tools.git import (
    run_git,
    get_branch_context,
    get_repo_context,
    get_latest_tag,
    get_commits_ahead,
    GitCommandError
)
from agent_tools.config import (
    get_release_version_files,
    get_release_tag_regex,
    get_full_commit_rules
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_release"

import re

def _validate_input(tag_name: str, commit_msg: str) -> Optional[Result]:
    """Validate tag and commit message against project rules."""
    rules = get_full_commit_rules()
    tag_regex = get_release_tag_regex()
    commit_regex = rules["message_regex"]

    if not re.match(tag_regex, tag_name):
        return Result(status="error", message=f"Tag name '{tag_name}' does not match policy: {tag_regex}", workflow=WORKFLOW)
    
    if commit_msg and not re.match(commit_regex, commit_msg):
        return Result(status="error", message=f"Commit message does not match policy: {commit_regex}", workflow=WORKFLOW)
    
    return None

def _check_safety_guards() -> Optional[Result]:
    """Strict pre-conditions (Branch check, Dirty check, Sync check)."""
    try:
        repo_info = get_repo_context()
        branch_info = get_branch_context(refresh=True)

        # Guard 1: Must be on default branch
        if branch_info.current_branch != repo_info.default_branch:
            return Result(
                status="error",
                message=f"Release must be cut from the default branch ('{repo_info.default_branch}'). Current: '{branch_info.current_branch}'",
                workflow=WORKFLOW
            )

        # Guard 2: Working tree must be clean
        if branch_info.is_dirty:
            return Result(
                status="error",
                message="Working tree remains dirty. Please commit or stash changes before releasing.",
                workflow=WORKFLOW
            )

        # Guard 3: Must be up to date with origin (behind == 0)
        if branch_info.behind > 0:
            return Result(
                status="error",
                message=f"Local branch is behind origin by {branch_info.behind} commits. Please pull first.",
                workflow=WORKFLOW
            )
            
        return None
    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)

def sense() -> Result:
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
                "configured_version_files": get_release_version_files(),
                "tag_regex": get_release_tag_regex(),
                "commit_rules": get_full_commit_rules(),
                "branch_info": asdict(get_branch_context())
            },
            instruction=(
                "1. Analyze commits in `details` to determine next SemVer. "
                "2. Update version strings in discovered files. "
                "3. **HANDOFF**: Propose the `tag_name`, `tag_message` (Release Notes), and `commit_message` to the user and AWAIT explicit authorization. "
                "4. **COMMIT**: Upon approval, run `git_commit_flow` to commit the bump (MUST follow `details.commit_rules`). "
                "5. **FINALIZE**: Once committed, call `git_release_execute` to tag and push."
            ),
        )
    except Exception as e:
        return Result(status="error", message=f"Sense failed: {str(e)}", workflow=WORKFLOW)

def execute(tag_name: str, tag_message: str) -> Result:
    """Stage 2: Tag, and Push atomically. REQUIRES clean worktree."""
    # Check regex locally first
    tag_regex = get_release_tag_regex()
    if not re.match(tag_regex, tag_name):
        return Result(status="error", message=f"Tag name '{tag_name}' does not match policy: {tag_regex}", workflow=WORKFLOW)

    guard = _check_safety_guards()
    if guard:
        return guard
    
    try:
        # Final safety: MUST NOT be dirty at this stage
        branch_info = get_branch_context(refresh=True)
        if branch_info.is_dirty:
             return Result(
                 status="error", 
                 message="Working tree remains dirty. You MUST commit the version bump (via git_commit_flow) before creating a tag.", 
                 workflow=WORKFLOW
             )

        # 1. Create Annotated Tag
        tag_cmd = ["tag", "-a", tag_name, "-m", tag_message]
        run_git(tag_cmd).raise_on_error(f"Failed to create tag {tag_name}")

        # 2. Push main and tags
        run_git(["push", "origin", "--atomic", "HEAD", tag_name]).raise_on_error("Push failed")

        return Result(
            status="success",
            message=f"Release {tag_name} successfully published.",
            workflow=WORKFLOW,
            details={"tag": tag_name}
        )

    except GitCommandError as e:
        return Result(status="error", message=str(e), workflow=WORKFLOW)

def run_release_workflow(mode: str, tag_json: str = None) -> Result:
    if mode == "sense":
        return sense()
    elif mode == "execute":
        if not tag_json:
            return Result(status="error", message="Missing tag_json", workflow=WORKFLOW)
        data = json.loads(tag_json)
        return execute(
            tag_name=data.get("tag_name"),
            tag_message=data.get("tag_message")
        )
    else:
        return Result(status="error", message=f"Invalid mode: {mode}", workflow=WORKFLOW)
