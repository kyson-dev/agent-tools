import subprocess
from pathlib import Path

import pytest

from agent_tools.infrastructure.config.context import REPO_CWD


class GitTester:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git"] + args, cwd=self.repo_path, capture_output=True, text=True)

    def create_file(self, path: str, content: str = "test content"):
        full_path = self.repo_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def add(self, files: list[str] | None = None):
        if files is None:
            files = ["."]
        self.run(["add"] + files)

    def commit(self, message: str):
        self.run(["commit", "-m", message])

    def create_branch(self, name: str):
        self.run(["checkout", "-b", name])


@pytest.fixture
def temp_git_repo(tmp_path):
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Init git
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

    # Create dummy rules to avoid loader issues
    rules_dir = repo_path / ".agent" / "configs"
    rules_dir.mkdir(parents=True)
    (rules_dir / "rules.yaml").write_text("git: {}\n")

    # Initial commit to ensure HEAD exists
    (repo_path / ".gitkeep").touch()
    subprocess.run(
        ["git", "add", ".gitkeep", ".agent/configs/rules.yaml"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo_path, check=True)

    # Set context
    token = REPO_CWD.set(str(repo_path))
    yield GitTester(repo_path)
    REPO_CWD.reset(token)
