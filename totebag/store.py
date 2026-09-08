"""The Store: totebag's application core.

The Store orchestrates every operation, validates input (the required-description rule), assigns
identifiers and last-update dates, and dispatches persistence to the active **sink** through the
Sink interface. It deals in Domain Model items and holds no knowledge of how any sink represents
them - OKF and on-disk layout live entirely in the sink (see `sink.py`).

Search runs here, above the sink, as a scan over the items the sink returns, so it works on any
sink whether or not that sink can search natively.
"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
from typing import Any

from . import __version__
from .ids import generate_id
from .models import (
    TOOL_CATEGORIES,
    Asset,
    AssetCategory,
    EntryList,
    Link,
    LinkType,
    Project,
    ProjectType,
    Stamp,
    Task,
    Workspace,
    _now,
)
from .sink import OKFSink, ProjectNotFound, Sink, WorkspaceNotFound

DEFAULT_ACTOR = f"totebag/{__version__}"  # OKF actor (§7); override via TOTEBAG_ACTOR

__all__ = [
    "DescriptionRequired",
    "OKFSink",
    "ProjectNotFound",
    "Sink",
    "Store",
    "WorkspaceNotFound",
]


class DescriptionRequired(ValueError):
    """Raised when caller-provided content is stored without a description."""


def _require_description(description: str | None, kind: str) -> str:
    if not description or not description.strip():
        raise DescriptionRequired(
            f"a non-empty description is required for every {kind} - the caller must describe what it stores"
        )
    return description


def _csv_cell(value: Any) -> Any:
    """CSV cell value: scalars pass through; nested objects/arrays are JSON-encoded."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value


def entries_to_csv(entries: list[dict[str, Any]]) -> str:
    """Render schema-free entries as CSV. Columns are the union of all keys across entries,
    ordered by first appearance; missing cells are blank. Returns the CSV text."""
    columns: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        for key in entry:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=columns, restval="", extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for entry in entries:
        writer.writerow({k: _csv_cell(v) for k, v in entry.items()})
    return buf.getvalue()


