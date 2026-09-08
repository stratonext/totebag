# CLI Output Conventions

A portable ruleset for a terminal CLI that is read by **both humans and AI agents**. Distilled from
totebag. Framework-agnostic in principle; the snippets assume Typer/Click + rich (swap freely).

## The one principle

**Two audiences, one command.** A human at a terminal wants color, alignment, and rendered
markdown. An agent (or a pipe, or a script) wants plain, stable, parseable text. Detect which, and
never make the machine pay for the human's polish.

Everything below follows from this.

---

## Rules

### 1. Decide "human vs machine" once, centrally
One predicate gates every cosmetic choice. Human = interactive TTY **and** not in JSON/agent mode.

```python
def _is_human_tty() -> bool:
    return sys.stdout.isatty() and not _OUT.json
```

- **Agent mode** is explicit: an env var (`<TOOL>_AGENT_MODE=1`) and/or a `--json` flag. Set it once
  at startup; it also forces plain help.
- **Piped** output (`| cat`, `> file`) is auto-detected via `isatty()` — plain even without the flag.

### 2. Color is a no-op off-TTY
Route all styling through one helper that returns the raw string when not human. Never call the
styler inline.

```python
def _color(text, fg=None, bold=False, dim=False):
    if not _is_human_tty():
        return text
    return typer.style(text, fg=fg, bold=bold, dim=dim)
```

Result: piped/agent output has **zero ANSI escapes** (assert this in a test).

### 3. `list` = one aligned row per record; never dump big fields
A list is a scannable inventory, not a full dump.
- One line per record. Columns sized from the data (`name_w = min(max(len(n) for n), CAP)`).
- **Long free-text (descriptions, bodies, commands) is truncated to terminal width** with `…`, and
  **only when human** — piped output stays full so nothing is lost.
- **Never render a large field inline** (a multi-line command, a body). Replace it with a flag
  (`[file]`, `[restore]`) and move the full value to the detail view.

```python
def _truncate(text, width):
    text = " ".join(text.split())          # collapse newlines → one line
    return text if len(text) <= width else text[: max(1, width - 1)].rstrip() + "…"
```

### 4. Pair every truncated `list` with a `get` (detail view)
The standard is **`list` (summary) + `get <id>` (full)**, plus `--json` for the machine. If `list`
hides something, `get` must show it in full. Mirror this for every entity.

### 5. Render markdown/code with a real renderer on TTY; raw when piped
For any field that *is* markdown or code (a doc body, a report, an assembled blob): render it with
rich `Markdown` for a human (styled headers, syntax-highlighted fenced code); emit the **raw source**
when piped, so a machine gets exact bytes.

```python
def _render_markdown(text):
    if not _is_human_tty():
        typer.echo(text); return
    try:
        from rich.console import Console
        from rich.markdown import Markdown
    except ImportError:
        typer.echo(text); return        # rule 8: degrade, don't crash
    Console().print(Markdown(text))
```

### 6. Color via shared helpers, not per-command
Put label/field coloring in the *shared* formatters (the `key: value` printer, the field emitter,
the tree). Coloring one helper colors every `get`/`show`/`info`/`summarize` at once — consistent and
cheap. Avoid hand-coloring 100 call sites.

### 7. A consistent, conventional palette
Pick a small palette and apply it everywhere. What totebag used:

| Element | Style |
|---|---|
| id / positional index / counts | dim |
| type / category / field label | cyan |
| name / title (the primary handle) | bold |
| status | green if healthy/active, yellow otherwise |
| URL | blue |
| section header (grouped view) | magenta bold |
| flags / attention markers | yellow |

Semantic, not decorative — the color should *mean* something.

### 8. Degrade gracefully; the pretty layer is optional
Rich (or any renderer) may be a transitive/optional dep. Guard imports with `try/except ImportError`
and fall back to plain `echo`. The CLI must fully work with zero styling libraries installed.

### 9. Errors are messages, not tracebacks
Catch the *expected* exceptions (`FileNotFoundError`, validation, not-found) and print a one-line
message via a `_fail()` that exits non-zero. A stack trace is a bug, not UX. Do this uniformly across
sibling commands (if `task delete` guards a missing id, so must `doc/asset/tool delete`). Also keep
the destructive verb itself consistent across entities — pick one (`delete`) and use it everywhere.

### 10. Filtered views partition cleanly — no overlap
When several commands are views over one underlying collection (e.g. `doc`/`tool`/`asset` over one
asset store), make them a **partition** by category: each id shows in exactly one command's `list`.
Overlap re-creates the confusion the unification removed.

### 11. Structure helps the machine too
Terse ≠ shapeless. Keep counts (`tools (3):`), stable id prefixes (`prj_`, `doc_`), and `--json` that
returns the real objects. Agents parse structure; don't strip it for terseness.

### 12. Lock it down with two tests
- **Piped output is plain:** run a colored command through a pipe, assert **no `\x1b`** in output.
- **`--json` round-trips:** assert the JSON parses and carries the fields the pretty view hides.

---

## Checklist for a new CLI

- [ ] One `_is_human_tty()` gate; agent mode via env + `--json`; piped auto-detected.
- [ ] `_color`, `_truncate`, `_render_markdown` helpers; all styling routed through them.
- [ ] Every `list`: aligned columns, human-only truncation, big fields → flags.
- [ ] Every entity has `list` + `get` + `--json`.
- [ ] Markdown/code fields rendered on TTY, raw when piped.
- [ ] Shared formatters colored once; conventional semantic palette.
- [ ] `try/except ImportError` around the renderer; plain fallback.
- [ ] Expected exceptions → `_fail()` one-liners, applied uniformly.
- [ ] Filtered views partition without overlap.
- [ ] Tests: piped = no ANSI; `--json` = complete + parseable.
