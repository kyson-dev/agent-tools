from agent_tools.infrastructure.clients.git.client import run_git
from agent_tools.infrastructure.config.context import REPO_CWD


def test_infra_isolation(temp_git_repo):
    # Verify REPO_CWD is set correctly
    current_cwd = REPO_CWD.get()
    assert str(temp_git_repo.repo_path) == current_cwd

    # Verify git init worked
    res = run_git(["rev-parse", "--is-inside-work-tree"])
    assert res.ok
    assert res.stdout.strip() == "true"


def test_git_tester_helpers(temp_git_repo):
    temp_git_repo.create_file("a.txt", "hello")
    temp_git_repo.add()
    temp_git_repo.commit("feat: add a.txt")

    res = run_git(["log", "-n", "1", "--format=%s"])
    assert res.stdout.strip() == "feat: add a.txt"
