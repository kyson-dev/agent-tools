from git.client import run_git

def test_run_git_version_ok():
    result = run_git(["--version"])
    assert result.ok
    assert "git" in result.stdout.lower()

def test_run_git_bad_command():
    result = run_git(["this-command-does-not-exist"])
    assert not result.ok
    assert result.returncode != 0
