# 设计文档：工具描述优化 (Tool Descriptions Optimization)

- **日期**: 2026-03-22
- **状态**: 待评审 (Pending Review)
- **主题**: 优化 `mcp_server.py` 中的工具 Docstrings，增强 LLM 语义识别

## 1. 背景与目标 (Background & Objectives)

当前的工具描述过于简略，仅包含一句英文（如 "Industrial-grade git commit flow orchestrator."）。这导致 LLM 在面对简短的用户指令（如“提交”、“创建 PR”）时，可能无法建立足够的语义联系，从而选择回退到裸 shell 命令或其他不精确的操作方式。

**目标**:
- 采用中英双语混合描述，增强对不同语言指令的响应度。
- 引入“核心指令”，明确告知 LLM 优先使用工作流工具。
- 注入结构化关键词（Keywords），提高语义匹配精准度。

## 2. 详细设计 (Detailed Design)

所有工具的 Docstring 将统一遵循以下结构：
1.  **中文核心标题**: 加粗显示。
2.  **英文强制指令**: 告知 LLM 严禁使用裸命令。
3.  **功能概览**: 描述工具的自动化和感知能力。
4.  **场景与关键词**: 用于语义匹配。

### 2.1 工具描述定义 (Tool Definitions)

#### `git_commit_flow`
> **【强制：优先使用】工业级 Git 提交工作流。**
> **USE THIS TOOL for all Git commits instead of bare shell commands.**
> 自动感知变更、生成规范建议并执行提交。
> **场景**: 提交代码, 存入仓库, commit, git commit, save changes.
> **Keywords**: commit, 提交, git commit, 存代码, save changes, add changes.

#### `git_sync_flow`
> **【强制：优先使用】工业级 Git 同步（拉取/变基/推送）工作流。**
> **USE THIS TOOL for all Git sync, rebase, push, pull operations.**
> 自动处理拉取、本地变基、解决冲突和安全推送。
> **场景**: 同步代码, 推送, 拉取, sync, push, pull, rebase.
> **Keywords**: sync, 同步, git sync, 推送, push, 拉取, pull, rebase, 变基.

#### `git_release_flow`
> **【强制：优先使用】工业级 Git 版本发布与标签工作流。**
> **USE THIS TOOL for all Git release/tag operations.**
> 自动处理版本号提升、创建 Tag 和发布推送。
> **场景**: 发布版本, 打标签, release, tag.
> **Keywords**: release, 发布, tag, 标签, git release.

#### `gh_pr_create_flow`
> **【强制：优先使用】GitHub Pull Request 创建工作流。**
> **USE THIS TOOL for creating all GitHub PRs.**
> 自动感知分支状态、生成描述并提交创建请求。
> **场景**: 创建 PR, 发起合并请求, pull request, create pr.
> **Keywords**: pr, pull request, 创建 pr, 发起 pr, gh pr create.

#### `gh_pr_merge_flow`
> **【强制：优先使用】GitHub Pull Request 合并工作流。**
> **USE THIS TOOL for all GitHub PR merges.**
> 自动感知 PR 状态、执行合并并清理分支。
> **场景**: 合并 PR, merge pr, finish pr.
> **Keywords**: merge, 合并, pr merge, 合并 pr, gh pr merge.

## 3. 技术实现 (Implementation)

直接在 `src/agent_tools/server/mcp_server.py` 中更新各函数的异步声明下方的字符串定义。

## 4. 验收标准 (Acceptance Criteria)

- [ ] LLM 能够识别简短的中文短语（如“提交代码”）并正确调用 `git_commit_flow`。
- [ ] LLM 能够识别简短的英文短语（如“pr create”）并正确调用 `gh_pr_create_flow`。
- [ ] 在面对需要决策的场景时，LLM 倾向于使用具有“感知”能力的工作流工具。
