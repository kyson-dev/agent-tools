import json

from agent_tools.orchestrators.git_commit import git_commit_flow


def test_commit_flow_sense_dirty(temp_git_repo):
    temp_git_repo.create_branch("feat/test")
    temp_git_repo.create_file("change.txt", "content")

    res = git_commit_flow(point="sense")

    assert res.status == "handoff", f"Error: {res.message}"
    assert any(f["filepath"] == "change.txt" for f in res.details["changed_files"])
    assert "build_plan" in res.next_step


def test_commit_flow_execute_plan(temp_git_repo):
    temp_git_repo.create_branch("feat/execution")
    temp_git_repo.create_file("a.py", "print(1)")
    temp_git_repo.create_file("b.py", "print(2)")

    plan = {
        "commits": [
            {"files": ["a.py"], "message": "feat(test): add a"},
            {"files": ["b.py"], "message": "feat(test): add b"},
        ]
    }

    res = git_commit_flow(point="commit", plan_json_str=json.dumps(plan))

    assert res.status == "success", f"Error: {res.message}"
    # Verify history
    log = temp_git_repo.run(["log", "--format=%s"]).stdout
    assert "feat(test): add b\nfeat(test): add a" in log
