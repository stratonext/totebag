---
id: ARCH-002
title: Lists Feature
type: feature
c4_level: cross-cutting
status: approved
tags: [lists, csv, feature]
---

## Purpose

Describe how a list works end to end across the totebag components, from creating it, through
appending entries in batches, to exporting the entries as CSV. This is a cross-cutting feature
view over the components defined in ARCH-001.

## Overview

A list is a named, described collection of schema-free entry records held inside a project. It
serves the need for lightweight tabular collections that are neither prose nor opaque bytes, and
that other tools can consume as CSV. The store does not enforce a schema on entries; the caller
keeps keys consistent (REQ-020). Entries are appended in batches, never one at a time (REQ-019),
and a list's description doubles as its required summary (REQ-013, REQ-017).

## Components

The Domain Model gains a list entity carrying an identifier, a name, a required description, and an
ordered collection of entry records. The Store gains the orchestration for creating a list,
appending a batch of entries, reading and listing lists, and removing a list, and it owns the pure
transformation that renders entries as CSV. The Sink interface gains the list persistence
operations, and the OKF Sink keeps each list as its own concept file, with the name and description
in front matter and the entries as a JSONL body. The CLI exposes one subcommand per list operation,
including batch entry input read as JSONL and CSV export written to a file or standard output.

## Interactions

Creating a list flows CLI to Store to Sink: the CLI collects the name and description and calls the
Store, which enforces the required description, assigns an identifier through the ID Generator, and
hands an empty list to the active sink to persist as its own file.

Adding entries flows CLI to Store to Sink: the CLI reads a batch of records as JSONL and calls the
Store, which loads the list, appends the batch in order, and saves it. No single-entry path exists.

Exporting flows CLI to Store: the CLI asks the Store for the list, the Store renders the entries as
CSV whose columns are the union of keys across all entries, and the CLI writes the result to the
chosen destination. Because a list is its own concept file, it also appears in the progressive
discovery view by identifier and description alone (REQ-016).

## Constraints and Decisions

- A list is stored as its own concept file, entries are schema-free and batch-appended, the
  description is the required summary, and CSV export uses the union of entry keys. See
  [ADR-003](decisions/ADR-003-lists-schema-free-batch.md) (REQ-017 through REQ-021).
- List persistence operations are additive to the store interface while it is draft and do not
  bump the interface version (REQ-010).
