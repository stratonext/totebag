"""totebag CLI - a thin Typer wrapper over totebag.core. Agent-driven: an LLM session
shells out to these commands (see `totebag skill`).

Output is terse, human-readable by default; `--help` is rich for a human at a terminal and
plain when piped. Set TOTEBAG_AGENT_MODE=1 (or pass --json) for machine-readable JSON + plain help.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from importlib import resources
from typing import Any

import typer

from . import __version__
from .context import build_context
from .models import BYTES_CATEGORIES, TOOL_CATEGORIES, AssetCategory, LinkType, ProjectStatus, ProjectType
from .store import ProjectNotFound, Store, WorkspaceNotFound, entries_to_csv


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no", "off")


# Agent mode: plain-text help + JSON output. Set once via TOTEBAG_AGENT_MODE=1 (recommended for
# agents whose output is a PTY rather than a pipe - it governs help too, decided at import).
# Piped output is auto-detected as plain regardless.
AGENT_MODE = _env_truthy("TOTEBAG_AGENT_MODE")


class _Out:
    json = False


_OUT = _Out()
_OUT.json = AGENT_MODE  # env-set agent mode ⇒ JSON by default (before the callback runs)


app = typer.Typer(
    add_completion=False,
    help="Portable project-knowledge store any AI Agent agent can restore over a CLI.",
    no_args_is_help=True,
)
project_app = typer.Typer(no_args_is_help=True, help="Manage projects.")
note_app = typer.Typer(no_args_is_help=True, help="Short text notes on a project.")
link_app = typer.Typer(no_args_is_help=True, help="URLs attached to a project.")
doc_app = typer.Typer(no_args_is_help=True, help="Editable markdown docs.")
list_app = typer.Typer(no_args_is_help=True, help="Named collections of schema-free entries, exportable as CSV.")
asset_app = typer.Typer(no_args_is_help=True, help="Arbitrary files attached to a project.")
task_app = typer.Typer(no_args_is_help=True, help="Future work to pick up later, each in its own folder.")
tool_app = typer.Typer(no_args_is_help=True, help="Tools/skills the project needs (restorable).")
workspace_app = typer.Typer(no_args_is_help=True, help="Top-level containers of projects.")
app.add_typer(workspace_app, name="workspace")
app.add_typer(project_app, name="project")
app.add_typer(note_app, name="note")
app.add_typer(link_app, name="link")
app.add_typer(doc_app, name="doc")
app.add_typer(list_app, name="list")
app.add_typer(asset_app, name="asset")
app.add_typer(task_app, name="task")
app.add_typer(tool_app, name="tool")


def _skill_text() -> str:
    return resources.files("totebag").joinpath("SKILL.md").read_text(encoding="utf-8")


def _skill_callback(value: bool) -> None:
    if value:
        typer.echo(_skill_text())
        raise typer.Exit()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"totebag {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    ctx: typer.Context,
    root: str | None = typer.Option(
        None,
        "--root",
        envvar="TOTEBAG_ROOT",
        help="Sink URL: file://~/.totebag (default), s3://bucket/prefix, gcs://bucket/prefix.",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        envvar="TOTEBAG_WORKSPACE",
        help="Current workspace id (overrides the store's configured default).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        envvar="TOTEBAG_PROJECT",
        help="Active project id for project-scoped commands (overrides the workspace's default).",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of terse human text."
    ),
    skill: bool = typer.Option(
        False, "--skill", callback=_skill_callback, is_eager=True,
        help="Print the bundled SKILL.md (agent usage) and exit - refresh your local copy after a CLI upgrade.",
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Print the totebag version and exit.",
    ),
) -> None:
    ctx.obj = (root, workspace, project)
    _OUT.json = json_out or AGENT_MODE


# --- output helpers --------------------------------------------------------
def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _print_json(value: object) -> None:
    typer.echo(json.dumps(_jsonable(value), indent=2, default=str))


def _print_obj(data: dict, indent: int = 0) -> None:
    """A single object as readable ``key: value`` lines; nested dicts recurse, lists counted."""
    pad = "  " * indent
    for key, val in data.items():
        if val is None or val == "" or val == [] or val == {}:
            continue
        label = _color(str(key), fg="cyan")
        if isinstance(val, dict):
            typer.echo(f"{pad}{label}:")
            _print_obj(val, indent + 1)
        elif isinstance(val, list):
            typer.echo(f"{pad}{label}: {len(val)} item(s)")
        else:
            typer.echo(f"{pad}{label}: {val}")


_CHILD_KINDS = ("projects", "notes", "links", "docs", "lists", "assets", "tools", "tasks")


def _is_human_tty() -> bool:
    """A real person is reading: interactive terminal and not machine-JSON mode."""
    return sys.stdout.isatty() and not _OUT.json


def _term_width(default: int = 100) -> int:
    return shutil.get_terminal_size((default, 24)).columns


def _truncate(text: str, width: int) -> str:
    """One-line, whitespace-collapsed, ellipsized to `width` (for long free-text in list rows)."""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: max(1, width - 1)].rstrip() + "…"


def _color(text: str, fg: str | None = None, bold: bool = False, dim: bool = False) -> str:
    """Style for a human at a terminal; a no-op in agent/JSON/piped mode so output stays plain."""
    if not _is_human_tty():
        return text
    return typer.style(text, fg=fg, bold=bold, dim=dim)


def _render_markdown(text: str) -> None:
    """Render markdown for a human (styled headers, real code blocks, emphasis). Falls back to the
    raw text when piped or in agent mode, so machine consumers get the exact markdown source."""
    if not _is_human_tty():
        typer.echo(text)
        return
    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        typer.echo(text)  # rich (via typer's extra) not installed - plain fallback
        return
    Console().print(Markdown(text))


def _emit_fields(it: dict, indent: str = "") -> None:
    """Labeled lines: `id:`, then `name:`, then `description:` (most nodes) or `value:` (notes/links).
    Missing fields are skipped."""
    typer.echo(f"{indent}{_color('id', fg='cyan')}: {_color(str(it['id']), dim=True)}")
    if it.get("name"):
        typer.echo(f"{indent}{_color('name', fg='cyan')}: {_color(str(it['name']), bold=True)}")
    if it.get("description"):
        typer.echo(f"{indent}{_color('description', fg='cyan')}: {it['description']}")
    if it.get("value"):
        typer.echo(f"{indent}{_color('value', fg='cyan')}: {it['value']}")


def _print_view(view: dict) -> None:
    """Progressive-discovery view: rich tree for a human at a TTY, terse text when piped/LLM."""
    if _is_human_tty() and _print_view_rich(view):
        return
    _emit_fields(view)
    for kind in _CHILD_KINDS:
        items = view.get(kind)
        if not items:
            continue
        typer.echo(f"\n{_color(kind, fg='magenta', bold=True)} ({len(items)}):")  # count = structure for the LLM
        for it in items:  # labeled fields, blank line separates entries
            _emit_fields(it, indent="  ")
            typer.echo("")


def _print_view_rich(view: dict) -> bool:
    """Render the view as a rich Tree. Returns False if rich is unavailable (caller falls back)."""
    try:
        from rich.console import Console
        from rich.tree import Tree
    except ImportError:
        return False
    name = view.get("name")
    header = f"[bold]{name}[/bold]  " if name else ""
    description = view.get("description") or ("" if name else "")
    root = Tree(f"{header}[dim]{view['id']}[/dim]" + (f"\n{description}" if description else ""))
    for kind in _CHILD_KINDS:
        items = view.get(kind)
        if not items:
            continue
        branch = root.add(f"[bold cyan]{kind}[/bold cyan] [dim]({len(items)})[/dim]")
        for it in items:
            name = it.get("name")
            text = it.get("description") or it.get("value") or ""
            label = (f"[bold]{name}[/bold]  " if name else "") + f"[dim]{it['id']}[/dim]  {text}"
            branch.add(label.rstrip())
    Console().print(root)
    return True


def _store(ctx: typer.Context) -> Store:
    root, workspace, _project_override = ctx.obj if ctx.obj else (None, None, None)
    return Store(root, workspace=workspace)


def _workspace(ctx: typer.Context) -> str:
    """Resolve the current workspace id: the -w/--workspace or TOTEBAG_WORKSPACE override, else the
    store's configured default. Fails if none is set."""
    try:
        return _store(ctx).sink._active_ws()
    except WorkspaceNotFound:
        _fail("no workspace set - run 'totebag init' or pass -w/--workspace")


