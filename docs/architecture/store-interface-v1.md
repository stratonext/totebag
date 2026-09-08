---
title: Store Interface v1
type: reference
status: approved
tags: [interface, store, sink, v1]
---

# Store Interface v1

The v1 store interface is the exact capability set a v1 store provides, referenced by
[REQ-010](../requirements.md#req-010--store-interface-version). A store declaring v1 MUST
implement every operation below and MUST NOT expose operations outside this set.

## 1. Workspace

A workspace is the top-level container. It holds many projects. A store MAY hold many workspaces.

| Operation | Description |
|---|---|
| Create | Create a workspace. |
| Get | Retrieve a workspace by identifier. |
| List | List all workspaces. |
| Update | Update a workspace's fields. |
| Delete | Delete a workspace and everything it contains. |

## 2. Projects

A project belongs to one workspace.

| Operation | Description |
|---|---|
| Create | Create a project. |
| Get | Retrieve a project by identifier. |
| List | List a workspace's projects. |
| Update | Update a project's fields and instructions. |
| Delete | Delete a project. |
| Set Default | Record the workspace's default project (must belong to the workspace). |
| Get Default | Report the workspace's default project, if any. |

## 3. Notes

A note is a short, short-lived piece of text: useful for temporary data or when a full document
is not warranted.

| Operation | Description |
|---|---|
| Add | Add a note to a project. |
| Get | Retrieve a note. |
| List | List a project's notes. |
| Delete | Delete a note from a project. |

## 4. Links

| Operation | Description |
|---|---|
| Add | Add a link to a project. |
| Get | Retrieve a link. |
| List | List a project's links. |
| Delete | Delete a link from a project. |

## 5. Assets

An asset is any stored item, distinguished by a **category**: a `document` (editable markdown), a
byte file (`binary`, `generic`, `transcript`), or a `tool`/`skill` (a dependency, with an optional
uploaded file). A document keeps its text in the item (`body`); every other category is a byte asset
that may carry a file. One operation set covers all categories; the `tool` and `doc` command groups
are filtered views over it.

| Operation | Description |
|---|---|
| Add | Add an asset of any category (with its content and required description). |
| Get | Retrieve an asset (metadata plus `body` for documents). |
| List | List a project's assets (optionally filtered by category). |
| Update | Update an asset's fields or content. |
| Read Bytes | Read a byte asset's bytes. |
| Delete | Delete an asset. |

## 6. Lists

A list is a named collection of schema-free entry records. The store does not validate entry
fields; the caller keeps keys consistent. Entries are added in batches, never one at a time.

| Operation | Description |
|---|---|
| Create | Create a list with a name and a description. |
| Get | Retrieve a list and its entries. |
| List | List a project's lists. |
| Add Entries | Append a batch of one or more entries to a list. |
| Delete Entry | Delete a single entry from a list by its position. |
| Export | Return the list's entries as CSV. |
| Delete | Delete a list. |

## 7. Tasks

A task is a deferred piece of work to pick up later - future/postponed work, not a tracker for
work in progress. A task SHOULD be removed once completed, though this is not mandatory.

| Operation | Description |
|---|---|
| Add | Add a task. |
| Get | Retrieve a task (its detail and attachment index). |
| List | List a project's tasks. |
| Attach | Attach an asset to a task. |
| Download | Read the bytes of one of a task's attachments. |
| Delete | Delete a task. |

## 8. Search

| Operation | Description |
|---|---|
| Search | Search stored content across a project or a whole workspace. |

## 9. Configuration

| Operation | Description |
|---|---|
| Info | Report the active sink and where its data lives. |
