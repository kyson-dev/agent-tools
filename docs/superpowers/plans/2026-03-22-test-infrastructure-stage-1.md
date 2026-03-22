# Industrial-Grade Test Infrastructure (Stage 1) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, isolated Git sandbox for integration testing using `pytest` fixtures and a helper utility.

**Architecture:** Use `pytest.fixture` with `tmp_path` to create isolated Git repositories. Leverage `agent_tools.context.REPO_CWD` to direct tool calls to these temporary repositories. Provide a `GitTester` class for easy state manipulation.

**Tech Stack:** Python 3.13, pytest, git

---

## Chunk 1: Infrastructure & Fixtures

### Task 1: Create `GitTester` Helper

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the GitTester class**

```python
import subprocess
from pathlib import Path

class GitTester:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

    def create_file(self, path: str, content: str = "test content"):
        full_path = self.repo_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def add(self, files: list[str] = ["."]):
        self.run(["add"] + files)

    def commit(self, message: str):
        self.run(["commit", "-m", message])

    def create_branch(self, name: str):
        self.run(["checkout", "-b", name])
```

- [ ] **Step 2: Commit infrastructure helper**

```bash
git add tests/conftest.py
git commit -m "test(infra): add GitTester helper class"
```

### Task 2: Implement `temp_git_repo` Fixture

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add pytest fixture**

```python
import pytest
from agent_tools.context import REPO_CWD

@pytest.fixture
def temp_git_repo(tmp_path):
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Init git
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    
    # Set context
    token = REPO_CWD.set(str(repo_path))
    yield GitTester(repo_path)
    REPO_CWD.reset(token)
```

- [ ] **Step 2: Commit fixture**

```bash
git add tests/conftest.py
git commit -m "test(infra): implement temp_git_repo fixture with REPO_CWD support"
```

## Chunk 2: Verification

### Task 3: Write Smoke Test

**Files:**
- Create: `tests/test_infra.py`

- [ ] **Step 1: Write the smoke test**

```python
from agent_tools.git.client import run_git
from agent_tools.context import REPO_CWD

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
```

- [ ] **Step 2: Run verification tests**

Run: `pytest tests/test_infra.py`
Expected: 2 passed

- [ ] **Step 3: Commit verification**

```bash
git add tests/test_infra.py
git commit -m "test(infra): add smoke tests for test infrastructure"
```