def _project(ctx: typer.Context) -> str:
    """Resolve the active project for a project-scoped command: the -p/--project or TOTEBAG_PROJECT
    override, else the active workspace's configured default. Validates it exists in that workspace
    (projects are workspace-scoped) so the resolved project is always in the same workspace."""
    override = ctx.obj[2] if ctx.obj else None
    store = _store(ctx)
    pid = override or store.default_project()
    if not pid:
        _fail("no project set - pass -p/--project, set TOTEBAG_PROJECT, or run 'totebag project use <id>'")
    try:
        store.get_project(pid)  # workspace-scoped: missing here means not in the active workspace
    except ProjectNotFound:
        _fail(f"project '{pid}' is not in the active workspace")
    return pid


def _fail(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


# Reusable --confirm flag; declare on every destructive command.
_CONFIRM = typer.Option(False, "--confirm", help="Skip the confirmation prompt.")


def _confirm_delete(confirm: bool, what: str) -> None:
    """Guard a destructive op: proceed only with --confirm or an interactive 'yes'."""
    if not confirm and not typer.confirm(f"Delete {what}? This cannot be undone."):
        _fail("Aborted.")


def _read_body(file: str | None, stdin: bool) -> str:
    if stdin:
        return sys.stdin.read()
    if file:
        with open(file, encoding="utf-8") as f:
            return f.read()
    _fail("Provide document body via --file PATH or --stdin.")
    return ""  # unreachable


def _read_jsonl(file: str | None, stdin: bool) -> list[dict[str, Any]]:
    """Read a batch of entries as JSONL (one JSON object per line) from --stdin or --file.
    Blank lines are skipped; a non-object line or bad JSON fails with its line number."""
    if not stdin and not file:
        _fail("Provide entries as JSONL via --stdin or --file PATH.")
    text = _read_body(file, stdin)
    entries: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            _fail(f"line {lineno}: invalid JSON ({e.msg})")
        if not isinstance(obj, dict):
            _fail(f"line {lineno}: each entry must be a JSON object, got {type(obj).__name__}")
        entries.append(obj)
    if not entries:
        _fail("No entries found in input.")
    return entries


# --- workspace -------------------------------------------------------------
@app.command()
def init(
    ctx: typer.Context,
    name: str = typer.Option("workspace", "--name", help="Workspace name."),
    description: str | None = typer.Option(
        None, "--description", help="What this workspace is for (defaults to the name)."
    ),
) -> None:
    """Create the store's first workspace and set it as the default."""
    store = _store(ctx)
    ws = store.init_workspace(name, description)
    typer.echo(f"Initialized workspace '{ws.name}' ({ws.id}) at {store.url}")


# --- workspaces ------------------------------------------------------------
@workspace_app.command("create")
def workspace_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option(..., "--description", help="Required: what this workspace is for."),
) -> None:
    """Create a new workspace and print its id."""
    typer.echo(_store(ctx).create_workspace(name, description).id)


