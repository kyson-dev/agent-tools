import json
import logging
from typing import Optional, Dict, Any, List
from agent_tools.protocol import Result
from agent_tools.git import (
    run_git,
    get_branch_context,
    get_repo_context,
    GitCommandError
)
from agent_tools.gh import run_gh
from agent_tools.config import (
    get_commit_allowed_types,
    get_commit_message_regex,
    get_commit_subject_max_length
)

WORKFLOW = "gh_pr_merge"
logger = logging.getLogger(WORKFLOW)

def sense() -> Result:
    """Stage 1: Gather PR context and hand off for final squash message synthesis."""
    try:
        repo_info = get_repo_context(refresh=True)
        branch_info = get_branch_context(refresh=True)
        
        if not repo_info.owner or not repo_info.repo:
            return Result(status="error", message="Not in a git repository or no remote configured.", workflow=WORKFLOW)
        
        if branch_info.is_detached:
            return Result(status="error", message="HEAD is detached. Merge requires being on a feature branch.", workflow=WORKFLOW)

        current_branch = branch_info.current_branch
        
        # Fetch PR Metadata
        view_res = run_gh([
            "pr", "view", current_branch, 
            "--json", "number,title,body,state,mergeable,mergeStateStatus,statusCheckRollup,reviews,headRefName,baseRefName"
        ])
        
        if view_res.returncode != 0:
            return Result(status="error", message=f"Failed to find PR for branch '{current_branch}': {view_res.stderr}", workflow=WORKFLOW)
        
        pr_data = json.loads(view_res.stdout)
        number = pr_data.get("number")
        state = pr_data.get("state")
        mergeable = pr_data.get("mergeable")
        merge_state = pr_data.get("mergeStateStatus")
        
        # Guards
        if state != "OPEN":
            return Result(status="error", message=f"PR #{number} is {state}, not open.", workflow=WORKFLOW)
        if mergeable == "CONFLICTING" or merge_state == "DIRTY":
            return Result(status="error", message=f"PR #{number} has merge conflicts.", workflow=WORKFLOW)
        if merge_state == "BEHIND":
             return Result(status="error", message=f"PR #{number} is behind base branch. Run git_sync first.", workflow=WORKFLOW)

        # CI Checks
        checks = pr_data.get("statusCheckRollup", [])
        if checks:
            failing = [c for c in checks if c.get("status") == "COMPLETED" and c.get("conclusion") not in ["SUCCESS", "SKIPPED", "NEUTRAL"]]
            pending = [c for c in checks if c.get("status") != "COMPLETED"]
            if failing:
                return Result(status="error", message=f"PR #{number} has {len(failing)} failing CI checks.", workflow=WORKFLOW, details={"failing": failing})
            if pending:
                return Result(status="error", message=f"PR #{number} has {len(pending)} pending CI checks.", workflow=WORKFLOW)

        # Reviews
        reviews = pr_data.get("reviews", [])
        changes_requested = [r for r in reviews if r.get("state") == "CHANGES_REQUESTED"]
        if changes_requested:
            return Result(status="error", message=f"PR #{number} has active 'Changes Requested' reviews.", workflow=WORKFLOW)
        
        if merge_state == "BLOCKED":
             return Result(status="error", message=f"PR #{number} is BLOCKED (likely missing approvals).", workflow=WORKFLOW)

        # Provide rules for message synthesis
        rules = {
            "allowed_types": get_commit_allowed_types(),
            "subject_max_length": get_commit_subject_max_length(),
            "message_regex": get_commit_message_regex()
        }

        return Result(
            status="handoff",
            message=f"PR #{number} is ready for merge. Please synthesize the final squash commit message.",
            workflow=WORKFLOW,
            next_step="synthesize_merge_message",
            resume_point="merge",
            instruction=(
                "1. Analyze PR title, body, and rules in `details`. "
                "2. Synthesize a final squash commit `title` (subject) and `body`. "
                "3. Call `gh_pr_merge_execute(repo_path=\".\", override_json='{\"title\": \"...\", \"body\": \"...\"}')`."
            ),
            details={
                "pr": pr_data,
                "commit_rules": rules
            }
        )

    except Exception as e:
        return Result(status="error", message=f"Merge sense error: {str(e)}", workflow=WORKFLOW)

def merge(title: str, body: Optional[str] = None) -> Result:
    """Stage 2: Execute the merge with the sanitized message."""
    try:
        repo_info = get_repo_context()
        branch_info = get_branch_context()
        current_branch = branch_info.current_branch
        
        # Fetch PR number one last time
        view_res = run_gh(["pr", "view", current_branch, "--json", "number,baseRefName"])
        if view_res.returncode != 0:
            return Result(status="error", message="Failed to fetch PR for final merge.", workflow=WORKFLOW)
        
        pr_data = json.loads(view_res.stdout)
        number = pr_data.get("number")
        base_branch = pr_data.get("baseRefName")

        # Execute Merge
        args = ["pr", "merge", str(number), "--squash", "--delete-branch"]
        if title:
            args.extend(["--subject", title])
        if body:
            args.extend(["--body", body])
            
        merge_res = run_gh(args)
        if merge_res.returncode != 0:
             return Result(status="error", message=f"Merge failed: {merge_res.stderr}", workflow=WORKFLOW)

        # Local Cleanup
        cleanup_report = []
        if branch_info.is_dirty:
            cleanup_report.append(f"Preserving local branch '{current_branch}' due to uncommitted changes.")
        else:
            try:
                run_git(["checkout", base_branch])
                run_git(["branch", "-D", current_branch])
                cleanup_report.append(f"Deleted local branch '{current_branch}' and switched to '{base_branch}'.")
            except Exception as e:
                cleanup_report.append(f"Local cleanup error: {str(e)}")

        return Result(
            status="success",
            message=f"PR #{number} merged successfully with optimized commit message.",
            workflow=WORKFLOW,
            details={"cleanup": cleanup_report}
        )

    except Exception as e:
        return Result(status="error", message=f"Merge execution error: {str(e)}", workflow=WORKFLOW)

def run_pr_merge_workflow(mode: str, data_json: Optional[str] = None) -> Result:
    if mode == "sense":
        return sense()
    if mode == "merge":
        if not data_json:
            return Result(status="error", message="mode='merge' requires data_json (title, body).", workflow=WORKFLOW)
        try:
            data = json.loads(data_json)
            return merge(title=data.get("title"), body=data.get("body"))
        except json.JSONDecodeError:
            return Result(status="error", message="Invalid data_json format.", workflow=WORKFLOW)
    return Result(status="error", message=f"Invalid mode: '{mode}'.", workflow=WORKFLOW)
