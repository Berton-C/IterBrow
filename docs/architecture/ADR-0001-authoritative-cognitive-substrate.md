# ADR-0001: Authoritative cognitive substrate

Status: Accepted
Date: 2026-09-21

## Decision

IterBrow will expose one canonical AtomSpace service contract. The first implementation uses a durable local journal and snapshots to own committed mutable atoms, with Hyperon as the live MeTTa reasoning engine.

All durable mutation uses structured transactions. Generic MeTTa evaluation is read-only with respect to authoritative state. Versioned `.metta` files are explicit source seeds; runtime `.metta` files are projections or legacy migration inputs.

DAS is an adapter behind this contract and is non-authoritative until a later ADR demonstrates that it satisfies the same live mutation, recovery, consistency, and reasoning invariants.

## Consequences

- Acknowledged writes survive process loss and can be replayed.
- Export/import/reset must coordinate with the service rather than copying files around a live process.
- Existing file stores migrate additively through domain events and compatibility projections.
- On first journaled startup, accumulated NACE beliefs, latest task states, semantic memories,
  Soul state/skills, and reliability records are admitted in one idempotent transaction using the
  same keys as future authority-first writers. Source files are not modified; embeddings remain a
  projection index.
- Hyperon can be replaced or supplemented without changing cognition callers or transaction identity.
- Endpoint health and state-lock ownership are separate lifecycle facts. A failed
  status RPC does not prove that a Unix socket is stale, so supervisors may
  unlink an endpoint only after an independent transport probe reports an
  explicit refused connection. If the endpoint is missing while the
  state-owned lock names a live process, recovery first verifies that the PID
  is this checkout's `metta_server.py`, retires it, and reconstructs the same
  authority from the journal. Foreign or unverifiable owners fail closed.
- High-volume cognition bridges must not perform an unbounded sequence of
  per-event authority calls inside a time-limited transformation. Reliability
  outcomes are committed in bounded deterministic batches; an exact pending
  record remains until all legacy projections finish. Retrying that record is
  idempotent across the AtomSpace transaction, reliability score projection,
  processed-ID projection, and reliability→NACE queue handoff.