@workspace_app.command("list")
def workspace_list(ctx: typer.Context) -> None:
    workspaces = _store(ctx).list_workspaces()
    if _OUT.json:
        _print_json(workspaces)
        return
    if not workspaces:
        typer.echo("(none)")
        return
    for ws in workspaces:
        typer.echo(f"{_color(ws.id, dim=True)}  {_color(ws.name, bold=True)}")


@workspace_app.command("get")
def workspace_get(
    ctx: typer.Context,
    brief: bool = typer.Option(
        False, "--brief", help="Return only id + name + description (progressive discovery)."
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="With --brief, also list every project's id + description."
    ),
) -> None:
    if recursive and not brief:
        _fail("--recursive requires --brief")
    wid = _workspace(ctx)
    store = _store(ctx)
    if brief:
        try:
            view = store.summarize_workspace(wid, recursive)
        except WorkspaceNotFound:
            _fail(f"No such workspace: {wid}")
        if _OUT.json:
            _print_json(view)
            return
        _print_view(view)
        return
    try:
        ws = store.get_workspace(wid)
    except WorkspaceNotFound:
        _fail(f"No such workspace: {wid}")
    if _OUT.json:
        _print_json(ws)
        return
    _print_obj(ws.model_dump(mode="json"))


@workspace_app.command("update")
def workspace_update(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
) -> None:
    wid = _workspace(ctx)
    try:
        _store(ctx).update_workspace(wid, name, description)
    except WorkspaceNotFound:
        _fail(f"No such workspace: {wid}")
    typer.echo("ok")


@workspace_app.command("use")
def workspace_use(ctx: typer.Context, workspace_id: str) -> None:
    """Set the store's default (active) workspace."""
    try:
        _store(ctx).set_default_workspace(workspace_id)
    except WorkspaceNotFound:
        _fail(f"No such workspace: {workspace_id}")
    typer.echo("ok")


@workspace_app.command("delete")
def workspace_delete(ctx: typer.Context, confirm: bool = _CONFIRM) -> None:
    """Delete a workspace and every project it contains (the active one unless -w is given)."""
    wid = _workspace(ctx)
    _confirm_delete(confirm, f"workspace {wid} and every project it contains")
    try:
        _store(ctx).delete_workspace(wid)
    except WorkspaceNotFound:
        _fail(f"No such workspace: {wid}")
    typer.echo("ok")


