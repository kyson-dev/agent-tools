# 设计文档：项目结构重组 (Project Structure Reorganization)

- **日期**: 2026-03-22
- **状态**: 待评审 (Pending Review)
- **主题**: 重组 `agent-tools` 代码库，采用紧凑服务型 (Compact Service-Oriented) 架构

## 1. 背景与目标 (Background & Objectives)

当前 `agent-tools` 的项目结构虽然功能完整，但随着工具集的扩展，核心业务逻辑（Orchestrators）、底层基础设施（Git/GitHub Clients）以及接口适配层（MCP Server）的边界变得模糊。

**目标**:
- 采用整洁架构 (Clean Architecture) 原则。
- 分离“业务大脑”与“执行手脚”。
- 建立清晰、可预测且符合现代 Python 规范的目录布局。

## 2. 详细设计 (Detailed Design)

### 2.1 目录结构变更 (Directory Structure Mapping)

我们将 `src/agent_tools` 内部划分为三个顶级区域：

1.  **`core/` (业务大脑)**: 包含领域模型和编排逻辑。
2.  **`infrastructure/` (执行手脚)**: 包含底层客户端集成、配置加载和上下文管理。
3.  **`server/` (接口适配层)**: 仅包含 MCP 协议相关的接入逻辑。

| 原始文件/目录 | 新路径 | 说明 |
| :--- | :--- | :--- |
| `protocol.py` | `core/models/workflow.py` | 定义 Result 等协议实体。 |
| `orchestrators/` | `core/orchestrators/` | 业务流编排器。 |
| `git/` | `infrastructure/clients/git/` | Git 底层操作库。 |
| `gh/` | `infrastructure/clients/github/` | GitHub 底层操作库。 |
| `config.py` | `infrastructure/config/manager.py` | 配置加载与校验。 |
| `context.py` | `infrastructure/config/context.py` | 上下文变量定义。 |
| `configs/` | `infrastructure/config/resources/` | yaml/json 配置文件。 |
| `server.py` | `server/mcp_server.py` | MCP Server 入口。 |

### 2.2 配置与依赖变更 (Configuration Changes)

- **`pyproject.toml`**:
    - `[project.scripts]` 更新为 `kyson-mcp-agent-tools = "agent_tools.server.mcp_server:main"`。
    - `[tool.setuptools.package-data]` 更新为 `agent_tools = ["infrastructure/config/resources/*.yaml", "infrastructure/config/resources/*.json"]`。

- **导入路径**:
    - 全局更新导入语句，例如 `from agent_tools.orchestrators import ...` -> `from agent_tools.core.orchestrators import ...`。

## 3. 迁移方案 (Migration Plan)

1.  **准备阶段**: 创建所有目标文件夹。
2.  **文件迁移**: 按映射关系移动物理文件。
3.  **导入修复**: 使用批量替换或 IDE 工具修复导入路径。
4.  **环境更新**: 运行 `pip install -e .` 以应用新的入口点和包元数据。
5.  **验证阶段**: 运行测试套件。

## 4. 风险与对策 (Risks & Mitigations)

- **导入冲突**: 可能会遗漏部分深层引用。对策：使用 `ruff` 或 `mypy` 进行全量静态扫描。
- **打包资源丢失**: 相对路径变更可能导致打包后找不到 `rules.yaml`。对策：在 `manager.py` 中使用 `Path(__file__).parent / "resources" / ...` 进行定位。

## 5. 验收标准 (Acceptance Criteria)

- [ ] 所有 `tests/` 下的测试用例全部通过。
- [ ] `ruff` 和 `mypy` 检查无错误。
- [ ] `kyson-mcp-agent-tools` 命令在本地环境中可正常启动并响应。
