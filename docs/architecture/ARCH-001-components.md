---
id: ARCH-001
title: totebag Main Components
type: component
c4_level: L3
status: approved
tags: [components, sinks, cli]
---

## Purpose

Describe the main components inside the totebag process and how they collaborate to turn a CLI
command into a change on a store, and back into the "restore" blob an agent reads. This is the
L3 view of the single totebag container.

## Overview

totebag is one command-line application with no server and no database. A command enters through
the CLI, is validated and orchestrated by the Store against the Domain Model, and is carried out
against the active store through the Sink interface (REQ-005). The Sink is an abstraction: it
defines the versioned set of store operations (REQ-010), and each concrete sink decides how items
are actually kept. The default concrete sink is the OKF Sink, which keeps items as an OKF v0.2
bundle over a filesystem, whether local disk or cloud object storage (REQ-004). Other sinks, such
as a remote-server sink reached over an API, implement the same interface with their own
representation and are not bound to OKF. Because the Store and Domain Model depend only on the
interface, switching the active store from one concrete sink to another is a configuration change,
not a code change (REQ-002, REQ-003).

## Components

The CLI is the only entry point (REQ-001). It exposes one subcommand per store operation, groups
them by entity (project, note, link, doc, asset, task, tool) plus top-level init, config,
and search, and enforces inputs the Store also guards, such as the required summary on stored
content. The config command reports the active store and where its data lives. It renders terse
text for humans and JSON for agents and holds no persistence logic of its own.

The Domain Model defines the typed entities and their validation rules, including the
required-summary rule, so that unsummarized content cannot be constructed regardless of entry
point.

The Store is the application core. It orchestrates every operation, validates input, assigns
identifiers and last-update dates through the ID Generator, and dispatches each operation to the
active sink through the Sink interface. It deals in Domain Model items and holds no knowledge of
how any sink represents them.

The Sink is the storage interface: the abstract, versioned contract of store operations for one
destination (REQ-010). It is expressed in Domain Model items, not in files or bytes. Concrete
sinks implement it and are interchangeable behind it (REQ-003), and the Store depends only on this
interface.

The OKF Sink is the default concrete sink. It keeps items as an OKF v0.2 bundle, a tree of
Markdown files with YAML front matter, one concept file per item, over an fsspec filesystem so the
same bundle round-trips across local disk, S3, and GCS. The mapping between a Domain Model item
and its concept file, including the reserved-key remapping OKF requires, lives here and nowhere
else (REQ-004).

The OKF Bundle is the on-disk format the OKF Sink reads and writes. It is what makes content
inspectable without the CLI and diffable under version control.

The Context Builder reads a project's items through the Store and assembles them into one ordered
Markdown document. It is read-only and has no persistence responsibility.

The ID Generator issues the prefixed identifiers the Store assigns to new items (REQ-014).

## Interactions

A write command flows CLI to Store to Sink: the CLI parses and validates input and calls the
Store; the Store constructs or updates a Domain Model item, assigns any new identifier and the
last-update date, and hands the item to the active sink, which keeps it in its own representation.

A read or restore command flows CLI to Store to Sink and back: the Store asks the active sink for
the stored items, receives Domain Model items, and either returns them to the CLI or passes the
project to the Context Builder, which returns the single restore blob. A sink can return an item as
its identifier and summary alone, so a caller can survey a store cheaply and fetch full content
only where needed (REQ-016).

Search runs above the Sink as a scan over the items the active sink returns, so it functions on
any destination whether or not that destination can search. A sink able to search may answer
queries directly.

The active store is selected once per invocation (REQ-008) and resolved to its concrete sink from
the store's destination identifier, so switching destinations is a configuration change rather
than a code change (REQ-002).

## Constraints and Decisions

- Storage is reached through an abstract, versioned Sink interface, so new destinations are added
  as concrete sinks without changing the CLI, Store, or Domain Model. See
  [ADR-001](decisions/ADR-001-pluggable-sink-interface.md) (REQ-002, REQ-003, REQ-010).
- The default OKF Sink keeps content as human-readable Markdown with YAML front matter in an OKF
  v0.2 bundle; other sinks are not bound to OKF. See
  [ADR-002](decisions/ADR-002-okf-file-format.md) (REQ-004).
- A remote-server sink is assumed to implement the same Sink interface behind its API. See
  [AAR-001](assumptions/AAR-001-remote-sink-interface.md) (REQ-003).
