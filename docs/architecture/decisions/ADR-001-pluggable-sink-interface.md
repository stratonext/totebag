---
id: ADR-001
title: Pluggable Sink Interface
status: accepted
supersedes: []
superseded_by: []
tags: [sinks, storage, extensibility, interface]
---

## Context

totebag must let the storage destination change from a local directory to cloud object storage and
eventually a remote server, without reworking the application (REQ-002, REQ-003). Each destination
has a different native API, and some do not share a representation at all. If the Store called each
destination directly, every new destination would ripple through the core, and portability would
erode as destination-specific concerns leaked into the domain logic.

## Decision

Define storage as an abstract Sink interface: the versioned set of store operations, expressed in
Domain Model items rather than files or bytes (REQ-010). The Store depends only on this interface.
A new destination is added as a concrete sink that implements the interface, with no change to the
CLI, Store, or Domain Model, and each concrete sink chooses its own representation.

The default concrete sink is the OKF Sink, which implements the interface over an fsspec filesystem
so one representation round-trips across local disk, S3, and GCS. Its on-disk format is covered by
[ADR-002](ADR-002-okf-file-format.md).

## Consequences

### Positive
- New destinations are isolated concrete sinks, satisfying REQ-003 by construction.
- The Store carries no storage-specific or format-specific logic.
- The default install stays server-free and dependency-light; cloud and remote backends are
  optional.

### Negative
- Each concrete sink must implement the full interface version (REQ-010). A destination whose
  native shape is far from the interface needs an adapter. See
  [AAR-001](../assumptions/AAR-001-remote-sink-interface.md).
- Destination-native features (such as server-side search) are not part of the interface and need
  separate treatment.

## Alternatives Considered

- **Direct per-destination SDK calls in the Store:** rejected because each destination would couple
  to the core and violate REQ-003.
- **One fixed representation for every destination (for example, forcing OKF everywhere):** rejected
  because a remote API sink need not be filesystem-shaped. The interface stays representation-agnostic
  and each sink chooses its own (REQ-004).
- **A custom storage abstraction of our own design for the default sink:** rejected because fsspec
  already unifies local, S3, and GCS, so a bespoke layer would add maintenance for no additional
  coverage.
