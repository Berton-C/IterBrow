# ADR-0002: PWQ is a human-agency protocol

Status: Accepted
Date: 2026-09-21

## Decision

PWQ is the reusable protocol by which Iter proposes consequential work and a human can inspect, modify, reorder, approve, reject, pause, resume, or complete it. A valid current-version approval is required to mint dispatch authorization.

The protocol belongs to Core, its durable event ledger and materialization belong to Platform, and the existing board belongs to Applications.

There is one canonical event writer and one status vocabulary. Board JSON is a projection. Browser localStorage may cache view state but is never authoritative.

## Consequences

- Direct writes to `.runtime/pwq.json` are removed.
- Board clients submit one narrow command at a time and cannot synchronize caller-supplied projection state.
- Existing status values are migrated deterministically.
- Proposal edits invalidate prior approvals.
- Active work must pause before its scope can be modified or rejected; resume is bound to the surviving current authorization and restores the exact pre-pause state.
- Torn final ledger writes are repaired before append with hash-chained recovery evidence; complete malformed records fail closed.
- Other PWQ presentations can be added without changing protocol semantics.
