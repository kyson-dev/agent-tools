import argparse
import sys

from protocol import Result
from orchestrators import (
    run_commit_workflow,
    run_sync_workflow,
    run_pr_create_workflow,
)

def execute_and_exit(func, *args, **kwargs) -> None:
    """Execute a workflow and print its JSON result, then exit with proper return code."""
    try:
        result: Result = func(*args, **kwargs)
        print(result.to_json())
        sys.exit(0 if result.ok else 1)
    except Exception as e:
        # Failsafe for unexpected generic exceptions
        fallback = Result(
            status="error",
            message=f"Catastrophic error in workflow: {str(e)}"
        )
        print(fallback.to_json())
        sys.exit(1)

def main():
    try:
        parser = argparse.ArgumentParser(description="Agent Tools CLI - Industrial Grade Git Workflows")
        subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-commands")

        # Command: git
        git_parser = subparsers.add_parser("git", help="Git workflow tools")
        git_subparsers = git_parser.add_subparsers(dest="subcommand", required=True, help="Git actions")

        # Command: git commit
        commit_parser = git_subparsers.add_parser("commit", help="Smart Commit Workflow")
        commit_parser.add_argument("--sense", action="store_true", help="Sense working tree status")
        commit_parser.add_argument("--plan", type=str, help="Commit plan JSON string to execute")

        # Command: git sync
        sync_parser = git_subparsers.add_parser("sync", help="Smart Sync Workflow")
        sync_parser.add_argument("--point", type=str, default="init", choices=["init", "current_rebase", "rebase_main", "push"], help="Pipeline stage to start/resume from")
        sync_parser.add_argument("--abort", action="store_true", help="Abort in-progress rebase")

        # Command: gh
        gh_parser = subparsers.add_parser("gh", help="GitHub workflow tools")
        gh_parser.add_argument("--repo", type=str, help="Target repository (owner/repo)")
        gh_parser.add_argument("--pr", type=int, help="Pull Request number")
        gh_parser.add_argument("--branch", type=str, help="Feature branch name")
        
        gh_subparsers = gh_parser.add_subparsers(dest="subcommand", required=True, help="GitHub actions")

        # Command: gh pr
        pr_parser = gh_subparsers.add_parser("pr", help="Smart PR Creation Workflow")
        pr_parser.add_argument("--sense", action="store_true", help="Extract PR context")
        pr_parser.add_argument("--create", type=str, help="PR draft JSON (title, body) to execute")

        # Command: gh merge
        gh_merge_parser = gh_subparsers.add_parser("merge", help="Merge a PR.")
        gh_merge_parser.add_argument("--mode", choices=["sense", "validate", "verdict", "cleanup"], default="sense")
        gh_merge_parser.add_argument("--data", help="JSON data for restoration.")

        args = parser.parse_args()

        if args.command == "git":
            if args.subcommand == "commit":
                if args.sense:
                    execute_and_exit(run_commit_workflow, mode="sense")
                elif args.plan:
                    execute_and_exit(run_commit_workflow, mode="plan", plan_json_str=args.plan)
                else:
                    execute_and_exit(run_commit_workflow, mode="sense")

            elif args.subcommand == "sync":
                if args.abort:
                    execute_and_exit(run_sync_workflow, mode="abort")
                else:
                    execute_and_exit(run_sync_workflow, mode="sync", point=args.point)

        elif args.command == "gh":
            if args.subcommand == "pr":
                if args.create:
                    execute_and_exit(run_pr_create_workflow, mode="create", draft_json=args.create)
                else:
                    execute_and_exit(run_pr_create_workflow, mode="sense")
            
            elif args.subcommand == "merge":
                # Note: run_pr_merge_workflow needs to be imported and implemented
                from orchestrators.pr_merge import run_pr_merge_workflow
                execute_and_exit(
                    run_pr_merge_workflow, 
                    mode=args.mode, 
                    data_json=args.data
                )

    except SystemExit:
        # argparse calls sys.exit() on --help or parse errors; let it through.
        raise
    except Exception as e:
        # Catastrophic failure (e.g., import error, config corruption).
        fallback = Result(status="error", message=f"CLI startup error: {str(e)}")
        print(fallback.to_json())
        sys.exit(1)


if __name__ == "__main__":
    main()
