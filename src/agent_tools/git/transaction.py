from .client import run_git
from .types import GitCommandError


class GitTransaction:
    """Atomic transaction context manager with rollback support.

    Usage:
        with GitTransaction() as txn:
            # ... git operations ...
            if something_failed:
                txn.rollback()
                return error_result

    The transaction snapshots HEAD on entry. If __enter__ cannot capture the
    initial HEAD (e.g. empty repo with no commits), it raises GitCommandError
    immediately — it is unsafe to proceed without a rollback anchor.

    The rollback() method is fire-and-forget: individual rollback commands may
    fail silently (best-effort), but it will always attempt to restore HEAD.
    """

    def __init__(self):
        self.initial_head: str | None = None
        self.snapshot_hash: str | None = None
        self.aborted: bool = False

    def __enter__(self) -> "GitTransaction":
        # Record initial HEAD — this is the rollback anchor. Fail loudly if
        # we cannot capture it (e.g. brand-new repo with no commits yet).
        res = run_git(["rev-parse", "HEAD"])
        res.raise_on_error("Cannot capture HEAD snapshot for transaction rollback")
        self.initial_head = res.stdout.strip()

        # Create a dangling stash object as workspace snapshot (no-op if clean).
        snapshot_res = run_git(["stash", "create"])
        if snapshot_res.ok and snapshot_res.stdout.strip():
            self.snapshot_hash = snapshot_res.stdout.strip()

        return self

    def rollback(self, reason: str = "Unknown") -> None:
        """Attempt to restore repository to the pre-transaction state.

        Always fire-and-forget: failures during rollback are not re-raised,
        since the primary purpose is cleanup — we cannot recover from a
        failed rollback by raising another exception.
        """
        if self.aborted:
            return

        # Cancel any in-progress git operations (best-effort).
        run_git(["rebase", "--abort"])
        run_git(["merge", "--abort"])
        run_git(["cherry-pick", "--abort"])

        # Hard-reset to the pre-transaction HEAD.
        if self.initial_head:
            run_git(["reset", "--hard", self.initial_head])

        # Restore the workspace snapshot if we created one.
        if self.snapshot_hash:
            run_git(["stash", "apply", "--index", self.snapshot_hash])

        self.aborted = True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Auto-rollback on any unexpected exception that escapes the `with` block.
        # SystemExit is explicitly excluded — it signals an intentional process exit.
        if exc_type is not None and exc_type is not SystemExit:
            self.rollback(reason=str(exc_val))
        # Do not suppress the exception — let it propagate to the orchestrator.
        return None
