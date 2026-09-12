# GitNexus in the AI Development Workflow

GitNexus is the shared code-intelligence layer for AI coding agents on repositories where architectural context matters. It complements, rather than replaces, repository instructions such as `AGENTS.md` and `CLAUDE.md`.

## Position in the toolchain

Use the layers together:

1. **Repository policy and engineering rules** — `AGENTS.md`, `CLAUDE.md`, project docs and ADRs.
2. **Structural code intelligence** — GitNexus knowledge graph, dependency graph, call chains, execution flows and impact analysis.
3. **Coding agent** — Codex, Claude Code, Cursor, OpenCode or another MCP-capable agent.
4. **Git workflow** — issue -> branch -> implementation -> tests -> review -> PR -> merge.

GitNexus should be the preferred context layer for medium/large repositories, unfamiliar repositories, cross-module work, refactors, API changes and debugging across call chains. It is optional for small, isolated edits where repository-wide structural analysis adds little value.

## Licensing boundary

The upstream GitNexus OSS repository currently uses the **PolyForm Noncommercial License 1.0.0**.

- Personal, research and other permitted non-commercial use can follow the OSS workflow below.
- Do **not** standardize the OSS build for company/commercial repositories until the applicable commercial or enterprise GitNexus licensing has been approved.
- Keep the integration opt-in in this bootstrap so installing the normal coding-agent toolchain does not silently introduce a commercial-use licensing dependency.

## Install

GitNexus requires Node.js/npm.

From the reproducible developer shell repository:

```powershell
pwsh -NoProfile -File .\scripts\Install-AgentClis.ps1 -IncludeGitNexus
```

Or as part of the full workstation bootstrap:

```powershell
.\install.ps1 -IncludeGitNexus
```

Upgrade the coding agents and GitNexus together:

```powershell
.\install.ps1 -IncludeGitNexus -Upgrade
```

The installer deliberately warns and skips GitNexus if npm is not available instead of breaking the rest of the workstation bootstrap.

## One-time agent setup

Run once after installation:

```powershell
gitnexus setup
```

GitNexus auto-detects supported coding agents and configures their MCP integration. To limit configuration to specific agents:

```powershell
gitnexus setup -c codex,claude,cursor
```

For Codex, use either the GitNexus setup route or the GitNexus Codex plugin route, not both, to avoid duplicate hooks.

## Per-repository indexing

From the repository root:

```powershell
gitnexus analyze
```

For repositories where generated area-specific agent skills are useful:

```powershell
gitnexus analyze --skills
```

For deeper statement-level dependency/taint analysis on security-sensitive or complex data-flow work:

```powershell
gitnexus analyze --pdg
```

Re-run analysis after meaningful code changes, branch switches, merges, rebases or pulls when the index becomes stale. GitNexus hooks can surface stale-index warnings in supported agents, but the repository index remains a local artifact that must match the working tree being analyzed.

## Required agent workflow for larger changes

For cross-module changes, refactors, shared types, API contracts, data models, authentication/authorization code, or other high-blast-radius work, agents should use GitNexus before editing:

1. **Explore** — locate the relevant functional area and execution flow with graph-backed search/context.
2. **Impact** — inspect upstream/downstream dependencies and likely blast radius before changing a public symbol or contract.
3. **Trace** — inspect call paths when behavior spans multiple modules.
4. **Implement** — make the smallest coherent change on the task branch.
5. **Validate** — run project tests plus GitNexus change/impact checks where applicable.
6. **Re-index** — refresh the graph after meaningful structural changes.
7. **Review** — use graph-backed review/impact information as an additional reviewer signal; it does not replace tests, static analysis, security review or human approval gates.

Useful GitNexus capabilities include `query`, `context`, `impact`, `trace`, `detect_changes`, `route_map`, `tool_map`, `shape_check`, `api_impact`, and graph queries. Repositories indexed with `--pdg` can additionally use statement-level dependence and taint-oriented analysis.

## Multi-agent rule

All coding agents should consume the **same repository index** rather than building agent-specific understandings of the same codebase. The goal is one structural source of truth that Codex, Claude Code, Cursor and other agents query through MCP.

This keeps parallel agents aligned on:

- symbols and ownership boundaries;
- callers/callees and dependency direction;
- execution flows;
- affected modules and processes;
- API producers and consumers;
- architectural clusters.

Agent-specific prompts and skills may differ, but the code graph should remain shared.

## Relationship to `AGENTS.md` and generated skills

`AGENTS.md` remains the authoritative project-specific instruction layer for engineering policy, task conventions, testing expectations, approvals and repository behavior.

GitNexus supplies structural context. During analysis it can create/update context files and agent skills; when a repository contains `.agents/`, GitNexus can mirror its skills there so Codex-compatible agents can consume them. Generated GitNexus context should therefore augment repository governance, not overwrite custom engineering policy.

When adopting GitNexus in a project template, keep custom policy in clearly owned sections/files and treat generated GitNexus material as generated context.

## PR / issue workflow

For governed projects:

```text
GitHub Issue / task
        |
        v
feature branch
        |
        v
GitNexus explore + impact analysis
        |
        v
agent implementation
        |
        v
tests + static/security checks
        |
        v
GitNexus detect_changes / review
        |
        v
Pull Request
        |
        v
independent reviewer / approval gates
        |
        v
merge
```

The existing approval rules still apply: agents may plan, edit, test and commit on branches, while destructive operations, production changes, secrets/permissions changes, releases/deployments and merges remain subject to the project's approval policy.

## Adoption recommendation

Use GitNexus by default when any of the following is true:

- the repository is large or unfamiliar;
- multiple agents are working in parallel;
- the task crosses package/module/service boundaries;
- a shared API, schema, type or contract is changing;
- a refactor can affect many callers;
- debugging requires following a call chain or execution path;
- architecture documentation or codebase onboarding is needed.

For a tiny, well-contained edit, agents can skip graph analysis when the overhead would exceed the value, but normal tests and repository policies still apply.
