---
id: AAR-001
title: A Remote Sink Can Implement the Store Interface Behind Its API
status: open
---

## Assumption

A remote destination, such as a server reached over an HTTP API, can implement the versioned
Sink interface in full, expressing every store operation in Domain Model items behind its own
transport and representation.

## Rationale

The Store depends only on the Sink interface, not on any storage mechanism, so any destination
that can honour the interface is interchangeable with the default file-system sink. No remote sink
ships yet, so this has not been proven against a real server implementation.

## Impact if Wrong

If a remote destination cannot express some operation without leaking transport details into the
interface, the interface would need reshaping (for example, splitting bulk and single-item reads,
or adding pagination) and the version would need to advance. The Store and Domain Model would stay
unchanged; only the interface contract and its implementations would move.

## Resolution

Open. To be confirmed when the first remote sink is implemented.
