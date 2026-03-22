# 设计文档：业务逻辑精简 (Business Logic Simplification)

- **日期**: 2026-03-22
- **状态**: 待评审 (Pending Review)
- **主题**: 精简 `mcp_server.py` 中的 Git 仓库路径探测逻辑

## 1. 背景与目标 (Background & Objectives)

当前的 `mcp_server.py` 包含大量复杂的代码用于探测 Git 仓库路径（包括向上搜索 `.git`、解析命令行参数、探测 MCP Root 等）。在现代化的部署环境中，环境变量 `AGENT_TOOLS_REPO_PATH` 应该是路径定义的单一事实来源。

**目标**:
- 移除所有主动探测逻辑。
- 移除命令行参数解析（`argparse`）。
- 简化 `_with_cwd` 包装器，仅依赖环境变量或 CWD。

## 2. 详细设计 (Detailed Design)

### 2.1 `_with_cwd` 简化逻辑

重构后的 `_with_cwd` 将不再处理复杂的优先级，逻辑如下：

```python
async def _with_cwd(func: Callable, ctx: Context | None, *args, **kwargs):
    # 1. 优先获取环境变量
    final_path = os.environ.get("AGENT_TOOLS_REPO_PATH")
    
    # 2. 如果环境变量缺失，回退到当前进程工作目录
    if not final_path:
        final_path = os.getcwd()
    
    # 3. 注入上下文并执行业务逻辑
    token = REPO_CWD.set(os.path.abspath(final_path))
    try:
        return func(*args, **kwargs)
    finally:
        REPO_CWD.reset(token)
```

**注意**: 所有工具函数（如 `git_commit_flow`）中的 `repo_path` 参数将被标记为废弃（Deprecated）或直接移除，不再作为路径解析的输入。

### 2.2 `main` 函数简化

```python
def main():
    """MCP server 纯净入口。"""
    mcp.run(transport="stdio")
```

### 2.3 清理范围

- 移除 `import argparse`。
- 移除 `sys.path.insert` 动态路径注入逻辑（应由正确的包安装处理）。
- 更新所有 `@mcp.tool()` 定义，移除或忽略 `repo_path` 参数。

## 3. 兼容性与风险 (Compatibility & Risks)

- **破坏性变更**: 显式依赖命令行参数 `-r` 或 `--repository` 的启动方式将失效。
- **风险**: 如果用户在非 Git 目录下且未设置环境变量时运行，工具将尝试在当前目录执行 Git 命令并报错。这是预期行为，符合“显示失败”的原则。

## 4. 验收标准 (Acceptance Criteria)

- [ ] `mcp_server.py` 代码量显著减少。
- [ ] 环境变量 `AGENT_TOOLS_REPO_PATH` 能正确驱动工具运行。
- [ ] 现有的自动化测试在设置正确环境变量后依然通过。
