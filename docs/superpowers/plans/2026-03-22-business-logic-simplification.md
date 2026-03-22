# 业务逻辑精简实施计划 (Business Logic Simplification)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精简 `mcp_server.py`，移除冗余的仓库探测逻辑，完全依赖环境变量 `AGENT_TOOLS_REPO_PATH`。

**Architecture:** 简化接口层适配器，移除不必要的参数。

**Tech Stack:** Python 3.13, FastMCP, Pytest.

---

## Chunk 1: 接口层重构与签名更新

**Files:**
- Modify: `src/agent_tools/server/mcp_server.py`

- [ ] **Step 1: 简化 `_with_cwd` 函数**
  - [ ] 移除所有优先级探测逻辑。
  - [ ] 仅保留对 `AGENT_TOOLS_REPO_PATH` 环境变量的获取和到 `os.getcwd()` 的回退。
  - [ ] 代码应如下：
    ```python
    async def _with_cwd(func: Callable, ctx: Context | None, *args, **kwargs):
        final_path = os.environ.get("AGENT_TOOLS_REPO_PATH") or os.getcwd()
        token = REPO_CWD.set(os.path.abspath(final_path))
        try:
            return func(*args, **kwargs)
        finally:
            REPO_CWD.reset(token)
    ```

- [ ] **Step 2: 更新所有工具函数签名**
  - [ ] 对以下函数移除 `repo_path: str = "."` 参数：
    - `git_commit_flow`
    - `git_sync_flow`
    - `git_release_flow`
    - `gh_pr_create_flow`
    - `gh_pr_merge_flow`
  - [ ] 更新对应的 `_with_cwd` 调用，移除 `repo_path=repo_path` 传参。
  - [ ] 更新 Docstrings，增加说明：“该工具在环境变量 AGENT_TOOLS_REPO_PATH 定义的仓库中运行”。

- [ ] **Step 3: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: simplify _with_cwd and remove repo_path parameter"`

---

## Chunk 2: 入口点简化与依赖清理

**Files:**
- Modify: `src/agent_tools/server/mcp_server.py`

- [ ] **Step 1: 简化 `main` 函数**
  - [ ] 移除 `argparse` 解析逻辑。
  - [ ] 移除 `sys.path.insert` 动态路径注入逻辑。
  - [ ] 代码应如下：
    ```python
    def main():
        """Main entry point for the MCP server."""
        mcp.run(transport="stdio")
    ```

- [ ] **Step 2: 清理导入**
  - [ ] 移除 `import argparse`。

- [ ] **Step 3: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: simplify main function and remove argparse"`

---

## Chunk 3: 测试适配与验证

**Files:**
- Modify: `tests/`

- [ ] **Step 1: 更新测试套件调用**
  - [ ] 在 `tests/` 下所有文件中，移除对工具函数调用时的 `repo_path` 参数传递。
  - [ ] 重点检查 `test_gh_pr_create_flow.py`, `test_git_commit_flow.py`, `test_git_sync_flow.py`。

- [ ] **Step 2: 运行全量测试**
  - [ ] 运行: `pytest tests/`

- [ ] **Step 3: 验证环境变量驱动**
  - [ ] 在设置 `AGENT_TOOLS_REPO_PATH` 和不设置时分别验证工具行为。

- [ ] **Step 4: 提交更改**
  - [ ] 运行: `git commit -m "test: adapt tests to new tool signatures and verify logic"`
