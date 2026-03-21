import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from orchestrators.git_commit import run_commit_workflow

print("=== 1. COMMITTING ===")
sense = run_commit_workflow('sense')

if sense.status == "handoff":
    plan = {
        "commits": [
            {
                "files": [
                    "ARCHITECTURE.md", "pyproject.toml", "src/orchestrators/__init__.py", 
                    "src/server.py", "00_SKILL_SPEC.md", "src/cli.py", "src/gh/__init__.py", "src/gh/client.py",
                    "src/orchestrators/gh_pr_create.py", "src/orchestrators/gh_pr_merge.py", 
                    "src/orchestrators/git_commit.py", "src/orchestrators/git_sync.py", 
                    "src/orchestrators/commit.py", "src/orchestrators/sync.py", 
                    "src/orchestrators/pr_create.py", "src/orchestrators/pr_merge.py", 
                    "src/git/__init__.py", "src/git/gh_client.py"
                ],
                "message": "refactor(core): migrate to MCP and integrate gh CLI\n\n- Replaced external GitHub MCP with internal `gh` CLI wrapper.\n- Renamed orchestrators to clarify domain.\n- Refactored server.py to expose double-stage merge and sync tools.\n- Merged ARCHITECTURE and SKILL_SPEC docs."
            }
        ]
    }
    
    exec_res = run_commit_workflow('plan', json.dumps(plan))
    print(exec_res.to_json())
