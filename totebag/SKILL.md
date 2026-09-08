---
name: totebag-knowledge
description: >-
  totebag is your persistent, second memory. Once this skill is loaded, route all work-related
  knowledge (facts, decisions, progress, tasks, docs, links, assets, tools) through the `totebag`
  CLI rather than keeping it only in your ephemeral context window: restore context at the start
  of a task, and write back what you learn as you go. Backed by a local, cloud, or remote store.
  Vendor-neutral - works from any agent that can run a shell command.
---

# totebag - portable project knowledge over a CLI

`totebag` is a portable project-knowledge store. Its backend (the **sink**) may be a local
directory, cloud object storage (S3/GCS), or a remote server - **you never need to know
which**. A store holds one or more **workspaces**; a workspace holds many **projects**. Every
node - workspace, project, doc, asset, task, tool - carries a **description**. A project also has
**docs** (markdown), **notes**, **links**, **assets** (files), **tools/skills** it needs, and a
**task list** (future work to pick up later).

## totebag is your second memory - route all work through it

Once this skill is loaded, treat totebag as your **persistent memory** for everything
work-related. Your own context window is ephemeral and will be lost between sessions; totebag is
not. So, for the rest of this session:

- **Start from totebag.** Before doing any work, restore what's already known -
  `totebag project use <id>` then `totebag project context` (and `totebag search "<keywords>"` if you
  don't know the project). Don't re-derive what a past session already wrote down.
- **Write back as you go.** The moment you learn a durable fact, make a decision, hit a gotcha, or
  finish a step, persist it immediately - a **note** for scratch/short-lived context, a **doc**
  for anything worth keeping, a **task** to defer future work for later.
  Capture it while it's in hand, not at the end.
- **Nothing important stays only in your head.** If a future session or a different agent would
  need it, it must live in totebag, not just in this conversation.
- **Keep it honest.** Refresh descriptions when content changes, prune notes that no longer apply,
  and drop tasks as you finish them, so the store stays high-signal.

That is the whole point: a memory that survives the session, the tool, and the vendor. Use it like
one. The rest of this guide is the mechanics.

## Access rule: the CLI is the only door

**Do everything through the `totebag` CLI. Never read, write, or inspect the store's files
directly** - do not `cat`, `ls`, `find`, or edit paths under the store, and do not assume it
lives on the local filesystem. The sink may be a remote server with no files to reach. Every
create, read, update, delete, and search is a `totebag` command. (Passing a *local* file to
`asset add` or a destination to `asset download` is fine - those are your files, not the store's.)

## The description rule (non-negotiable)

**Everything you store must carry a description you write, or the store rejects it.** Every
`workspace`, `project`, `doc`, `asset`, `task`, task attachment, and `tool` requires a
`--description`. This keeps `project context` and progressive discovery high-signal - the
description is what the next agent skims first. Empty descriptions fail with exit code 1.

The **sink** (backend) is set by `$TOTEBAG_ROOT`; the **active workspace** by `$TOTEBAG_WORKSPACE`
or `-w/--workspace`, otherwise the store's configured default. Assume both are already configured
unless the user says otherwise - run `totebag config` to see the active sink and workspace.

## Output: set agent mode for machine-readable JSON

Commands print **terse, human-readable text by default**, and `--help` is rich-formatted for
humans. The CLI auto-detects a pipe: piped/redirected output drops the rich formatting to plain
text on its own.

**If your tool runs commands in a pseudo-terminal (PTY) - output is _not_ piped - the CLI sees a
TTY and emits rich boxes/color.** In that case set **`TOTEBAG_AGENT_MODE=1`** once in your
environment: all `--help` becomes plain text and every command emits **JSON**. Not sure whether
you're piped? Just set it - it's harmless when you already are.

## Deleting: always pass `--confirm`

Every destructive command (`delete` on any node, e.g. `project delete`, `note delete`, `tool delete`)
prompts for confirmation and **aborts on non-interactive stdin** - so without the flag your call
fails and deletes nothing. Always pass **`--confirm`** to delete non-interactively, e.g.
`totebag -p prj_xxx project delete --confirm`.

For a one-off JSON result, pass **`--json`** on the call (any position):
`totebag project get --json`. List commands then return a JSON array; `project get`,
`doc get`, and `search` return JSON objects.

## At the start of a task: restore context

```bash
totebag config                       # active sink, workspace, AND project
totebag workspace list               # workspaces in this store (each holds its own projects)
totebag project list                 # projects in the ACTIVE workspace (find the prj_… id)
totebag project use prj_xxx          # make it the active project for this workspace
totebag project context              # <- READ THIS. Full knowledge blob for the active project.
```

**The active project.** Project-scoped commands do not take a project id argument; they act on
the **active project**, resolved as: `-p/--project <id>` flag → `TOTEBAG_PROJECT` env → the
workspace's configured default (`totebag project use <id>`). The project must belong to the active
workspace. Set it once with `project use` (or `-p`) and then omit it everywhere. `totebag config`
shows the active project and where it came from.

Projects are scoped to the **active workspace**. Work in another with `-w <wsp_id>` on any
command, or switch the default with `totebag workspace use <wsp_id>`; create one with
`totebag workspace create --name "<name>" --description "<what it's for>"`.

There are three ways to read a project - pick by how much you need:

- **`totebag project context`** - the **restore blob**: description, instructions, **tools/skills**,
  notes, links, every doc, the asset inventory, and the **open task list**, assembled
  into one markdown document. This is what you read to rehydrate a project. Start here.
- **`totebag project get`** - the project's **own record** (fields + instructions) as terse text or
  JSON. It does not walk every child's content. Use it when you want the project metadata, not the
  whole blob.
- **`totebag project get --brief`** - **progressive discovery**: just `id + description`, cheap. Add
  **`--recursive`** to also list every child (docs, notes, links, lists, assets, tools, tasks) as
  `id + description`, so you can survey what exists and then fetch only the items you actually need.
  The same `--brief` / `--recursive` work on `workspace get` (each project's description).

```bash
totebag project   context                           # full restore blob - read this first
totebag project   get                               # the project's own fields/instructions
totebag project   get --brief --recursive           # active project + each child's id + description
totebag workspace get --brief --recursive           # active workspace + each project's description
```

Rule of thumb: **`context` to work, `--brief --recursive` to survey, `get` for the record.**

If you don't know which project, `totebag search "<keywords>"` locates hits across all
projects and tells you which `prj_…` they live in. Target a one-off project without changing the
default by prefixing any command with `-p <prj_id>`.

## The project's tools and skills

The context blob lists the tools and skills this project depends on. Add tools as you discover the
project needs them - a tool is just an asset with a tool/skill category, so it can be a named
dependency or carry an uploaded file (a script, a binary) you pull back later. `tool` mirrors
`asset`:

```bash
totebag tool add --name "stripe-cli" --description "calls the Stripe API" --type tool
totebag tool add ./scripts/deploy.sh --name deploy --description "one-shot deploy" --type skill
totebag tool list            # one summary row per tool; [file] marks tools carrying a file
totebag tool get tol_xxx     # the full detail for one tool
totebag tool download tol_xxx ./deploy.sh
```

## Park future work on the task list

A task is a **note to your future self** - something worth doing later that you are deliberately
**postponing**, not a tracker for what you're doing right now. Use it to hand off a follow-up,
a deferred implementation, or a known gap to the next session (or a different agent), so the
intent isn't lost when this context is. Don't log in-progress work here; put durable findings in
**notes**/**docs** and only what's genuinely outstanding on the list. **Remove each task the
moment it's done** so the list only ever shows real, still-open future work:

```bash
totebag task add    --title "Wire webhooks" --description "handle Stripe retries"
totebag task attach tsk_yyy ./payload.json --description "sample webhook payload"
totebag task list                                 # what's left to do (title + description)
totebag task get    tsk_yyy                        # one task in full: its detail (body) + attachments
totebag task download tsk_yyy ast_zzz ./payload.json   # pull an attachment back out (id from `task get`)
totebag task delete tsk_yyy --confirm             # drop it once done
```

Each task keeps its own attachments, so a task carries its own working files with it.

## While working: write knowledge back

Capture durable facts so the next session (or a different LLM) inherits them. Prefer the
lightest type that fits:

```bash
totebag note add "Deploys run from CI only; never push to main."
totebag link add --url https://... --name "Runbook" --type documentation
totebag doc  add --title "Incident 2026-09 postmortem" --description "root-cause & fix" --stdin < notes.md
totebag asset add ./architecture.pdf --name "Arch diagram" --description "v2 topology"
```

- **note** - a short piece of text (self-describing; no `--description` needed). Good for durable
  one-line facts, and usable as lightweight, **temporary memory chunks** while you work - scratch
  context you jot down now and prune later. For anything worth keeping long-term, promote it to a **doc**.
- **link** - a URL (`--type generic|source_code|documentation|tool`); takes an optional `--description`.
- **doc** - an editable markdown document; `--description` is **required**.
- **asset** - an arbitrary file; `--description` is **required** (the bytes aren't inlined into context).

## Lists: named collections of entries, exportable as CSV

A **list** holds many **entries** (arbitrary key/value records). Use it for tabular collections -
prospects, endpoints, a checklist of accounts. Create the list with a `--name` and a **required**
`--description`, then add entries in **batches** as **JSONL** (one JSON object per line). There is
**no single-entry command** - always pass a batch. The store does **not** enforce a schema; keep
your keys consistent so the CSV lines up.

```bash
LST=$(totebag list create --name "Prospects" --description "Q3 target accounts")
printf '{"name":"Acme","tier":"A"}\n{"name":"Globex","region":"EU"}\n' | totebag list add "$LST" --stdin
totebag list add "$LST" --file more_rows.jsonl           # or from a file
totebag list get    "$LST"                               # metadata + entries
totebag list list                                        # all lists in the project
totebag list export "$LST"                               # CSV to stdout (columns = union of all keys)
totebag list export "$LST" --output prospects.csv        # or to a file
totebag list delete-entry "$LST" 0 --confirm             # drop one entry by 0-based index
totebag list delete "$LST" --confirm                     # delete the whole list
```

Entries have no id, so `delete-entry` removes by **0-based index** (the position shown in `list get`).
It prints the removed entry as a JSONL line, so you can add it straight back:
`totebag list delete-entry "$LST" 2 --confirm | totebag list add "$LST" --stdin`.

## Editing

Everything is editable. Update descriptions so `project context` stays high-signal.

A body edit stands on its own - `doc edit` changes the body and leaves the description as-is;
pass `--description "…"` when you also want to refresh it to match the new content.

```bash
totebag project update --description "One-paragraph what/why of this project."
totebag doc edit doc_yyy --description "What this document covers."     # description only
totebag doc edit doc_yyy --description "Revised: now covers X" --stdin < revised.md
totebag doc edit doc_yyy --stdin < typo-fix.md           # body-only; description unchanged
totebag note list ; totebag note delete 3 --confirm
```

## Conventions

- Keep every node's **description** current - it's what an agent skims first, and a stale
  description is worse than none. When you edit a doc body, refresh its description with
  `--description` if the change makes the old one wrong.
- Write knowledge that outlives the session (decisions, gotchas, where things live), not
  transient chatter.
- Keep the task list honest: it's for future work you're deferring, not work in progress; add a
  task to postpone something, remove it (`task delete`) when done.
- IDs are prefixed: `wsp_` workspace, `prj_` project, `doc_` doc, `lnk_` link, `ast_` asset, `tsk_` task, `tol_` tool.

## Keeping this skill current

This skill ships **inside** the `totebag` CLI. After the CLI is upgraded it may carry a newer
version of these instructions - refresh your local copy from the installed binary:

```bash
totebag --skill > "$(dirname "$0")/SKILL.md"    # or wherever your agent loads skills from
```

`totebag --skill` prints the bundled SKILL.md; re-read it after refreshing.

## Full command list

Run `totebag --help`, or any subgroup: `totebag project --help`, `totebag doc --help`, etc.
