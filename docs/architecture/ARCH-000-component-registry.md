---
id: ARCH-000
title: Component Registry
type: component
c4_level: L3
status: approved
tags: [registry]
---

## Purpose

Single source of truth for every component named in totebag architecture documents. Any
component referenced in an ARCH document is defined here once, with its type, technology, and
single responsibility. ARCH documents refer to these components by name and do not repeat
these fields.

## Registry

| Component | Type | Technology | Responsibility |
|---|---|---|---|
| CLI | Command layer | Typer | Parse subcommands, enforce required inputs, format terse or JSON output. |
| Domain Model | Data model | Pydantic v2 | Typed entities (Project, Doc, Note, Link, Asset, Tool, Task, JournalEntry) and their validation, including the required-summary rule. |
| Store | Application core | Python | Orchestrate and validate every operation and dispatch it to the active sink through the Sink interface. Holds no storage-representation knowledge. |
| Sink | Storage interface | Abstract contract | The versioned set of store operations for one destination. Concrete sinks implement it and are interchangeable behind it. |
| OKF Sink | Concrete sink | fsspec + Markdown/YAML | Default sink. Persist items as an OKF v0.2 bundle over an fsspec filesystem (local disk, S3, GCS). |
| OKF Bundle | Data format | Markdown + YAML front matter | On-disk representation produced by the OKF Sink. |
| Context Builder | Component | Python | Assemble one project's stored items into the single Markdown "restore" blob an agent reads. |
| ID Generator | Component | Python `secrets` | Produce prefixed, collision-resistant identifiers (`prj_`, `doc_`, `tsk_`, and so on). |

## Notes

- The Sink is an interface, not a storage system. Concrete sinks implement it; the OKF Sink is
  the only one today. Adding a destination adds a concrete sink and nothing else (REQ-003, ADR-001).
- OKF is the concern of the OKF Sink alone (REQ-004, ADR-002). Other sinks, such as a remote-server
  sink, implement the same interface with their own representation and are not bound to OKF.
- The OKF Bundle is a data format, not runnable code. It is registered because ARCH documents
  refer to it by name.
