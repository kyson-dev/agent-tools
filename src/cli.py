import argparse
import sys

from protocol import Result
from orchestrators import (
    run_commit_workflow,
    run_sync_workflow,
    run_pr_workflow,
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
        gh_subparsers = gh_parser.add_subparsers(dest="subcommand", required=True, help="GitHub actions")

        # Command: gh pr
        gh_subparsers.add_parser("pr", help="Sense PR creation context (owner, repo, commits)")

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
                execute_and_exit(run_pr_workflow, mode="sense")

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
