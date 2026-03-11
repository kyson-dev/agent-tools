from typing import List

from .client import run_git
from .repo import get_repo_context
from .types import DiffSummary, FileStatus
from config import get_diff_max_total_lines


def get_git_status() -> List[FileStatus]:
    """Returns a list of changed files and their porcelain status codes.

    Raises:
        GitCommandError: if the status command fails.
    """
    result = run_git(["status", "-uall", "--porcelain"])
    result.raise_on_error("Failed to get git status")

    files = []
    for line in result.stdout.splitlines():
        if len(line) < 3:
            continue
        status_code = line[:2]
        filepath = line[3:].strip()
        files.append(FileStatus(status_code=status_code, filepath=filepath))
    return files


def get_git_diff(staged: bool = False) -> str:
    """Gets the diff for staged or unstaged changes.

    Raises:
        GitCommandError: if the diff command fails.
    """
    args = ["diff"]
    if staged:
        args.append("--cached")

    result = run_git(args)
    result.raise_on_error("Failed to generate git diff")
    return result.stdout


def truncate_diff(diff_text: str, max_lines: int) -> str:
    """Truncates diff text to a maximum number of lines to save tokens."""
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text

    half = max_lines // 2
    head = lines[:half]
    tail = lines[-half:]
    omitted = len(lines) - max_lines
    return "\n".join(head + [f"\n... [TRUNCATED {omitted} lines] ...\n"] + tail)


def get_diff_summary() -> DiffSummary:
    """Returns the semantic summary of changed files and diff.

    Raises:
        GitCommandError: propagated from get_git_status / get_git_diff.
    """
    max_total_lines = get_diff_max_total_lines()

    status_data = get_git_status()
    unstaged_diff = get_git_diff(staged=False)
    staged_diff = get_git_diff(staged=True)

    combined_diff = staged_diff + "\n" + unstaged_diff
    truncated_diff = truncate_diff(combined_diff, max_total_lines)

    repo_ctx = get_repo_context()

    return DiffSummary(
        changed_files=status_data,
        diff_summary=truncated_diff,
        repo_context=repo_ctx,
    )
