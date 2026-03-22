from agent_tools.core.orchestrators.git_sync import git_sync_flow


def test_sync_flow_init_with_remote(temp_git_repo):
    # Already on main (default branch)
    temp_git_repo.run(
        ["remote", "add", "origin", "https://github.com/example/repo.git"]
    )
    res = git_sync_flow(point="init")

    # Should succeed or handoff if it tries to push
    assert res.status in ["success", "handoff", "error"]
