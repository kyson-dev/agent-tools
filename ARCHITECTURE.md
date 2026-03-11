# Architecture Design Guidelines

This document defines the core architectural principles, layering specifications, and inter-layer communication rules for the project. All contributors (human and AI) must adhere to these standards.

## 1. System Layering (The L1-L2-L3 Model)

The architecture strictly separates responsibilities into three layers plus a thin Entry Point. **Upward dependencies are prohibited** (L1 must not import L2; L2 must not import L3).

### **L3: The Cognitive Layer (Agent)**
- **Definition**: The AI model / LLM agent.
- **Responsibility**: Reasoning, intent interpretation, plan generation, conflict resolution.
- **Constraints**:
  - Must act as a "dumb consumer" of L2 capabilities. If an L2 orchestrator exists for an operation, L3 must not bypass it and call L1 directly.
  - Must strictly follow the `instruction` and `next_step`/`point` signals returned by L2.
  - **Stateless across calls**: L3 must not cache or memorize L2's internal state (e.g., a `point` value) to make cross-invocation decisions. Each call to L2 must be self-contained and driven only by the most recent L2 response.

### **L2: The Orchestration Layer (State Machines)**
- **Definition**: Domain-specific skill directors.
- **Responsibility**:
  - Translate high-level intents into sequenced atomic steps.
  - Enforce business rules, security guards, and pre-conditions.
  - Manage state transitions within multi-step operations.
  - Catch all L1 exceptions and translate them into standardized signals for L3.
- **Constraints**:
  - Must be stateless. State is maintained only via explicit resumption parameters (e.g., a `point` token passed in and out).
  - Must never perform raw I/O or low-level calls directly; all primitive execution must be delegated to L1.
  - Must never crash with unhandled exceptions; all outcomes must be expressed via the Communication Protocol.

### **L1: The Capability Layer (Base Utilities)**
- **Definition**: Foundation modules wrapping primitive APIs, SDKs, or raw OS commands.
- **Responsibility**:
  - Execute atomic, single-purpose functions.
  - Parse raw outputs into strongly-typed data structures.
  - Fail loudly by raising domain-specific Exceptions.
- **Constraints**:
  - Completely unaware of L2 and L3. Must not contain policy logic or skill state.
  - Must not import from orchestrators, protocol definitions, or any higher-level module.

### **Entry Point (CLI / MCP Adapter)**
- **Definition**: A thin routing layer that parses external input (CLI args, MCP requests) and dispatches to L2 orchestrators.
- **Responsibility**: Argument parsing, mode/subcommand routing, and converting L2 `Result` objects into external output (JSON, exit codes, etc.).
- **Constraints**:
  - Must contain zero business logic. It is a pure adapter.
  - Must not call L1 directly; all domain logic flows through L2.

---

## 2. Communication Protocols

### 2.1 L2 → L3 Protocol (The `Result` Contract)
Every L2 execution must resolve to a `Result` with one of three statuses:

| Status | Semantics | L3 Action |
|---|---|---|
| `success` | Workflow completed entirely | Report completion to user |
| `error` | Terminal failure, cannot proceed | Report failure; do not blindly retry with identical parameters |
| `paused` | Expected breakpoint requiring cognitive intervention | Follow `instruction`, then re-invoke L2 with the provided `point` |

**`paused` state obligations**: When returning `paused`, L2 must include:
- **`point`**: A resumption token indicating where to re-enter the pipeline.
- **`instruction`**: A natural-language imperative telling L3 exactly what to do.

**`skill` field obligation**: Every `Result` must include a `skill` identifier string, enabling L3 to correctly route responses when multiple skills coexist.

**Serialization constraint**: The `details` field of a `Result` must be fully JSON-serializable. Raw dataclass objects, class instances, or non-primitive types must be converted (e.g., via `dataclasses.asdict()`) before inclusion.

### 2.2 L1 → L2 Protocol (Dual-Mode Reporting)
L1 communicates outcomes to L2 via two mechanisms:

| Mechanism | When to Use | Example |
|---|---|---|
| **Return a typed Result object** (with `.ok` property) | For operations where partial failure is expected and L2 needs to branch on the outcome | `run_git(["rebase", ...])` returns `GitResult` with `.ok`, `.stderr` |
| **Raise a domain Exception** | For operations where failure is unrecoverable at L1's scope and L2 must catch it | `res.raise_on_error("context")` throws `GitCommandError` |

L2 is responsible for catching all L1 exceptions within a `try...except` block and converting them to structured `Result` objects. **L1 exceptions must never leak to L3.**

---

## 3. Design Patterns

### 3.1 The Stateless Pipeline Pattern
For complex multi-step L2 skills:
- Define distinct, sequential **Stages**.
- Use the `point` input parameter to determine the entry stage.
- On stage completion, advance the `point` variable to allow natural fall-through to the next stage.
- Any stage can independently halt and yield control back to L3 with the current `point`.
- **Stages must never call each other directly.** Stage A cannot invoke Stage C; it can only set `point` to let control flow naturally to Stage C.

### 3.2 Pre-condition Guarding (Fail Fast)
L2 orchestrators must validate all pre-conditions before any mutating action:
- Environment integrity (e.g., is the tool's runtime available?).
- Conflicting external state (e.g., leftover operations from other tools).
- Authorization / policy checks (e.g., protected resources).

If any guard fails, return `error` or `paused` immediately. Never proceed to execution.

### 3.3 Import Boundaries
- **Top-Down Only**: Entry Point → L2 → L1. Never the reverse.
- **Intra-package Relative Imports**: Modules within the same L1 package must use relative imports (e.g., `from .types import X`).
- **No Circularity**: No circular imports between packages, even at the same layer.

---

## 4. Anti-Patterns (What NOT to Do)

| Anti-Pattern | Why It's Dangerous |
|---|---|
| L3 directly calling L1 primitives when an L2 orchestrator exists | Bypasses all guards, rules, and state management |
| L2 returning `paused` without `point` and `instruction` | L3 has no way to know what to do next; leads to hallucinated recovery |
| L2 putting raw dataclass objects in `Result.details` | JSON serialization fails at the Entry Point boundary |
| L2 silently swallowing L1 errors (`try: ... except: pass`) | Masks failures; L3 believes success when state is corrupted |
| L2 stages calling each other like functions | Destroys the linear pipeline invariant; creates hidden control flow |
| L3 "remembering" a `point` from a previous, unrelated invocation | Resumes into an invalid state; the `point` is only valid in the context of its originating `paused` response |
| Entry Point containing business/policy logic | Violates separation; makes the system untestable and non-portable across CLI/MCP/API surfaces |
