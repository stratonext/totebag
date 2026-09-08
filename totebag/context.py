"""Assemble a project's (or workspace's) knowledge into one markdown blob - the thing an agent reads
to rehydrate ("restore knowledge"). Summary-first, then the full contents.
"""

from __future__ import annotations

from .models import BYTES_CATEGORIES, TOOL_CATEGORIES, AssetCategory, Project, Workspace
from .store import Store


def build_workspace_context(store: Store, workspace: Workspace) -> str:
    """The workspace-level restore blob for a department agent: its charter plus a cheap index of
    its workstream projects. The agent drills into a workstream with `project context`."""
    lines: list[str] = [f"# Department: {workspace.name}  ({workspace.id})"]
    if workspace.description:
        lines.append(f"\n{workspace.description}")

    if workspace.instructions:
        lines.append("\n## Charter\n")
        lines.append(workspace.instructions)

    view = store.summarize_workspace(workspace.id, recursive=True)
    projects = view.get("projects", [])
    lines.append("\n## Workstreams (projects)\n")
    if projects:
        for p in projects:
            line = f"- **{p.get('name') or ''}** ({p['id']})"
            if p.get("description"):
                line += f" - {p['description']}"
            lines.append(line)
        lines.append("\n_Load a workstream with `totebag -p <prj_id> project context`._")
    else:
        lines.append("_No projects yet._")

    return "\n".join(lines) + "\n"


def build_context(store: Store, project: Project) -> str:
    lines: list[str] = [f"# Project: {project.name}  ({project.id})"]
    if project.description:
        lines.append(f"\n{project.description}")
    lines.append(f"\n**Status:** {project.status.value}  |  **Type:** {project.type.value}")

    if project.instructions:
        lines.append("\n## Instructions\n")
        lines.append(project.instructions)

    tools = [a for a in project.assets if a.category in TOOL_CATEGORIES]
    if tools:
        lines.append("\n## Tools & skills\n")
        lines.append("_Dependencies this project needs; download any with an attached file if missing._")
        for tool in tools:
            line = f"- **{tool.name}** (_{tool.category.value}_) - {tool.description}"
            if tool.path:
                line += "  [file attached]"
            lines.append(line)

    if project.notes:
        lines.append("\n## Notes\n")
        lines.extend(f"- {note}" for note in project.notes)

    if project.links:
        lines.append("\n## Links\n")
        for link in project.links:
            line = f"- [{link.name}]({link.url}) - _{link.type.value}_"
            if link.description:
                line += f": {link.description}"
            lines.append(line)

    docs = [a for a in project.assets if a.category == AssetCategory.document]
    if docs:
        lines.append("\n## Docs\n")
        for doc in docs:
            lines.append(f"\n### {doc.name}  ({doc.id})")
            if doc.description:
                lines.append(f"_{doc.description}_")
            lines.append("")
            lines.append(doc.body)

    files = [a for a in project.assets if a.category in BYTES_CATEGORIES]
    if files:
        lines.append("\n## Assets\n")
        for asset in files:
            line = f"- **{asset.name}** ({asset.id}, {asset.media_type}, {asset.size} bytes)"
            if asset.description:
                line += f" - {asset.description}"
            lines.append(line)

    tasks = store.list_tasks(project.id)
    if tasks:
        lines.append("\n## Open tasks (future work to pick up later)\n")
        for task in tasks:
            line = f"- **{task.title}** ({task.id}) - {task.description}"
            if task.assets:
                line += f"  [{len(task.assets)} attachment(s)]"
            lines.append(line)

    return "\n".join(lines) + "\n"
