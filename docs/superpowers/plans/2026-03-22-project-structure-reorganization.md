# 项目结构重组实施计划 (Project Structure Reorganization)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `agent-tools` 重构为紧凑服务型 (Compact Service-Oriented) 架构，分离业务逻辑与基础设施。

**Architecture:** 采用整洁架构原则，分为 `core` (业务), `infrastructure` (基础设施), `server` (接口) 三层。采用绝对导入以提高稳定性。

**Tech Stack:** Python 3.13, FastMCP, Pytest, Ruff, Mypy.

---

## Chunk 1: 基础设施与配置重组

**Files:**
- Create: `src/agent_tools/core/__init__.py`, `src/agent_tools/infrastructure/__init__.py`, `src/agent_tools/server/__init__.py`
- Create: `src/agent_tools/infrastructure/config/__init__.py`, `src/agent_tools/infrastructure/config/resources/__init__.py`
- Create: `src/agent_tools/infrastructure/clients/__init__.py`
- Modify: `src/agent_tools/infrastructure/config/manager.py` (原 `config.py`)
- Modify: `src/agent_tools/infrastructure/config/context.py` (原 `context.py`)

- [ ] **Step 1: 创建目录结构与初始化文件**
  - [ ] 运行: `mkdir -p src/agent_tools/core/models src/agent_tools/core/orchestrators src/agent_tools/infrastructure/clients/git src/agent_tools/infrastructure/clients/github src/agent_tools/infrastructure/config/resources src/agent_tools/server`
  - [ ] 运行: `touch src/agent_tools/core/__init__.py src/agent_tools/core/models/__init__.py src/agent_tools/core/orchestrators/__init__.py src/agent_tools/infrastructure/__init__.py src/agent_tools/infrastructure/clients/__init__.py src/agent_tools/infrastructure/clients/github/__init__.py src/agent_tools/infrastructure/config/__init__.py src/agent_tools/infrastructure/config/resources/__init__.py src/agent_tools/server/__init__.py`

- [ ] **Step 2: 迁移配置文件**
  - [ ] 运行: `mv src/agent_tools/configs/* src/agent_tools/infrastructure/config/resources/`
  - [ ] 运行: `rmdir src/agent_tools/configs`

- [ ] **Step 3: 迁移并更新配置管理器**
  - [ ] 运行: `mv src/agent_tools/config.py src/agent_tools/infrastructure/config/manager.py`
  - [ ] 修改 `src/agent_tools/infrastructure/config/manager.py`:
    - 更新 `get_base_dir()`: `return Path(__file__).parent.parent.parent.parent.parent` (由于深度增加 2 层，从 3 个 `.parent` 增加到 5 个)
    - 更新 `get_internal_base_rules_path()`: `return Path(__file__).parent / "resources" / "rules.yaml"`
    - 更新 `get_schema_path()`: `return Path(__file__).parent / "resources" / "schema.json"`
    - 更新导入: `from .context import REPO_CWD` -> `from agent_tools.infrastructure.config.context import REPO_CWD` (改用绝对导入)

- [ ] **Step 4: 迁移并更新上下文变量**
  - [ ] 运行: `mv src/agent_tools/context.py src/agent_tools/infrastructure/config/context.py`

- [ ] **Step 5: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: reorganize infrastructure and configuration"`

---

## Chunk 2: 核心模型与底层客户端重构

**Files:**
- Create: `src/agent_tools/core/models/workflow.py` (原 `protocol.py`)
- Create: `src/agent_tools/infrastructure/clients/github/client.py` (原 `gh/client.py`)
- Modify: `src/agent_tools/infrastructure/clients/git/` (原 `git/`)

- [ ] **Step 1: 迁移领域模型**
  - [ ] 运行: `mv src/agent_tools/protocol.py src/agent_tools/core/models/workflow.py`

- [ ] **Step 2: 迁移 GitHub 客户端**
  - [ ] 运行: `mv src/agent_tools/gh/client.py src/agent_tools/infrastructure/clients/github/client.py`
  - [ ] 运行: `rm -rf src/agent_tools/gh`

