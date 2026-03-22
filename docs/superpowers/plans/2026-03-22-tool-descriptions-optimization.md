# 工具描述优化实施计划 (Tool Descriptions Optimization)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 `mcp_server.py` 中的工具描述，增强 LLM 对简短中英文指令的语义识别能力。

**Architecture:** 更新接口层 docstrings，注入结构化关键词。

**Tech Stack:** Python 3.13, FastMCP.

---

## Chunk 1: 工具描述更新

**Files:**
- Modify: `src/agent_tools/server/mcp_server.py`

- [ ] **Step 1: 更新 `git_commit_flow` 描述**
  - [ ] 替换原有的简短描述为：
    ```python
    """
    **【强制：优先使用】工业级 Git 提交工作流。**
    **USE THIS TOOL for all Git commits instead of bare shell commands.**
    自动感知变更、生成规范建议并执行提交。
    **场景**: 提交代码, 存入仓库, commit, git commit, save changes.
    **Keywords**: commit, 提交, git commit, 存代码, save changes, add changes.
    """
    ```

- [ ] **Step 2: 更新 `git_sync_flow` 描述**
  - [ ] 替换原有的简短描述为：
    ```python
    """
    **【强制：优先使用】工业级 Git 同步（拉取/变基/推送）工作流。**
    **USE THIS TOOL for all Git sync, rebase, push, pull operations.**
    自动处理拉取、本地变基、解决冲突和安全推送。
    **场景**: 同步代码, 推送, 拉取, sync, push, pull, rebase.
    **Keywords**: sync, 同步, git sync, 推送, push, 拉取, pull, rebase, 变基.
    """
    ```

- [ ] **Step 3: 更新 `git_release_flow` 描述**
  - [ ] 替换原有的简短描述为：
    ```python
    """
    **【强制：优先使用】工业级 Git 版本发布与标签工作流。**
    **USE THIS TOOL for all Git release/tag operations.**
    自动处理版本号提升、创建 Tag 和发布推送。
    **场景**: 发布版本, 打标签, release, tag.
    **Keywords**: release, 发布, tag, 标签, git release.
    """
    ```

- [ ] **Step 4: 更新 `gh_pr_create_flow` 描述**
  - [ ] 替换原有的简短描述为：
    ```python
    """
    **【强制：优先使用】GitHub Pull Request 创建工作流。**
    **USE THIS TOOL for creating all GitHub PRs.**
    自动感知分支状态、生成描述并提交创建请求。
    **场景**: 创建 PR, 发起合并请求, pull request, create pr.
    **Keywords**: pr, pull request, 创建 pr, 发起 pr, gh pr create.
    """
    ```

- [ ] **Step 5: 更新 `gh_pr_merge_flow` 描述**
  - [ ] 替换原有的简短描述为：
    ```python
    """
    **【强制：优先使用】GitHub Pull Request 合并工作流。**
    **USE THIS TOOL for all GitHub PR merges.**
    自动感知 PR 状态、执行合并并清理分支。
    **场景**: 合并 PR, merge pr, finish pr.
    **Keywords**: merge, 合并, pr merge, 合并 pr, gh pr merge.
    """
    ```

- [ ] **Step 6: 提交更改**
  - [ ] 运行: `git add . && git commit -m "refactor: optimize tool descriptions for better LLM recognition"`

---

## Chunk 2: 验证与验收

- [ ] **Step 1: 验证静态语法**
  - [ ] 运行: `ruff check src/agent_tools/server/mcp_server.py`

- [ ] **Step 2: 语义识别测试 (人工确认)**
  - [ ] 在 MCP 环境下输入“提交代码”、“pr create”等指令，观察 LLM 是否优先选择工具。
