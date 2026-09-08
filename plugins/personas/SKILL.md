---
name: personas
description: >-
  Turn totebag workspaces into scoped "persona" subagents. Each workspace's charter lives in totebag
  and generates a native Claude Code subagent — a role/persona (a department, a researcher, an editor,
  …) with its own private skills and a totebag-backed memory. Use when the user wants to set up
  personas, dispatch work to several in parallel, run a standup across them, or "become"/switch to a
  persona. Each persona restores its workspace, works in its scope, and writes results back — so any
  fresh spin-up carries the accumulated work.
---

# personas — scoped agents over a totebag memory

Model: **one totebag workspace = one persona** (a role — a department, a function, a specialist).
The workspace's **charter** (`workspace.instructions`) is the persona's identity/scope/rules and is
the portable source of truth. A generator turns each charter into a native Claude Code subagent at
`~/.claude/agents/<persona>.md`. You (the main session) are the **orchestrator**: you dispatch work to
persona subagents and synthesize — you do not do a persona's work inline.

Why this works with no resident state: every persona **writes back to its totebag workspace**, so
"carrying its work" is automatic — a fresh spin-up re-restores everything. A standup is just
*re-restore + report*.

## 1. Set up a persona

```bash
wsp=$(totebag workspace create --name marketing --description "GTM & demand gen")
totebag -w "$wsp" workspace update --stdin < marketing-charter.md   # the charter (identity/scope/rules)
totebag -w "$wsp" project create --name "Q3 GTM" --description "Q3 go-to-market plan"   # a workstream
```

A good charter states: role & mandate, scope (what's in/out), voice, and **escalation rules** (what
must come back to a human). Repeat per persona (engineering, legal, research, editing, …).

**Give a persona its skills.** Store each skill as a `skill`-category asset carrying its `SKILL.md`,
on any of the persona's projects — sync will materialize it to disk automatically (next step):

```bash
totebag -w "$wsp" -p <prj_id> tool add ./competitor-intel/SKILL.md \
  --name competitor-intel --description "competitor research skill" --type skill
```

## 2. Sync — generate the subagents (and restore their skills, isolated)

```bash
python <path-to>/plugins/personas/generate_agents.py      # agents + each persona's private skills
```

Sync does two things per persona: writes `~/.claude/agents/<persona>.md`, and **auto-restores its
skills, isolated to that agent** — downloads every skill-asset (that carries a file) across the
persona's projects to a PRIVATE dir `~/.claude/personas/<persona>/<skill>/SKILL.md` (**not** the
global `~/.claude/skills/`, so one persona's skills aren't visible to other agents or the main
session). The agent's system prompt lists them and it `Read`s the relevant one on demand. Global
skills you install normally (e.g. `totebag-knowledge`) stay shared. Pass `--no-skills` to skip.
Re-run whenever a charter or skill changes. Only workspaces **with a charter** become agents (the
default `init` workspace is skipped). Each generated agent is scoped to its workspace (`-w <wsp_id>`)
and carries the memory protocol (restore first, write back, stay in scope).

## 3. Orchestrate — fan out in parallel

When the user asks for work spanning personas, act as the orchestrator and spawn **one subagent per
persona in a single message** (so they run concurrently), then synthesize:

- `Agent(subagent_type="marketing",   prompt="<the marketing slice of the ask>")`
- `Agent(subagent_type="engineering", prompt="<the engineering slice>")`

Each agent restores its workspace, does the work in scope, **writes results back** (notes/docs/tasks),
and returns a summary. Do **not** grind a persona's work inline in the main session.

## 4. Standup — check in / switch

To run a standup, re-spawn each persona with: *"Restore your workspace and report status + next
step."* It reads its written-back state from totebag and reports — it always carries its work because
the work lives in the workspace, not the session. "Switching" to a persona is just spawning that
`subagent_type` (or, for a focused solo session, `totebag -w <wsp> workspace context` and adopt the
charter yourself).

## Notes
- **Scope discipline:** a persona that notices out-of-scope work should hand it back to you, not do
  it. The charter's escalation rules are prose the agent honors.
- **Other hosts (Codex, etc.):** the memory is portable — `totebag -w <wsp> workspace context`
  restores a persona's charter + workstreams, and write-back is the same CLI. Native parallel fan-out
  is Claude-Code-only for now.
- **The CLI is the only door** to the store — see the bundled `totebag --skill` (the totebag-knowledge
  guide) for restore/write-back mechanics and the description rule.
