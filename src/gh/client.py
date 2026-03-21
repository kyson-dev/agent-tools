import subprocess
from typing import List, Union
from git.types import GitResult

def run_gh(args: Union[List[str], str], check: bool = False) -> GitResult:
    """Wrapper for GitHub CLI commands returning unified GitResult."""
    cmd = ["gh"] + args if isinstance(args, list) else ["gh"] + args.split()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return GitResult(
            returncode=res.returncode,
            stdout=res.stdout,
            stderr=res.stderr,
            command=cmd
        )
    except subprocess.CalledProcessError as e:
        return GitResult(
            returncode=e.returncode,
            stdout=e.output or "",
            stderr=e.stderr or "",
            command=cmd
        )
    except Exception as e:
        return GitResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            command=cmd
        )
