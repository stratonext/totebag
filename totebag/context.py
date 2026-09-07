"""Assemble a project's knowledge into one markdown blob - the thing an agent reads to
rehydrate ("restore knowledge"). Summary-first, then the full contents.
"""

from __future__ import annotations

from .models import Project
from .store import Store


def build_context(store: Store, project: Project) -> str:
    lines: list[str] = [f"# Project: {project.name}  ({project.id})"]
    if project.description:
        lines.append(f"\n{project.description}")
    lines.append(f"\n**Status:** {project.status.value}  |  **Type:** {project.type.value}")

    if project.instructions:
        lines.append("\n## Instructions\n")
        lines.append(project.instructions)

    if project.tools:
        lines.append("\n## Tools & skills\n")
        lines.append("_Restore any that aren't already available before starting work._")
        for tool in project.tools:
            line = f"- **{tool.name}** (_{tool.kind.value}_) - {tool.description}"
            if tool.restore:
                line += f"\n  - restore: `{tool.restore}`"
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

    docs = store.list_docs(project.id)
    if docs:
        lines.append("\n## Docs\n")
        for doc in docs:
            lines.append(f"\n### {doc.title}  ({doc.id})")
            if doc.description:
                lines.append(f"_{doc.description}_")
            lines.append("")
            lines.append(doc.body)

    if project.assets:
        lines.append("\n## Assets\n")
        for asset in project.assets:
            line = f"- **{asset.name}** ({asset.id}, {asset.media_type}, {asset.size} bytes)"
            if asset.description:
                line += f" - {asset.description}"
            lines.append(line)

    tasks = store.list_tasks(project.id)
    if tasks:
        lines.append("\n## Open tasks (work to do)\n")
        for task in tasks:
            line = f"- **{task.title}** ({task.id}) - {task.description}"
            if task.assets:
                line += f"  [{len(task.assets)} attachment(s)]"
            lines.append(line)

    journal = store.list_journal(project.id)
    if journal:
        lines.append("\n## Journal (recent work, newest first)\n")
        for entry in journal[:7]:  # last 7 days in-context; the full log stays on disk
            lines.append(f"\n### {entry.date}")
            lines.append(entry.body)

    return "\n".join(lines) + "\n"
