# Orchestrator Integration Tests (Stage 2) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full-chain integration tests for `git_commit_flow` and `git_sync_flow` using the Stage 1 sandbox infrastructure.

**Architecture:** Use the `temp_git_repo` fixture to create realistic Git scenarios and verify that orchestrators produce the correct `Result` objects and physical side effects in the repository.

**Tech Stack:** Python 3.13, pytest

---

## Chunk 1: Refactoring & Base Tests

### Task 1: Refactor `tests/test_git_client.py`

**Files:**
- Modify: `tests/test_git_client.py`

- [ ] **Step 1: Rewrite git client tests using sandbox**

```python
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
```

- [ ] **Step 2: Run and verify**

Run: `pytest tests/test_git_client.py`
Expected: PASS

## Chunk 2: `git_commit_flow` Integration

### Task 2: Implement `tests/test_git_commit_flow.py`

**Files:**
- Create: `tests/test_git_commit_flow.py`

- [ ] **Step 1: Test `sense` with dirty tree**

```python
import json
from agent_tools.orchestrators.git_commit import git_commit_flow

def test_commit_flow_sense_dirty(temp_git_repo):
    temp_git_repo.create_file("change.txt", "content")
    
    res = git_commit_flow(point="sense")
    
    assert res.status == "handoff"
    assert any(f["filepath"] == "change.txt" for f in res.details["changed_files"])
    assert "build_plan" in res.next_step
```

- [ ] **Step 2: Test `commit` execution**

```python
def test_commit_flow_execute_plan(temp_git_repo):
    temp_git_repo.create_file("a.py", "print(1)")
    temp_git_repo.create_file("b.py", "print(2)")
    
    plan = {
        "commits": [
            {"files": ["a.py"], "message": "feat: add a"},
            {"files": ["b.py"], "message": "feat: add b"}
        ]
    }
    
    res = git_commit_flow(point="commit", plan_json_str=json.dumps(plan))
    
    assert res.status == "success"
    # Verify history
    log = temp_git_repo.run(["log", "--format=%s"]).stdout
    assert "feat: add b\nfeat: add a" in log
```

- [ ] **Step 3: Run and verify**

Run: `pytest tests/test_git_commit_flow.py`
Expected: PASS (or reveal bugs to fix)

## Chunk 3: `git_sync_flow` Integration

### Task 3: Implement `tests/test_git_sync_flow.py` (Local)

**Files:**
- Create: `tests/test_git_sync_flow.py`

- [ ] **Step 1: Test `init` on fresh repo**

```python
from agent_tools.orchestrators.git_sync import git_sync_flow

def test_sync_flow_init_no_remote(temp_git_repo):
    # Default branch is usually main or master after git init
    res = git_sync_flow(point="init")
    
    # Should probably handoff to push or just finish if no remote
    assert res.status in ["success", "handoff"]
```

- [ ] **Step 2: Run and verify**

Run: `pytest tests/test_git_sync_flow.py`
Expected: PASS

---

## Final Review & Cleanup

- [ ] **Step 1: Run all tests**
Run: `make test`
- [ ] **Step 2: Commit all Stage 2 tests**
```bash
git add tests/
git commit -m "test(orchestrator): implement Stage 2 integration tests for commit and sync flows"
```
