# Kyson MCP Agent Tools

[![PyPI](https://img.shields.io/pypi/v/kyson-mcp-agent-tools)](https://pypi.org/project/kyson-mcp-agent-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Industrial-grade Git Workflow Agent Infrastructure** based on the Model Context Protocol (MCP).

---

## 🚀 Overview

`kyson-mcp-agent-tools` is a high-reliability MCP server designed to empower AI agents with professional Git and GitHub management capabilities. Unlike simple command wrappers, this tool implements a strict **L1-L2-L3 layered architecture** to ensure all agentic actions are safe, validated, and compliant with project standards.

## 🏗 Architecture (L1-L2-L3 Model)

Based on the core principles defined in our [ARCHITECTURE.md](./ARCHITECTURE.md):

1.  **L1 (Adapters)**: Atomic wrappers around Git and GitHub CLI. They handle the "dirty work" of command execution.
2.  **L2 (Orchestrators)**: Stateful business logic (e.g., Commit Plans, Sync Guards). They ensure semantic correctness and provide safe transaction-like operations.
3.  **L3 (Cognition)**: High-level Prompts and Flow definitions that align the AI's reasoning with the tool's capabilities.

## 📦 Quick Start

### For AI Users (via `uvx`)
The fastest way to use this tool in your MCP-compatible client (like Cursor or Claude CLI):

```json
{
  "mcpServers": {
    "agent-tools": {
      "command": "uvx",
      "args": ["kyson-mcp-agent-tools"]
    }
  }
}
```

### For Developers
```bash
# Clone the repository
git clone https://github.com/kyson-dev/agent-tools.git

# Set up environment
cd agent-tools
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .
```

## 🛡 Cascading Rules System

This tool features a unique 3-level configuration system that allows for granular control over agent behavior:

| Priority | Level | Path | Purpose |
| :--- | :--- | :--- | :--- |
| **1 (Highest)** | **Project** | `<repo_root>/.agent/configs/rules.yaml` | Per-project constraints (e.g., Mandatory Scopes). |
| **2** | **User** | `~/.agent/configs/rules.yaml` | User-wide global preferences. |
| **3 (Lowest)** | **Internal** | Inside package | Default sane fallback rules. |

### Example Rule Table (`rules.yaml`)
```yaml
git:
  commit:
    # Forces scope in commit message: feat(auth): add login
    message_regex: "^(feat|fix|docs|refactor)\\([a-z0-9._\\-]+\\): .{1,72}$"
    subject_max_length: 72
```

## 🤖 Available Workflows

### 1. Smart Commit Flow
*   **Action**: Automatically stages changes, analyzes diffs, and synthesizes a professional commit message.
*   **Constraint**: Validates against `rules.yaml` before every commit.

### 2. Guarded Sync Flow
*   **Action**: Safely pulls and pushes changes.
*   **Safety**: Automatically detects protected branches (e.g., `main`) and prevents direct commits/rebases unless permitted.

### 3. Automated PR Flow
*   **Action**: Senses differences between branches, generates PR descriptions, and executes creation.
*   **Merge**: Supports semantic squash-merging and branch cleanup.

## 🌐 CI/CD & Distribution

This project is built for automated distribution:
- **Build System**: PEP 517 compliant via `pyproject.toml`.
- **Auto-Publish**: Simply push a tag (e.g., `v0.1.0`) to GitHub to trigger the PyPI release workflow.

---

## 📄 License
MIT License. Created by [Kyson](https://github.com/kyson-dev).
