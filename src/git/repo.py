import re

from .client import run_git
from .types import RepoContext


def parse_remote_url(url: str):
    """Extract (owner, repo) from a remote URL (HTTP or SSH)."""
    if not url:
        return None, None

    clean_url = re.sub(r"(\.git)?/?$", "", url.strip())

    if "://" in clean_url:
        path = clean_url.split("://")[-1].split("/", 1)[-1]
    elif "@" in clean_url and ":" in clean_url:
        path = clean_url.split(":", 1)[-1]
    else:
        path = clean_url

    parts = path.split("/")
    if len(parts) >= 2:
        repo = parts[-1]
        owner = "/".join(parts[:-1])
        return owner, repo
    return None, None


def get_repo_context() -> RepoContext:
    """Returns repository-wide metadata.

    Raises:
        GitCommandError: if any required git command fails (fail-fast).
    """
    res = run_git(["rev-parse", "--is-inside-work-tree"])
    res.raise_on_error("Not inside a git work-tree")

    remote_names_res = run_git(["remote"])
    # `git remote` always exits 0 — even with no remotes. No raise needed.
    remote_names = [r for r in remote_names_res.stdout.splitlines() if r.strip()]

    primary_remote = None
    if remote_names:
        primary_remote = "origin" if "origin" in remote_names else remote_names[0]

    remote_url = None
    owner = None
    repo_name = None

    if primary_remote:
        url_res = run_git(["remote", "get-url", primary_remote])
        url_res.raise_on_error(f"Failed to get URL for remote '{primary_remote}'")
        remote_url = url_res.stdout.strip()
        owner, repo_name = parse_remote_url(remote_url)

    # --- Default branch detection ---
    default_branch = None
    if primary_remote:
        remote_head = run_git(
            ["symbolic-ref", f"refs/remotes/{primary_remote}/HEAD"]
        ).stdout.strip()
        if remote_head:
            default_branch = remote_head.split("/")[-1]

    if not default_branch:
        local_branches_res = run_git(["branch", "--format=%(refname:short)"])
        local_branches_res.raise_on_error("Failed to list local branches")
        local_branches = local_branches_res.stdout.splitlines()
        for b in ("main", "master", "develop", "production"):
            if b in local_branches:
                default_branch = b
                break

    return RepoContext(
        primary_remote=primary_remote,
        remote_url=remote_url,
        owner=owner,
        repo=repo_name,
        default_branch=default_branch or "main",
        all_remotes=remote_names,
    )
