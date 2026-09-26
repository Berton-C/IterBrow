# ADR-0004: PWQ build execution Tracking

Status: Accepted
Date: 2026-09-21

## Decision

PWQ build work declares its allowed IterBrow Build Atlas slices and invariants as proposal scope before human approval. Once the current proposal version is approved and dispatched, executors and platform services may append immutable Tracking events containing:

- Target;
- Stage: one approved Atlas slice, a bounded claim, and approved invariant references;
- Evidence/open gaps;
- Boundaries;
- Next/trigger.

The event ledger is authoritative; the board shows only the latest materialized tracker plus its sequence. A Tracking event is tied to the current proposal version. It cannot approve, reject, reorder, pause, complete, change scope, change proposal version, mint authorization, or amend the Build Atlas.

Modifying a proposal clears its current tracker and invalidates authorization. General work may use PWQ without Build Atlas references and cannot claim an IterBrow Atlas slice. Because most current PWQ items are build work, build-class proposals should be the default for IterBrow implementation proposals, while the protocol retains the general class for other work.

Hot-load admission, activation, external probation observations, promotion, and rollback emit Tracking automatically. A recovery rollback pauses the work item, retains the failed generation/evidence, and names the repair/reapproval trigger.

## Consequences

- Human consent and execution reporting remain separate authorities.
- The current build position is visible without trusting conversation memory or a mutable board note.
- Out-of-scope Atlas claims and invariant references fail at the canonical writer.
- Tracking replay is deterministic and shares PWQ's command idempotency and hash chain.
- Board/UI changes remain projections and cannot broaden the approved build scope.
