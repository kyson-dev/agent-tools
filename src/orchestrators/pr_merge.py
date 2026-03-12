import json
from typing import Optional, Dict, Any
from protocol import Result
from git import (
    run_git,
    get_branch_context,
    get_repo_context,
    GitCommandError
)

WORKFLOW = "pr_merge"

def sense() -> Result:
    """Stage 1: Identification (Simplified - Local Branch Only)."""
    repo_info = get_repo_context(refresh=True)
    branch_info = get_branch_context(refresh=True)
    
    if not repo_info.owner or not repo_info.repo:
        return Result(status="error", message="Not in a git repository or no remote configured.", workflow=WORKFLOW)
    
    if branch_info.is_detached:
        return Result(status="error", message="HEAD is detached. Merge requires being on a feature branch.", workflow=WORKFLOW)

    slug = f"{repo_info.owner}/{repo_info.repo}"
    # Always target the PR associated with the active local branch
    instruction = f"Call `mcp_github_list_pull_requests` for {slug} with head='{branch_info.current_branch}' to find the PR."

    return Result(
        status="handoff",
        message=f"Identifying PR for current branch '{branch_info.current_branch}'...",
        workflow=WORKFLOW,
        next_step="fetch_pr_object",
        resume_point="validate",
        instruction=instruction,
        details={
            "owner": repo_info.owner, 
            "repo": repo_info.repo, 
            "branch": branch_info.current_branch
        }
    )

def validate(data: Dict[Any, Any]) -> Result:
    """Stage 2: Metadata Validation."""
    # Data is expected to be a PR object (or list of PR objects) from Stage 1
    pr = data[0] if isinstance(data, list) and len(data) > 0 else data
    if not pr or not isinstance(pr, dict):
        return Result(status="error", message="No PR data received from Phase 1.", workflow=WORKFLOW)
    
    number = pr.get("number")
    state = pr.get("state")
    draft = pr.get("draft", False)
    mergeable = pr.get("mergeable")
    mergeable_state = pr.get("mergeable_state")
    
    # Identify local ownership based on Git Metadata comparison
    repo_info = get_repo_context()
    head_owner = pr.get("head", {}).get("repo", {}).get("owner", {}).get("login")
    pr_owner = pr.get("user", {}).get("login")
    # Rule: I am the 'owner' if I am working in the same namespace as the PR's head branch source
    is_owner = (repo_info.owner == head_owner)
    
    # Comprehensive PR Status Audit
    if state != "open":
        return Result(status="error", message=f"PR #{number} is {state}, not open.", workflow=WORKFLOW)

    # Authorization Check: Verify push/merge permissions (Target repo)
    permissions = pr.get("base", {}).get("repo", {}).get("permissions", {})
    repo_owner = pr.get("base", {}).get("repo", {}).get("owner", {}).get("login")
    repo_name = pr.get("base", {}).get("repo", {}).get("name")
    
    if not permissions.get("push", True): 
        return Result(status="error", message=f"PERMISSION DENIED: Your token does not have push/merge access to {repo_owner}/{repo_name}.", workflow=WORKFLOW)

    if mergeable_state != "clean":
        # A. Conflict Handling: Return error primarily. Skill should have synced.
        if mergeable is False or mergeable_state == "dirty":
            return Result(status="error", message=f"PR #{number} has merge conflicts. Author @{pr_owner} must resolve them.", workflow=WORKFLOW)
        
        # B. Behind Handling: Return error. Skill should have synced.
        if mergeable_state == "behind":
            return Result(status="error", message=f"PR #{number} is out of date (behind base). Please ensure your branch is synced.", workflow=WORKFLOW)

        # C. Draft check
        if draft or mergeable_state == "draft":
            return Result(status="error", message=f"PR #{number} is a draft. Convert to 'Ready for review' on GitHub first.", workflow=WORKFLOW)
            
        # D. Calculating State
        if mergeable is None:
            return Result(status="error", message=f"GitHub is still calculating mergeability for PR #{number}. Please try again in 5-10 seconds.", workflow=WORKFLOW)

        # E. Policy Blocked/Unstable: Proceed to Stage 3 for internal analysis
        if mergeable_state in ["blocked", "unstable"]:
            pass 
        else:
            return Result(status="error", message=f"PR #{number} is in unexpected state: '{mergeable_state}'.", workflow=WORKFLOW)

    return Result(
        status="handoff",
        message=f"PR #{number} metadata valid. Checking CI and Reviews...",
        workflow=WORKFLOW,
        next_step="fetch_status_and_reviews",
        resume_point="verdict",
        instruction=(
            f"1. Call `mcp_github_get_pull_request_status` for {repo_owner}/{repo_name} PR #{number}.\n"
            f"2. Call `mcp_github_get_pull_request_reviews` for {repo_owner}/{repo_name} PR #{number}."
        ),
        details={"pr": pr}
    )

