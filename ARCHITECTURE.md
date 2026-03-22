# Architecture & Skill Specification

This document defines the core architectural principles, layering specifications, and skill writing standards for the `agent-tools` project. All contributors (human and AI) must adhere to these standards.

---

## 1. System Layering (The L1-L2-L3 Model)

The architecture strictly separates responsibilities into three layers plus a thin Entry Point. **Upward dependencies are prohibited** (L1 must not import L2; L2 must not import L3).

### **L3: The Cognitive Layer (Agent/Actuator)**
- **Definition**: The AI model / LLM agent.
- **Responsibility**: Reasoning, intent interpretation, plan generation, synthesis (e.g., writing descriptions).
- **Secondary Role (Actuator)**: Acts as a bridge for tools that L2 cannot reach directly (if applicable).
- **Constraints**:
  - Must strictly follow the `instruction` and `resume_point` signals returned by L2.
  - **Stateless across calls**: L3 must not cache or memorize L2's internal state. Each call to L2 must be self-contained.

### **L2: The Orchestration Layer (State Machines)**
- **Definition**: Domain-specific skill directors and policy enforcers (e.g., `src/orchestrators/`).
- **Responsibility**:
  - Translate high-level intents into sequenced atomic stages.
  - **Decision Maker**: Owns all logic, policy guards, and pre-condition audits.
  - **Direct Mutation**: Performs all deterministic operations (e.g., `git` / `gh` mutations) directly.
  - Catch all L1 exceptions and translate them into standardized `Result` signals for L3.

### **L1: The Capability Layer (Base Utilities)**
- **Definition**: Foundation modules wrapping primitive APIs or raw OS commands (e.g., `src/git/`, `src/gh/`).
- **Responsibility**: Execute atomic, single-purpose functions and parse raw outputs into typed structures.

### **Entry Point (MCP Adapter)**
- **Definition**: `src/server.py` using FastMCP.
- **Responsibility**: Argument parsing, routing, and converting L2 `Result` objects into MCP tool/prompt outputs.

---

## 2. Communication Protocols

### 2.1 L2 → L3 Protocol (The `Result` Contract)
Every L2 execution must resolve to a `Result` with one of three statuses:

| Status | Semantics | L3 Action |
|---|---|---|
| `success` | Workflow completed | Report completion to user |
| `error` | Terminal failure | Report failure; do not retry with identical parameters |
| `handoff` | Expected breakpoint | Follow `instruction`, then re-invoke L2 at the `resume_point` |

---

## 3. Skill Specification (V2)

All workflow documentation under `skills/` MUST conform to this specification.

### 3.1 YAML Frontmatter
Every skill file MUST begin with:
```yaml
---
name: <snake_case_identifier>
description: <One-line English summary for Agent indexing>
---
```

### 3.2 Document Structure
1. **# <Title>**
2. **## Objective**: What this skill achieves.
3. **## Constraints**: Mandatory prohibitions (e.g., "Do NOT push to main").
4. **## Steps**: Numbered list using `### Step N: <Verb Phrase>`.
5. **## Acceptance Criteria**: Observable, verifiable outcomes.

---

## 4. Design Patterns & Style Rules

### 4.1 The Stateless Pipeline Pattern
- Define sequential **Stages**.
- Use `resume_point` to determine the entry stage.
- Stages must never call each other directly; flow is managed by the Result return.

### 4.2 Pre-condition Guarding (Fail Fast)
- Validate environment, authorization, and conflicting state before any mutating action.

### 4.3 `// turbo` Annotation
- Places `// turbo` directly above a step to permit auto-execution by the Agent without user approval (for safe, non-destructive steps).

---

## 6. MCP Tool Standards

To ensure high-quality semantic recognition by LLM agents, all tools exposed via the MCP Entry Point (`src/agent_tools/server/mcp_server.py`) MUST follow these documentation standards.

### 6.1 Bilingual Docstrings
Every tool MUST include a docstring with both Chinese and English descriptions to support diverse user intents.

### 6.2 Mandatory Components
1. **Core Mandate (Bold Chinese)**: A clear, bolded Chinese title indicating the tool's primary purpose.
2. **Force Directive (Uppercase English)**: A directive starting with `USE THIS TOOL...` to explicitly guide the LLM away from bare shell commands.
3. **Capability Overview**: A brief explanation of the tool's automation and "sensing" (L2 orchestration) abilities.
4. **Context Note**: Explicitly state that the tool operates on the repository path defined by the environment.
5. **Keywords**: A structured list of both English and Chinese keywords for semantic indexing.

### 6.3 Example Format
```python
@mcp.tool()
async def my_tool_flow(...):
    """
    **【强制：优先使用】核心任务标题。**
    **USE THIS TOOL for [Task Name] instead of bare shell commands.**
    自动感知状态、执行编排并返回结果。
    该工具在环境变量 AGENT_TOOLS_REPO_PATH 定义的仓库中运行。
    
    Keywords: [keyword1], [关键词2], ...
    """
```

