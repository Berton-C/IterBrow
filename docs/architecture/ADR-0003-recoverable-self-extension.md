# ADR-0003: Recoverable self-extension and build Tracking

Status: Accepted
Date: 2026-09-21

## Decision

Runtime revisions to managed tools, transformations, and channels use immutable complete generations. A candidate is inert while quarantined, carries a declared contract and provenance, and is validated by fixed platform-owned checks. Consequential activation requires a current PWQ human authorization. Candidate code cannot run its own admission decision.

Activation changes one generation pointer at a cycle boundary and enters probation. The previous verified generation remains named explicitly. A supervisor outside the managed self-modification surface evaluates process liveness, timely cycle heartbeats, generation identity, and hard health floors. Failure rolls back the pointer before restart. Startup resolves abandoned probation before Iter can run.

Changes to the core loop, supervisor, AtomSpace authority, PWQ authority, state manifest, or governing documents are outside the first hot-load surface and require a separately governed restart migration.

Miter-style Tracking is adopted for the IterBrow build: every substantive progress report binds the stable target to an Atlas slice, evidence/open gaps, boundaries, and next action/trigger. Tracking is reconstructed from primary state. It is builder discipline, not Iter cognition or a second control authority.

PWQ may later add immutable execution-progress events and a tracker projection under an approved item. Those events cannot approve work, change approved scope, or alter the Build Atlas.

## Consequences

- Direct writes by the legacy self-improvement tool are transitional and must route through revision quarantine before this slice closes.
- A syntactically valid file is not a promoted revision; validation, authorization, probation, and external observation are distinct states.
- Rollback restores an exact named generation while retaining failed-candidate history and diagnostics.
- Heartbeat state is evidence for the external supervisor, never self-certification by the candidate.
- The existing source tree remains the development baseline; runtime generation state is explicit in the state manifest and portable backups.

## Source adaptation

The safety and Tracking distinctions are adapted from the Miter build at source revision `37c92391b8adc09759831cffee9cff8a387a72cc`, particularly its Build Atlas §4.2, declarative capability contract, independent trial/admission separation, retained prior version, and hot rollback behavior.
