# personas — a totebag plugin

Turn [totebag](../../README.md) workspaces into scoped **persona agents**. Each workspace's
**charter** lives in totebag and is projected into a native Claude Code subagent — a role/persona (a
department, a function, a specialist: marketing, engineering, researcher, editor, …) with its own
private skills and a totebag-backed memory. From one session you dispatch work to several personas in
parallel and run a standup across them — each restores its workspace, works in its scope, and writes
results back, so any fresh spin-up carries the accumulated work.

The plugin adds **no runtime of its own**: totebag is the memory, native subagents are the behaviour,
and the built-in Agent tool is the orchestrator. `personas` is the thin glue between them.

## Building on totebag

totebag already gives every **project** an `instructions` field (its charter) and a
`project context` restore blob. This plugin builds on the **symmetric primitive at the workspace
level**: a workspace carries `instructions` too — its persona charter (role, scope, voice, escalation
rules) — and `totebag workspace context` emits a cheap restore blob (the charter plus an index of the
workspace's projects). That primitive is the foundation:

- **Portable source of truth.** The charter lives *in the store*, not in a host config — readable by
  any agent over the totebag CLI, durable across sinks (file/S3/GCS/remote) and vendors.
- **One cheap bootstrap.** `workspace context` = charter + workstream index in a single call; the
  agent drills into a workstream with `project context` only when it works it.
- **"Carrying work" is free.** Because each agent writes progress/decisions/tasks back to its
  workspace, a standup is just *re-restore + report* — no long-lived processes, no lost state.

The plugin then **projects** each charter into a host-native agent definition. Generation lives here,
outside the CLI, so totebag stays vendor-neutral and only ever exposes the charter via
`workspace get` / `workspace context`.

## How it fits together

```
totebag store  (portable memory + charters)
  wsp_marketing   .instructions = "# Marketing Charter …"   ← source of truth
  wsp_research    .instructions = "# Research Charter …"
        │  generate_agents.py  (sync)
        ▼
~/.claude/agents/marketing.md      (system prompt = charter + memory protocol, scoped to wsp_marketing)
~/.claude/personas/marketing/…     (that persona's PRIVATE skills — not global)
        │  main session (orchestrator)
        ▼
Agent(subagent_type='marketing', task)  ┐  parallel fan-out
Agent(subagent_type='research',  task)  ┘  each: restore wsp → work → write back → summarize
standup: re-spawn each persona → it re-restores from totebag → reports status + next
```

- **Source of truth:** totebag (`workspace.instructions` = the charter). Edit once, re-run the
  generator to resync.
- **Behaviour:** native Claude Code subagents (`~/.claude/agents/*.md`) generated from the charter.
- **Skills (isolated per agent):** stored in totebag as `skill`-category assets (carrying their
  `SKILL.md`); sync **auto-restores** them to a private `~/.claude/personas/<persona>/` dir — not the
  global `~/.claude/skills/` — so a persona's skills aren't visible to other agents. The agent lists
  them in its prompt and `Read`s the relevant one on demand.
- **Orchestration:** the built-in Agent tool (`subagent_type=<persona>`), parallel calls.
- **Memory:** each agent writes back to its workspace via the totebag CLI.

## Pieces

| File | What |
|---|---|
| `SKILL.md` | The `personas` skill: set up personas, sync, orchestrate (fan-out), standup. |
| `generate_agents.py` | Reads totebag charters over the CLI → writes `~/.claude/agents/<persona>.md` and restores each persona's private skills. Only workspaces **with a charter** become agents. |
| `install.sh` | Installs the skill into `~/.claude/skills/` and syncs the agents. Safe/idempotent. |

## Quick start

```bash
# 1. a persona = a workspace with a charter
wsp=$(totebag workspace create --name marketing --description "GTM & demand gen")
totebag -w "$wsp" workspace update --stdin < marketing-charter.md
totebag -w "$wsp" project create --name "Q3 GTM" --description "Q3 go-to-market plan"   # a workstream

# 2. generate the subagent(s) + restore their private skills
python3 generate_agents.py            # -> ~/.claude/agents/marketing.md  (+ ~/.claude/personas/marketing/…)

# 3. in Claude Code, fan out from the main session
#    Agent(subagent_type="marketing", prompt="draft the Q3 GTM plan")
#    Agent(subagent_type="research",  prompt="size the EU market")
```

A good charter states role & mandate, scope (in/out), voice, and **escalation rules** (what must come
back to a human). Repeat per persona.

## Design notes

- **Charter as a workspace field, not a convention doc.** Storing the charter in a specially-named
  project/doc would force readers to hunt for it and make bootstrap expensive. A first-class
  `workspace.instructions` (symmetric with `project.instructions`, persisted as the `workspace.md`
  body) is the natural home and makes `workspace context` a single cheap call.
- **Generation outside the CLI.** Host agent files are Claude-specific; keeping the generator in the
  plugin (not in totebag) preserves totebag's vendor-neutrality. totebag only exposes the charter.
- **Skills isolated by convention.** Claude Code has no per-agent skill scoping — anything in
  `~/.claude/skills/` is global. So a persona's skills go to a private `~/.claude/personas/<persona>/`
  dir the agent `Read`s on demand, instead of the global namespace.
- **Scope yourself first.** A generated agent runs `export TOTEBAG_WORKSPACE=<wid>` before anything,
  so every command targets its workspace (project commands otherwise need both `-w` and `-p`).

## Other hosts (Codex, …)

The memory is portable: any agent can restore a persona with `totebag -w <wsp> workspace context` and
write back via the CLI. Native parallel fan-out is Claude-Code-only for now
(`generate_agents.py --format codex` is a stub).

## Limitations / not yet

- Personas don't yet carry their **own** shared tools/skills — skills are gathered from the persona's
  projects (until workspaces can hold assets directly).
- Skills are isolated by convention (a private per-persona dir the agent `Read`s on demand), since
  Claude Code has no per-agent skill scoping — they aren't auto-invoked via the Skill tool the way a
  global skill is. Auto-restore also assumes **one `SKILL.md` per skill**; multi-file skill folders
  and same-named skills across a persona's projects (last-write-wins) aren't handled yet.
- Non-skill tools (external CLIs) aren't auto-installed — the `restore` command was removed; a persona
  is told it needs them via `workspace context`.
- Escalation rules are prose the agent honours, not machine-enforced gates.
