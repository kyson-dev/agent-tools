from dataclasses import dataclass
from typing import Any


class GitCommandError(Exception):
    """Exception raised when a git command fails."""

    def __init__(self, command: list[str], stderr: str, context: str = ""):
        self.command = command
        self.stderr = stderr
        self.context = context
        msg = f"Git command failed: {' '.join(self.command)}\nError: {self.stderr}"
        if self.context:
            msg = f"{self.context} - {msg}"
        super().__init__(msg)


@dataclass
class GitResult:
    """Unified result type for git commands."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    command_cwd: str | None = None
    context_repo_cwd: str | None = None

    @property
    def ok(self) -> bool:
        """Check if git command was successful."""
        return self.returncode == 0

    def raise_on_error(self, context: str = ""):
        """Raise GitCommandError if command failed."""
        if not self.ok:
            # Industrial Debug: include CWD in error message
            debug_info = ""
            if self.command_cwd:
                debug_info += f"\n[INTERNAL-DEBUG] Effective CWD: {self.command_cwd}"
            if self.context_repo_cwd:
                debug_info += f"\n[INTERNAL-DEBUG] REPO_CWD: {self.context_repo_cwd}"

            # The GitCommandError constructor expects (command, stderr, context)
            # We are prepending the debug_info to the context.
            full_context = f"{context}{debug_info}" if context else debug_info
            raise GitCommandError(self.command, self.stderr, full_context)


@dataclass
class BranchContext:
    """Represents the current git branch state."""

    current_branch: str | None
    is_detached: bool
    upstream: str | None
    ahead: int
    behind: int
    is_dirty: bool


@dataclass
class RepoContext:
    """Represents the repository-wide metadata."""

    primary_remote: str | None
    remote_url: str | None
    owner: str | None
    repo: str | None
    default_branch: str | None
    all_remotes: list[str]


@dataclass
class FileStatus:
    """Represents the git status of a single file."""

    status_code: str
    filepath: str


@dataclass
class DiffSummary:
    """Represents the summary of changes in the repository."""

    changed_files: list[FileStatus]
    diff_summary: str
    repo_context: RepoContext


@dataclass
class CommitRecord:
    """Represents a single parsed commit from git log."""

    hash: str
    subject: str
    body: str


@dataclass
class GitCommitResult:
    """Represents the result of a multi-commit plan execution."""

    ok: bool
    message: str
    executed_commits: list[dict[str, Any]] | None = None