- [ ] **Step 3: 迁移 Git 客户端**
  - [ ] 运行: `mv src/agent_tools/git/* src/agent_tools/infrastructure/clients/git/`
  - [ ] 运行: `rmdir src/agent_tools/git`

- [ ] **Step 4: 修复 Git 客户端内部导入**
  - [ ] 在 `src/agent_tools/infrastructure/clients/git/` 下所有文件中，将 `from . import ...` 或 `from agent_tools.git import ...` 更新为绝对导入 `from agent_tools.infrastructure.clients.git import ...`。
  - [ ] 更新对 `REPO_CWD` 的引用: `from agent_tools.infrastructure.config.context import REPO_CWD`。

- [ ] **Step 5: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: migrate core models and infrastructure clients"`

---

## Chunk 3: 编排器迁移与导入修复

**Files:**
- Modify: `src/agent_tools/core/orchestrators/` (原 `orchestrators/`)

- [ ] **Step 1: 迁移编排器目录**
  - [ ] 运行: `mv src/agent_tools/orchestrators/* src/agent_tools/core/orchestrators/`
  - [ ] 运行: `rmdir src/agent_tools/orchestrators`

- [ ] **Step 2: 批量修复编排器导入**
  - [ ] 将所有编排器文件中的 `from agent_tools.protocol import Result` 更新为 `from agent_tools.core.models.workflow import Result`。
  - [ ] 将 `from agent_tools.config import ...` 更新为 `from agent_tools.infrastructure.config.manager import ...`。
  - [ ] 将 `from agent_tools.git import ...` 更新为 `from agent_tools.infrastructure.clients.git import ...`。
  - [ ] 将 `from agent_tools.gh import ...` 更新为 `from agent_tools.infrastructure.clients.github import ...`。

- [ ] **Step 3: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: migrate orchestrators and fix imports"`

---

## Chunk 4: 接口层迁移与环境配置更新

**Files:**
- Modify: `src/agent_tools/server/mcp_server.py` (原 `server.py`)
- Modify: `pyproject.toml`

- [ ] **Step 1: 迁移 MCP Server**
  - [ ] 运行: `mv src/agent_tools/server.py src/agent_tools/server/mcp_server.py`

- [ ] **Step 2: 修复 MCP Server 导入**
  - [ ] 更新 `mcp_server.py` 中的所有导入路径为新的绝对路径。

- [ ] **Step 3: 更新项目元数据**
  - [ ] 修改 `pyproject.toml`:
    - `[project.scripts]` -> `kyson-mcp-agent-tools = "agent_tools.server.mcp_server:main"`
    - `[tool.setuptools.package-data]` -> `agent_tools = ["infrastructure/config/resources/*.yaml", "infrastructure/config/resources/*.json"]`

- [ ] **Step 4: 重新安装开发环境**
  - [ ] 运行: `pip install -e .`

- [ ] **Step 5: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: migrate server and update project metadata"`

---

## Chunk 5: 验证与清理

**Files:**
- Modify: `tests/`

- [ ] **Step 1: 修复测试套件导入**
  - [ ] 在 `tests/` 下所有文件中执行批量替换：
    - `from agent_tools.orchestrators` -> `from agent_tools.core.orchestrators`
    - `from agent_tools.protocol` -> `from agent_tools.core.models.workflow`
    - `from agent_tools.config` -> `from agent_tools.infrastructure.config.manager`
    - `from agent_tools.context` -> `from agent_tools.infrastructure.config.context`
    - `from agent_tools.server` -> `from agent_tools.server.mcp_server`

- [ ] **Step 2: 运行静态检查与自动修复**
  - [ ] 运行: `ruff check --fix src tests`
  - [ ] 运行: `mypy src tests`

- [ ] **Step 3: 运行自动化测试**
  - [ ] 运行: `pytest tests/`

- [ ] **Step 4: 最终提交**
  - [ ] 运行: `git commit -m "refactor: final cleanup and verification of project reorganization"`
