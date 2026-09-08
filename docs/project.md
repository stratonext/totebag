---
title: totebag
type: project
status: approved
tags: [project, overview, knowledge-store]
---

# totebag

**Portable, vendor-neutral project knowledge any AI Agent agent can restore over a CLI.**

## What it is

`totebag` is a project-knowledge store on disk (or S3/GCS) that any agent rehydrates with one
shell command. Your context shouldn't live inside one vendor's chat history - `totebag` keeps it
as a plain, human-readable, git-diffable tree that any AI Agent can read and write back to. No server,
no API keys, no lock-in.

One **workspace** holds many **projects**. Each project carries:

| Item | What | Summary |
|---|---|---|
| **summary / instructions** | one-paragraph what/why + standing guidance | - |
| **docs** | editable markdown documents | required |
| **notes** | one-line facts | self-summarizing |
| **links** | typed URLs (generic / source_code / documentation / tool) | - |
| **lists** | named collections of schema-free entries, exportable as CSV | required (description) |
| **assets** | arbitrary files (bytes not inlined into context) | required |
| **tools** | tools/skills the project needs (an asset by category; file optional) | required |
| **tasks** | future work to pick up later (deferred/postponed), each in its own folder with attachments | required |

## The core loop

An agent starting a task runs `totebag project context <id>` and gets a single markdown blob -
summary, instructions, tools/skills, notes, links, docs, assets, and the open task list. It
downloads any missing tool files, works the task list, and writes knowledge back as it learns. The next session (or a different LLM, or a different vendor) inherits all of it.

Two rules keep the store high-signal:

- **Everything stored is summarized by the caller, or rejected.** Every doc, asset, task,
  attachment, and tool requires a summary - the thing the next agent skims first.
- **The task list stays honest.** It holds future work to pick up later, not work in progress;
  add a task to defer something, and remove it when done.

## On-disk format

The tree is an **Open Knowledge Format (OKF) v0.2 bundle**: every item is a UTF-8 markdown
"concept" file with a YAML front-matter block whose `type` names its kind
(`project | note | link | document | list | asset | tool | task`).

```
$TOTEBAG_ROOT/
  config.yaml                       # store config (plain YAML): default_workspace
  workspaces/wsp_abc/
    workspace.md                    # container metadata + okf_version: "0.2" marker
    projects/prj_abc/
      project.md                    # type: project; notes/links/tools inline in frontmatter
      docs/doc_x.md                 # type: document
      lists/lst_w.md                # type: list; entries as JSONL body, exportable as CSV
      assets/ast_y/{report.pdf, asset.md}
      tasks/tsk_z/task.md           # type: task; attachments in tasks/tsk_z/assets/
```

(`index.md` progressive-disclosure files are optional in OKF v0.2 and not written; the CLI's
`… get --brief` serves that need from source-of-truth instead.)

All persistence routes through a single [`fsspec`](https://filesystem-spec.readthedocs.io)
filesystem - the "sink" - so the same bundle round-trips to `file://`, `s3://`, or `gcs://` with
zero extra code. Deploy the store wherever you want it to persist.

## Interface

`totebag` is **agent-driven**: it's a Typer CLI (`totebag --skill` prints the bundled SKILL.md that
teaches an agent the commands). Output is terse human text by default, or JSON under `--json` /
`TOTEBAG_AGENT_MODE=1`. Command groups: `project`, `note`, `link`, `doc`, `list`, `asset`, `task`,
`tool`, plus top-level `init`, `config` (shows the active sink and path), and `search`
(substring).

Stack: Python ≥3.11, `typer`, `pydantic` v2, `pyyaml`, `python-frontmatter`, `fsspec`
(optional `s3fs` / `gcsfs` extras).
