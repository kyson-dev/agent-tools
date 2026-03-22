import subprocess

from agent_tools.context import REPO_CWD
from agent_tools.git.types import GitResult


def run_gh(
    args: list[str] | str, check: bool = False, cwd: str | None = None
) -> GitResult:
    """Wrapper for GitHub CLI commands returning unified GitResult."""
    cmd = ["gh"] + args if isinstance(args, list) else ["gh"] + args.split()
    use_cwd = cwd or REPO_CWD.get()
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