@app.command()
def config(ctx: typer.Context) -> None:
    """Show the active sink, workspace, and project."""
    store = _store(ctx)
    info = store.info()
    # Project context isn't known to the sink (the -p flag lives in the CLI), so resolve it here.
    override = ctx.obj[2] if ctx.obj else None
    default_project = store.default_project()
    active_project = override or default_project
    if override:
        project_source = "TOTEBAG_PROJECT" if override == os.environ.get("TOTEBAG_PROJECT") else "--project"
    elif default_project:
        project_source = "default"
    else:
        project_source = None
    info = {**info, "project": active_project, "project_source": project_source,
            "default_project": default_project}
    if _OUT.json:
        _print_json(info)
        return
    source = info.get("workspace_source")
    ws_line = info["workspace"] or "(unset - run totebag init)"
    if source in ("TOTEBAG_WORKSPACE", "--workspace"):
        ws_line += f"  (from {source} override)"
    typer.echo(f"sink:        {info['sink']}")
    typer.echo(f"root:        {info['root']}")
    typer.echo(f"workspace:   {ws_line}")
    typer.echo(f"path:        {info['path'] or '(unset)'}")
    typer.echo(f"initialized: {'yes' if info['initialized'] else 'no'}")
    # When an override is active, show the store's configured default too so `workspace use` is
    # not mistaken for a no-op.
    if source in ("TOTEBAG_WORKSPACE", "--workspace") and info.get("default_workspace") != info["workspace"]:
        typer.echo(f"default:     {info.get('default_workspace') or '(unset)'}  (overridden above)")
    proj_line = active_project or "(unset)"
    if project_source in ("TOTEBAG_PROJECT", "--project"):
        proj_line += f"  (from {project_source} override)"
    typer.echo(f"project:     {proj_line}")
    if project_source in ("TOTEBAG_PROJECT", "--project") and default_project != active_project:
        typer.echo(f"default proj:{default_project or '(unset)'}  (overridden above)")


@app.command()
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Substring to look for."),
) -> None:
    """Substring search across a project's descriptions, notes, links, docs, lists, assets, tools,
    and tasks. Scans every project in the active workspace, or just one when a project is set with
    -p/--project or TOTEBAG_PROJECT."""
    project_override = ctx.obj[2] if ctx.obj else None  # explicit -p/env narrows; default does not
    hits = _store(ctx).search(query, project_override)
    if _OUT.json:
        _print_json(
            [
                {"projectId": pid, "kind": kind, "location": loc, "snippet": snippet}
                for pid, kind, loc, snippet in hits
            ]
        )
        return
    if not hits:
        typer.echo("No matches.")
        return
    for pid, kind, loc, snippet in hits:
        typer.echo(f"{pid}  {kind:18} {loc:16} {snippet[:80]}")


# --- projects --------------------------------------------------------------
@project_app.command("create")
def project_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option(..., "--description", help="Required: what this project is."),
    type: ProjectType = typer.Option(ProjectType.other, "--type"),
) -> None:
    project = _store(ctx).create_project(name, description, type)
    typer.echo(project.id)


@project_app.command("list")
def project_list(ctx: typer.Context) -> None:
    projects = _store(ctx).list_projects()
    if _OUT.json:
        _print_json(projects)
        return
    if not projects:
        typer.echo("(none)")
        return
    for project in projects:
        status = _color(f"{project.status.value:9}", fg="green" if project.status.value == "active" else "yellow")
        typer.echo(f"{_color(project.id, dim=True)}  {status} {_color(project.name, bold=True)}")


@project_app.command("use")
def project_use(ctx: typer.Context, project_id: str) -> None:
    """Set the active workspace's default project (must be a project in that workspace)."""
    try:
        _store(ctx).set_default_project(project_id)
    except ProjectNotFound:
        _fail(f"project '{project_id}' is not in the active workspace")
    typer.echo("ok")


@project_app.command("get")
def project_get(
    ctx: typer.Context,
    brief: bool = typer.Option(
        False, "--brief", help="Return only id + name + description (progressive discovery)."
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="With --brief, also list every child's id + description."
    ),
) -> None:
    if recursive and not brief:
        _fail("--recursive requires --brief")
    pid = _project(ctx)
    store = _store(ctx)
    if brief:
        view = store.summarize_project(pid, recursive)
        if _OUT.json:
            _print_json(view)
            return
        _print_view(view)
        return
    project = store.get_project(pid)
    if _OUT.json:
        _print_json(project)
        return
    _print_obj(project.model_dump(mode="json"))


