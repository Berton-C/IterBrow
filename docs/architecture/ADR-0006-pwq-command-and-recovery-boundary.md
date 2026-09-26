# ADR-0006: PWQ narrow-command and recovery boundary

Status: Accepted
Date: 2026-09-21

## Context

The canonical PWQ writer already validated state transitions, but the browser
board still exposed a compatibility operation that synchronized a complete
caller-supplied board projection. That interface could infer several protocol
events from one UI mutation. In particular, marking an unsigned card complete
could be interpreted as approve-then-complete. The protocol also had a pause
transition without a corresponding resume command, and an incomplete final
ledger write was ignored during replay but not repaired before the next append.

## Decision

PWQ applications may read the materialized projection but submit only narrow,
version-bound protocol commands. The Electron board boundary exposes `read`
and the allowlisted human commands; it exposes no file write or whole-board
synchronization capability. `sync_board` remains internal migration machinery
for legacy state admission only.

Pause records whether work was `approved` or `in_progress`. Resume requires the
surviving current dispatch authorization and restores that exact pre-pause
state. Work already `in_progress` must pause before its proposal can be modified
or rejected. Modification still changes the proposal digest and revokes all
signatures, authorization, and Tracking.

The writer atomically repairs only a torn final ledger record before appending.
It records the discarded bytes' SHA-256 digest in a hash-chained
`ledger_tail_recovered` event. A complete malformed record or hash-chain error
continues to fail closed.

## Consequences

- A board gesture maps to one explicit auditable command.
- UI code cannot manufacture intermediate approvals by submitting a desired
  final projection.
- Pausing approved work does not falsely claim that execution started when it
  resumes; paused active work resumes as active.
- Scope and rejection changes cannot race silently with active execution.
- Interrupted final writes recover without erasing valid history, while
  non-tail corruption remains visible and blocking.
- Legacy import retains a bounded compatibility path outside the board bridge.
