import re

from agent_tools.config import (
    get_commit_allowed_types,
    get_commit_body_wrap_length,
    get_commit_max_groups,
    get_commit_message_regex,
    get_commit_subject_max_length,
    load_rules,
)

from .client import run_git
from .transaction import GitTransaction
from .types import GitCommitResult


def validate_plan(plan: dict, rules: dict) -> tuple[bool, str]:
    """Validates the structure and content of the commit plan against rules.yaml."""
    if "commits" not in plan or not isinstance(plan["commits"], list):
        return False, "Plan must contain a 'commits' array."

    # --- Max groups check ---
    max_groups = get_commit_max_groups()
    if len(plan["commits"]) > max_groups:
        return (
            False,
            f"Plan contains {len(plan['commits'])} commit groups, max allowed is {max_groups}.",
        )

    allowed_types = get_commit_allowed_types()
    regex_pattern = get_commit_message_regex()
    subject_max = get_commit_subject_max_length()
    body_wrap = get_commit_body_wrap_length()

    for idx, commit in enumerate(plan["commits"]):
        if (
            "files" not in commit
            or not isinstance(commit["files"], list)
            or len(commit["files"]) == 0
        ):
            return (
                False,
                f"Commit at index {idx} must contain a non-empty 'files' array.",
            )
        if "message" not in commit or not isinstance(commit["message"], str):
            return False, f"Commit at index {idx} must contain a message string."

        msg = commit["message"]
        lines = msg.split("\n")
        subject = lines[0]

        # --- Subject length check ---
        if len(subject) > subject_max:
            return False, (
                f"Commit at index {idx}: subject is {len(subject)} chars, "
                f"max allowed is {subject_max}."
            )

        # --- Regex validation (subject only) ---
        if regex_pattern and not re.match(regex_pattern, subject):
            return (
                False,
                f"Commit message at index {idx} ('{subject}') fails regex validation.",
            )

        # --- Allowed types check (subject only) ---
        if allowed_types:
            msg_type = subject.split(":")[0].split("(")[0]
            if msg_type not in allowed_types:
                return (
                    False,
                    f"Commit message at index {idx} uses disallowed type '{msg_type}'.",
                )

        # --- Body wrap length check ---
        # Body starts after the first blank line following the subject
        body_lines = lines[1:]
        for line_num, line in enumerate(body_lines):
            if len(line) > body_wrap:
                return False, (
                    f"Commit at index {idx}: body line {line_num + 1} is {len(line)} chars, "
                    f"max allowed is {body_wrap}."
                )

    return True, ""


def execute_commit_plan(plan: dict) -> GitCommitResult:
    """
    Executes a structured commit plan safely within a transaction.
    Returns the final GitCommitResult object.
    """
    rules = load_rules()

    # 1. Validate
    is_valid, err_msg = validate_plan(plan, rules)
    if not is_valid:
        return GitCommitResult(ok=False, message=err_msg)

    # 2. Atomic Execution
    executed = []
    with GitTransaction() as txn:
        try:
            # Clear staging area — must succeed or the subsequent add/commit
            # will operate on a stale/corrupt index.
            reset_res = run_git(["reset"])
            if not reset_res.ok:
                txn.rollback()
                return GitCommitResult(
                    ok=False,
                    message=f"Failed to reset staging area: {reset_res.stderr}",
                )

            for idx, commit_chunk in enumerate(plan["commits"]):
                # Stage files
                add_res = run_git(["add"] + commit_chunk["files"])
                if not add_res.ok:
                    txn.rollback()
                    return GitCommitResult(
                        ok=False,
                        message=f"Failed to add files for chunk {idx}: {add_res.stderr}",
                    )

                # Commit
                commit_result = run_git(["commit", "-m", commit_chunk["message"]])
                if not commit_result.ok:
                    txn.rollback()
                    return GitCommitResult(
                        ok=False,
                        message=f"Commit failed for chunk {idx}: {commit_result.stderr}",
                    )

                new_hash_res = run_git(["rev-parse", "HEAD"])
                executed.append(
                    {
                        "hash": new_hash_res.stdout.strip(),
                        "message": commit_chunk["message"],
                        "files": commit_chunk["files"],
                    }
                )

            return GitCommitResult(
                ok=True,
                message="All commits executed successfully.",
                executed_commits=executed,
            )

        except Exception as e:
            txn.rollback()
            return GitCommitResult(
                ok=False, message=f"Unexpected execution error: {str(e)}"
            )
