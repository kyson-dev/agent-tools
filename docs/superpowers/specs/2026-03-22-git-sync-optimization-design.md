# 设计文档：`git_sync` 逻辑加固与指令精细化 (Git Sync Optimization)

- **日期**: 2026-03-22
- **状态**: 待评审 (Pending Review)
- **主题**: 提升 `git_sync.py` 的自愈能力与 LLM 指令精准度

## 1. 背景与目标 (Background & Objectives)

当前的 `git_sync` 在处理复杂 Git 状态（如 Upstream 缺失、冲突处理）时，往往通过简单的报错来终止流程。这增加了 Agent 介入修复的难度。

**目标**:
- **自动修复 Upstream**: 解决新分支无法直接拉取的问题。
- **结构化指令**: 引导 LLM 进行高质量的冲突解决。
- **错误路径自愈**: 捕获典型 Git 错误并转化为带动作的 `handoff`。

## 2. 详细设计 (Detailed Design)

### 2.1 状态机增强 (State Machine Refinement)

引入一个更严谨的调度逻辑，优先检查当前的 Git 阻塞状态（Rebase/Merge in progress）。

| 状态节点 | 逻辑增强 |
| :--- | :--- |
| `INIT` | 增加对 `status` 的详细扫描，识别是否处于 `detached HEAD`。 |
| `CURRENT_REBASE` | **核心优化**: 检查 `upstream`。若无，则跳过 Pull 直接进入推送引导。 |
| `REBASE_MAIN` | 细化对默认分支的识别，增加 `fetch` 动作以确保远端状态最新。 |
| `PUSH` | 识别 `non-fast-forward` 错误，并给出“是否强制推送”的二次确认手势。 |

### 2.2 Upstream 自愈流程

1. 检测到 `branch_info.upstream` 为空。
2. 检查本地是否有 `ahead > 0` 的提交。
3. 如果有，返回 `handoff` 指令：`"检测到本地分支未关联远端。请执行 git_sync_flow(point='push')，我们将尝试执行推送并关联。"`。

### 2.3 指令模版规范 (Instruction Precision)

所有返回给 LLM 的指令必须包含：
- **CONTEXT (上下文)**: 解释当前处于同步的哪个阶段。
- **ACTION (必需动作)**: 明确 LLM 下一步要调用哪个工具及参数。
- **SAFETY (安全边界)**: 明确禁止执行的操作（如 `NEVER run git commit during rebase`）。

### 2.4 冲突解决指南 (Conflict Guidance)

当检测到冲突时，`instruction` 将被增强为：
> "检测到 [文件名] 存在冲突。请：
> 1. 使用 `read_file` 查看文件内容，寻找 `<<<<<<< HEAD` 标记。
> 2. 结合上下文逻辑手动修改文件以解决冲突。
> 3. 运行 `git add <file>`。
> 4. 完成后调用 `git_sync_flow(point='current_rebase')` 继续。"

## 3. 验收标准 (Acceptance Criteria)

- [ ] 本地新建分支（无远端）时，运行 `git_sync` 不再直接报错，而是引导推送。
- [ ] 冲突发生时，返回的 JSON 详情包含完整的冲突文件列表。
- [ ] 所有逻辑分支均覆盖了异常捕获，禁止直接向 LLM 抛出 Python Traceback。
