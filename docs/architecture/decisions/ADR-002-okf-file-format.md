---
id: ADR-002
title: OKF Markdown-with-Front-Matter On-Disk Format
status: accepted
supersedes: []
superseded_by: []
tags: [format, storage, inspectability]
---

## Context

Content kept by the default sink must be inspectable without the totebag CLI and must not lock
users into a vendor-specific representation (REQ-004). A binary or database format would make the
store opaque and tie inspection to a running tool, undermining portability. This decision governs
the default OKF Sink only; other concrete sinks choose their own representation (ADR-001).

## Decision

The default sink, the OKF Sink, keeps every item as a UTF-8 Markdown file with a YAML front-matter
header, arranged as an Open Knowledge Format (OKF) v0.2 bundle: a concept tree whose per-item
`type` names its kind (project, note, link, document, asset, tool, task, journal) and whose bundle
root declares the OKF version. Structured fields live in front matter; free-form text lives in the
Markdown body. OKF is the concern of this sink alone.

## Consequences

### Positive
- Any item opens in a text editor with no tooling, satisfying REQ-004.
- The tree is diffable and mergeable under version control.
- Adopting an existing open format avoids inventing a proprietary schema and eases
  interoperability with other OKF readers.

### Negative
- The format reserves front-matter keys such as `type`, forcing domain fields like project type
  and tool kind to be remapped on save and load. The OKF Sink must keep these mappings correct.
- Text files are less compact than a binary store and carry parsing overhead at scale, an
  accepted trade for inspectability at knowledge-store sizes.

## Alternatives Considered

- **A single database file (for example SQLite):** rejected because it is not human-readable
  without a tool and weakens portability and inspectability.
- **A bespoke JSON or YAML schema of our own:** rejected in favour of an existing open format so
  the store is not vendor-specific and can interoperate with other OKF tooling.
