---
title: Totebag Requirements
type: requirements
status: approved
tags: [requirements, sinks, cli, portability]
---

# totebag Requirements

Requirements for `totebag`, a portable, vendor-neutral project-knowledge store. See
[project.md](project.md) for system context. Written per NASA requirement-writing rules
(`shall` = requirement, `should` = goal, `will` = fact).

## Terminology

- **Sink** - the low-level mechanism that performs byte-level persistence. A sink is local (a filesystem) or remote (object storage such as `s3://` / `gcs://`, or a server exposed via an API).
- **Store** - a sink registered in configuration under a name. The CLI operates on the active store and is agnostic to whether that store's sink is local or remote.

---

## REQ-001 - Command-Line Access

The totebag CLI shall provide a command for every store operation.

> **Rationale:** The store is agent-driven. Any agent that can run a shell command must be able to perform every operation without a second interface.

---

## REQ-002 - Sink Resolution

totebag shall resolve a store's sink at runtime from the store's destination identifier.

> **Rationale:** The destination identifier (its URI scheme) determines the storage mechanism, so a store can target any supported backend without changing application code.

---

## REQ-003 - Sink Extensibility

totebag shall support the addition of a new sink type without modification to the command layer or the domain model.

---

## REQ-004 - Open Knowledge Format Compliance (File-System only)

The totebag filesystem sink shall persist every stored item as a concept file conforming to the Open Knowledge Format (OKF) v0.2 specification.

---

## REQ-005 - Store-Agnostic Interface

The totebag CLI shall perform every store operation through a single stable interface, independent of the active store's sink.

---

## REQ-006 - Multiple Store Registration

The totebag configuration shall support registration of more than one store.

---

## REQ-007 - Single Active Store

totebag shall treat exactly one registered store as active for a command invocation.

---

## REQ-008 - Runtime Store Override

totebag shall accept a `--store` option that sets the active store for a single command invocation.

---

## REQ-009 - Store Independence

totebag shall treat each registered store as independent of every other registered store.

> **Note:** Synchronization of content between stores is out of scope. Each store holds its own content and is neither read from nor written to when another store is active.

---

## REQ-010 - Store Interface Version

Every totebag store shall declare which version of the store interface it implements.

> **Note:** Interface versions are enumerated under [docs/architecture/](architecture/); v1 is [store-interface-v1.md](architecture/store-interface-v1.md).

---

## REQ-011 - Multiple Contract Versions

totebag shall support more than one version of the store interface.

---

## REQ-012 - Unsupported Command Response

totebag shall return a not-supported message when a command is not part of the active store's declared interface version.

---

## REQ-013 - Mandatory Description

totebag shall reject persistence of any node (workspace, project, doc, asset, task, or tool) that has no caller-provided description.

> **Rationale:** The description is what the next agent skims first, so undescribed content is refused at write time rather than stored.

---

## REQ-014 - Item Identifier

Every stored item shall carry an identifier that is unique within its store.


---

## REQ-015 - Last-Updated Timestamp

Every stored item shall carry the date of its last update.

---

## REQ-016 - Progressive Discovery

totebag shall be able to return a stored item as its identifier and description alone, without its full content.

> **Rationale:** A caller can survey what exists cheaply and fetch full content only for the items it needs.
> **Note:** Depends on REQ-013 (description) and REQ-014 (identifier).

---

## REQ-017 - List Creation

totebag shall create a named list within a project, where each list carries a name and a description.

> **Rationale:** A project needs lightweight collections of records that are neither prose (docs) nor opaque bytes (assets).
> **Note:** The description satisfies REQ-013 for a list; no separate summary is required.

---

## REQ-018 - Multiple Lists

totebag shall allow a project to hold more than one list.

---

## REQ-019 - Batch Entry Addition

totebag shall add list entries in batches of one or more entries per command.

> **Rationale:** Callers append records in bulk. A single-entry command is intentionally not provided.

---

## REQ-020 - Schema-Free Entries

totebag shall store list entries without validating their fields against a schema.

> **Rationale:** The store does not know the caller's record shape. The caller is responsible for keeping keys consistent across entries.

---

## REQ-021 - CSV Export

totebag shall export a list's entries in CSV format.

> **Note:** Because entries are schema-free (REQ-020), the export columns are the union of keys across all entries.

---

## REQ-022 - List Entry Removal

totebag shall remove a single list entry identified by its position in the list.

> **Rationale:** Entries carry no identifier, so position is the only handle. The removed entry is returned so the caller can add it back.

---

## REQ-023 - Default Project

totebag shall let a workspace record a default project used by project-scoped commands when none is given.

> **Note:** Set with `project use`. Mirrors the store's default workspace (REQ-007).

---

## REQ-024 - Active Project Resolution

totebag shall resolve the active project for a project-scoped command from the command-line project option, then the project environment variable, then the workspace's default project.

> **Note:** Mirrors workspace resolution (REQ-007, REQ-008).

---

## REQ-025 - Project Workspace Membership

totebag shall require the active project to belong to the active workspace.

> **Rationale:** Projects are workspace-scoped; a project from another workspace is not addressable in the active one.
