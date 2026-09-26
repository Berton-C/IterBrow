# PWQ — Human-Agency Protocol

Status: implemented protocol v2. The controlling decisions are
`docs/architecture/ADR-0002-pwq-human-agency-protocol.md`,
`docs/architecture/ADR-0004-pwq-build-execution-tracking.md`, and the active
role-threshold decision in `docs/architecture/ADR-0005-pwq-role-threshold-authorization.md`,
the narrow-command/recovery decision in
`docs/architecture/ADR-0006-pwq-command-and-recovery-boundary.md`, plus the active
build ledger in `docs/ITERBROW_BUILD_ATLAS.md`.

## Contract

PWQ is the reusable consent boundary between Iter and a human:

1. Iter proposes work.
2. The human sees the pending intent.
3. The human approves, rejects, modifies, or reorders it.
4. The card's declared threshold and required distinct roles sign/attest the exact proposal version and digest.
5. Only a satisfied approval set mints dispatch authorization.
6. Execution may start only with the current authorization.
7. A modification invalidates every prior attestation and authorization.

The protocol belongs to Platform/Core. The dark-gold board in `pwq.html` is
one application of the protocol and has no independent authority.

## Canonical implementation

| File | Role |
|---|---|
| `iterbrow_runtime/pwq_protocol.py` | Sole protocol writer, transition validator, event ledger, materializer |
| `pwq_service.py` | JSON-lines process boundary used by Electron and tools |
| `tools/pwq_write.py` | Agent-facing client for protocol commands |
| `.runtime/pwq/events.jsonl` | Hash-chained authoritative event ledger |
| `.runtime/pwq.json` | Rebuildable board projection |
| `pwq.html` | Human board client/projection |
| `pwq_seed.json` | Initial example/import input only |

No board code, IPC handler, agent tool, or localStorage entry may directly
write canonical PWQ state. `sync_board` exists only as a compatibility
migration path and still passes through the sole protocol writer.

## Canonical states

`proposed` (including partial attestations), `modified`, `approved`, `in_progress`, `paused`, `completed`,
`rejected`, `superseded`.

Legacy inputs are normalized at the boundary:

| Legacy | Canonical |
|---|---|
| `waiting`, `proposed` | `proposed` |
| `negotiating` | `modified` |
| `orders given` | `approved` |
| `in progress` | `in_progress` |
| `done` | `completed` |

## Commands

- `propose`: create proposal version 1.
- `modify`: create a new version and revoke any prior approval.
- `sign`: append one eligible role attestation to the current proposal digest.
- `approve`: compatibility alias for the human-owner signature; authorization is minted only if the policy is then satisfied.
- `reject`: make the item terminal.
- `reorder`: record a durable ordering decision.
- `start`: require the matching current authorization, then enter progress.
- `pause`: stop active dispatch while preserving history.
- `resume`: return paused work to its exact pre-pause state using the current dispatch authorization.
- `complete`: make successfully executed work terminal.
- `supersede`: guardian-only retirement of inert or paused hot-load work in favor of a named replacement.
- `read`: return the materialized board projection.

## Required verification

- Reusing an event/command id is idempotent.
- Event hashes verify on replay; corrupt or truncated history fails visibly.
- A torn final ledger write is hash-recorded, discarded, and atomically repaired before the next append; a complete malformed record fails closed.
- Start without approval fails.
- Start with an obsolete authorization after modification fails.
- Sensitive cards do not mint authorization until threshold and required roles are satisfied.
- A runtime guardian cannot replace the human owner, and the human owner cannot impersonate the guardian.
- Modification revokes the full signature set; an exact hot-load candidate/scope mismatch fails.
- Proof types without an installed verifier fail closed.
- Reload/restart produces the same materialized state and ordering.
- The browser board has no localStorage mirror or direct filesystem writer.
- The browser board has no whole-projection synchronization capability; every mutation is a narrow protocol command.
- Electron IPC and the Iter tool both invoke `pwq_service.py`.

When this contract changes, update the ADR, Atlas ledger, protocol tests, and
this document in the same change.

## Execution tracker (protocol v1 additive projection)

The Build Atlas uses Miter-style Tracking to report Target, Stage,
Evidence/open gaps, Boundaries, and Next/trigger. Builder reports remain a
discipline reconstructed from primary state, not Iter cognition.

For build-class PWQ work, the proposal declares its allowed Atlas slices and
invariants before approval. After authorized dispatch, immutable `track`
events project the five fields beneath that item. Tracking reports progress and
evidence only. It cannot approve,
reject, reorder, modify proposal scope, mint dispatch authorization, or amend
the Build Atlas. General PWQ work cannot claim an IterBrow Atlas slice.

Modifying the proposal clears the current tracker and invalidates approval.
The next execution must be approved again and tracked against the new version.
The hot-load manager automatically records admission, probation heartbeats,
promotion, and rollback; rollback pauses the work item and names the retained
failure evidence and repair trigger.
