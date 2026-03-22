from agent_tools.infrastructure.config.manager import (
    get_diff_max_lines_per_file,
    get_diff_max_total_lines,
)

from .client import run_git
from .git_types import DiffSummary, FileStatus
from .repo import get_repo_context


def get_git_status() -> list[FileStatus]:
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
    return "\n".join(head + [f"\n.. [TRUNCATED {omitted} lines] ..\n"] + tail)


def truncate_diff_per_file(diff_text: str, max_lines_per_file: int) -> str:
    """Truncates each file's diff independently to max_lines_per_file."""
    import re

    # Split on file boundaries: 'diff --git a/.. b/..'
    file_chunks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    result_chunks = []
    for chunk in file_chunks:
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        if len(lines) > max_lines_per_file:
            half = max_lines_per_file // 2
            head = lines[:half]
            tail = lines[-half:]
            omitted = len(lines) - max_lines_per_file
            chunk = "\n".join(
                head + [f"\n.. [TRUNCATED {omitted} lines in this file] ..\n"] + tail
            )
        result_chunks.append(chunk)
    return "\n".join(result_chunks)


def get_diff_summary() -> DiffSummary:
    """Returns the semantic summary of changed files and diff.

    Raises:
        GitCommandError: propagated from get_git_status / get_git_diff.
    """
    max_total_lines = get_diff_max_total_lines()
    max_per_file = get_diff_max_lines_per_file()

    status_data = get_git_status()
    unstaged_diff = get_git_diff(staged=False)
    staged_diff = get_git_diff(staged=True)

    combined_diff = staged_diff + "\n" + unstaged_diff
    # Step 1: per-file truncation
    per_file_truncated = truncate_diff_per_file(combined_diff, max_per_file)
    # Step 2: global total truncation
    truncated_diff = truncate_diff(per_file_truncated, max_total_lines)

    repo_ctx = get_repo_context()

    return DiffSummary(
        changed_files=status_data,
        diff_summary=truncated_diff,
        repo_context=repo_ctx,
    )