def verdict(data: Dict[Any, Any]) -> Result:
    """Stage 3: Quality Audit & Merge Instruction."""
    # This stage acts as a "Last-Mile" safety audit. Even if Stage 2 saw a 'clean' 
    # summary, we now verify the fresh atomic Status and Review data to catch 
    # cache lag or state changes that occurred between stages.
    
    pr = data.get("pr")
    status = data.get("status") # Fresh Status from L3/MCP
    reviews = data.get("reviews", []) # Fresh Reviews from L3/MCP
    
    number = pr.get("number")
    pr_owner = pr.get("user", {}).get("login")
    repo_owner = pr.get("base", {}).get("repo", {}).get("owner", {}).get("login")
    repo_name = pr.get("base", {}).get("repo", {}).get("name")
    
    # Safety Audit 1: Real-time Review check (Catch late-breaking rejections)
    changes_requested = [r for r in reviews if r.get("state") == "CHANGES_REQUESTED"]
    if changes_requested:
        return Result(status="error", message=f"Last-minute audit: PR #{number} has active 'Changes Requested' reviews. Merge aborted.", workflow=WORKFLOW)
    
    # Safety Audit 2: CI Status check (only if status data is available)
    if status:
        ci_state = status.get("state")
        if ci_state and ci_state != "success":
            if ci_state == "pending":
                return Result(status="error", message=f"Last-minute audit: PR #{number} CI is still PENDING. Please wait.", workflow=WORKFLOW)
            elif ci_state in ["failure", "error"]:
                return Result(status="error", message=f"PR #{number} CI has FAILED ({ci_state}). Author @{pr_owner} must fix test failures.", workflow=WORKFLOW)
            else:
                return Result(status="error", message=f"Last-minute audit: PR #{number} CI status is currently '{ci_state}'.", workflow=WORKFLOW)

    # Safety Audit 3: Missing Approvals Check
    # If GitHub says 'blocked' but CI is successful and there are no requested changes,
    # the failure is almost certainly due to lack of approvals or required reviewers.
    mergeable_state = pr.get("mergeable_state")
    if mergeable_state == "blocked":
        return Result(
            status="error",
            message=f"PR #{number} is BLOCKED by repository policy (likely missing approvals).",
            workflow=WORKFLOW
        )

    return Result(
        status="handoff",
        message=f"PR #{number} passed last-minute safety audit. Proceeding to merge.",
        workflow=WORKFLOW,
        next_step="execute_merge",
        resume_point="cleanup",
        instruction=(
            f"Call `mcp_github_merge_pull_request` for {repo_owner}/{repo_name} PR #{number}.\n"
            "Use 'squash' merge strategy."
        ),
        details={"pr": pr}
    )

def cleanup(data: Dict[Any, Any]) -> Result:
    """Stage 4: Mandatory Local & Optional Remote Cleanup."""
    pr = data.get("pr")
    success = data.get("merge_confirmed", False)
    
    if not success:
        return Result(status="error", message="Merge failed or was not confirmed.", workflow=WORKFLOW)
    
    number = pr.get("number")
    head_branch = pr.get("head", {}).get("ref")
    base_branch = pr.get("base", {}).get("ref")
    pr_head_sha = pr.get("head", {}).get("sha")
    
    # FOR REMOTE CLEANUP: Use head repo info (crucial for forks)
    head_owner = pr.get("head", {}).get("repo", {}).get("owner", {}).get("login")
    head_repo = pr.get("head", {}).get("repo", {}).get("name")

    cleanup_report = []
    
    # 1. Deterministic Local Mutation (L2 handles this with strict logic)
    try:
        branch_info = get_branch_context(refresh=True)
        
        # A. Existence Check
        branches_res = run_git(["branch", "--list", head_branch])
        if head_branch not in branches_res.stdout:
            cleanup_report.append(f"Local branch '{head_branch}' not found.")
        else:
            # B. Ahead Check: Does local head_branch have commits not in the merged PR?
            # rev-list count of commits in head_branch but NOT in the PR's head SHA.
            ahead_res = run_git(["rev-list", "--count", f"{pr_head_sha}..{head_branch}"])
            is_ahead = int(ahead_res.stdout.strip()) > 0 if ahead_res.ok else False
            
            if is_ahead:
                cleanup_report.append(f"Local branch '{head_branch}' is ahead. Preserved.")
            else:
                # C. Identical or Behind: Determine if it's safe to delete based on active state
                if branch_info.current_branch != head_branch:
                    # Not checked out: Safe to delete
                    run_git(["branch", "-D", head_branch]) # Use -D as we've manually verified ahead status
                    cleanup_report.append(f"Deleted local branch '{head_branch}'.")
                else:
                    # Checked out: Check worktree hygiene
                    if branch_info.is_dirty:
                        cleanup_report.append(f"Preserving current branch '{head_branch}' because it has uncommitted changes.")
                    else:
                        # Clean and checked out: Move to base branch and then delete
                        run_git(["checkout", base_branch])
                        run_git(["branch", "-D", head_branch])
                        cleanup_report.append(f"Switched and deleted branch.")
    except Exception as e:
        cleanup_report.append(f"Local cleanup failed: {str(e)}")

    return Result(
        status="success",
        message=f"PR #{number} merged and cleaned up.",
        workflow=WORKFLOW,
        details={
            "report": cleanup_report,
            "remote_cleanup": f"Call `mcp_github_delete_branch` for {head_owner}/{head_repo} branch '{head_branch}'."
        }
    )

def run_pr_merge_workflow(
    mode: str, 
    data_json: Optional[str] = None
) -> Result:
    if mode == "sense":
        return sense()
    
    if not data_json:
        return Result(status="error", message=f"mode='{mode}' requires data_json.", workflow=WORKFLOW)
    
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        return Result(status="error", message="Invalid data_json format.", workflow=WORKFLOW)

    if mode == "validate":
        return validate(data)
    elif mode == "verdict":
        return verdict(data)
    elif mode == "cleanup":
        return cleanup(data)
    
    return Result(status="error", message=f"Invalid mode: '{mode}'.", workflow=WORKFLOW)
