"""Data model - a lean, single-workspace store.

One `Asset` covers docs, tools/skills, and byte files (distinguished by `AssetCategory`); links and
notes stay their own small types. Everything is editable and carries a required description.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class Stamp(BaseModel):
    """An OKF actor+time event (§5.2). `by` uses the actor convention (§7):
    `<producer>/<version>`, `human:<id>`, or `process:<id>`."""

    by: str
    at: datetime = Field(default_factory=_now)


class LinkType(StrEnum):
    generic = "generic"
    source_code = "source_code"
    documentation = "documentation"
    tool = "tool"


class ProjectType(StrEnum):
    software_application = "software_application"
    other = "other"


class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


class AssetCategory(StrEnum):
    document = "document"    # editable markdown, content in `Asset.body`
    binary = "binary"        # bytes on disk, located by `Asset.path`
    generic = "generic"      # bytes on disk (default for uploads)
    transcript = "transcript"  # bytes on disk
    tool = "tool"            # a tool dependency, stored like a byte asset (file optional)
    skill = "skill"          # an agent skill dependency, stored like a byte asset (file optional)


# Category groupings, so callers filter one flat Asset list by purpose without repeating the sets.
BYTES_CATEGORIES = frozenset({AssetCategory.binary, AssetCategory.generic, AssetCategory.transcript})
TOOL_CATEGORIES = frozenset({AssetCategory.tool, AssetCategory.skill})


class Link(BaseModel):
    id: str
    url: str
    name: str
    description: str = ""
    type: LinkType = LinkType.generic


class Asset(BaseModel):
    """A stored item, unified across purposes. `category` decides where content lives:
    a `document` keeps editable markdown in `body`; the byte categories (including tool/skill)
    keep a file located by `path`. One flat model, empty fields for the modes a given category
    doesn't use."""

    id: str
    name: str
    description: str = ""
    category: AssetCategory = AssetCategory.generic
    body: str = ""  # document only: the markdown content
    media_type: str = "application/octet-stream"  # byte categories only
    size: int = 0  # byte categories only
    path: str = ""  # byte categories only: sink-relative location, assigned by the sink on save


class Task(BaseModel):
    """A deferred piece of work to pick up later. Stored in its own folder alongside any attachments."""

    id: str
    title: str
    description: str  # required: what the task is
    body: str = ""
    assets: list[Asset] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class EntryList(BaseModel):
    """A named collection of schema-free entry records, exportable as CSV.

    Named `EntryList` to avoid shadowing the builtin `list`. Stored as its own .md file (like a
    doc): metadata in front-matter, entries as a JSONL body. No schema is enforced on entries;
    the caller keeps keys consistent. `description` is required and doubles as the caller summary.
    """

    id: str
    name: str
    description: str  # required: what the list holds; serves as the mandatory summary
    entries: list[dict[str, Any]] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    type: ProjectType = ProjectType.other
    status: ProjectStatus = ProjectStatus.active
    instructions: str = ""
    links: list[Link] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)  # every category: docs, tools, and byte files
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    # OKF provenance (§5.2): how the content was produced.
    generated: Stamp | None = None


class Workspace(BaseModel):
    """A top-level container of projects. A store may hold many; one is active at a time."""

    id: str
    name: str = "workspace"
    description: str = ""
    default_project: str | None = None  # the workspace's default project id, used when none is given
    created_at: datetime = Field(default_factory=_now)
