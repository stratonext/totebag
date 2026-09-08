# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-07

Initial release.

### Added

- Portable, vendor-neutral project-knowledge CLI (`totebag`) that any AI Agent restores over a
  single shell command. No server, no API keys.
- The store: an abstraction over the physical storage layer, selected by a root URL - `file://`
  (default, at `~/.totebag`), `s3://`, and `gcs://` via `fsspec`, with `s3` and `gcs` install
  extras. The same OKF tree round-trips across all three.
- Default on-disk format: an Open Knowledge Format (OKF) v0.2 bundle of markdown-with-front-matter
  files; git-diffable and editor-readable. Store config in `config.yaml`.
- Workspaces and projects, with per-item types: docs, notes, links, lists, assets, tools, and tasks.
- The description rule: stored content must carry a caller-written description or it is rejected.
- Progressive discovery: `get --brief` (and `--recursive`) return id + description without full
  content; `project context` assembles the full restore blob for an agent.
- Active workspace and project as ambient context, resolved from `-w`/`-p` flags, the
  `TOTEBAG_WORKSPACE`/`TOTEBAG_PROJECT` environment variables, or per-container defaults set with
  `workspace use` / `project use`. `config` reports both and where each came from.
- Lists: named, schema-free entry collections. Batch append as JSONL, remove an entry by index,
  and export to CSV (columns are the union of all entry keys).
- Substring `search` across a project or workspace.
- `totebag --skill` prints the bundled agent guide; `--version` prints the version.

[0.1.0]: https://github.com/stratonext/totebag/releases/tag/v0.1.0