@project_app.command("context")
def project_context(ctx: typer.Context) -> None:
    """Emit the agent 'restore knowledge' blob for a project (always markdown)."""
    store = _store(ctx)
    _render_markdown(build_context(store, store.get_project(_project(ctx))))


@project_app.command("update")
def project_update(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    instructions: str | None = typer.Option(None, "--instructions"),
    status: ProjectStatus | None = typer.Option(None, "--status"),
) -> None:
    store = _store(ctx)
    project = store.get_project(_project(ctx))
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if instructions is not None:
        project.instructions = instructions
    if status is not None:
        project.status = status
    store.save_project(project)
    typer.echo("ok")


@project_app.command("delete")
def project_delete(ctx: typer.Context, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"project {pid} and all its contents")
    _store(ctx).delete_project(pid)
    typer.echo("ok")


# --- notes -----------------------------------------------------------------
@note_app.command("add")
def note_add(ctx: typer.Context, text: str) -> None:
    _store(ctx).add_note(_project(ctx), text)
    typer.echo("ok")


@note_app.command("list")
def note_list(ctx: typer.Context) -> None:
    notes = _store(ctx).get_project(_project(ctx)).notes
    if _OUT.json:
        _print_json(notes)
        return
    for i, note in enumerate(notes):
        typer.echo(f"{_color(f'[{i}]', dim=True)} {note}")


@note_app.command("delete")
def note_delete(ctx: typer.Context, index: int, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"note [{index}] on {pid}")
    _store(ctx).remove_note(pid, index)
    typer.echo("ok")


# --- links -----------------------------------------------------------------
@link_app.command("add")
def link_add(
    ctx: typer.Context,
    url: str = typer.Option(..., "--url"),
    name: str = typer.Option(..., "--name"),
    type: LinkType = typer.Option(LinkType.generic, "--type"),
    description: str = typer.Option("", "--description"),
) -> None:
    link = _store(ctx).add_link(_project(ctx), url, name, type, description)
    typer.echo(link.id)


@link_app.command("list")
def link_list(ctx: typer.Context) -> None:
    links = _store(ctx).get_project(_project(ctx)).links
    if _OUT.json:
        _print_json(links)
        return
    for link in links:
        typer.echo(
            f"{_color(link.id, dim=True)}  {_color(f'{link.type.value:13}', fg='cyan')} "
            f"{_color(link.name, bold=True)}  {_color(link.url, fg='blue')}"
        )


@link_app.command("delete")
def link_delete(ctx: typer.Context, link_id: str, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"link {link_id} on {pid}")
    _store(ctx).remove_link(pid, link_id)
    typer.echo("ok")


# --- docs ------------------------------------------------------------------
@doc_app.command("add")
def doc_add(
    ctx: typer.Context,
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option(..., "--description", help="Required: what this doc covers."),
    file: str | None = typer.Option(None, "--file", help="Read body from this file."),
    stdin: bool = typer.Option(False, "--stdin", help="Read body from stdin."),
) -> None:
    body = _read_body(file, stdin)
    try:
        doc = _store(ctx).add_doc(_project(ctx), title, body, description)
    except (ProjectNotFound, ValueError) as e:
        _fail(str(e))
    typer.echo(doc.id)


@doc_app.command("list")
def doc_list(ctx: typer.Context) -> None:
    docs = _store(ctx).list_docs(_project(ctx))
    if _OUT.json:
        _print_json(docs)
        return
    for doc in docs:
        typer.echo(f"{_color(doc.id, dim=True)}  {_color(doc.name, bold=True)}")


@doc_app.command("get")
def doc_get(ctx: typer.Context, doc_id: str) -> None:
    doc = _store(ctx).get_doc(_project(ctx), doc_id)
    if _OUT.json:
        _print_json(doc)
        return
    _render_markdown(doc.body)


@doc_app.command("edit")
def doc_edit(
    ctx: typer.Context,
    doc_id: str,
    file: str | None = typer.Option(None, "--file", help="Read the new body from this file."),
    stdin: bool = typer.Option(False, "--stdin", help="Read the new body from stdin."),
    description: str | None = typer.Option(
        None, "--description", help="Update the description (may be given alone, without a body)."
    ),
) -> None:
    """Update a doc's body and/or description. Pass --file/--stdin to replace the body, and/or
    --description to change the description; at least one is required."""
    body = _read_body(file, stdin) if (file or stdin) else None  # None ⇒ body unchanged
    if body is None and description is None:
        _fail("nothing to update — pass --file/--stdin to change the body and/or --description")
    if description is not None and not description.strip():
        _fail("description cannot be empty")
    _store(ctx).update_doc(_project(ctx), doc_id, body=body, description=description)  # None ⇒ unchanged
    typer.echo("ok")


