"""Storage sinks.

The **Sink** is the abstract, versioned store interface (see
`docs/architecture/store-interface-v1.md`). It is expressed in Domain Model items, not files or
bytes, so the Store core depends only on this contract and never on how a destination keeps
content. Concrete sinks implement it and are interchangeable behind it.

The default concrete sink is the **OKFSink**, which keeps items as an Open Knowledge Format (OKF)
v0.2 bundle over an `fsspec` filesystem, so the same bundle round-trips to `file://`, `s3://`, or
`gcs://` unchanged. OKF is the concern of this sink alone; another sink (for example a remote
server reached over an API) may keep content however its API dictates.

OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

import json
import os
import posixpath
from abc import ABC, abstractmethod

import frontmatter
import fsspec
import yaml

from .models import (
    Asset,
    AssetCategory,
    EntryList,
    Project,
    ProjectType,
    Task,
    Workspace,
)

DEFAULT_ROOT = "file://" + os.path.expanduser("~/.totebag")
OKF_VERSION = "0.2"


class ProjectNotFound(Exception):
    pass


class WorkspaceNotFound(Exception):
    pass


class Sink(ABC):
    """The versioned store-operation contract for one destination (REQ-010).

    Operations are expressed in Domain Model items. A concrete sink declares which interface
    version it implements and MUST provide every operation of that version exactly (REQ-010).
    """

    INTERFACE_VERSION = "1"

    # --- workspaces (top-level containers) ---------------------------------
    @abstractmethod
    def save_workspace(self, workspace: Workspace) -> None: ...
    @abstractmethod
    def load_workspace(self, wid: str) -> Workspace: ...
    @abstractmethod
    def list_workspaces(self) -> list[Workspace]: ...
    @abstractmethod
    def delete_workspace(self, wid: str) -> None: ...
    @abstractmethod
    def default_workspace(self) -> str | None:
        """The store's configured current workspace id, or None if unset."""
        ...
    @abstractmethod
    def set_default_workspace(self, wid: str) -> None: ...
    @abstractmethod
    def summarize_workspace(self, wid: str, recursive: bool = False) -> dict:
        """Progressive-discovery read: the workspace as id + name, and with `recursive`, each of
        its projects as id + description."""
        ...
    @abstractmethod
    def info(self) -> dict: ...

    # --- projects ----------------------------------------------------------
    @abstractmethod
    def save_project(self, project: Project) -> None: ...
    @abstractmethod
    def load_project(self, pid: str) -> Project: ...
    @abstractmethod
    def list_projects(self) -> list[Project]: ...
    @abstractmethod
    def delete_project(self, pid: str) -> None: ...
    @abstractmethod
    def summarize_project(self, pid: str, recursive: bool = False) -> dict:
        """Progressive-discovery read (REQ-016): the project as id + description, and with
        `recursive`, every child as id + description, without loading item bodies."""
        ...

    # --- lists -------------------------------------------------------------
    @abstractmethod
    def save_list(self, pid: str, entry_list: EntryList) -> None: ...
    @abstractmethod
    def load_list(self, pid: str, list_id: str) -> EntryList: ...
    @abstractmethod
    def list_lists(self, pid: str) -> list[EntryList]: ...
    @abstractmethod
    def delete_list(self, pid: str, list_id: str) -> None: ...

    # --- assets (unified: documents, tools/skills, and byte files) ---------
    @abstractmethod
    def save_asset(self, pid: str, asset: Asset, filename: str | None = None, data: bytes | None = None) -> None:
        """Persist an asset. Byte categories pass `filename`+`data`; a document carries its text in
        the model (`body`) and passes neither."""
        ...
    @abstractmethod
    def load_asset(self, pid: str, asset_id: str) -> Asset: ...
    @abstractmethod
    def list_assets(self, pid: str) -> list[Asset]: ...
    @abstractmethod
    def load_asset_bytes(self, pid: str, asset_id: str) -> bytes: ...
    @abstractmethod
    def delete_asset(self, pid: str, asset_id: str) -> None: ...

    # --- tasks -------------------------------------------------------------
    @abstractmethod
    def save_task(self, pid: str, task: Task) -> None: ...
    @abstractmethod
    def load_task(self, pid: str, tid: str) -> Task: ...
    @abstractmethod
    def list_tasks(self, pid: str) -> list[Task]: ...
    @abstractmethod
    def delete_task(self, pid: str, tid: str) -> None: ...
    @abstractmethod
    def save_task_asset(self, pid: str, task: Task, asset: Asset, filename: str, data: bytes) -> None: ...


