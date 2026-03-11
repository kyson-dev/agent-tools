from dataclasses import dataclass
from typing import Optional, List, Dict

class GitCommandError(Exception):
    """Exception raised when a git command fails."""
    def __init__(self, command: List[str], stderr: str, context: str = ""):
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
    command: List[str]
    
    @property
    def ok(self) -> bool:
        """Check if git command was successful."""
        return self.returncode == 0
    
    def raise_on_error(self, context: str = ""):
        """Raise GitCommandError if command failed."""
        if not self.ok:
            raise GitCommandError(self.command, self.stderr, context)

@dataclass
class BranchContext:
    """Represents the current git branch state."""
    current_branch: Optional[str]
    is_detached: bool
    upstream: Optional[str]
    ahead: int
    behind: int
    is_dirty: bool

@dataclass
class RepoContext:
    """Represents the repository-wide metadata."""
    primary_remote: Optional[str]
    remote_url: Optional[str]
    owner: Optional[str]
    repo: Optional[str]
    default_branch: str
    all_remotes: List[str]

@dataclass
class FileStatus:
    """Represents the git status of a single file."""
    status_code: str
    filepath: str

@dataclass
class DiffSummary:
    """Represents the summary of changes in the repository."""
    changed_files: List[FileStatus]
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
    executed_commits: List[Dict] = None