@doc_app.command("delete")
def doc_delete(ctx: typer.Context, doc_id: str, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"doc {doc_id} on {pid}")
    try:
        _store(ctx).remove_doc(pid, doc_id)
    except FileNotFoundError:
        _fail(f"No such doc: {doc_id}")
    typer.echo("ok")


# --- lists ------------------------------------------------------------------
@list_app.command("create")
def list_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="List name."),
    description: str = typer.Option(..., "--description", help="Required: what this list holds."),
) -> None:
    """Create an empty list. Entries are added later in batches with `list add`."""
    try:
        entry_list = _store(ctx).create_list(_project(ctx), name, description)
    except (ProjectNotFound, ValueError) as e:
        _fail(str(e))
    typer.echo(entry_list.id)


@list_app.command("add")
def list_add(
    ctx: typer.Context,
    list_id: str,
    file: str | None = typer.Option(None, "--file", help="Read entries (JSONL) from this file."),
    stdin: bool = typer.Option(False, "--stdin", help="Read entries (JSONL) from stdin."),
) -> None:
    """Append a batch of entries as JSONL (one JSON object per line). No single-entry form."""
    entries = _read_jsonl(file, stdin)
    try:
        _store(ctx).add_entries(_project(ctx), list_id, entries)
    except (ProjectNotFound, FileNotFoundError) as e:
        _fail(str(e))
    typer.echo(str(len(entries)))  # entries appended


@list_app.command("get")
def list_get(ctx: typer.Context, list_id: str) -> None:
    try:
        entry_list = _store(ctx).get_list(_project(ctx), list_id)
    except (ProjectNotFound, FileNotFoundError) as e:
        _fail(str(e))
    if _OUT.json:
        _print_json(entry_list)
        return
    typer.echo(
        f"{_color(entry_list.id, dim=True)}  {_color(entry_list.name, bold=True)}  "
        f"{_color(f'({len(entry_list.entries)} entries)', dim=True)}"
    )
    typer.echo(entry_list.description)


@list_app.command("list")
def list_list(ctx: typer.Context) -> None:
    lists = _store(ctx).list_lists(_project(ctx))
    if _OUT.json:
        _print_json(lists)
        return
    if not lists:
        typer.echo("(none)")
        return
    name_w = min(max(len(el.name) for el in lists), 28)
    for entry_list in lists:
        typer.echo(
            f"{_color(entry_list.id, dim=True)}  {_color(f'{entry_list.name:{name_w}}', bold=True)}  "
            f"{_color(f'({len(entry_list.entries)})', dim=True)}"
        )


@list_app.command("export")
def list_export(
    ctx: typer.Context,
    list_id: str,
    output: str | None = typer.Option(
        None, "--output", help="Write CSV to this file instead of stdout."
    ),
) -> None:
    """Export the list's entries as CSV (columns = union of all entry keys)."""
    try:
        entry_list = _store(ctx).get_list(_project(ctx), list_id)
    except (ProjectNotFound, FileNotFoundError) as e:
        _fail(str(e))
    text = entries_to_csv(entry_list.entries)
    if output:
        with open(output, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        typer.echo(output)
    else:
        typer.echo(text, nl=False)


@list_app.command("delete-entry")
def list_delete_entry(
    ctx: typer.Context,
    list_id: str,
    index: int = typer.Argument(..., help="0-based position of the entry to remove."),
    confirm: bool = _CONFIRM,
) -> None:
    """Remove a single entry by index. Prints the removed entry as JSONL so you can add it back."""
    pid = _project(ctx)
    _confirm_delete(confirm, f"entry [{index}] in list {list_id} on {pid}")
    try:
        removed = _store(ctx).remove_entry(pid, list_id, index)
    except (ProjectNotFound, FileNotFoundError, IndexError) as e:
        _fail(str(e))
    typer.echo(json.dumps(removed, ensure_ascii=False))  # re-add with: list add ... --stdin


@list_app.command("delete")
def list_delete(ctx: typer.Context, list_id: str, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"list {list_id} on {pid}")
    _store(ctx).remove_list(pid, list_id)
    typer.echo("ok")


# --- assets ----------------------------------------------------------------
@asset_app.command("add")
def asset_add(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="Local file to store."),
    description: str = typer.Option(..., "--description", help="Required: what this file is."),
    name: str | None = typer.Option(None, "--name"),
    category: AssetCategory | None = typer.Option(
        None, "--category", help="One of: binary, generic, transcript. (Use `doc`/`tool` for those.)"
    ),
) -> None:
    if category is not None and category not in BYTES_CATEGORIES:
        _fail("--category must be binary, generic, or transcript; add docs with `doc` and tools with `tool`")
    try:
        asset = _store(ctx).add_asset(_project(ctx), file, description, name, category)
    except (ProjectNotFound, ValueError) as e:
        _fail(str(e))
    typer.echo(asset.id)