def _normalize_root(root: str) -> str:
    """Accept a bare path or a URL. Expand `~` and make local paths absolute."""
    if "://" not in root:
        return "file://" + os.path.abspath(os.path.expanduser(root))
    if root.startswith("file://"):
        path = root[len("file://") :]
        return "file://" + os.path.abspath(os.path.expanduser(path))
    return root


def _dump_concept(meta: dict, body: str = "") -> str:
    """Serialize an OKF concept: YAML frontmatter + markdown body. Drops null keys."""
    clean = {k: v for k, v in meta.items() if v is not None}
    return frontmatter.dumps(frontmatter.Post(body, **clean))


def _load_concept(text: str) -> tuple[dict, str]:
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content


def _legacy_summary_to_description(meta: dict) -> None:
    """Pre-rename stores keyed descriptive text as `summary`. Fold it into `description`
    (only when description is absent/empty) and drop the old key. Mutates in place."""
    if meta.get("summary") and not meta.get("description"):
        meta["description"] = meta["summary"]
    meta.pop("summary", None)


class OKFSink(Sink):
    """Default sink: an OKF v0.2 bundle on an fsspec filesystem.

    Owns the mapping between a Domain Model item and its on-disk concept file, including the
    reserved-key remapping OKF requires. Bundle layout:

        $ROOT/
          config.yaml                       # store config (plain YAML): default_workspace
          workspaces/<wsp_id>/
            workspace.md                    # container metadata + okf_version marker
            projects/prj_x/
              project.md                    # type: project (frontmatter carries notes/links)
              docs/doc_y.md                 # type: document (body = markdown)
              assets/ast_z/{report.pdf, asset.md}   # byte asset: binary + type: asset concept
              assets/tol_v/asset.md         # a tool/skill: a (maybe fileless) asset, category=tool
              tasks/tsk_w/task.md           # type: task; attachments in tasks/tsk_w/assets/

    Everything a project stores is one `Asset`, distinguished by `AssetCategory`. Only `document`
    is special: it is editable text, kept in docs/ as an OKF `type: document`. Every other category
    (binary/generic/transcript, and tool/skill) is a byte asset in assets/ (`type: asset`), where a
    tool is simply an asset whose `category` is tool/skill - it may carry a file or be fileless.
    """

    def __init__(self, root: str | None = None, workspace: str | None = None) -> None:
        root = root or os.environ.get("TOTEBAG_ROOT") or DEFAULT_ROOT
        self.url = _normalize_root(root)
        self.fs, self.base = fsspec.core.url_to_fs(self.url)
        # Active workspace = explicit override, else the store's configured default (config.yaml).
        self._workspace_override = workspace or os.environ.get("TOTEBAG_WORKSPACE")
        self._active: str | None = None

    # --- path + io helpers -------------------------------------------------
    def _rp(self, *parts: str) -> str:
        """Path under the sink root, independent of the active workspace."""
        return posixpath.join(self.base, *parts)

    def _resolve_ws(self) -> str | None:
        if self._workspace_override:
            return self._workspace_override
        if self._active:
            return self._active
        self._active = self.default_workspace()  # None until a default is set
        return self._active

    def _active_ws(self) -> str:
        ws = self._resolve_ws()
        if ws is None:
            raise WorkspaceNotFound("no active workspace - run `totebag init` or pass --workspace")
        return ws

    def _wb(self) -> str:
        """The active workspace's OKF bundle root: <root>/workspaces/<id>/."""
        return posixpath.join(self.base, "workspaces", self._active_ws())

    def _p(self, *parts: str) -> str:
        """Path inside the active workspace bundle. Every project/item path routes through here,
        so the active workspace scopes the whole store to one container."""
        return posixpath.join(self._wb(), *parts)

    def _write_text(self, path: str, text: str) -> None:
        self.fs.makedirs(posixpath.dirname(path), exist_ok=True)
        with self.fs.open(path, "wb") as f:
            f.write(text.encode("utf-8"))

    def _write_bytes(self, path: str, data: bytes) -> None:
        self.fs.makedirs(posixpath.dirname(path), exist_ok=True)
        with self.fs.open(path, "wb") as f:
            f.write(data)

    def _read_text(self, path: str) -> str:
        with self.fs.open(path, "rb") as f:
            return f.read().decode("utf-8")

    def _read_bytes(self, path: str) -> bytes:
        with self.fs.open(path, "rb") as f:
            return f.read()

    def info(self) -> dict:
        proto = self.fs.protocol
        if isinstance(proto, (list, tuple)):
            proto = proto[0]
        ws = self._resolve_ws()
        ws_path = posixpath.join(self.base, "workspaces", ws) if ws else None
        # Where the active workspace came from: an override (TOTEBAG_WORKSPACE env or -w flag) wins
        # over the store's configured default. Surfacing this explains why `workspace use` can look
        # like a no-op while an override is in effect.
        override = self._workspace_override
        default = self.default_workspace()
        if override:
            source = "TOTEBAG_WORKSPACE" if override == os.environ.get("TOTEBAG_WORKSPACE") else "--workspace"
        elif default:
            source = "default"
        else:
            source = None
        return {
            "sink": proto,
            "root": self.url,
            "workspace": ws,
            "workspace_source": source,
            "default_workspace": default,
            "path": ws_path,
            "initialized": bool(ws_path) and self.fs.exists(posixpath.join(ws_path, "workspace.md")),
        }

    # --- workspaces (each is its own OKF bundle) ---------------------------
    def _config_path(self) -> str:
        return self._rp("config.yaml")

    def _legacy_config_path(self) -> str:
        return self._rp("config.md")  # pre-YAML stores kept config as an OKF concept file

    def _read_config(self) -> dict:
        """Store config as a plain YAML mapping. Falls back to the legacy config.md concept."""
        path = self._config_path()
        if self.fs.exists(path):
            return yaml.safe_load(self._read_text(path)) or {}
        legacy = self._legacy_config_path()
        if self.fs.exists(legacy):
            meta, _ = _load_concept(self._read_text(legacy))
            return meta
        return {}

    def default_workspace(self) -> str | None:
        return self._read_config().get("default_workspace")

    def set_default_workspace(self, wid: str) -> None:
        config = self._read_config()
        config["default_workspace"] = wid
        self._write_text(self._config_path(), yaml.safe_dump(config, sort_keys=False))
        legacy = self._legacy_config_path()
        if self.fs.exists(legacy):
            self.fs.rm(legacy)  # migrated to config.yaml; drop the old concept file
        self._active = wid

    def _workspace_dir(self, wid: str) -> str:
        return self._rp("workspaces", wid)

    def save_workspace(self, workspace: Workspace) -> None:
        wsdir = self._workspace_dir(workspace.id)
        # workspace.md carries the container metadata plus the optional OKF format marker
        # (okf_version is MAY in OKF v0.2; no separate index.md is written).
        meta = {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description or None,
            "default_project": workspace.default_project or None,
            "created_at": workspace.created_at.isoformat(),
            "okf_version": OKF_VERSION,
        }
        self._write_text(posixpath.join(wsdir, "workspace.md"), _dump_concept(meta, f"# {workspace.name}\n"))
        self.fs.makedirs(posixpath.join(wsdir, "projects"), exist_ok=True)

    def load_workspace(self, wid: str) -> Workspace:
        path = posixpath.join(self._workspace_dir(wid), "workspace.md")
        if not self.fs.exists(path):
            raise WorkspaceNotFound(wid)
        meta, _ = _load_concept(self._read_text(path))
        data = {
            "id": meta.get("id", wid),
            "name": meta.get("name", wid),
            "description": meta.get("description") or "",
            "default_project": meta.get("default_project"),
        }
        if meta.get("created_at"):
            data["created_at"] = meta["created_at"]
        return Workspace.model_validate(data)

    def list_workspaces(self) -> list[Workspace]:
        d = self._rp("workspaces")
        if not self.fs.exists(d):
            return []
        out: list[Workspace] = []
        for sub in sorted(self.fs.ls(d, detail=False)):
            wid = posixpath.basename(sub.rstrip("/"))
            if self.fs.exists(posixpath.join(sub, "workspace.md")):
                out.append(self.load_workspace(wid))
        return out

    def delete_workspace(self, wid: str) -> None:
        d = self._workspace_dir(wid)
        if not self.fs.exists(d):
            raise WorkspaceNotFound(wid)
        self.fs.rm(d, recursive=True)

    def summarize_workspace(self, wid: str, recursive: bool = False) -> dict:
        ws = self.load_workspace(wid)  # raises WorkspaceNotFound
        view: dict = {"id": ws.id, "name": ws.name, "description": ws.description}
        if not recursive:
            return view
        pdir = posixpath.join(self._workspace_dir(wid), "projects")
        projects: list[dict] = []
        if self.fs.exists(pdir):
            for sub in sorted(self.fs.ls(pdir, detail=False)):
                ppath = posixpath.join(sub, "project.md")
                if self.fs.exists(ppath):
                    meta, _ = _load_concept(self._read_text(ppath))  # project.md only, no children
                    projects.append({
                        "id": meta.get("id", posixpath.basename(sub.rstrip("/"))),
                        "name": meta.get("title") or meta.get("name") or "",
                        "description": meta.get("description") or meta.get("summary") or "",
                    })
        view["projects"] = projects
        return view

    # --- projects (type: project) ------------------------------------------
    def _project_path(self, pid: str) -> str:
        return self._p("projects", pid, "project.md")

    def save_project(self, project: Project) -> None:
        # Structured meta -> frontmatter; free-form instructions -> body. `type` is reserved by
        # OKF for the concept kind, so the project's own ProjectType is carried as `project_type`.
        # Notes and links live inline in project.md's frontmatter (small, few, edited together).
        # Assets (docs, tools, byte files) each stay as their own concept files.
        meta = project.model_dump(mode="json", exclude={"assets", "instructions"})
        meta["project_type"] = meta.pop("type")
        for empty in ("notes", "links"):
            if not meta.get(empty):
                meta.pop(empty, None)  # keep frontmatter clean when there are none
        meta = {"type": "project", "title": project.name, **meta}
        self._write_text(self._project_path(project.id), _dump_concept(meta, project.instructions))

    def load_project(self, pid: str) -> Project:
        path = self._project_path(pid)
        if not self.fs.exists(path):
            raise ProjectNotFound(pid)
        meta, body = _load_concept(self._read_text(path))
        meta.pop("type", None)
        meta.pop("title", None)
        meta["type"] = meta.pop("project_type", ProjectType.other.value)
        meta["instructions"] = body
        _legacy_summary_to_description(meta)  # pre-rename stores carried `summary`
        project = Project.model_validate(meta)  # notes, links come inline from frontmatter
        project.assets = self.list_assets(pid)  # docs, tools, and byte files, all their own files
        return project

    def list_projects(self) -> list[Project]:
        projects_dir = self._p("projects")
        if not self.fs.exists(projects_dir):
            return []
        out: list[Project] = []
        for entry in sorted(self.fs.ls(projects_dir, detail=False)):
            pid = posixpath.basename(entry.rstrip("/"))
            if self.fs.exists(self._project_path(pid)):
                out.append(self.load_project(pid))
        return out

    def delete_project(self, pid: str) -> None:
        self.fs.rm(self._p("projects", pid), recursive=True)

    def summarize_project(self, pid: str, recursive: bool = False) -> dict:
        path = self._project_path(pid)
        if not self.fs.exists(path):
            raise ProjectNotFound(pid)
        meta, _ = _load_concept(self._read_text(path))  # project.md only
        view: dict = {
            "id": pid,
            "name": meta.get("title") or meta.get("name") or "",
            "description": meta.get("description") or meta.get("summary") or "",
        }
        if not recursive:
            return view

        def frontmatters(d: str) -> list[tuple[dict, str]]:
            # Reads each concept file whole and keeps its frontmatter; bodies are dropped in memory,
            # not skipped on disk. Adequate at knowledge-store sizes.
            if not self.fs.exists(d):
                return []
            out = []
            for entry in sorted(self.fs.ls(d, detail=False)):
                if entry.endswith(".md"):
                    out.append(_load_concept(self._read_text(entry)))
            return out

        view["notes"] = [
            {"id": f"[{i}]", "value": note}  # a note is just its text
            for i, note in enumerate(meta.get("notes") or [])
        ]
        view["links"] = [
            {"id": lk.get("id", ""), "name": lk.get("name") or "", "value": lk.get("url", "")}
            for lk in (meta.get("links") or [])
        ]
        view["docs"] = [
            {"id": m.get("id", ""), "name": m.get("title") or "", "description": m.get("description") or ""}
            for m, _b in frontmatters(self._docs_dir(pid))
        ]
        view["lists"] = [
            {"id": m.get("id", ""), "name": m.get("title") or "", "description": m.get("description") or ""}
            for m, _b in frontmatters(self._lists_dir(pid))
        ]
        # Both tools and plain files are byte assets in assets/; split them by category for the view.
        asset_concepts = self._subdir_concepts(self._p("projects", pid, "assets"), "asset.md")
        view["tools"] = [
            {"id": m.get("id", ""), "name": m.get("title") or "", "description": m.get("description") or ""}
            for m in asset_concepts if m.get("category") in ("tool", "skill")
        ]
        view["assets"] = [
            {"id": m.get("id", ""), "description": m.get("description") or m.get("summary") or m.get("title", "")}
            for m in asset_concepts if m.get("category") not in ("tool", "skill")
        ]
        view["tasks"] = [
            {"id": m.get("id", ""), "description": m.get("description") or m.get("summary") or ""}
            for m in self._subdir_concepts(self._tasks_dir(pid), "task.md")
        ]
        return view

    def _subdir_concepts(self, parent: str, concept_name: str) -> list[dict]:
        """Frontmatter of each `<parent>/<item>/<concept_name>` (assets, tasks live in subdirs)."""
        if not self.fs.exists(parent):
            return []
        out: list[dict] = []
        for sub in sorted(self.fs.ls(parent, detail=False)):
            concept = posixpath.join(sub, concept_name)
            if self.fs.exists(concept):
                meta, _ = _load_concept(self._read_text(concept))
                meta.setdefault("id", posixpath.basename(sub.rstrip("/")))
                out.append(meta)
        return out

    # --- document assets (type: document; body = markdown) -----------------
    def _docs_dir(self, pid: str) -> str:
        return self._p("projects", pid, "docs")

    def _doc_path(self, pid: str, doc_id: str) -> str:
        return posixpath.join(self._docs_dir(pid), f"{doc_id}.md")

    def _save_doc_asset(self, pid: str, asset: Asset) -> None:
        meta = {"type": "document", "id": asset.id, "title": asset.name, "description": asset.description or None}
        self._write_text(self._doc_path(pid, asset.id), _dump_concept(meta, asset.body))

    def _load_doc_asset(self, path: str) -> Asset:
        meta, body = _load_concept(self._read_text(path))
        return Asset(
            id=meta.get("id"),
            name=meta.get("title", ""),
            description=meta.get("description") or meta.get("summary") or "",
            category=AssetCategory.document,
            body=body,
        )

    # --- lists (type: list; body = JSONL, one entry object per line) --------
    def _lists_dir(self, pid: str) -> str:
        return self._p("projects", pid, "lists")

    def _list_path(self, pid: str, list_id: str) -> str:
        return posixpath.join(self._lists_dir(pid), f"{list_id}.md")

    def _load_list_file(self, path: str) -> EntryList:
        meta, body = _load_concept(self._read_text(path))
        entries = [json.loads(line) for line in body.splitlines() if line.strip()]
        return EntryList(
            id=meta.get("id"),
            name=meta.get("title", ""),
            description=meta.get("description") or "",
            entries=entries,
        )

    def save_list(self, pid: str, entry_list: EntryList) -> None:
        meta = {
            "type": "list",
            "id": entry_list.id,
            "title": entry_list.name,
            "description": entry_list.description,
        }
        body = "\n".join(json.dumps(e, ensure_ascii=False) for e in entry_list.entries)
        self._write_text(self._list_path(pid, entry_list.id), _dump_concept(meta, body))

    def list_lists(self, pid: str) -> list[EntryList]:
        lists_dir = self._lists_dir(pid)
        if not self.fs.exists(lists_dir):
            return []
        lists: list[EntryList] = []
        for entry in sorted(self.fs.ls(lists_dir, detail=False)):
            if entry.endswith(".md"):
                lists.append(self._load_list_file(entry))
        return lists

    def load_list(self, pid: str, list_id: str) -> EntryList:
        path = self._list_path(pid, list_id)
        if not self.fs.exists(path):
            raise FileNotFoundError(list_id)
        return self._load_list_file(path)

    def delete_list(self, pid: str, list_id: str) -> None:
        self.fs.rm(self._list_path(pid, list_id))

    # --- byte assets (type: asset; resource = the binary) ------------------
    def _asset_dir(self, pid: str, asset_id: str) -> str:
        return self._p("projects", pid, "assets", asset_id)

    def _write_asset_concept(self, pid: str, asset: Asset) -> None:
        meta = {
            "type": "asset",
            "id": asset.id,
            "title": asset.name,
            "description": asset.description or None,
            "resource": f"/projects/{pid}/{asset.path}" if asset.path else None,  # bundle-relative per OKF
            "media_type": asset.media_type,
            "category": asset.category.value,
            "size": asset.size,
        }
        self._write_text(posixpath.join(self._asset_dir(pid, asset.id), "asset.md"), _dump_concept(meta))

    def _load_byte_asset(self, sub: str) -> Asset | None:
        asset_id = posixpath.basename(sub.rstrip("/"))
        concept = posixpath.join(sub, "asset.md")
        if not self.fs.exists(concept):
            return None
        meta, _ = _load_concept(self._read_text(concept))
        # The binary is the one file in the dir that isn't the concept doc (a fileless asset, e.g. an
        # external tool, has none).
        binaries = [f for f in self.fs.ls(sub, detail=False) if not f.rstrip("/").endswith("/asset.md")]
        filename = posixpath.basename(binaries[0].rstrip("/")) if binaries else None
        return Asset(
            id=meta.get("id", asset_id),
            name=meta.get("title", filename or ""),
            description=meta.get("description") or meta.get("summary") or "",
            media_type=meta.get("media_type", "application/octet-stream"),
            category=meta.get("category", "generic"),
            size=meta.get("size", 0),
            path=f"assets/{asset_id}/{filename}" if filename else "",
        )

    def _load_dir_assets(self, d: str, loader) -> list[Asset]:
        """Load every `.md` concept in a flat dir (docs, tools) via `loader`."""
        if not self.fs.exists(d):
            return []
        return [loader(e) for e in sorted(self.fs.ls(d, detail=False)) if e.endswith(".md")]

    def _load_byte_assets(self, pid: str) -> list[Asset]:
        d = self._p("projects", pid, "assets")
        if not self.fs.exists(d):
            return []
        out = [self._load_byte_asset(sub) for sub in sorted(self.fs.ls(d, detail=False))]
        return [a for a in out if a is not None]

    def save_asset(self, pid: str, asset: Asset, filename: str | None = None, data: bytes | None = None) -> None:
        """Route by category: `document` is text in docs/; every other category is a byte asset in
        assets/ (a tool/skill is just such an asset). The file is optional - a fileless asset
        (e.g. a named tool dependency) writes just the concept."""
        if asset.category == AssetCategory.document:
            self._save_doc_asset(pid, asset)
            return
        if data is not None and filename:
            rel = f"assets/{asset.id}/{filename}"
            self._write_bytes(self._p("projects", pid, rel), data)
            asset.path = rel
        self._write_asset_concept(pid, asset)  # asset index lives on disk as a concept file

    def list_assets(self, pid: str) -> list[Asset]:
        """Every asset of the project: text documents in docs/, everything else in assets/."""
        return [
            *self._load_dir_assets(self._docs_dir(pid), self._load_doc_asset),
            *self._load_byte_assets(pid),
        ]

    def load_asset(self, pid: str, asset_id: str) -> Asset:
        doc_path = self._doc_path(pid, asset_id)
        if self.fs.exists(doc_path):
            return self._load_doc_asset(doc_path)
        asset = self._load_byte_asset(self._asset_dir(pid, asset_id))
        if asset is None:
            raise FileNotFoundError(asset_id)
        return asset

    def load_asset_bytes(self, pid: str, asset_id: str) -> bytes:
        asset = self._load_byte_asset(self._asset_dir(pid, asset_id))
        if asset is None or not asset.path:
            raise FileNotFoundError(asset_id)
        return self._read_bytes(self._p("projects", pid, asset.path))

    def delete_asset(self, pid: str, asset_id: str) -> None:
        doc_path = self._doc_path(pid, asset_id)
        if self.fs.exists(doc_path):
            self.fs.rm(doc_path)
            return
        d = self._asset_dir(pid, asset_id)
        if not self.fs.exists(d):
            raise FileNotFoundError(asset_id)
        self.fs.rm(d, recursive=True)

    # --- tasks (type: task; own folder, own attachments) -------------------
    def _tasks_dir(self, pid: str) -> str:
        return self._p("projects", pid, "tasks")

    def _task_dir(self, pid: str, tid: str) -> str:
        return posixpath.join(self._tasks_dir(pid), tid)

    def _task_path(self, pid: str, tid: str) -> str:
        return posixpath.join(self._task_dir(pid, tid), "task.md")

    def save_task(self, pid: str, task: Task) -> None:
        meta = {
            "type": "task",
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "created_at": task.created_at.isoformat(),
            # attachment index inlined in the task concept; binaries sit next to it
            "assets": [a.model_dump(mode="json") for a in task.assets] or None,
        }
        self._write_text(self._task_path(pid, task.id), _dump_concept(meta, task.body))

    def load_task(self, pid: str, tid: str) -> Task:
        path = self._task_path(pid, tid)
        if not self.fs.exists(path):
            raise FileNotFoundError(tid)
        meta, body = _load_concept(self._read_text(path))
        assets = meta.get("assets") or []
        for a in assets:
            _legacy_summary_to_description(a)
        data = {
            "id": meta.get("id", tid),
            "title": meta.get("title", ""),
            "description": meta.get("description") or meta.get("summary") or "",
            "body": body,
            "assets": assets,
        }
        if meta.get("created_at"):
            data["created_at"] = meta["created_at"]
        return Task.model_validate(data)

    def list_tasks(self, pid: str) -> list[Task]:
        d = self._tasks_dir(pid)
        if not self.fs.exists(d):
            return []
        tasks: list[Task] = []
        for sub in sorted(self.fs.ls(d, detail=False)):
            tid = posixpath.basename(sub.rstrip("/"))
            if self.fs.exists(self._task_path(pid, tid)):
                tasks.append(self.load_task(pid, tid))
        return tasks

    def save_task_asset(self, pid: str, task: Task, asset: Asset, filename: str, data: bytes) -> None:
        rel = f"assets/{filename}"  # relative to the task's own folder
        self._write_bytes(posixpath.join(self._task_dir(pid, task.id), rel), data)
        asset.path = rel
        task.assets.append(asset)
        self.save_task(pid, task)

    def delete_task(self, pid: str, tid: str) -> None:
        d = self._task_dir(pid, tid)
        if not self.fs.exists(d):
            raise FileNotFoundError(tid)
        self.fs.rm(d, recursive=True)
