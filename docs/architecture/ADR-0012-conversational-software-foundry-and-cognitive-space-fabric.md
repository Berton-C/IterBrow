# ADR-0012: Conversational software foundry and cognitive space fabric

- Status: accepted
- Date: 2026-09-22
- Atlas scope: CONTRACT-1, FABRIC-1, APP-FACTORY-1, MAGIC-BUILD-1,
  MAGIC-REVISE-1, GENERALITY-1
- Amends: ADR-0001 and ADR-0010 product topology; preserves their durability,
  human-agency, native-governance, recovery, and no-competing-authority decisions

Delivery sequence amended by ADR-0013: named cognitive fabric, the general native
build loop and cumulative learning are mandatory in the first integrated proof.
The conditional fabric and post-demo learning sequence below is historical.

## Context

The durable AtomSpace, PWQ protocol, native engineering-governor seam, tab/app
contract, and recoverable CRM app-revision lane established a strong correctness
kernel. They also exposed two architectural drifts before the remaining product
work began.

First, “one logical cognitive authority” was being read too easily as one
physical runtime map, service endpoint, journal, and reasoner. The current
implementation serializes native construction and query entry behind one lock,
reconstructs Hyperon from the complete runtime map when validating a mutation,
and sends the complete map to each isolated query. That is sound at the present
scale and valuable as a compatibility kernel. It has not been established as
the best topology for control, learning, application knowledge, personal
memory, and temporary computation over the life of the product.

Second, the product goal was narrowed from “Iter can build whatever useful
tool the user describes” to “Iter proves governance by adding one CRM briefing
capability.” CRM is important to the partner demonstration, but it is an
application of the platform. A CRM-specific factory would not satisfy the
product intention.

The user explicitly accepted the realignment: IterBrow is the tool that builds
tools, and the shortest route to a real working demonstration takes priority
over speculative hardening or exhaustive infrastructure work.

## Decision

### Product identity

IterBrow is a user-owned conversational software foundry. The authoritative
outcome contract is `docs/ITERBROW_PRODUCT_BUILD_CONTRACT.md`, with the
machine-readable acceptance surface in
`docs/contracts/software_foundry_magic_v1.json`.

The Build Atlas remains the sole architecture and execution control document.
The Product Build Contract is an acceptance-locked subordinate artifact: it
defines observable outcomes and cannot be silently changed by the builder,
candidate app, or governor. An amendment requires a new version and explicit
human approval.

### Coherence is not physical singularity

IterBrow requires one cognitive-fabric contract, not one physical AtomSpace.
The contract will identify every logical space and every composed read by:

- `space_id`;
- per-space epoch, commit, and state hash;
- globally unique atom/event/evidence identity;
- provenance and schema version;
- declared read/write capability;
- a `SnapshotSet` listing every named space observed by a decision.

The intended logical topology is:

- `control`: constitution, governance, authorization references, and recovery
  invariants;
- `personal`: durable user/Iter knowledge and identity;
- `learning`: engineering evidence and capability reliability;
- `project/<app-id>`: application specification, domain cognition, and
  project-owned facts;
- `scratch/<build-id>`: bounded disposable hypotheses and candidate reasoning.

Transactions are atomic within one logical space. Cross-space operations use
explicit references and completion evidence rather than pretending that every
future backend participates in one distributed transaction. A consequential
decision binds the exact `SnapshotSet` it observed. Application and learning
spaces may not mutate control space.

The present journaled AtomSpace remains the first implementation and the
compatibility/default space. FABRIC-1 first introduces identity, routing, and
composed-read seams; it does not require multiple processes, distributed
consensus, physical sharding, DAS, PeTTa, or SWI-Prolog. Those remain additive
implementation choices behind the fabric contract.

### General application factory

APP-FACTORY-1 removes CRM-only assumptions from application registration,
staging, activation, and collaboration. A user-owned app project has a visible,
portable structure containing:

```text
apps/<app-id>/
  app.json
  specification/
  source/
  tests/
  data/
  migrations/
  research/
  revisions/
  evidence/
```