@asset_app.command("list")
def asset_list(ctx: typer.Context) -> None:
    # project.assets holds every category; `asset list` shows only the byte files (docs/tools have
    # their own `list`).
    assets = [a for a in _store(ctx).get_project(_project(ctx)).assets if a.category in BYTES_CATEGORIES]
    if _OUT.json:
        _print_json(assets)
        return
    for asset in assets:
        typer.echo(
            f"{_color(asset.id, dim=True)}  {asset.size:>9}  "
            f"{_color(f'{asset.media_type:24}', fg='cyan')} {_color(asset.name, bold=True)}"
        )


@asset_app.command("download")
def asset_download(ctx: typer.Context, asset_id: str, dest: str) -> None:
    data = _store(ctx).read_asset_bytes(_project(ctx), asset_id)
    with open(dest, "wb") as f:
        f.write(data)
    typer.echo(dest)


@asset_app.command("delete")
def asset_delete(ctx: typer.Context, asset_id: str, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"asset {asset_id} on {pid}")
    try:
        _store(ctx).remove_asset(pid, asset_id)
    except FileNotFoundError:
        _fail(f"No such asset: {asset_id}")
    typer.echo("ok")


# --- tasks -----------------------------------------------------------------
@task_app.command("add")
def task_add(
    ctx: typer.Context,
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option(..., "--description", help="Required: what the task is."),
    file: str | None = typer.Option(None, "--file", help="Read task detail from this file."),
    stdin: bool = typer.Option(False, "--stdin", help="Read task detail from stdin."),
) -> None:
    """Add future work to pick up later (a deferred/postponed item). Remove it (with `task rm`) once done."""
    body = _read_body(file, stdin) if (file or stdin) else ""
    try:
        task = _store(ctx).add_task(_project(ctx), title, description, body)
    except (ProjectNotFound, ValueError) as e:
        _fail(str(e))
    typer.echo(task.id)


@task_app.command("list")
def task_list(ctx: typer.Context) -> None:
    tasks = _store(ctx).list_tasks(_project(ctx))
    if _OUT.json:
        _print_json(tasks)
        return
    if not tasks:
        typer.echo("(none)")
        return
    name_w = min(max(len(t.title) for t in tasks), 28)
    width = _term_width()
    for task in tasks:
        head = f"{task.id}  {task.title:{name_w}}  - "
        desc = _truncate(task.description, max(10, width - len(head))) if _is_human_tty() else task.description
        typer.echo(f"{_color(task.id, dim=True)}  {_color(f'{task.title:{name_w}}', bold=True)}  - {desc}")


@task_app.command("attach")
def task_attach(
    ctx: typer.Context,
    task_id: str,
    file: str = typer.Argument(..., help="Local file to attach to the task."),
    description: str = typer.Option(..., "--description", help="Required: what this attachment is."),
    name: str | None = typer.Option(None, "--name"),
) -> None:
    """Attach a file to a task; it lives in the task's own folder."""
    try:
        asset = _store(ctx).add_task_asset(_project(ctx), task_id, file, description, name)
    except (FileNotFoundError, ValueError) as e:
        _fail(str(e))
    typer.echo(asset.id)


@task_app.command("delete")
def task_delete(ctx: typer.Context, task_id: str, confirm: bool = _CONFIRM) -> None:
    """Drop a task from the list."""
    pid = _project(ctx)
    _confirm_delete(confirm, f"task {task_id} on {pid}")
    try:
        _store(ctx).remove_task(pid, task_id)
    except FileNotFoundError:
        _fail(f"No such task: {task_id}")
    typer.echo("ok")


# --- tools / skills --------------------------------------------------------
@tool_app.command("add")
def tool_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option(..., "--description", help="Required: what it does / why it's needed."),
    kind: str = typer.Option("tool", "--type", help="'tool' or 'skill'."),
    file: str | None = typer.Argument(None, help="Optional file to upload (e.g. a script or binary)."),
) -> None:
    """Register a tool/skill the project depends on. It's stored like any asset: attach a file to
    upload it, or leave it fileless as a named dependency."""
    if kind not in TOOL_CATEGORIES:
        _fail("--type must be 'tool' or 'skill'")
    try:
        tool = _store(ctx).add_tool(_project(ctx), name, description, AssetCategory(kind), file)
    except (ProjectNotFound, ValueError, FileNotFoundError) as e:
        _fail(str(e))
    typer.echo(tool.id)


