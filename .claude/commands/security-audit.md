---
description: Run the security-auditor agent for a full-repo audit (investigate by default, execute with approval)
argument-hint: [execute <numbers|all>]
allowed-tools: Agent
---

# Security audit

Launch the `security-auditor` subagent (defined in `.claude/agents/security-auditor.md`) to audit the repo. The agent has two modes: it investigates read-only by default and only applies fixes when re-invoked with explicit approval.

**Arguments (`$ARGUMENTS`)**
- empty → run **investigate** mode. The agent returns a findings report + numbered remediation plan and waits for approval.
- `execute <numbers>` (e.g. `execute 1,3,5`) → run **execute** mode against the listed plan items from the most recent investigate report.
- `execute all` → apply every item from the most recent plan.

## Steps

1. Use the `Agent` tool with `subagent_type: security-auditor`.
2. Build the prompt:
   - If `$ARGUMENTS` is empty: `"Run in investigate mode per your instructions. Return the full report ending with the approval line."`
   - If `$ARGUMENTS` starts with `execute`: pass it through as `"mode: execute, items: <rest of args>. Re-read the relevant files first, apply only the listed items, then write SECURITY.md per your instructions."`
3. Relay the agent's report to the user verbatim — do not re-summarize. The agent's output structure (What I checked / Findings / Proposed plan, or post-execute summary) is the contract.
4. After an investigate run, remind the user they can apply fixes with `/security-audit execute <numbers>` or `/security-audit execute all`. Do not auto-invoke execute mode.
5. After an execute run, do not commit or push — the agent already declines to do so. Tell the user to review `git status` and the new `SECURITY.md` themselves.
