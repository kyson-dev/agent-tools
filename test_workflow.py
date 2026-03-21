import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from orchestrators.git_commit import run_commit_workflow
from orchestrators.gh_pr_create import run_pr_create_workflow
from orchestrators.gh_pr_merge import run_pr_merge_workflow
from orchestrators.git_sync import run_sync_workflow

print("=== 1. COMMITTING ===")
plan = {
    "commits": [
        {
            "files": ["."],
            "message": "refactor(core): migrate to MCP and integrate gh CLI\n\n- Replaced external GitHub MCP with internal gh CLI wrapper.\n- Renamed orchestrators to clarify domain.\n- Refactored server.py to expose double-stage merge and sync tools.\n- Merged ARCHITECTURE and SKILL_SPEC docs."
        }
    ]
}
exec_res = run_commit_workflow('plan', json.dumps(plan))
print("COMMIT RESULT:", exec_res.to_json())

print("\n=== 2. CREATING PR ===")
pr_draft = {
    "title": "refactor(core): migrate to MCP architecture and integrate GitHub CLI",
    "body": "This PR integrates the local `gh` CLI directly into the orchestrators, completely removing the dependency on the external GitHub MCP. It also finalizes the transition to FastMCP by simplifying tools and prompts, and merges the architecture docs."
}
pr_res = run_pr_create_workflow('create', json.dumps(pr_draft))
print("PR CREATE RESULT:", pr_res.to_json())

print("\n=== 3. MERGING PR ===")
override_json = {
    "title": "refactor(core): migrate to MCP and integrate GitHub CLI",
    "body": "Replaced external GitHub MCP with internal gh CLI wrapper. Refactored PR workflows into multi-stage operations for MCP."
}
merge_res = run_pr_merge_workflow('merge', json.dumps(override_json))
print("MERGE RESULT:", merge_res.to_json())

print("\n=== 4. SYNCING AND CLEANUP ===")
# Sync will pull origin main and fast path switch if we deleted the current branch inside merge.
# However, gh pr merge with --delete-branch actually deletes the branch on the remote. 
# And our orchestrator deletes it locally too! So we might be on main already.
sync_res = run_sync_workflow('init')
print("SYNC RESULT:", sync_res.to_json())
