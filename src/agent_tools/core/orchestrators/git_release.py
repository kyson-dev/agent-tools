import json
import logging
import re
from dataclasses import asdict
from typing import Literal

from agent_tools.core.models.workflow import Result
from agent_tools.infrastructure.clients.git import (
    get_branch_context,
    get_commits_ahead,
    get_latest_tag,
    get_repo_context,
    run_git,
)
from agent_tools.infrastructure.config.manager import (
    get_full_commit_rules,
    get_release_tag_regex,
    get_protected_branches,
    get_allow_direct_actions_to_protected,
)

logger = logging.getLogger(__name__)
WORKFLOW = "git_release"


def _check_safety_guards() -> Result | None:
    """Strict pre-conditions for releasing."""

    # 1. 游离分支
    branch_info = get_branch_context(refresh=True)
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached.", workflow=WORKFLOW)

    # 2. 没有remote origin
    repo_info = get_repo_context(refresh=True)
    if not repo_info.primary_remote:
        return Result(status="error", message="No remote origin.", workflow=WORKFLOW)

    # 3. 默认分支不存在
    if not repo_info.default_branch:
        return Result(status="error", message="Missing branch information.", workflow=WORKFLOW)

    # 4. 必须在默认分支
    if branch_info.current_branch != repo_info.default_branch:
        return Result(
            status="error",
            message=f"Releases must be cut from the default branch ('{repo_info.default_branch}').",
            workflow=WORKFLOW,
            instruction=f"Switch to '{repo_info.default_branch}' and sync before releasing.",
        )
    return None


def _handle_init() -> Result:
    """Stage 0: Initialization and Sync."""

    safety_guard_res = _check_safety_guards()
    if safety_guard_res:
        return safety_guard_res

    # 工作区不干净、本地领先远程
    branch_info = get_branch_context()
    if branch_info.is_dirty or branch_info.ahead > 0:
        return Result(
            status="handoff",
            message="Release initialized.",
            workflow=WORKFLOW,
            next_step="SYNC_BEFORE_RELEASE",
            resume_point="sense",
            instruction=(
                "【ACTION】\n"
                "1. Run 'git_sync_flow' to ensure your branch is updated and pushed.\n"
                "2. After sync, call 'git_release_flow' with point='sense'."
            ),
        )

    return _handle_sense()


def _is_protected_branch() -> bool:
    branch_info = get_branch_context()
    if (
        branch_info.current_branch
        and branch_info.current_branch in get_protected_branches()
        and not get_allow_direct_actions_to_protected()
    ):
        return True

    return False


def _handle_sense() -> Result:
    """Stage 1: Context gathering and planning."""

    latest_tag = get_latest_tag()
    if latest_tag:
        commits = get_commits_ahead(latest_tag)
    else:
        res = run_git(["rev-list", "--max-parents=0", "HEAD"])
        first_commit = res.stdout.strip()
        commits = get_commits_ahead(f"{first_commit}^!") if first_commit else []

    # if commits list is none, return no commits to release
    if not commits:
        return Result(
            status="error",
            message="No commits to release.",
            workflow=WORKFLOW,
            instruction="No commits to release.",
        )

    # Detect if current default branch is protected
    is_protected = _is_protected_branch()

    return Result(
        status="handoff",
        message="Ready to plan release.",
        workflow=WORKFLOW,
        next_step="PLAN_VERSION_BUMP",
        resume_point="release",
        instruction=(
            "【STRICT PROTOCOL / 严格协议】\n"
            "1. Analyze 'commits' in details to determine the next SemVer increment.\n"
            "2. Read versioning files to find current version. If already updated via recent merges, proceed to step 4.\n"
            "3. If version bump is needed (【PAUSE】You MUST propose the new version and its rationale, then WAIT for USER approval before proceeding):\n"
            f"   - **IF PROTECTED (is_protected={is_protected})**: Use 'gh_pr_create_flow' for a version PR. IMPORTANT: Wait for CI checks, then merge using 'gh_pr_merge_flow'.\n"
            f"   - **ELSE**: Update and commit directly using 'git_commit_flow'.\n"
            "4. Finalize with 'git_release_flow' (point='release'), providing a structured message with descriptive title and categorized changes (Features, Bug Fixes, Refactors)."
        ),
        constraints=[
            "Tag MUST match the regex in details.",
            "Each commit message MUST follow Conventional Commits and `commit_rules`.",
            "Do NOT proceed if version files and git history are out of sync.",
        ],
        details={
            "latest_tag": latest_tag,
            "commits": [asdict(c) for c in commits],
            "is_protected": is_protected,
            "json_format": {
                "name": "v1.2.3",
                "message": (
                    "v1.2.3: Descriptive Title Summary\n\n"
                    "### 🚀 Features\n- List key new features here.\n\n"
                    "### 🐛 Bug Fixes\n- List important bug fixes here.\n\n"
                    "### ⚙️ Refactors\n- List major internal improvements here."
                ),
            },
            "tag_regex": get_release_tag_regex(),
            "commit_rules": get_full_commit_rules(),
            "branch_info": asdict(get_branch_context()),
        },
    )


def _handle_release(tag_json_str: str) -> Result:
    """Stage 2: Physical tagging and atomic push."""
    try:
        data = json.loads(tag_json_str)
        name = data.get("name")
        message = data.get("message")
    except json.JSONDecodeError:
        return Result(
            status="error",
            message="Invalid JSON in tag_json_str.",
            workflow=WORKFLOW,
            instruction="Fix the JSON format and retry.",
        )

    if not name or not message:
        return Result(status="error", message="Missing 'name' or 'message'.", workflow=WORKFLOW)

    tag_regex = get_release_tag_regex()
    if not re.match(tag_regex, name):
        return Result(
            status="error",
            message=f"Tag '{name}' violates policy: {tag_regex}",
            workflow=WORKFLOW,
        )

    # Create Annotated Tag
    run_git(["tag", "-a", name, "-m", message]).raise_on_error("Tag creation failed")
    repo_info = get_repo_context(refresh=True)
    remote = repo_info.primary_remote
    if not remote:
        return Result(status="error", message="No remote origin.", workflow=WORKFLOW)

    # Push HEAD and tag atomically
    res = run_git(["push", remote, "--atomic", "HEAD", name])
    if not res.ok:
        # Cleanup tag if push failed to allow retry
        run_git(["tag", "-d", name])
        return Result(
            status="error",
            message=f"Atomic push failed: {res.stderr}",
            workflow=WORKFLOW,
            instruction="Investigate the push error (e.g., remote tag already exists) and retry.",
        )

    return Result(
        status="success",
        message=f"Release {name} published successfully.",
        workflow=WORKFLOW,
        details={"tag": name},
    )


def git_release_flow(point: Literal["init", "sense", "release"] = "init", tag_json_str: str = "") -> Result:
    """Industrial-grade git release flow orchestrator."""
    handlers = {
        "init": _handle_init,
        "sense": _handle_sense,
        "release": lambda: _handle_release(tag_json_str),
    }

    try:
        handler = handlers.get(point)
        if not handler:
            return Result(status="error", message=f"Invalid point: {point}", workflow=WORKFLOW)
        return handler()
    except Exception as e:
        logger.exception("Release workflow crash")
        return Result(status="error", message=f"Release failed: {str(e)}", workflow=WORKFLOW)