class Store:
    """Application core. Validates and orchestrates; persistence is delegated to `self.sink`."""

    def __init__(
        self,
        root: str | None = None,
        actor: str | None = None,
        sink: Sink | None = None,
        workspace: str | None = None,
    ) -> None:
        self.sink = sink or OKFSink(root, workspace)
        self.actor = actor or os.environ.get("TOTEBAG_ACTOR") or DEFAULT_ACTOR

    @property
    def url(self) -> str:
        # Only the OKF sink is URL-addressed today; expose it when present.
        return getattr(self.sink, "url", "")

    # --- workspaces --------------------------------------------------------
    def init_workspace(self, name: str = "workspace", description: str | None = None) -> Workspace:
        """The `init` entry point: create a workspace and make it the store's default, unless a
        valid default already exists (then it's a no-op). Description defaults to the name."""
        current = self.sink.default_workspace()
        if current:
            try:
                return self.sink.load_workspace(current)
            except WorkspaceNotFound:
                pass  # stale default; fall through and create a fresh one
        workspace = self.create_workspace(name, description=description or name)
        self.sink.set_default_workspace(workspace.id)
        return workspace

    def create_workspace(self, name: str, description: str = "", instructions: str = "") -> Workspace:
        _require_description(description, "workspace")
        workspace = Workspace(
            id=generate_id("wsp"), name=name, description=description, instructions=instructions
        )
        self.sink.save_workspace(workspace)
        return workspace

    def get_workspace(self, wid: str) -> Workspace:
        return self.sink.load_workspace(wid)

    def list_workspaces(self) -> list[Workspace]:
        return self.sink.list_workspaces()

    def update_workspace(
        self,
        wid: str,
        name: str | None = None,
        description: str | None = None,
        instructions: str | None = None,
    ) -> Workspace:
        workspace = self.sink.load_workspace(wid)
        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        if instructions is not None:
            workspace.instructions = instructions
        self.sink.save_workspace(workspace)
        return workspace

    def delete_workspace(self, wid: str) -> None:
        self.sink.delete_workspace(wid)

    def set_default_workspace(self, wid: str) -> None:
        self.sink.load_workspace(wid)  # ensure exists
        self.sink.set_default_workspace(wid)

    def summarize_workspace(self, wid: str, recursive: bool = False) -> dict:
        """Progressive-discovery view: workspace id + name, optionally with each project's description."""
        return self.sink.summarize_workspace(wid, recursive)

    def info(self) -> dict:
        return self.sink.info()

    # --- projects ----------------------------------------------------------
    def create_project(
        self,
        name: str,
        description: str = "",
        type: ProjectType = ProjectType.other,
    ) -> Project:
        _require_description(description, "project")
        project = Project(id=generate_id("prj"), name=name, description=description, type=type)
        self.save_project(project)
        return project

    def save_project(self, project: Project) -> None:
        # A save is a content change (§5.2): bump updated_at and re-stamp `generated`.
        project.updated_at = _now()
        project.generated = Stamp(by=self.actor, at=project.updated_at)
        self.sink.save_project(project)

    def get_project(self, pid: str) -> Project:
        return self.sink.load_project(pid)

    def list_projects(self) -> list[Project]:
        return self.sink.list_projects()

    def delete_project(self, pid: str) -> None:
        self.sink.delete_project(pid)

    def summarize_project(self, pid: str, recursive: bool = False) -> dict:
        """Progressive-discovery view (REQ-016): id + description, optionally for every child too.
        Cheaper than get_project - non-recursive reads only the project concept."""
        return self.sink.summarize_project(pid, recursive)

    def set_default_project(self, pid: str) -> None:
        """Set the active workspace's default project. The project must live in that workspace."""
        self.sink.load_project(pid)  # workspace-scoped: raises ProjectNotFound if not in this ws
        workspace = self.sink.load_workspace(self.sink._active_ws())
        workspace.default_project = pid
        self.sink.save_workspace(workspace)

    def default_project(self) -> str | None:
        """The active workspace's configured default project id, or None if unset/no workspace."""
        try:
            return self.sink.load_workspace(self.sink._active_ws()).default_project
        except WorkspaceNotFound:
            return None

    # --- notes -------------------------------------------------------------
    def add_note(self, pid: str, text: str) -> None:
        project = self.sink.load_project(pid)
        project.notes.append(text)
        self.save_project(project)

    def remove_note(self, pid: str, index: int) -> None:
        project = self.sink.load_project(pid)
        del project.notes[index]
        self.save_project(project)

    # --- links -------------------------------------------------------------
    def add_link(
        self,
        pid: str,
        url: str,
        name: str,
        type: LinkType = LinkType.generic,
        description: str = "",
    ) -> Link:
        project = self.sink.load_project(pid)
        link = Link(id=generate_id("lnk"), url=url, name=name, type=type, description=description)
        project.links.append(link)
        self.save_project(project)
        return link

    def remove_link(self, pid: str, link_id: str) -> None:
        project = self.sink.load_project(pid)
        project.links = [link for link in project.links if link.id != link_id]
        self.save_project(project)

    # --- docs (document-category assets) -----------------------------------
    def add_doc(self, pid: str, title: str, body: str, description: str) -> Asset:
        self.sink.load_project(pid)  # ensure exists
        _require_description(description, "doc")
        doc = Asset(
            id=generate_id("doc"), name=title, description=description,
            category=AssetCategory.document, body=body,
        )
        self.sink.save_asset(pid, doc)
        return doc

    def list_docs(self, pid: str) -> list[Asset]:
        return [a for a in self.sink.list_assets(pid) if a.category == AssetCategory.document]

    def get_doc(self, pid: str, doc_id: str) -> Asset:
        return self.sink.load_asset(pid, doc_id)

    def update_doc(
        self,
        pid: str,
        doc_id: str,
        body: str | None = None,
        description: str | None = None,
        title: str | None = None,
    ) -> Asset:
        doc = self.sink.load_asset(pid, doc_id)
        if body is not None:
            doc.body = body
        if description is not None:
            doc.description = description
        if title is not None:
            doc.name = title
        self.sink.save_asset(pid, doc)
        return doc

    def remove_doc(self, pid: str, doc_id: str) -> None:
        self.sink.delete_asset(pid, doc_id)

    # --- lists -------------------------------------------------------------
    def create_list(self, pid: str, name: str, description: str) -> EntryList:
        self.sink.load_project(pid)  # ensure exists
        _require_description(description, "list")  # description doubles as the caller summary
        entry_list = EntryList(id=generate_id("lst"), name=name, description=description)
        self.sink.save_list(pid, entry_list)
        return entry_list

    def add_entries(self, pid: str, list_id: str, entries: list[dict[str, Any]]) -> EntryList:
        """Append a batch of entries to a list. No schema is enforced. Returns the updated list."""
        entry_list = self.sink.load_list(pid, list_id)
        entry_list.entries.extend(entries)
        self.sink.save_list(pid, entry_list)
        return entry_list

    def remove_entry(self, pid: str, list_id: str, index: int) -> dict[str, Any]:
        """Remove a single entry by its 0-based index. Entries have no id, so position is the
        handle. Returns the removed entry so the caller can add it back."""
        entry_list = self.sink.load_list(pid, list_id)
        n = len(entry_list.entries)
        if index < 0 or index >= n:
            raise IndexError(f"entry index {index} out of range (list has {n} entries: valid 0..{n - 1})")
        removed = entry_list.entries.pop(index)
        self.sink.save_list(pid, entry_list)
        return removed

    def get_list(self, pid: str, list_id: str) -> EntryList:
        return self.sink.load_list(pid, list_id)

    def list_lists(self, pid: str) -> list[EntryList]:
        return self.sink.list_lists(pid)

    def remove_list(self, pid: str, list_id: str) -> None:
        self.sink.delete_list(pid, list_id)

    # --- assets ------------------------------------------------------------
    def add_asset(
        self,
        pid: str,
        src_path: str,
        description: str = "",
        name: str | None = None,
        category: AssetCategory | None = None,
    ) -> Asset:
        self.sink.load_project(pid)  # ensure exists
        _require_description(description, "asset")
        src_path = os.path.expanduser(src_path)
        filename = os.path.basename(src_path)
        with open(src_path, "rb") as f:
            data = f.read()
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        asset = Asset(
            id=generate_id("ast"),
            name=name or filename,
            description=description,
            media_type=media_type,
            category=category or AssetCategory.generic,
            size=len(data),
        )
        self.sink.save_asset(pid, asset, filename, data)
        return asset

    def get_asset(self, pid: str, asset_id: str) -> Asset:
        return self.sink.load_asset(pid, asset_id)

    def read_asset_bytes(self, pid: str, asset_id: str) -> bytes:
        return self.sink.load_asset_bytes(pid, asset_id)

    def remove_asset(self, pid: str, asset_id: str) -> None:
        self.sink.delete_asset(pid, asset_id)

    # --- tools / skills (tool|skill-category assets, stored like any asset) -
    def add_tool(
        self,
        pid: str,
        name: str,
        description: str,
        kind: AssetCategory = AssetCategory.tool,
        src_path: str | None = None,
    ) -> Asset:
        """A tool/skill is just an asset with a tool category. It may carry a file (uploaded like any
        asset) or be fileless (a named dependency the project depends on)."""
        self.sink.load_project(pid)  # ensure exists
        _require_description(description, "tool")
        tool = Asset(id=generate_id("tol"), name=name, description=description, category=kind)
        if src_path:
            src_path = os.path.expanduser(src_path)
            filename = os.path.basename(src_path)
            with open(src_path, "rb") as f:
                data = f.read()
            tool.media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            tool.size = len(data)
            self.sink.save_asset(pid, tool, filename, data)
        else:
            self.sink.save_asset(pid, tool)
        return tool

    def list_tools(self, pid: str) -> list[Asset]:
        return [a for a in self.sink.list_assets(pid) if a.category in TOOL_CATEGORIES]

    def remove_tool(self, pid: str, tool_id: str) -> None:
        self.sink.delete_asset(pid, tool_id)

    # --- tasks -------------------------------------------------------------
    def add_task(self, pid: str, title: str, description: str, body: str = "") -> Task:
        self.sink.load_project(pid)  # ensure exists
        _require_description(description, "task")
        task = Task(id=generate_id("tsk"), title=title, description=description, body=body)
        self.sink.save_task(pid, task)
        return task

    def get_task(self, pid: str, tid: str) -> Task:
        return self.sink.load_task(pid, tid)

    def list_tasks(self, pid: str) -> list[Task]:
        return self.sink.list_tasks(pid)

    def add_task_asset(
        self,
        pid: str,
        tid: str,
        src_path: str,
        description: str,
        name: str | None = None,
    ) -> Asset:
        _require_description(description, "attachment")
        task = self.sink.load_task(pid, tid)
        src_path = os.path.expanduser(src_path)
        filename = os.path.basename(src_path)
        with open(src_path, "rb") as f:
            data = f.read()
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        asset = Asset(
            id=generate_id("ast"),
            name=name or filename,
            description=description,
            media_type=media_type,
            category=AssetCategory.generic,
            size=len(data),
        )
        self.sink.save_task_asset(pid, task, asset, filename, data)
        return asset

    def remove_task(self, pid: str, tid: str) -> None:
        self.sink.delete_task(pid, tid)

    # --- search (runs above the sink, over the items it returns) -----------
    def search(self, query: str, pid: str | None = None) -> list[tuple[str, str, str, str]]:
        """Substring scan. Returns (project_id, kind, location, snippet) hits."""
        q = query.lower()
        projects = [self.get_project(pid)] if pid else self.list_projects()
        hits: list[tuple[str, str, str, str]] = []
        for project in projects:
            if q in project.description.lower():
                hits.append((project.id, "project.description", project.name, project.description))
            for i, note in enumerate(project.notes):
                if q in note.lower():
                    hits.append((project.id, "note", f"[{i}]", note))
            for link in project.links:
                haystack = f"{link.name} {link.url} {link.description}".lower()
                if q in haystack:
                    hits.append((project.id, "link", link.id, f"{link.name} - {link.url}"))
            # One loop over every asset - docs, tools, and byte files all live in project.assets,
            # each tagged by category, which doubles as the hit kind.
            for asset in project.assets:
                haystack = f"{asset.name} {asset.description} {asset.body}".lower()
                if q in haystack:
                    hits.append((project.id, asset.category.value, asset.id, asset.name))
            for task in self.list_tasks(project.id):
                haystack = f"{task.title} {task.description} {task.body}".lower()
                if q in haystack:
                    hits.append((project.id, "task", task.id, task.title))
            for entry_list in self.list_lists(project.id):
                entries_text = json.dumps(entry_list.entries, ensure_ascii=False)
                haystack = f"{entry_list.name} {entry_list.description} {entries_text}".lower()
                if q in haystack:
                    hits.append((project.id, "list", entry_list.id, entry_list.name))
        return hits
