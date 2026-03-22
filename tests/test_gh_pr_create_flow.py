from agent_tools.core.orchestrators.gh_pr_create import gh_pr_create_flow


def test_pr_create_init(temp_git_repo):
    res = gh_pr_create_flow(point="init")
    assert res.status == "handoff"
    assert res.workflow == "gh_pr_create"
    assert "git_sync_flow" in res.instruction


def test_pr_create_sense_no_remote(temp_git_repo):
    # Should fail because no remote is configured to determine owner/repo
    res = gh_pr_create_flow(point="sense")
    assert res.status == "error"
    assert "Cannot determine GitHub repository context." in res.message
