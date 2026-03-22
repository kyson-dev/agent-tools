from .client import run_git
from .git_types import CommitRecord


def get_commits_ahead(base: str) -> list[CommitRecord]:
    """Returns commits on HEAD that are not yet in `base`.

    Uses NUL-delimited records to safely handle multi-line commit bodies.

    Args:
        base: The reference to compare against (e.g., 'main', 'origin/main').

    Returns:
        A list of CommitRecord objects ordered from oldest to newest.

    Raises:
        GitCommandError: If the git log command fails.
    """
    # %x00 is NUL — used as the record separator (safe with multi-line bodies)
    # Format: hash NL subject NL body NUL
    res = run_git(
        [
            "log",
            f"{base}..HEAD",
            "--format=%H%n%s%n%b%x00",
            "--reverse",
        ]
    )
    res.raise_on_error(f"Failed to get commits ahead of '{base}'")

    raw = res.stdout.strip()
    if not raw:
        return []

    records = []
    for entry in raw.split("\x00"):
        entry = entry.strip()
        if not entry:
            continue
        lines = entry.split("\n", 2)
        commit_hash = lines[0].strip() if len(lines) > 0 else ""
        subject = lines[1].strip() if len(lines) > 1 else ""
        body = lines[2].strip() if len(lines) > 2 else ""
        if commit_hash:
            records.append(CommitRecord(hash=commit_hash, subject=subject, body=body))

    return records
