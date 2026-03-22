from agent_tools.git.client import run_git


def test_run_git_in_sandbox(temp_git_repo):
    # Verify it runs in the isolated path
    res = run_git(["rev-parse", "--show-toplevel"])
    assert res.ok
    assert res.stdout.strip() == str(temp_git_repo.repo_path)


def test_run_git_status_empty(temp_git_repo):
    res = run_git(["status", "--porcelain"])
    assert res.ok
    assert res.stdout == ""
