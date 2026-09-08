#!/usr/bin/env python3
"""Generate Claude Code subagent files from totebag workspace charters — the `personas` plugin.

Each totebag workspace becomes a persona agent: `<out>/<slug>.md`, whose system prompt is the
workspace's charter (its `instructions`) plus a fixed memory protocol scoped to that workspace.
It also **auto-restores skills, isolated per agent**: every `skill`-category asset that carries a
file, across the workspace's projects, is downloaded to a PRIVATE dir
`~/.claude/personas/<persona>/<skill>/SKILL.md` — NOT the global `~/.claude/skills/`, so a persona's
skills are not visible to other agents or the main session. The agent's system prompt lists them and
it `Read`s the relevant one on demand. Re-run any time to resync after a charter or skill changes.
totebag is the portable source of truth; these files are a generated projection.

Usage:
    python generate_agents.py                 # all personas -> agents + their private skills
    python generate_agents.py --only marketing
    python generate_agents.py --out ./.claude/agents --skills-base ~/.claude/personas
    python generate_agents.py --no-skills     # agent files only

Reads totebag over the CLI only (never touches the store's files), so it works against any sink
(file/s3/gcs/remote). Requires `totebag` on PATH and a configured store ($TOTEBAG_ROOT).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MEMORY_PROTOCOL = """\
## Operating protocol (totebag memory)

You are the **{name}** agent. Your persistent memory is the totebag workspace `{wid}`.

- **Scope yourself first.** Run `export TOTEBAG_WORKSPACE={wid}` at the very start of the session so
  every command targets your workspace — then project-scoped commands work with `-p <prj_id>` alone.
  (Without it, project commands need both `-w {wid}` and `-p <prj_id>`.)
- **Restore first.** Run `totebag workspace context` to reload your charter and workstreams, then
  `totebag -p <prj_id> project context` for the workstream you'll work.
- **Write back as you go.** Persist durable facts, decisions, and follow-ups immediately
  (`note add`, `doc add`, `task add`). Your context window is ephemeral; totebag is not — anything a
  future spin-up of you would need must live in the workspace, not just this conversation.
- **Stay in scope.** Act only within your scope. If work belongs to another persona, say so and hand
  it back to the orchestrator instead of doing it yourself.
- **Honor the charter's escalation rules** stated above.
"""

TEMPLATE = """\
---
name: {slug}
description: {description_json}
tools: Bash, Read, Grep, Glob, Edit, Write
---
{charter}

{protocol}
"""


def _totebag(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "TOTEBAG_AGENT_MODE": "1"}  # JSON + plain output
    return subprocess.run(["totebag", *args], capture_output=True, text=True, env=env)


def totebag_json(*args: str) -> object:
    """Run a totebag command in agent mode and parse its stdout as JSON."""
    proc = _totebag(*args)
    if proc.returncode != 0:
        sys.exit(f"totebag {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(proc.stdout)


def totebag_ok(*args: str) -> bool:
    """Run a totebag command for effect; return whether it succeeded (warn on failure)."""
    proc = _totebag(*args)
    if proc.returncode != 0:
        print(f"  ! totebag {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}", file=sys.stderr)
    return proc.returncode == 0


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "persona"


def restore_skills(ws: dict, skills_base: Path) -> list[dict]:
    """Materialize the persona's skills into a PRIVATE, per-agent directory (not the global
    `~/.claude/skills/`, so they aren't visible to other agents or the main session). For every
    `skill`-category asset that carries a file, across the workspace's projects, download it to
    `<skills_base>/<persona>/<skill>/SKILL.md`. The persona dir is wiped first so a resync reflects
    the current set. Returns [{name, description, path}] for the agent's "Your skills" section."""
    persona = slugify(ws["name"])
    persona_dir = skills_base / persona
    shutil.rmtree(persona_dir, ignore_errors=True)  # idempotent: drop stale/removed skills
    wid = ws["id"]
    restored: list[dict] = []
    for project in totebag_json("-w", wid, "project", "list"):
        pid = project["id"]
        for tool in totebag_json("-w", wid, "-p", pid, "tool", "list"):
            if tool.get("category") != "skill" or not tool.get("path"):
                continue  # only skills that actually carry a file can be restored
            dest = persona_dir / slugify(tool["name"]) / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if totebag_ok("-w", wid, "-p", pid, "tool", "download", tool["id"], str(dest)):
                restored.append({"name": tool["name"], "description": tool.get("description") or "", "path": str(dest)})
    return restored


def _skills_section(skills: list[dict]) -> str:
    if not skills:
        return ""
    lines = [
        "\n## Your skills (private to you)",
        "",
        "These procedures are yours alone — not global Claude Code skills. `Read` the relevant one"
        " before that kind of work:",
        "",
    ]
    for s in skills:
        desc = f" — {s['description']}" if s["description"] else ""
        lines.append(f"- **{s['name']}**{desc}\n  `{s['path']}`")
    return "\n".join(lines) + "\n"


def render(ws: dict, skills: list[dict]) -> str:
    name, wid = ws["name"], ws["id"]
    charter = (ws.get("instructions") or "").strip() or (
        f"# {name} charter\n\n"
        f"_No charter set yet — add one with_ `totebag -w {wid} workspace update --stdin`."
    )
    description = (ws.get("description") or f"{name} agent").replace("\n", " ").strip()
    return TEMPLATE.format(
        slug=slugify(name),
        description_json=json.dumps(description),  # JSON string is valid YAML — safe for any chars
        charter=charter,
        protocol=MEMORY_PROTOCOL.format(name=name, wid=wid),
    ) + _skills_section(skills)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate persona subagent files from totebag workspace charters.")
    ap.add_argument("--out", default=os.path.expanduser("~/.claude/agents"),
                    help="Output directory (default: ~/.claude/agents).")
    ap.add_argument("--format", choices=["claude", "codex"], default="claude",
                    help="Agent-file format. 'codex' is not implemented yet.")
    ap.add_argument("--only", help="Only this workspace, by name or id (default: all).")
    ap.add_argument("--skills-base", default=os.path.expanduser("~/.claude/personas"),
                    help="Base dir for PRIVATE per-persona skills (default: ~/.claude/personas). "
                         "Skills land in <base>/<persona>/<skill>/SKILL.md — NOT the global ~/.claude/skills.")
    ap.add_argument("--no-skills", action="store_true",
                    help="Only (re)generate agent files; skip downloading skills.")
    args = ap.parse_args()

    if args.format == "codex":
        sys.exit("codex format not implemented yet — Codex restores via `totebag workspace context` for now.")

    workspaces = totebag_json("workspace", "list")  # full Workspace objects, incl. instructions
    if args.only:
        workspaces = [w for w in workspaces if args.only in (w["name"], w["id"])]
        if not workspaces:
            sys.exit(f"no workspace matched: {args.only}")
    else:
        # A persona is a workspace that has a charter; skip charterless ones (e.g. the default
        # `init` workspace) so they don't become empty agents.
        workspaces = [w for w in workspaces if (w.get("instructions") or "").strip()]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    skills_base = Path(args.skills_base)
    for ws in workspaces:
        skills = [] if args.no_skills else restore_skills(ws, skills_base)  # private per-agent skills
        path = out_dir / f"{slugify(ws['name'])}.md"
        path.write_text(render(ws, skills), encoding="utf-8")
        print(path)
        for skill in skills:
            print(f"  skill: {skill['path']}")
    if not workspaces:
        print("no workspaces found", file=sys.stderr)


if __name__ == "__main__":
    main()
