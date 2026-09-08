---
id: ADR-004
title: One Asset Concept for Documents, Tools/Skills, and Byte Files
status: accepted
supersedes: []
superseded_by: []
tags: [model, assets, storage, unification]
---

## Context

The domain model carried three near-parallel item types that overlapped in confusing ways. A `Doc`
was editable markdown (`id, title, description, body`) stored as its own file; an `Asset` was opaque
bytes plus metadata; a `Tool` was a dependency pointer (`kind, description, restore`) with no content
at all, stored inline in the project's front matter. In practice a document is just a *text* asset,
and a tool is an asset-shaped record whose purpose is to describe a dependency rather than hold
content. Three types for one idea (a stored project item) meant duplicated store methods, three
search loops, and a `tools`-inline special case in the project serializer.

## Decision

Collapse `Doc` and `Tool` into a single `Asset` model, discriminated by `AssetCategory`
(`document`, `binary`, `generic`, `transcript`, `tool`, `skill`). Content lives in whichever field
the category uses: `body` for documents, `path`/`size`/`media_type` for byte files. `ToolKind` is
deleted — its `tool`/`skill` values fold into the category. One set of store and sink operations
(add/get/list/update/read-bytes/remove) serves every category.

**A tool is just an asset.** A tool/skill is a byte asset with a tool category; it may carry an
uploaded file (a script, a binary) or be fileless (a named dependency). It is stored, listed, and
downloaded exactly like any other asset. The CLI therefore makes `tool` a filtered view over assets
— `tool add` (with an optional file), `tool list`, `tool get`, `tool download`, `tool rm` — the same
surface `asset` exposes, scoped to the tool categories.

On disk there are only two shapes. `document` is special: editable text kept in `docs/<id>.md` as an
OKF `type: document` (chosen so a generic OKF reader still sees prose as prose, and so text edits
stay diffable). **Every other category** — byte files and tools/skills alike — is a byte asset in
`assets/<id>/` (`type: asset`, `category` in its `asset.md`), with or without a sibling binary. Tools
thus leave the inline `project.md` array and become ordinary assets.

`asset`, `tool`, and `doc` partition the categories: `asset` lists the plain byte files
(binary/generic/transcript), `tool` the tool/skill assets, `doc` the documents — no overlap.

This is a breaking on-disk change. Because it landed at `0.1.0rc1`, before any release depended on
the format, **no migration path is provided** — the change is clean rather than shimmed.

## Consequences

### Positive
- One model, one description-required path, one search loop, one sink operation set.
- Tools become ordinary assets: uploadable, downloadable, inspectable files instead of buried
  front-matter, with no bespoke storage path.
- Documents keep their OKF `type: document`, so prose stays diffable and legible to a generic OKF
  reader (§ADR-002).

### Negative
- The `Asset` model has fields only some categories use (empty otherwise); a flat model with an
  "unused field stays empty" convention is accepted over a discriminated union for its simplicity.
- Tools no longer self-identify as OKF `type: tool` — they are `type: asset` with `category: tool`.
  Accepted: the tool-vs-asset distinction is a category concern, and treating a tool as a first-class
  asset (upload/download) was the explicit goal.
- Old on-disk stores that kept tools inline in `project.md` are not read; acceptable pre-release.

## Alternatives Considered

- **A separate `tools/` tree of `type: tool` concept files (content-less):** rejected — it made a
  tool a special metadata record rather than an asset, so it could not be uploaded or downloaded like
  one; the whole point was that a tool *is* an asset, just categorized.
- **Flatten documents to `type: asset` too:** rejected — text documents benefit from staying OKF
  `type: document` (diffable prose, legible to generic OKF readers); only `document` keeps a distinct
  on-disk type.
- **Keep tools inline in `project.md` like notes/links:** rejected — it leaves a special case in the
  project serializer and makes tools the one asset that isn't file-backed.
- **A Pydantic discriminated union / subclasses per category:** rejected as over-engineering at this
  field count; revisit only if a category ever needs a conflicting field *type*.
