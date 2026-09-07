"""Data model - a lean, single-workspace

Separate item types (assets, docs, links, notes), each editable, each with a description.
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
    document = "document"
    binary = "binary"
    generic = "generic"
    transcript = "transcript"


class ToolKind(StrEnum):
    tool = "tool"
    skill = "skill"


class Link(BaseModel):
    id: str
    url: str
    name: str
    description: str = ""
    type: LinkType = LinkType.generic


class Asset(BaseModel):
    id: str
    name: str
    description: str = ""
    media_type: str = "application/octet-stream"
    category: AssetCategory = AssetCategory.generic
    size: int = 0
    path: str = ""  # sink-relative location, assigned by the sink on save (e.g. "assets/ast_x/report.pdf")


class Doc(BaseModel):
    """An editable markdown document. Stored as a .md file with YAML front-matter."""

    id: str
    title: str
    description: str | None = None
    body: str = ""


class Tool(BaseModel):
    """A tool or skill the project depends on, plus how to restore it if it's not available."""

    id: str
    name: str
    kind: ToolKind = ToolKind.tool
    description: str  # required: what it does / why the project needs it
    restore: str = ""  # command or steps to install/enable it when missing


class Task(BaseModel):
    """A unit of work to do. Stored in its own folder alongside any attachments."""

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


class JournalEntry(BaseModel):
    date: str  # YYYY-MM-DD
    body: str  # markdown bullet list of work done that day


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    type: ProjectType = ProjectType.other
    status: ProjectStatus = ProjectStatus.active
    instructions: str = ""
    links: list[Link] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)
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