An App Blueprint declares the user intention, observable examples, non-goals,
data ownership, optional cognitive-space dependencies, permissions,
entrypoint, test obligations, recovery point, and provenance. Iter receives a
bounded factory tool to validate the blueprint, create the project, record
research, stage a candidate, and request its normal PWQ/APP-2 lifecycle. The
tool cannot approve, activate, promote, report its own health, or change the
Build Contract.

Trusted research is evidence, not authority. Iter records the URLs consulted,
retrieval time, relevant pattern, license/usage disposition, and what it reused
or rejected. No third-party source silently becomes application code or a new
runtime dependency.

### Acceptance-locked delivery

Each build begins with an intent checksum: “what the user means” and “the
adjacent but incorrect interpretation.” Observable examples and their `BC-*`
clauses freeze before feature implementation. Every work unit names the clause
it advances. Candidate code cannot edit its governing contract, verifier, or
fixed acceptance fixtures. The builder may propose an amendment but cannot
reinterpret the existing version.

Infrastructure activity is supporting evidence. It is not progress unless it
closes a Build Contract clause or removes a demonstrated blocker to the next
clause.

### Fast vertical slice before broad hardening

The near-term sequence is deliberately parallel where that shortens the demo:

1. CONTRACT-1: freeze the product contract and external acceptance surface.
2. APP-FACTORY-1: generalize the existing app contract/revision lane and expose
   the bounded Iter factory tool.
3. In parallel, FABRIC-1 adds only the logical named-space/SnapshotSet seam and
   retains the current physical store. It gates the first app only if that
   app's accepted blueprint requests native cognition.
4. MAGIC-BUILD-1: let the human request a previously unprepared app; Iter alone
   authors it and passes BC-01 through BC-06.
5. MAGIC-REVISE-1: perform a material conversational revision, preserve or
   migrate data, and prove exact failed-candidate rollback through BC-07/BC-08.
6. Rehearse and show the working demonstration.
7. Use observed build evidence to implement only the learning/ranking seam
   actually required, then build a materially different second app for BC-10.
8. Continue CRM partner value and one-command distribution on the proven
   general factory.

Physical sharding, additional reasoning engines, broad ontology work, and
nonessential CRM connectors are deferred until the first demonstration works.

## Existing mechanisms retained

- AS-1 through AS-3 remain the durable default-space implementation.
- PWQ remains the human decision and bounded authorization protocol.
- COG-GOV-1 remains the native recursive reasoning proof.
- APP-1 remains the typed durable application-state collaboration seam.
- APP-2 remains a proven CRM-only v1 quarantine/probation/rollback lane whose
  mechanics are generalized additively rather than reopened.
- HOT-2 and REC-1 remain the recovery patterns.
- DAS remains optional and non-authoritative.

## Superseded framing

ADR-0010's claim that CRM is the first autonomous app-build proof is superseded.
CRM remains a partner-value application and may proceed after the generic
factory is demonstrated. The unsigned proposal
`pwq-cog-learn-cumulative-evidence-20260922-a` must not be approved or executed
in its current abstract, single-space-first framing. A later learning slice is
driven by evidence from real foundry builds.

## Consequences

- The current AtomSpace is retained and honestly described as a correctness
  kernel rather than canonized as the only future topology.
- General toolmaking, user ownership, repeated revisions, and real visible
  behavior become the delivery center.
- CRM-specific branches become transitional compatibility behavior.
- The first demonstration arrives before broad substrate optimization.
- Generality requires a second materially different app, but does not block the
  first partner demonstration once BC-01 through BC-08 pass.
- The user no longer has to rely on increasingly emphatic prose to prevent
  drift: the accepted examples, external verifier, authorship boundary, and
  amendment rule make reinterpretation observable and fail closed.

## Verification

- Validate the machine-readable contract independently of candidate code.
- Refuse a work unit that cannot name an open `BC-*` clause.
- Refuse candidate attempts to edit the contract, verifier, or acceptance
  fixtures.
- Prove one manifest-registered non-CRM project uses the generalized APP-1 and
  APP-2 mechanics without a source restart.
- Prove Iter authors the previously unprepared app from the user conversation.
- Prove visible primary behavior, durable data, restart, a material requested
  revision, data preservation/migration, and exact rollback.
- Later replay the unchanged factory contract with a materially different app.
