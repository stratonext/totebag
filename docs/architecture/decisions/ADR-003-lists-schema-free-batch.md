---
id: ADR-003
title: Lists as a Schema-Free, Batch-Appended, Per-File Item Type
status: accepted
supersedes: []
superseded_by: []
tags: [lists, storage, csv, schema-free]
---

## Context

Projects need lightweight tabular collections, for example a list of prospect accounts or
endpoints, that can be handed to other tools as CSV. None of the existing item types fit: notes
and links are single values, docs are prose, and assets are opaque bytes. The records have no
fixed shape known to the store, and callers append them in bulk rather than one at a time
(REQ-017 through REQ-021).

## Decision

A list is a new item type stored as its own concept file per list, under `projects/<pid>/lists/`,
with the OKF `type: list`. The list name and description live in front matter, and the entries
live in the body as JSONL, one JSON object per line. The description is required and serves as the
list's mandatory summary (REQ-013), so no separate summary field exists.

Entries are schema-free: the store does not validate their fields. Entries are added only in
batches through a single command that reads JSONL. There is no single-entry command. Export
produces CSV whose columns are the union of keys across all entries, ordered by first appearance,
with blank cells for missing keys and JSON-encoded cells for nested values.

## Consequences

### Positive
- Lists reuse the docs storage pattern (one file per item), so a list write touches only that
  list's file and never rewrites `project.md`.
- JSONL round-trips schema-free and nested records faithfully and stays diffable under version
  control, consistent with ADR-002.
- CSV export gives callers a portable interchange format without imposing a schema on storage.

### Negative
- Because entries are schema-free, an inconsistent caller can produce a wide, sparse CSV. This is
  an accepted trade for not enforcing a schema (REQ-020).
- Lists add operations to the store interface. While the interface is draft, these are treated as
  additive and do not bump the interface version.

## Alternatives Considered

- **Store lists inline in `project.md` front matter (like notes, links, tools):** rejected because
  a list can hold many entries, which would bloat `project.md` and, on every project save, incur a
  full rewrite of that content.
- **Enforce a schema on entries:** rejected because it contradicts the requirement that the store
  not know the caller's record shape (REQ-020).
- **Provide a single-entry add command:** rejected because callers append in bulk and a per-entry
  command is unnecessary surface (REQ-019).
- **Persist entries directly as CSV on disk:** rejected because CSV cannot faithfully represent
  schema-free rows with differing keys or nested values; JSONL can.
