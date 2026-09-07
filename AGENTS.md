# totebag

Portable, vendor-neutral project-knowledge store any AI Agent restores over a CLI. No server, no API keys. Persists to a single fsspec "sink" (`file://`, `s3://`, `gcs://`) as an **Open Knowledge Format (OKF) v0.2** bundle of markdown-with-frontmatter files.

## Commands

```bash
uv sync                        # install (add --extra s3 / --extra gcs for cloud sinks)
uv run pytest -q               # run tests
totebag --skill                 # print SKILL.md (the agent-facing command guide)
```

`TOTEBAG_ROOT` (or `--root`) picks the sink; defaults to `file://~/.totebag`. `TOTEBAG_WORKSPACE` (or `-w`/`--workspace`) overrides the active workspace; otherwise the store's configured default is used (set by `totebag init` / `totebag workspace use`, recorded in `<root>/config.yaml`). `TOTEBAG_PROJECT` (or `-p`/`--project`) overrides the active project; otherwise the active workspace's default project is used (set by `totebag project use`).

## Layout

- `totebag/models.py` - pydantic models. `Project` holds notes/links/**tools** inline. `Doc`/`Asset`/`Task`/`Tool`/`EntryList` carry a `description`. `Doc`, `EntryList`, `Asset`, and `Task` live in their own files, not inline in `Project`.
- `totebag/store.py` - the application **core**. Validates (`_require_description`), assigns IDs and last-update stamps, orchestrates, and runs `search`. Holds no on-disk knowledge; delegates all persistence to a `Sink`.
- `totebag/sink.py` - the `Sink` interface (abstract, versioned, expressed in domain items) and the default **`OKFSink`**. `OKFSink` owns the fsspec filesystem and the model↔OKF concept-file mapping (`type: project|note|link|document|list|asset|tool|task|journal`, frontmatter + markdown body). OKF lives here and nowhere else; another sink may use its own representation.
- `totebag/context.py` - assembles a project into the single markdown blob an agent reads (`project context`): description → tools → notes → links → docs → assets → open tasks → recent journal.
- `totebag/cli.py` - Typer app; subcommands `workspace`, `project`, `note`, `link`, `doc`, `list`, `asset`, `task`, `tool`, `journal` + top-level `init`/`config`/`search`.
- `totebag/ids.py` - `{prefix}_{15 chars}` IDs (`wsp_`, `prj_`, `doc_`, `lnk_`, `lst_`, `ast_`, `tsk_`, `tol_`).

## On-disk layout

A sink root holds many **workspaces**, each its own OKF bundle under an id-folder (`wsp_…`); `<root>/config.yaml` records the default workspace. All project/item paths in `OKFSink` route through `_p()` (= `<root>/workspaces/<active>/…`), so the active workspace scopes the whole store. Active = `-w`/`TOTEBAG_WORKSPACE` override, else the config default; resolved by `OKFSink._active_ws()`. No `index.md` is written - OKF §8 progressive disclosure is optional, nothing reads it back, and the CLI (`… get --brief`) serves that need from source-of-truth instead.

```
<root>/config.yaml           # store config (plain YAML): default_workspace: wsp_…
<root>/workspaces/<wsp_id>/
  workspace.md               # container metadata (id, name, default_project, created_at) + okf_version marker
  projects/prj_x/
    project.md               # type: project; notes/links/tools live INLINE in its frontmatter
    docs/doc_y.md            # type: document
    lists/lst_v.md           # type: list; entries as a JSONL body
    assets/ast_z/{binary, asset.md}
    tasks/tsk_w/task.md      # type: task; attachments sit in tasks/tsk_w/assets/
    log.md                   # OKF reserved log (§9); one per project, appended
```

## Active workspace and project

Workspace and project are ambient context, not per-command arguments. Project-scoped commands take no project id; they act on the active project, resolved as `-p`/`--project` → `TOTEBAG_PROJECT` → the active workspace's `default_project`. The active project must belong to the active workspace (projects are workspace-scoped). Set the defaults with `totebag workspace use <id>` and `totebag project use <id>`; `totebag config` reports both and where each came from.

## Conventions that bite

- **The description rule:** `add_doc`/`add_asset`/`add_task`/`add_task_asset`/`add_tool`/`create_list` all call `_require_description` and raise `DescriptionRequired` (a `ValueError`) on empty. The CLI also marks `--description` required and catches the error → exit 1. Notes/links are exempt (self-describing). Don't add a stored content type without wiring this guard.
- OKF reserves frontmatter `type` for the concept kind, so `ProjectType` is stored as `project_type` and remapped on load. These swaps live in `OKFSink` (`sink.py`) - keep them intact.
- Notes, links, and **tools** live **inline in `project.md` frontmatter** (small, few, edited together) and round-trip via `Project.model_dump`/`model_validate` in `OKFSink.save_project`/`load_project`. Docs, lists, assets, and tasks are their own files.
- **Lists** are schema-free: `create_list` then `add_entries` appends a batch (JSONL in, no single-entry command); entries persist as a JSONL body and export to CSV via `entries_to_csv` (columns = union of all entry keys). Remove one entry by 0-based index with `remove_entry` (it returns the removed entry).
- `complete_task` = journal the accomplishment + `remove_task`. Tasks are meant to be removed when done; the journal is the durable record. `task rm` drops one without journaling.
- Search is substring-only (`store.search`), scanning descriptions and content across item types. Semantic/embedding search, an HTTP API, and AI auto-descriptions are deliberately out of scope for v1 (see README "Status").
- **No em dashes (`—`).** Use a hyphen (`-`) in all prose, docs, comments, and strings. Applies everywhere in the repo.

## Non-negotiables

MIT-licensed public OSS. Every model change must round-trip through the OKF on-disk format across all three sink backends without extra code - that portability is the whole point. `tests/test_roundtrip.py` guards it (roundtrip + tasks/tools/journal + the description-rejection rule).
