---
name: skill-spec
description: The canonical specification for writing agent skill files. Read this before creating or editing any skill.
---

# Agent Skill Specification (V2)

This document defines the mandatory structure, style, and conventions for all `.md` skill files under `.agents/skills/`. Every skill file MUST conform to this specification.

---

## 1. YAML Frontmatter

Every skill file MUST begin with a YAML frontmatter block containing exactly these fields:

```yaml
---
name: <snake_case_identifier>
description: <One-line English summary of what this skill does>
---
```

### Field Rules

| Field | Required | Format | Purpose |
|---|---|---|---|
| `name` | **YES** | `snake_case`, lowercase, underscores only | Unique identifier. Must match the parent directory name. |
| `description` | **YES** | Single English sentence, ≤ 120 chars | **Critical**: The Agent runtime uses this field to index and match skills to user intent. Must be in **English** regardless of the body language. |

> [!CAUTION]
> Do NOT add arbitrary fields (e.g. `version`, `tags`, `triggers`). The Agent runtime only parses `description`. The `name` field is kept for human indexing. Use Git history for versioning.

---

## 2. Directory & File Structure

- Each skill lives in its own directory: `skills/<skill_name>/SKILL.md`
- The directory name MUST be `snake_case` (lowercase, underscores)
- Use a domain prefix to group related skills: `git_*`, `gh_*`, `deploy_*`, `test_*`
- The directory name serves as the skill identifier (e.g. `skills/git_smart_commit/` → skill `git_smart_commit`)
- Additional resources (scripts, examples, etc.) may be placed alongside `SKILL.md` in the same directory
- This spec file itself (`00_SKILL_SPEC.md`) is the only exception, placed at the `.agents/` root

---

## 3. Body Language Policy

- **Frontmatter `description`**: MUST be English (system contract)
- **Body content**: Choose ONE language per file and use it consistently. Do not mix languages within a single skill

---

## 4. Document Structure

Every skill body MUST follow this section order. Omit a section only if explicitly marked Optional.

```
# <Title>                         ← H1, human-readable name
## Objective                      ← What this skill achieves
## Constraints                    ← What the Agent MUST NOT do
## Prerequisites                  ← (Optional) Conditions before Step 1
## Steps                          ← The ordered execution procedure
## Acceptance Criteria            ← How to verify success
## Error Handling                 ← (Optional) Known failure recovery
```

### 4.1 Title (`# H1`)

- One line. Descriptive. No emoji.
- Example: `# Git Smart Sync Skill`

### 4.2 Objective (`## Objective`)

- 1–2 sentences. State the end-goal in concrete terms.
- Use present tense, declarative voice.

### 4.3 Constraints (`## Constraints`)

> [!IMPORTANT]
> This section is **mandatory** and comes BEFORE the steps. It is the guardrail that prevents the Agent from deviating.

- Use a numbered list of **imperative prohibitions**.
- Each item must start with "Do NOT" or "NEVER" or "MUST NOT".
- Reference specific tools, commands, or patterns to avoid.

Example:
```markdown
## Constraints
1. Do NOT use `gh pr create` or any `gh` CLI command. Use the `mcp_github_*` toolset exclusively.
2. Do NOT push directly to `main` or `master` without a PR.
```

### 4.4 Prerequisites (`## Prerequisites`) — Optional

- Bulleted checklist of objective, verifiable conditions.
- Agent should verify these before executing Step 1.

Example:
```markdown
## Prerequisites
- Working directory is the project root (contains `pyproject.toml`).
- No uncommitted changes in the working tree.
```

### 4.5 Steps (`## Steps`)

This is the core execution section. Rules:

1. **Numbered list only**. Use `### Step N: <Verb Phrase>` for each step.
2. **Imperative voice**. Every step title MUST begin with a verb: "Run", "Extract", "Verify", "Create", "Parse".
3. **Single responsibility**. One step = one action. If a step contains "and", split it.
4. **No nested branching**. If a step has complex `if/else` logic, either:
   - Extract it into a separate skill and reference it, or
   - Encapsulate it in a script the Agent runs.
5. **Max nesting: 2 levels**. A step (`###`) may contain sub-items (`-`), but no deeper.
6. **Inline code for all references**. Wrap all command names, file paths, field names, and tool names in backticks.

#### `// turbo` Annotation

The `// turbo` marker tells the Agent it may auto-run the **immediately following numbered step** without user approval. Placement rules:

```markdown
// turbo
3. Run `npm install` in the project root.
```

- The `// turbo` line MUST be placed **directly above the step number line**.
- It applies ONLY to the single step immediately below it.
- Use ONLY for steps that are provably safe (read-only, or idempotent non-destructive commands).

The `// turbo-all` marker may be placed once, anywhere in the Steps section, to auto-run ALL steps. Use only for purely read-only skills.

### 4.6 Acceptance Criteria (`## Acceptance Criteria`)

- Bulleted list of **observable, verifiable** outcomes.
- Each item must be a factual assertion the Agent can check (exit code, file existence, output content).
- Do NOT use subjective language ("it should work correctly").

Example:
```markdown
## Acceptance Criteria
- The `dist/` directory exists and contains at least one `.js` file.
- The build command exited with code `0`.
- No `ERROR` or `FATAL` lines appear in the build output.
```

### 4.7 Error Handling (`## Error Handling`) — Optional

- List known failure scenarios and their recovery actions.
- End with a catch-all: "For any unrecognized error, stop execution and report the full error output to the user."

---

## 5. Style Rules Summary

| Rule | Do | Don't |
|---|---|---|
| Section headings | `## Constraints` | `## ⚠️ 约束条件 (Constraints)` |
| Step titles | `### Step 1: Extract repo metadata` | `### Step 1` or `### 1. Maybe try to get info` |
| Prohibitions | "Do NOT run `git push` directly." | "Try to avoid pushing if possible." |
| References | `` `mcp_github_create_pull_request` `` | `the GitHub PR creation tool` |
| Language | Consistent single language per file | Mixed Chinese and English in the same file |
| Emoji | None in headings or structure | `🚀 执行步骤` |

---

## 6. Template

Copy this skeleton when creating a new skill:

```markdown
---
name: <domain>-<action>
description: <English one-liner describing what this skill does>
---

# <Human-Readable Title>

## Objective

<1–2 sentences: what is the end-goal.>

## Constraints

1. Do NOT <prohibited action 1>.
2. MUST NOT <prohibited action 2>.

## Prerequisites

- <Condition 1>.
- <Condition 2>.

## Steps

### Step 1: <Verb Phrase>

<Instruction body.>

### Step 2: <Verb Phrase>

<Instruction body.>

## Acceptance Criteria

- <Observable outcome 1>.
- <Observable outcome 2>.

## Error Handling

- If <known failure>: <recovery action>.
- For any unrecognized error: stop and report full output to the user.
```
