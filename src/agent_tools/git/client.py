import subprocess

from agent_tools.context import REPO_CWD

from .types import GitResult


def run_git(
    args: list[str] | str, check: bool = False, cwd: str | None = None
) -> GitResult:
    """Wrapper for git commands returning unified GitResult."""
    cmd = ["git"] + args if isinstance(args, list) else ["git"] + args.split()
    use_cwd = cwd or REPO_CWD.get()

    # Industrial Debugging
    import logging

    debug_logger = logging.getLogger("agent-tools")
    debug_logger.debug(
        f"[DEBUG] run_git: REPO_CWD ID: {id(REPO_CWD)}, Value: {REPO_CWD.get()}, Effective CWD: {use_cwd}"
    )

    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=check, cwd=use_cwd
        )
        return GitResult(
            returncode=res.returncode, stdout=res.stdout, stderr=res.stderr, command=cmd
        )
    except subprocess.CalledProcessError as e:
        return GitResult(
            returncode=e.returncode,
            stdout=e.output or "",
            stderr=e.stderr or "",
            command=cmd,
        )
    except Exception as e:
        return GitResult(returncode=-1, stdout="", stderr=str(e), command=cmd)