@tool_app.command("list")
def tool_list(ctx: typer.Context) -> None:
    tools = _store(ctx).list_tools(_project(ctx))
    if _OUT.json:
        _print_json(tools)
        return
    if not tools:
        typer.echo("(none)")
        return
    # One aligned row per tool; a [file] flag marks tools that carry an uploaded file.
    name_w = min(max(len(t.name) for t in tools), 28)
    width = _term_width()
    for t in tools:
        flag_txt = "[file] " if t.path else ""
        head = f"{t.id}  {t.category.value:5}  {t.name:{name_w}}  {flag_txt}"
        desc = _truncate(t.description, max(10, width - len(head))) if _is_human_tty() else t.description
        typer.echo(
            f"{_color(t.id, dim=True)}  {_color(f'{t.category.value:5}', fg='cyan')}  "
            f"{_color(f'{t.name:{name_w}}', bold=True)}  {_color(flag_txt, fg='yellow')}{desc}"
        )


@tool_app.command("get")
def tool_get(ctx: typer.Context, tool_id: str) -> None:
    """Show one tool in full."""
    try:
        tool = _store(ctx).get_asset(_project(ctx), tool_id)
    except FileNotFoundError:
        _fail(f"No such tool: {tool_id}")
    if tool.category not in TOOL_CATEGORIES:
        _fail(f"{tool_id} is not a tool (it's a {tool.category.value})")
    if _OUT.json:
        _print_json(tool)
        return
    typer.echo(f"{_color(tool.id, dim=True)}  {_color(tool.category.value, fg='cyan')}  {_color(tool.name, bold=True)}")
    if tool.description:
        typer.echo(tool.description)
    if tool.path:
        typer.echo(_color(f"file: {tool.name} ({tool.media_type}, {tool.size} bytes)", fg="green"))


@tool_app.command("download")
def tool_download(ctx: typer.Context, tool_id: str, dest: str) -> None:
    """Download a tool's uploaded file (fails if the tool is fileless)."""
    try:
        data = _store(ctx).read_asset_bytes(_project(ctx), tool_id)
    except FileNotFoundError:
        _fail(f"tool {tool_id} has no uploaded file to download")
    with open(dest, "wb") as f:
        f.write(data)
    typer.echo(dest)


@tool_app.command("delete")
def tool_delete(ctx: typer.Context, tool_id: str, confirm: bool = _CONFIRM) -> None:
    pid = _project(ctx)
    _confirm_delete(confirm, f"tool {tool_id} on {pid}")
    try:
        _store(ctx).remove_tool(pid, tool_id)
    except FileNotFoundError:
        _fail(f"No such tool: {tool_id}")
    typer.echo("ok")


def _set_plain_help() -> None:
    """Plain Click help/errors (no rich boxes/color) + plain tracebacks, for piped/agent output."""
    for grp in (app, workspace_app, project_app, note_app, link_app, doc_app, list_app, asset_app, task_app, tool_app):
        grp.rich_markup_mode = None
    app.pretty_exceptions_enable = False


# Rich help for a human at a terminal; plain when piped or in agent mode. Rich drops ANSI color
# in a pipe but keeps box-drawing borders - noise for an agent - so switch it off on !isatty.
if AGENT_MODE or not sys.stdout.isatty():
    _set_plain_help()


# Global callback options that Typer only parses before the subcommand. Agents/users write them
# after (`totebag workspace delete -w foo`), so main() hoists them to the front. Flags take no value;
# the rest consume the following token (or use the `--opt=val` form).
_GLOBAL_FLAGS = {"--json"}
_GLOBAL_VALUE_OPTS = {"--root", "--workspace", "-w", "--project", "-p"}


def _hoist_globals(argv: list[str]) -> list[str]:
    front, rest, i = [], [], 0
    while i < len(argv):
        a = argv[i]
        if a in _GLOBAL_FLAGS:
            front.append(a)
        elif a in _GLOBAL_VALUE_OPTS:
            front.append(a)
            if i + 1 < len(argv):  # move its value too; if missing, Typer reports the error
                i += 1
                front.append(argv[i])
        elif a.split("=", 1)[0] in _GLOBAL_VALUE_OPTS and "=" in a:
            front.append(a)
        else:
            rest.append(a)
        i += 1
    return front + rest


def main() -> None:
    app(args=_hoist_globals(sys.argv[1:]), prog_name="totebag")


if __name__ == "__main__":
    main()
