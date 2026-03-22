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
- **清理 API**: 完全移除工具函数中的 `repo_path` 参数，强制调用方依赖环境配置。

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

### 2.2 工具函数签名更新 (Breaking Changes)

所有 `@mcp.tool()` 装饰的函数将进行以下变更：
- **移除 `repo_path` 参数**: 彻底从函数签名中删除该参数。
- **更新 Docstrings**: 在文档字符串中明确标注“该工具在环境变量 `AGENT_TOOLS_REPO_PATH` 定义的仓库中运行”。

### 2.3 `main` 函数与环境要求

```python
def main():
    """MCP server 纯净入口。"""
    mcp.run(transport="stdio")
```

**环境说明**:
- 移除 `sys.path.insert` 逻辑。
- 要求在开发/运行环境中通过 `pip install -e .` 安装包，或者正确设置 `PYTHONPATH` 环境变量。

## 3. 兼容性与风险 (Compatibility & Risks)

- **破坏性变更**: 显式依赖命令行参数 `-r` 或 `--repository` 的启动方式将失效。
- **API 变更**: 任何尝试传递 `repo_path` 参数的 MCP 调用都将失败。这是为了强制执行单一路径源原则。
- **风险**: 如果用户在非 Git 目录下且未设置环境变量时运行，工具将尝试在当前目录执行 Git 命令并报错。

## 4. 验收标准 (Acceptance Criteria)

- [ ] `mcp_server.py` 移除 `argparse` 和所有探测逻辑。
- [ ] 所有工具函数均不再包含 `repo_path` 参数。
- [ ] **回退验证**: 在未设置 `AGENT_TOOLS_REPO_PATH` 时，验证工具正确回退至 `os.getcwd()`。
- [ ] **注入验证**: 设置 `AGENT_TOOLS_REPO_PATH` 后，验证工具在指定路径运行。
- [ ] 现有的自动化测试在适配新签名后全部通过。

