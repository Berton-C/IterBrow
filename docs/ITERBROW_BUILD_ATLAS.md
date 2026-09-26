# IterBrow Build Atlas

Status: **R1 RESTORATION ONLY — QUESTION PoC PARKED; OLD ROLLOUT SUPERSEDED**

The active delivery plan is **IterBrow: integrated build control**, repository
document `docs/ITERBROW_INTEGRATED_BUILD_CONTROL.md`, with a user-facing copy
in the current Codex task's outputs. The user's September 23 correction is:
preserve useful Iter, remove added administrative burden, THEN add strategic
native question/observation/learning support to the ordinary loop for all work,
including self-repair. Request fulfillment must be checked against actual
observations, not merely a successful build or a completed plan.

This Atlas remains the technical inventory and historical commitment ledger.
Where older rollout instructions, acceptance machinery, or completion labels below
conflict with the corrected control document, the corrected document governs.
The prior ADR-0013/0014 rollout is not being resumed. Keep its evidence as history;
do not bootstrap it again or turn document labels into execution prerequisites.

The old continuation automation remains paused. Corrective work in this thread
is authorized; no corrective runtime patch is yet installed. Re-observe process
and memory state before maintenance; historical PID/generation observations are
not current facts. Preserve both memories, current apps/data, and recovery history.

Branch baseline: `TheWholeEnchilada` at `1acd0448ea178e72f97e5c8a29b0898ac71d2847`
Started: 2026-09-21
Scope: product magic, authoritative cognition, coherent state lifecycle, additive store integration, PWQ human agency, recoverable self-extension, reusable tab/apps, one-command Mac distribution, and DAS readiness.

Current delivery correction (2026-09-22): ADR-0013 and Product Build Contract
`software-foundry-magic-v2` govern the complete integrated build. Named cognitive
spaces, a general native build loop, and cumulative learning are required in the
first Iter-authored build/revision proof. Earlier factory-only sequencing is
superseded. Isolated platform implementation is authorized; runtime adoption
retains the existing authorization and recovery boundary. No isolated result
may be reported as a live Iter capability.

This Atlas is the build's control plane. It records the decisions that must remain true, the dependency order, the compatibility promises, the acceptance evidence, and the exact point from which a future contributor should resume. It is updated with the code, not after the code.

## 1. North star

IterBrow is a **user-owned conversational software foundry**. A user describes
a tool; Iter clarifies consequential ambiguity, researches trustworthy and
appropriately licensed examples when useful, creates a versioned App Blueprint,
builds the tool in IterBrow's native tab/app style, proves its real behavior,
and opens it. The user may request continuing changes. Each accepted revision
updates the specification and implementation, preserves or explicitly migrates
application data, and can restore the exact last healthy version. The user owns
the source, specification, tests, data, research provenance, and revision
history.

The fixed observable outcome contract is
`docs/ITERBROW_PRODUCT_BUILD_CONTRACT.md`; its machine-readable acceptance
surface is `docs/contracts/software_foundry_magic_v2.json`. These artifacts are
subordinate to this Atlas but acceptance-locked: a builder or candidate may
propose a new human-approved version, never silently reinterpret the current
one.

IterBrow has one **logical cognitive-fabric contract**, not necessarily one
physical AtomSpace, journal, reasoner, process, or socket. Every acknowledged
cognitive mutation is journaled, recoverable, versioned, attributable, and
visible to native reasoning in its named logical space. A consequential
decision identifies the exact set of space snapshots it observed. Supporting
stores and engines remain useful, but have explicit roles:

- Hyperon is the first live reasoning engine.
- MeTTa/PeTTa/SWI-Prolog-style evaluation is performed against an identified authoritative state version.
- JSON, text, vector indexes, dashboards, and `.metta` exports are projections, indexes, application state, or migration seeds.
- DAS is an adapter behind the canonical AtomSpace API. It is not that API and is not authoritative by default.
- PWQ is the reusable human-agency protocol. A board is only one presentation.
- The current single journaled AtomSpace is the first correctness kernel and
  compatibility/default space. It is not canonized as the only long-haul
  physical topology.

The product expression of that architecture is **magic that just works**:

- A first-time user can request a previously unprepared tool through ordinary
  chat and receive a working, durable, user-owned tab/app, with Iter present in
  the application context as a collaborator rather than a detached chatbot.
- The user can request material revisions repeatedly; the blueprint, source,
  tests, and data migration change together, and a broken candidate restores
  the exact healthy version without data loss.
- A critical business audience can experience that capability through a
  reliable live build/use/revise demonstration without needing to understand
  the control plane beneath it. CRM remains a business-value demonstration,
  not the definition of the factory.
- A first-time Mac user can download one installer, run it once, and reach one
  verified healthy IterBrow instance. The same installer can resume after an
  interruption and upgrade an existing installation without erasing user state.

The build proves both layers. PWQ is the control-plane dogfood proof that an
approved intention is governed natively from reasoning through outcome. The
general app factory and a previously unprepared application are the product
proof. CRM is a subsequent partner-facing value proof built through the same
factory.

### 1.1 AtomSpace persistence boundary

The phrase "a `.metta` file is in the AtomSpace" is too ambiguous for this
build. IterBrow has three distinct MeTTa-bearing paths, and they must never be
described as though they were interchangeable:

1. A file with manifest role `source_seed` is versioned reasoning source. The
   AtomSpace service reads only those declared files when that service starts,
   parses them into logical units, and loads those units into Hyperon. Editing
   such a file does not commit runtime state, does not advance the AtomSpace
   commit, and does not change the already-running service. A controlled
   service restart is the adoption boundary.
2. A runtime atom becomes authoritative only through the structured AtomSpace
   transaction API. Its keyed value is written to the fsynced prepare/commit
   journal, incorporated into the named state hash, periodically included in
   an atomic checksummed snapshot, and reconstructed by journal replay. That is
   the writable, persistent, durable, mutable space.
3. Every other `.metta` file is a declared projection, compatibility file,
   legacy log/queue, or undeclared source artifact. Merely creating or editing
   it neither imports it nor grants it authority. A deliberate migration or
   transaction must do that.

`runtime_atom_count` is therefore the number of keyed durable MeTTa
expressions in the current authoritative runtime map, not a count of files,
concepts, independent beliefs, reasoning steps, or Hyperon's internal nodes.
`seed_atom_count` is the number of parsed logical source units loaded beside
that runtime map. Native queries run in a disposable Hyperon process rebuilt
from the service's boot-pinned seed units plus one exact epoch/commit/hash
runtime snapshot; query-local setup and evaluation are discarded. The resident
service also maintains a validation engine rebuilt on every proposed mutation,
but the journal/snapshot state—not an immortal Hyperon process—is the durable
authority.

This is already a genuine durable native substrate for the migrated cognitive
domains and engineering-governor path. It is not yet an honest claim that all
IterBrow state lives there: PWQ, revision ledgers, and application state retain
their deliberately separate platform/application authorities, while manifest
entries such as legacy memory and experience remain explicit convergence work.

## 2. Non-negotiable invariants

| ID | Invariant | Acceptance evidence |
|---|---|---|
| INV-01 | An acknowledged atom mutation survives process crash and restart exactly once. | Journal/recovery integration test. |
| INV-02 | Native evaluation sees the same committed atom version reported by status. | Query-at-version integration test. |
| INV-03 | Generic evaluation cannot silently create durable state. | Read-only evaluation test plus explicit mutation API test. |
| INV-04 | Source seeds are loaded only from the state manifest; runtime directory recursion is forbidden. | Seed-manifest test. |
| INV-05 | Export checkpoints one known cognitive commit. Import/reset quiesces writers and reconstructs the live engine before Iter resumes. | Lifecycle test and Electron orchestration test. |
| INV-06 | Secrets are never included in portable state exports or automatic state backups. | Archive-manifest test. |
| INV-07 | Every persisted path has exactly one role: source seed, authority, event log, projection/index, cache, secret, or application state. | `iter/state_manifest.json` validation. |
| INV-08 | NACE, Soul, tasks, reliability, and semantic-memory changes emit transactions into the shared cognitive ledger; their legacy files remain compatible projections during migration. | Per-domain bridge tests and reconciliation status. |
| INV-09 | PWQ has one canonical event writer and one status vocabulary. UI localStorage is never an authority. | Protocol state-machine and competing-writer tests. |
| INV-10 | Consequential PWQ work cannot enter dispatchable state without an explicit human decision event. | Approval-token test. |
| INV-11 | A projection can be rebuilt from an authoritative commit or is explicitly declared application-owned. | Projection metadata/rebuild test. |
| INV-12 | DAS can be enabled, disabled, or replaced without changing cognition callers or the canonical transaction format. | Adapter contract test with in-memory/no-op adapter. |
| INV-13 | A runtime revision is inert in quarantine until its complete contract, bounded validation, and current human authorization are present. Candidate code cannot certify or activate itself. | Candidate-state and authorization tests. |
| INV-14 | One Iter cycle executes against one immutable module generation. Activation requires a current heartbeat from a still-live stable parent, is an atomic pointer change observed by the next cycle, permits only the exact activation-time parent PID/session/cycle to finish, and retains the exact prior generation until probation closes. | Live-parent admission, cycle-identity pinning, activation, and exact-rollback tests. |
| INV-15 | Probation is judged by a supervisor outside the self-modifiable surface. The overwriteable latest heartbeat is liveness state, while completed-cycle promotion evidence is immutable and content-verified; same-process/session successor progress may prove a completion emitted by a pre-journal Iter. Process death, stale evidence, tampering, or a hard health-floor failure rolls back before restart; startup also resolves abandoned probation. | Lossless completion, compatibility, tamper, crash, hang, restart, and supervisor-loss recovery tests. |
| INV-16 | Build Tracking is reconstructed from the Atlas, requirements, repository state, and evidence—not copied from a previous report. Every stage boundary explicitly names the Atlas slice, active claim, evidence, unresolved work, counterexamples/non-claims, and next dependency. | Fresh Tracking block at every stage boundary and in substantive build reports. |
| INV-17 | One authoritative state directory has at most one service writer, regardless of how many socket names, Electron versions, or launchers can address it. | State-directory singleton-lock test and cross-socket lifecycle check. |
| INV-18 | Every consequential action is evaluated from an identified authoritative cognitive commit at the dispatch boundary; a legacy projection may inform recovery but cannot silently become the governing authority. | Gate integration test records evaluated commit and rejects projection-only success claims. |
| INV-19 | KB/NACE governance is material: hard ownership and human-agency violations veto before side effects; adaptive efficacy can allow, advise, or veto according to declared policy, and a reasoning outage is surfaced rather than silently described as governance. | Allowed/blocked dispatch tests, authority-loss test, and live negative-control drill. |
| INV-20 | A governance decision cannot approve, modify, or enlarge PWQ scope. Build activation still requires the current human decision token, declared Atlas slices/invariants, and the independent hot-load supervisor. | Cross-check gate, PWQ authorization, and hot-load activation tests. |
| INV-21 | Sensitive PWQ dispatch authorization is minted only after the exact proposal version/digest satisfies its declared threshold and required distinct roles. Technical/recovery witnesses cannot substitute for the human owner; modification revokes the entire attestation set. | Role-threshold replay, impersonation, revocation, exact-candidate-binding, and no-early-token tests. |
| INV-22 | Immutable generations relocate executable code only. Every queue, ledger, projection, index, secret, and application-owned store resolves from the canonical Iter root (`ITER_DIR`, with Iter cwd only as the direct-launch fallback); generation-local state forks are forbidden. | Simulated relocated-generation path test across chat, semantic memory, PWQ, museum, capture, CRM feeds, and Soul; live canonical-state inspection; managed-root-only staging and non-managed-file rejection tests. |
| INV-23 | A live browser-control endpoint cannot be unlinked or stolen by a competing checkout or launch. The main process and its supervised Iter child use the same checkout-scoped endpoint, and cognition cannot start until this checkout proves it is listening. | Two-server endpoint-ownership test, start-order assertion, and controlled-restart live bridge check. |
| INV-24 | An accepted sidebar chat message has a stable ID and a durable UI-subsystem record. Queue publication is atomic; Electron never acknowledges an Iter reply before journaling it; renderer reload/restart replays without loss or duplication. | Queue/journal/replay/dedup/recovery tests plus one labeled visible round trip and reload. |
| INV-25 | For governed build work, AtomSpace owns the semantic chain from approved intention through gap, alternatives, prediction, obligations, decision, observed outcome, revision, and next move. External code may verify and execute the exact decision but may not silently replace it with independent cognitive policy. | Commit-bound native decision trace, semantic-policy negative control, and no-Python-reclassification test. |
| INV-26 | Governed work uses one recursive work-unit shape at Atlas, feature, change, and repair scale. Parent completion requires verified child evidence; actions running is never completion by itself. | Recursive decomposition, evidence propagation, and false-completion tests. |
| INV-27 | Runtime Tracking for governed work is a projection of authoritative work atoms and observed evidence. It cannot approve work, enlarge PWQ scope, or amend the Atlas. | Restart reconstruction, projection parity, and authority-separation tests. |
| INV-28 | The partner-facing magic proof turns a bounded read-only Mattermost scan plus a small user direction into a useful, source-grounded brief without developer-terminal intervention or hidden direct writes. Credentials never enter prompts, cognitive state, briefs, logs, or exports; visible application state, source provenance, durable state, AtomSpace evidence, and recovery state agree after refresh and restart. A synthetic fixture independently proves deterministic replay and recovery. | One live Mattermost demonstration and one clean-fixture replay, including credential-boundary, bounded-read, source-provenance, usefulness-feedback, promotion, correction/undo, persistence, dedupe, and restart checks. |
| INV-29 | CRM connectors are evidence adapters into one source-neutral AtomSpace relationship/project/event model. CSV import is previewed, idempotent, provenance-preserving, and undoable; Mattermost, Calendar, Gmail, and later sources cannot become separate semantic authorities or silently merge uncertain identities. | CSV duplicate/re-import/undo tests; source-identity and uncertain-entity-resolution tests; connector contract fixture shared by CSV and Mattermost, then reused unchanged by later adapters. |
| INV-30 | Mac installation is one resumable, idempotent, state-preserving path from a downloaded script to exactly one verified healthy IterBrow instance. Core runtime dependencies are distinct from optional development extras; secrets never enter installer output; success requires live app, AtomSpace, and Iter acceptance rather than dependency installation alone. | Clean-install, interrupted-resume, rerun, existing-state upgrade, duplicate-owner, credential-boundary, launch, AtomSpace status, and one Iter round-trip check on Apple Silicon and Intel-compatible profiles. |
| INV-31 | Every open PWQ board is a live attention projection of the canonical event ledger. A proposal, signature, status transition, Tracking update, reorder, or alarm created by any authorized writer becomes visible without manual reload, while focused draft text and selection remain intact; refresh never creates a decision or competing writer. | Two-open-board external-update test, focus/draft-preservation test, attention-count/title test, reconnect/focus refresh test, and no-write-on-refresh assertion. |
| INV-32 | A tab/app revision is an immutable, content-addressed bundle that remains inert until fixed validation and exact PWQ authorization succeed. Activation changes one per-app pointer atomically; the prior bundle remains the exact rollback target. App content cannot certify, activate, promote, or suppress its own failure. An external supervisor requires both a visible load handshake and an authoritative application-contract round trip; load error, timeout, pointer tampering, or failed health evidence restores the exact prior bundle across reload and restart. | Quarantine/non-execution, path/CSP/boundary validation, exact-candidate authorization, atomic pointer, visible handshake, application-context read, failure/timeout/tamper rollback, promotion, reload, and restart-reconstruction tests. |
| INV-33 | The autonomous app-build proof is valid only when Iter is the sole feature-code writer. Codex may define the approved Atlas/PWQ boundary, observe, authenticate evidence, and invoke recovery, but may not write or repair the proof feature. “Done” requires fixed tests, real visible behavior, authoritative state/read-back, restart agreement, and exact rollback evidence; an overseer repair makes that attempt a learning counterexample rather than a pass. | Authorship manifest/diff, Iter tool-call provenance, fixed non-candidate tests, visible acceptance, AtomSpace read-back, restart reconstruction, deliberate failed-candidate rollback, and no-overseer-feature-edit audit. |
| INV-34 | Every completed governed engineering action emits one uniquely identified first-class evidence record binding strategy, change class, repository context, prediction, observation, and test result to its work/authorization/observation identities and authoritative state version. Later work consults accumulated evidence to rank alternatives and strengthen proof obligations; learned evidence may never mint authorization or weaken a constitutional floor. | Duplicate/replay identity test, contrasting-outcome Truth Revision test, evidence-informed alternative/proof-obligation test, restart reconstruction, and hard-floor non-regression control. |
| INV-35 | Product completion is governed by the current acceptance-locked Product Build Contract. Every work unit names an open `BC-*` clause; candidate code cannot edit the contract, external verifier, or fixed acceptance fixtures. A change in meaning requires a new explicitly human-approved contract version rather than builder reinterpretation. | Contract schema/hash check, clause-bound work validation, candidate-write denial, adjacent-but-wrong negative control, and amendment-version authorization test. |
| INV-36 | Cognitive coherence is expressed through named logical spaces and exact composed snapshot identity, not dependence on one physical store. Every consequential multi-space read names a `SnapshotSet` of space ID/epoch/commit/hash values; transactions are atomic within one space; application and learning capabilities cannot mutate control space. | Default-space compatibility, named-space isolation, composed-read identity, denied cross-space write, replay, and physical-routing substitution tests. |
| INV-37 | Every factory-created app is a visible, exportable, user-owned project containing its blueprint, source, tests, data, migrations, research provenance, revisions, and evidence. Immutable runtime bundles are deployment artifacts, never the only source copy or the application's data authority. | Project-boundary and manifest tests, export/reopen proof, bundle/source separation, revision provenance, and state-preserving rollback. |
| INV-38 | The first autonomous magic proof begins from a human-provided, previously unprepared application request after the generic factory exists. CRM-specific preparation, a prewritten proof app, Codex feature authorship, screenshots, or internal test success cannot substitute for visible use, durable data, conversational revision, and recovery. | Conversation/blueprint provenance, baseline-to-app authorship diff, external primary-workflow test, restart, requested revision, data migration/preservation, and failed-candidate rollback. |

### Preservation clarification (user direction, 2026-09-22)

**INV-39 — Capability and cognitive continuity.** The software foundry is
additive to Iter, not a replacement runtime or a whitelist of things Iter may
build. Its initial executor catalogue is an extensible transport interface,
not the boundary of Iter's imagination, source languages, or existing tools.
Source projects may contain arbitrary languages; the current renderer bundle
format limits only that deployment artifact. Existing managed Python repair,
hot-loading, external probation, exact rollback, ordinary tools and reasoning
remain available. New governor activation checks apply to that governor's
protected changes, not to all existing Iter activity.

Both existing memory systems remain essential inputs: semantic memory has
authoritative records plus its Chroma search projection; episodic continuity
includes experience/history, immutable recaps and the tiered summaries used in
context. Foundry work must read them through their existing owners with source
identities, retain original episode/knowledge links, and preserve their data
through code changes and rollback. Named personal/learning spaces must not
silently create an empty replacement mind. Any derived retrieval view is
explicitly a projection, not another memory authority. Retrieval truncation,
unavailability and stale source identity remain visible. A TTL or code-generation
path is not memory identity, and a cache miss is not evidence that Iter forgot.

Authorization still binds consequential effects and exact runtime activation;
it does not impose arbitrary categories of permitted products. New build
capabilities extend the existing tools/adapters and native work grammar. They
must not route around the user's existing consent or recovery mechanisms.

Preservation proof is part of BUILD-LOOP-1/FABRIC-1/COG-LEARN-1 integration, not
a separately deferred project: existing hot-load/recovery/domain tests; additive
managed-runtime adapter; semantic and episodic read/retrieval identity tests;
memory unchanged through stage/activation/rollback; stale-context invalidation;
and a live continuity check before the integrated capability is called complete.

## 3. Canonical ownership

```text
Core
  Browser shell, tabs, browser bridge, durable chat delivery, permissions
  PWQ proposal/decision/role-threshold/dispatch contract

Cognition
  Iter loop, native reasoning, memory/Soul/NACE/task semantics
  Perception, capability learning, self-extension
  Recursive engineering governor and outcome-driven strategy revision

Platform
  Cognitive-space fabric API, routing, SnapshotSet identity
  Default AtomSpace journal, snapshots, process lifecycle
  State manifest, export/import/reset, projections, providers, secrets
  Hyperon engine adapter and DAS adapter interface
  Immutable revision generations, probation, rollback, heartbeat supervision
  Thin constitutional verifier/executor for native governor decisions
  Acceptance-locked contract verifier outside candidate control

Applications
  PWQ board, CRM, NodeQuest, dashboards, MapStation, museum, workbenches
  User-owned app projects and generic conversational app factory
  Reusable tab/app collaboration seam and CRM partner-value experience

Legacy / migration
  Direct file writers, recursive `.metta` loading, local debug scripts,
  generated source-tree artifacts, stale runtime documentation
```

Builder-authored Tracking is a control-document reconstruction discipline used by the human and builder. It is not an authority or a substitute for evidence. Under COG-GOV-1, governed PWQ work additionally exposes runtime Tracking as a projection of authoritative AtomSpace work/evidence atoms beneath the approved proposal. Neither form can mint approval, enlarge scope, or amend the Atlas.

## 4. Build dependency map

```text
Accepted Product Build Contract + external verifier
      │
      ├──► clause-bound work / no silent reinterpretation
      │
      ▼
Atlas + manifest
      │
      ▼
Cognitive-space fabric contract
      │
      ├──► default journaled AtomSpace ──► Hyperon adapter ──► read-only evaluation
      ├──► named space identity + per-space epoch/commit/hash
      └──► composed SnapshotSet reads + capability boundaries
      │                              │
      ├────────► lifecycle RPC ◄─────┘
      │              │
      │              └──► export / import / reset orchestration
      │
      ├──► cognitive transaction bridges
      │       ├── NACE / reliability
      │       ├── tasks / Soul
      │       └── semantic memory
      │
      ├──► governed action decision
      │       ├── approved intention + recursive native work graph
      │       ├── alternatives, predictions, obligations, evidence at commit N
      │       ├── AtomSpace-derived bounded decision + next move
      │       ├── thin constitutional verification before exact dispatch
      │       └── accumulated engineering evidence ──► later ranking/proof duties
      │
      ├──► PWQ event ledger + board projection
      │       └──► native-governor dogfood and Tracking projection
      │
      ├──► revision quarantine ──► fixed validation ──► runtime-guardian witness
      │                                  │                         │
      │                                  └──► human-owner signature┤
      │                                                            ▼
      │                                                   threshold authorization
      │                                                            │
      │                                                   probation activation
      │                                                       │
      │                              external heartbeat ◄──────┤
      │                                  │                    │
      │                                  └──► promote / exact rollback
      │
      ├──► reusable tab/app collaboration seam
      │       └──► user-owned app project + generic factory
      │              └──► unprepared app ──► revision/rollback ──► second app
      │                                      │
      │                                      └──► evidence-driven learning
      │
      ├──► general factory ──► CRM partner-value proof
      │
      ├──► state-safe Mac installer ──► launch + live health acceptance
      │
      └──► projection feed ──► DAS adapter (optional, non-authoritative)
```

No downstream slice may invent its own transaction identity, commit numbering, or recovery semantics.

## 5. Additive migration rules

1. Existing public tool signatures remain available until a tested replacement is active.
2. Legacy files remain readable projections during migration; their direct writers are removed only after reconciliation proves parity.
3. New authoritative state is written first. Compatibility projections are written from the committed event, never the reverse.
4. Failure to update a projection is surfaced and retryable; it does not roll back an already durable authoritative commit.
5. No migration step deletes user data. Reset is an explicit product operation and reseeds only declared source seeds.
6. Every format carries `schema_version`; every transaction carries stable `transaction_id`, `actor`, `source`, timestamp, and ordered operations.
7. All filesystem replacement writes use same-directory temporary files, flush, and atomic rename.
8. A service reports `ready` only after snapshot verification, journal replay, seed load, and engine reconstruction succeed.

## 6. Build slices and live ledger

Legend: `TODO`, `BUILDING`, `VERIFYING`, `DONE`, `DEFERRED`, `SUPERSEDED`, `BLOCKED`.

| Slice | Status | Deliverables | Depends on | Exit condition |
|---|---|---|---|---|
| ATLAS-1 Control and decisions | **DONE** | This Atlas; ADRs; state manifest | — | Manifest validates; stale architecture claims corrected. |
| CONTRACT-1 Acceptance-locked product contract | **VERIFYING** | Human-readable outcome contract; machine-readable `BC-*` surface; intent checksum; external verifier; amendment and candidate-write boundary | ATLAS-1 | The accepted software-foundry meaning and adjacent-but-wrong interpretation are explicit; BC-01–BC-13 pass the external schema/immutability verifier; candidate surfaces cannot modify the contract or verifier. Isolated platform preparation is authorized by ADR-0013; live adoption retains exact approval and recovery. |
| FABRIC-1 Named cognitive-space seam | **BUILDING — CONNECTED ISOLATED** | Logical named spaces and SnapshotSet over the existing journal; trusted service-owned access; default compatibility | CONTRACT-1, AS-1–3 | Seven fabric checks plus connected native service tests prove routing, isolation and replay in disposable state. Real Iter build use and live continuity remain open; no second memory/store authority was introduced. |
| AS-1 Durable transaction store | **DONE** | WAL, transaction validation, idempotency, snapshots, replay | ATLAS-1 | Crash/restart and duplicate-ID tests pass. |
| AS-2 Hyperon service integration | **DONE** | Explicit seed loading; authoritative atom reconstruction; query/mutate/checkpoint/status RPC | AS-1 | Fake-engine integration and isolated real packaged Hyperon crash/replay smoke pass. |
| AS-3 Evaluation boundary | **DONE** | Read-only/ephemeral evaluation; legacy `run` compatibility; explicit mutation tool | AS-2 | Query-isolation and explicit-mutation tests pass. |
| LIFE-1 Coherent lifecycle | **DONE** | Quiesce/checkpoint/shutdown/restart; import/reset rebuild; state-owned singleton; endpoint-ownership recovery; durable user Start/Stop intent | AS-2 | Visible Stop → app restart → remains stopped → visible Start resumed exactly one supervised Iter process on the stable generation while the same journaled AtomSpace retained its epoch and advanced normally. Unit/static/live source recovery and packaged clean-workspace/export/replay checks also pass. |
| STATE-1 Export and secrets | **DONE** | Manifest-driven archive set; settings separation; state-free packaged template; writable per-user workspace | ATLAS-1, LIFE-1 | Rebuilt package contains no audited secret/live-state paths; a real packaged export restores exact epoch/commit/hash/atom count and native query in a second clean workspace. |
| COG-1 Shared cognition events | **DONE** | Domain bridge and first-start admission for NACE, reliability, tasks, Soul, semantic memory | AS-1 | Bridge/recovery/migration tests and real 606-record Hyperon rebuild pass; legacy files are post-commit projections. |
| COG-2 Governed action contract | **DONE** | Authoritative KB/NACE query, argument-aware dispatch preflight, material allow/advise/veto, durable decision evidence | COG-1, AS-3, PWQ-1 | Live Iter allow/dispatch succeeded from a named commit; a promoted negative control vetoed before side effects, retained its evaluated epoch/commit/hash, remained natively queryable, and left PWQ authority unchanged. |
| COG-GOV-1 Lean native recursive engineering governor | **DONE** | Recursive work atoms; reuse-first MeTTa rules; shadow decision; evidence comparison; PLN/NACE revision; exact constitutional handoff | COG-1, COG-2, AS-3, PWQ-1, HOT-2 | One bounded PWQ item produces a restart-recoverable native work graph and commit-bound shadow decision, then one low-risk authorized action completes through observed outcome and accept/iterate/escalate/rollback without Python semantic reclassification. |
| COG-LEARN-1 Learning from real foundry builds | **BUILDING — CONNECTED ISOLATED** | Native EngineeringEvidence, cumulative PLN/NACE revision, later ranking/proof duty, unique action/observation identities | COG-GOV-1, FABRIC-1, BUILD-LOOP-1, PWQ-1 | Twelve native learning checks plus governor/service cases cover contrasting outcomes, interrupted/incomplete evidence, replay and strengthened browser duties. Connected service actions publish actual fixture observations. Real Iter's later choice and live causal improvement remain open. GOV-SELF-1 owns protected changes; INV-39 preserves both existing memories. |
| BUILD-LOOP-1 General native engineering loop | **BUILDING — CONNECTED ISOLATED** | Iter tool/RPC; native decisions; service-owned execution/observations; durable claims/reconciliation; recursive work; memory intake and learning | COG-GOV-1, FABRIC-1, APP-FACTORY-1, PWQ-1 | Connected project create/source write traverse native decision through durable outcome. Running/uncertain work is never blindly repeated. App and original managed-runtime adapters are additive; research retrieval, general build commands and other artifact adapters are not yet integrated. Live general build/repair proof remains required. |
| GOV-SELF-1 Protected governor evolution | **BUILDING — CONNECTED HOST HANDOFF; LIVE ACTIVATION OPEN** | Exact-source installer; state-owned offline lease; journal-authenticated proof/decision readers; native successor adoption/recovery; explicit once-only initial trust admission | COG-GOV-1, PWQ-1, HOT-2, REC-1 | Connected temporary PWQ/native/journal installation and restoration pass. ADR-0014 distinguishes the first human trust-root admission from subsequent native decisions. Host subprocess observers never invent absent production recipes. Actual initial admission, service/tool-generation activation, live continuity and real successor proof recipes remain open. Existing memory, tools and recovery stay available. |
| REUSE-1 Traceable reuse in the real loop | **ISOLATED PATTERNS; LIVE TRACE OPEN** | Linked native work; bounded action/observation; repair children; source context/feedback; existing candidate/parent recovery | BUILD-LOOP-1, APP-FACTORY-1, APP-2 | Concrete isolated runtime mechanisms now embody the five patterns. COM-05–COM-09 still require source-to-action-to-outcome mapping in the same real Iter build/revision proof. No competing framework runtime is installed. |
| EPI-1 Audited and consumed v08.7.2 subset | **ISOLATED CONSUMPTION PROVEN** | Pinned source attribution; selected native categorical alignment; explicit unknown handling; governor call site | COG-GOV-1, BUILD-LOOP-1 | Five actual-Hyperon subset tests and native governor comparison consume the selected alignment rules. Initial audit found absent extracted numeric helpers and pair-lattice absorption failure; those are not smuggled into a full-quantale claim. Live consumption is pending exact adoption. |
| PWQ-1 Protocol and ledger | **DONE** | Event schema, state machine, approval/modify/reject/reorder/supersede, one writer | AS-1 | Protocol tests pass, including agent denial, idempotency, tracking scope, exact-threshold authorization, and guardian-only terminal supersession. |
| PWQ-2 Board migration | **DONE** | Board as projection/client; no localStorage or whole-board sync authority; narrow IPC commands invoke the canonical writer | PWQ-1 | Static boundary and protocol tests pass; visible owner-sign, reorder/reject, authorized start, scoped Tracking, pause/resume, and completion agree with canonical replay without whole-board writes. |
| PWQ-4 Live board attention sync | **DONE** | Two-second sequence-gated canonical read; single-flight interval plus focus/visibility catch-up; attention badge/title update; draft/focus/selection/filter/scroll-preserving rerender | PWQ-1, PWQ-2 | Two repaired live boards independently observed the external sequence 109 Tracking fixture without manual reload; the instrumented board preserved its exact unsaved draft, focused field, selection 6–16, `waiting` filter, and scroll position 240. Canonical sequence remained 109 throughout refresh observation, and the read-only boundary plus full control suite pass. |
| GOV-2 Threshold PWQ authorization | **DONE** | Proposal digest, role/threshold policy, distinct attestations, exact action/resource scope, future verifier envelope | PWQ-1, HOT-1 | Live human-owner plus runtime-guardian approval bound one exact candidate digest/scope, minted no early token, and drove successful probation/promotion through the source UI. |
| DAS-1 Adapter boundary | **DONE** | Adapter interface, disabled/no-op implementation, projection cursor | AS-1 | Adapter failure/disable contract tests pass. |
| HOT-1 Revision contract and quarantine | **DONE** | Versioned contract, managed-surface policy, inert immutable generation | ATLAS-1, PWQ-1 | Twelve hot-load tests pass; all 127 reachable current component files pass the fixed admission contract. |
| HOT-2 Atomic activation and rollback | **DONE** | Cycle-pinned active pointer, probation state, retained parent, exact rollback, canonical runtime-path binding | HOT-1 | Split-approved candidate `candidate-3f2da49ef5334611a1248072a805904f` promoted after three healthy completions; canonical semantic-memory/PWQ inspection and live UI round trip pass. Additive chat repair `candidate-33887e67bdf4410f934e39450c0f3920` then promoted over that retained parent and passed both exact-generation and UI round-trip probes. |
| REC-1 External heartbeat supervisor | **DONE** | Latest liveness heartbeat, immutable completed-cycle evidence, probation health floors, restart recovery | HOT-2 | Lossless/tamper/crash/error/stale/startup/corruption tests, live rollback, live promotion, promoted restart, and intentional live hang recovery pass. |
| CHAT-1 Durable sidebar delivery | **DONE** | Atomic queues, stable message envelopes, main-process receipt journal, replay/dedup, OS lock/resume reconciliation and native repaint, transcript evidence | STATE-1, LIFE-1 | Exact `E` probe and ACK each persisted once across restart, then rendered once in the live sidebar after unlock; renderer-DOM-only and blank-native-surface counterexamples are both covered by focus/unlock reattachment. |
| TRACK-1 Build Tracking discipline | **BUILDING** | Five-field reports, primary-state reconstruction, stage-boundary checks | ATLAS-1 | Every substantive build report remains anchored without inventing evidence. |
| PWQ-3 Execution tracking projection | **DONE** | Scope-bound progress/evidence/next-action events beneath approved work | PWQ-1, TRACK-1 | Replay/scope tests pass; tracking cannot approve, reorder, alter scope, or claim unapproved Atlas authority. |
| APP-1 Reusable tab/app collaboration seam | **DONE** | Minimal scoped app context, Iter interaction, canonical mutation/provenance, subscription, and correction/undo contract | CHAT-1, COG-GOV-1, STATE-1 | CRM uses the seam without a broad preload or direct competing writer; the same contract can be consumed by a second fixture tab/app. |
| APP-2 Recoverable tab/app revision lane | **DONE** | Immutable scoped app bundles; fixed validation; exact PWQ threshold; per-app atomic active pointer; external visible/contract health probation; exact rollback and restart recovery | APP-1, HOT-2, PWQ-1, REC-1 | A quarantined CRM bundle cannot execute; the exact approved bundle activates without changing source authority, passes a visible handshake and APP-1 context read, promotes only from external evidence, reconstructs after restart, and restores the exact prior bundle after deliberate load failure, timeout, or tamper. Existing Python hot-load semantics and authority remain unchanged. |
| APP-FACTORY-1 Generic conversational app factory | **BUILDING — CONNECTED ISOLATED** | Language-neutral projects/history; blueprint/research; generic manifests; existing APP-2 recovery; Electron open/inspect adapter | CONTRACT-1, APP-1, APP-2 | Non-CRM project and source lifecycle, generic bundle registration and mocked browser observations pass. Existing CRM and managed Python recovery remain intact. External Product Contract verifier, real Electron acceptance and Iter-only authorship proof remain open. Source rollback is not proof of automatic domain-data rollback. |
| MAGIC-BUILD-1 Previously unprepared app proof | **TODO** | Human runtime request; clarification/blueprint; research; Iter-only authorship; visible workflow; durable data; fabric/governor/learning trace | APP-FACTORY-1, FABRIC-1, BUILD-LOOP-1, COG-LEARN-1, TRACK-1 | Iter alone satisfies BC-01–BC-06 and uses BC-11–BC-13. Codex writes no proof app feature code. Each accepted action has native reasoning and uniquely identified outcome evidence; a later choice shows its effect. |
| MAGIC-REVISE-1 Conversational revision and recovery proof | **TODO** | Material requested blueprint/source change; data preservation or migration; changed visible acceptance; deliberate failed candidate; exact rollback | MAGIC-BUILD-1, APP-2 | The user requests a meaningful revision; Iter alone updates and proves it through BC-07, while a separate broken candidate proves BC-08 and restores the exact parent with unchanged accepted data. |
| GENERALITY-1 Second-category counterexample | **TODO** | Second materially different human-requested app through the unchanged factory contract | MAGIC-REVISE-1, COG-LEARN-1 | BC-10 passes without adding an app-specific factory branch; the second app independently replays BC-01–BC-08. It does not block the first partner demonstration. |
| MAGIC-AUTO-1 CRM-specific autonomous proof | **SUPERSEDED** | Historical CRM-first framing retained for traceability | — | Superseded by APP-FACTORY-1, MAGIC-BUILD-1, and MAGIC-REVISE-1 under ADR-0012. CRM remains a later application of the general factory. |
| CRM-1 Canonical relationship-intelligence slice | **TODO** | Source-neutral person/project/conversation/commitment/event atoms; conservative entity resolution; usefulness feedback; idempotent CSV import; bounded Mattermost evidence adapter; CRM JSON compatibility projections | AS-1, COG-1, APP-1 | Drop one CSV and ingest one synthetic Mattermost fixture twice without duplicates; the same canonical atoms and provenance rebuild the CRM projections and a useful brief; uncertain identity matches remain user-visible candidates; undo/restart pass. Calendar and Gmail remain additive adapters, not exit dependencies. |
| MAGIC-1 Partner-value CRM proof | **TODO** | CRM built/extended through the general factory; CSV-to-people and live Mattermost-to-brief value proof; deterministic rehearsal; repeatable demo script | MAGIC-REVISE-1, APP-FACTORY-1, CRM-1, PWQ-2 | An unfamiliar user receives the useful CRM workflow defined by ADR-0010, but no CRM-specific platform branch is introduced and the demonstration remains subordinate to the general software-foundry contract. |
| DIST-1 One-command Mac installation | **TODO** | Downloadable installer; Apple Silicon/Intel detection; minimal core dependency plan; resumable stage ledger and support log; state-preserving install/upgrade; single-instance launch; live health acceptance; optional developer extras | STATE-1, LIFE-1, QA-1; MAGIC-1 for partner release | A clean Mac reaches one healthy app, authoritative AtomSpace, and responsive Iter from one downloaded-script invocation; interruption resumes safely; rerun is idempotent; upgrade preserves exact user state; secrets are redacted; a false or duplicate launch cannot report success. Local MAGIC-1 work may proceed before this release gate, but partner distribution may not. |
| QA-1 Recovery suite | **VERIFYING** | Unit/integration/lifecycle/PWQ/hot-load tests and one command runner | All | The current baseline passes 166 authoritative tests, 104 historical checks, and its live acceptance drills. QA-1 remains the additive umbrella while open slices add only their focused obligations; each source-boundary slice runs the complete control command at exit rather than repeatedly treating unchanged tests as progress. |
| DOC-1 Future-self handoff | **DONE** | Updated README/AGENTS/runtime docs and final Atlas ledger | All | Docs describe shipped behavior, package/workspace boundaries, remaining migrations, and the exact visible-acceptance handoff below. |

### 6.1 Remaining commitment convergence path

The remaining work is one complete integrated delivery path under ADR-0013.
Compact implementation reduces duplication and unnecessary infrastructure;
it does not remove named spaces, native governance, learning or visible proof:

```text
CONTRACT-1 v2: accepted complete behavior, BC-01 through BC-13
        ↓
FABRIC-1 + APP-FACTORY-1 + BUILD-LOOP-1 + COG-LEARN-1
  one working path: named spaces, generic actions, native reasoning, learning
  GOV-SELF-1 protects activation; EPI-1 supplies the audited consumed subset
  REUSE-1 measures the five patterns inside this path, not beside it
        ↓
MAGIC-BUILD-1 → MAGIC-REVISE-1
  Iter authors the app, demonstrates it, revises it, preserves data, recovers
  later action consults evidence from earlier action in the same trace
        ↓
GENERALITY-1: repeat with a materially different app
        ↓
CRM-1 / MAGIC-1 / DIST-1: retained partner-value and distribution commitments
```

Commitment closure is allocated as follows:

| Commitment | Present truth | Smallest closing slice |
|---|---|---|
| Predictable fulfillment of the user's meaning | Product intent was previously implicit enough to drift toward CRM | CONTRACT-1 plus INV-35; every work item and completion claim binds a `BC-*` clause |
| One coherent cognition without one physical bottleneck | Current single service/journal/lock is durable but physically monolithic | FABRIC-1 adds logical identity and composed reads only; later topology remains replaceable |
| User-owned arbitrary code and tab/apps | Isolated user-owned projects support arbitrary text source languages; generic renderer and original managed-runtime adapters exist. Other build/test/deployment adapters remain open, not forbidden categories. | APP-FACTORY-1 + BUILD-LOOP-1 + INV-39 |
| Trusted example discovery | Existing web-search tools remain; foundry records source/license/pattern provenance but does not yet perform authenticated research retrieval itself. | APP-FACTORY-1 + REUSE-1; the real build must retain retrieval evidence |
| Iter builds something it was not prepared for | Not yet proven | MAGIC-BUILD-1; the human chooses the app only after the factory is active |
| Repeated requested changes work | APP-2 proved bundle rollback, not open-ended conversational app revision | MAGIC-REVISE-1 |
| Every completed action has reusable engineering evidence and later decisions consult it | Isolated native revision/ranking/replay checks pass; actual Iter integration is open | COG-LEARN-1 within the first complete build/revision proof, linked to BUILD-LOOP-1 |
| The factory is genuinely general | Generic isolated project/renderer paths retain CRM compatibility, but a second real Iter-authored category is unproven. | GENERALITY-1 without a new app-specific branch |
| Authority, persistence, authorization, and recovery | Operational and live-proven | Reused unchanged by every later slice |
| Partner-visible CRM value and portable installation | Not yet proven | First demo → CRM-1/MAGIC-1 → DIST-1 |

Efficiency and stop rules:

1. The next source work must advance FABRIC-1, APP-FACTORY-1, BUILD-LOOP-1 or COG-LEARN-1,
   including their bounded GOV-SELF-1/EPI-1/REUSE-1 obligations, and name the
   affected `BC-*` clauses and `COM-*` commitments. A task with neither is off-path.
2. FABRIC-1 stops at logical identity, capability isolation, and one composed
   read on the existing store. Physical sharding, consensus, DAS, PeTTa, and
   SWI-Prolog are deferred.
3. APP-FACTORY-1 stops when one non-CRM fixture traverses the generic project,
   APP-1, APP-2, dynamic-open, export, and rollback surfaces. It does not author
   the human's proof app.
4. Spec Kit, mini-SWE-agent, Agentless, Aider, and Plandex are pattern sources,
   not additional runtime authorities or installation dependencies. A pattern
   is counted as adopted only when its effect appears in the native work/evidence
   trace.
5. The v08.7.2 audit is demand-driven: audit and actually consume the smallest
   alignment subset required by the bounded proof. Ordinary PLN/NACE revision
   alone does not fulfill the separate v08.7.2 commitment. Broader quantale
   operations remain outside the first build; unknown/unreduced values cannot
   silently become alignment or authorization.
6. Tests are proof obligations, not the product. Use focused deterministic
   tests during a slice; run the complete control suite once at its source
   boundary and once at exit only when the boundary changed. Perform live UI,
   restart, or rollback drills only for claims that cannot be established below
   that level.
7. A deliverable that does not lower the uncertainty or implementation cost of
   the next slice is deferred. Calendar, Gmail, broad entity intelligence, a
   general arbitrary-command governor, broad learning algebra, and aesthetic
   CRM expansion do not gate the first demonstration.
8. MAGIC-BUILD-1 and MAGIC-REVISE-1 are the anti-overengineering gates. If the
   factory cannot deliver the real requested behavior, extend only the exact
   missing seam exposed by that failure; do not enlarge it speculatively.
9. Isolated preparation uses a source snapshot with baseline hashes and no live
   state or credentials. Review and conflict-check the patch before adoption.
   Iter-authored feature work and live UI/restart/recovery remain necessary proof.
10. No subset may be presented as the complete delivery. Keep CRM, installation,
    reuse-source traceability and protected-governor obligations visible until closed.

### 6.2 Complete engineering-governor commitment register

This is the authoritative accounting of the user's thirteen commitments, not
a second plan. None is silently replaced by another or completed by a test
count. Status distinguishes historical live proof, isolated implementation,
design adoption and missing integration. Scope is every completed governed
engineering action, including failed, timed-out and interrupted outcomes—not
only successful commands. General non-build tool telemetry is not evidence of
engineering-loop coverage.

| ID / commitment | Current evidence and limits | Owner / next implementation | Completion evidence |
|---|---|---|---|
| COM-01 Unique evidence for every completed action | **Connected isolated implementation.** Native seven-field EngineeringEvidence, JSON provenance and revised belief commit atomically. Service captures actual executor observations; durable pending claims reconcile without repeating uncertain effects. Twelve learning checks cover failures, incompletes and replay; actual service evidence records the native ruleset that interpreted the observation. | COG-LEARN-1 + BUILD-LOOP-1; BC-12/13. Complete live observation/recovery proof. | Each governed terminal action has one stable identity; incomplete outcomes never become invented success; replay neither loses evidence nor double-learns. |
| COM-02 PLN/NACE revises engineering beliefs | **Narrow live seam plus broader isolated tests.** Existing PWQ QA revision is not a general learner. The isolated seed uses native Truth Revision across contrasting outcomes. | COG-LEARN-1; BC-13. Feed authenticated real Iter build observations to that seed. | Real failures and successes revise the same context-bound belief, preserve evidence links and reconstruct after restart. |
| COM-03 Later builds rank alternatives and strengthen proof obligations | **Isolated native ranking and strengthening.** Prior failure changes the two-alternative ranking; native rules add browser proof at verification/activation phases, not impossible immediate source-write duties. | COG-LEARN-1 + BUILD-LOOP-1; BC-12/13. Show actual Iter's later decision with/without history. | The causal evidence identity, changed choice and strengthened duty are visible; authorization and fixed floors cannot be weakened. |
| COM-04 Governor protects its own changes | **Connected isolated handoff.** Exact candidate, canonical PWQ, journal-authenticated native decision and four proof kinds bind successor adoption; source install/restore uses a stopped-service lease. Explicit initial human admission is distinct and once-only (ADR-0014). | GOV-SELF-1; BC-12. Perform exact live initial admission/service/tool activation and supply real successor observer recipes. | All five successor conditions enforced in actual activation; no candidate self-certification; self-repair and memory remain available when the new governor is inactive. |
| COM-05 Spec Kit process grammar | **Isolated linked work grammar.** Intention, invariants, gap, alternatives, obligations and child work have durable identities. Children cannot drop parent scope/floors or automatically complete the parent. | REUSE-1 + BUILD-LOOP-1; BC-01/12. Real Iter decomposition and convergence proof. | Observed acceptance closes the parent intention, not merely a successful child or a written plan. |
| COM-06 mini-SWE-agent execution discipline | **Connected isolated executor.** The new Iter tool/RPC performs one claimed action then independent observation/native comparison. App and managed-runtime adapters coexist with original tools. | REUSE-1 + BUILD-LOOP-1; BC-12. Activate and prove real build/revision use; extend coverage as needed. | Resume preserves action identity and does not blindly repeat side effects or lose observations. |
| COM-07 Agentless repair discipline | **Isolated recursive repair structure; autonomous repair unproven.** Child work retains scope/invariants; native outcomes iterate/escalate/rollback; original runtime recovery is reused. | REUSE-1 + BUILD-LOOP-1; BC-07/08/12. Iter localizes and repairs an induced failure. | Real reproduction, bounded repair and regression proof; no Codex feature repair presented as Iter's achievement. |
| COM-08 Aider repository context and immediate feedback | **Connected isolated context.** Source/blueprint hashes and named snapshots bind decisions; external edits invalidate a pending write. Mechanical feedback is recorded; remembered sources have content identity and coverage. | REUSE-1 + APP-FACTORY-1 + BUILD-LOOP-1; BC-02/07/12. Demonstrate the actual Iter correction loop. | Feedback and current context materially inform the next native decision; unchecked files and missing observations cannot be success. |
| COM-09 Plandex sandbox/rewind principles | **Historical live CRM proof plus generic isolated recovery.** Generic app registration reuses immutable candidates/exact parent rollback; original Python generations remain unchanged. | REUSE-1 + APP-FACTORY-1 + APP-2; BC-04/08. Real non-CRM recovery and data preservation. | Quarantine isolates pending code; exact source rollback and domain-data preservation/recovery have separate evidence. No wholesale memory reset. |
| COM-10 Audited v08.7.2 epistemic subset | **Selected native subset consumed in isolation.** Pinned MIT-attributed categorical alignment and explicit unknown semantics are called by the native governor. Five actual-Hyperon tests pass. Extracted arithmetic/absorption counterexamples remain documented. | EPI-1 + BUILD-LOOP-1; BC-12. Exact-source activation and live decision trace. | Actual call and effect are observable; do not claim a full imported engine, proven quantale, or full-library audit. |
| COM-11 Hyperon PLN/NACE evidence revision | **Same implementation obligation as COM-02, not a second learner.** The native seam and isolated cumulative tests are real; general live use is not. | COG-LEARN-1; BC-13. Retain one canonical evidence ledger, native revision owner and replay identity. | COM-02/03 pass from real Iter outcomes; no Python fallback invents semantic labels, ranking or truth revision if native evaluation fails. |
| COM-12 Existing authority, persistence, authorization and recovery | **Historical live mechanisms retained; isolated preservation checks.** Original loop/hotload manager unchanged. New runtime adapter uses canonical roots and original supervisor. Semantic records, linked episodes/history and their writers remain; foundry views are projections. | FABRIC-1 + APP-FACTORY-1 + BUILD-LOOP-1 + INV-39; BC-06/08/11/12. Pre/post activation continuity proof. | Same mind/state owners survive code changes and rollback; remembered evidence affects work; no competing ledger, empty replacement memory or product-category gate. |
| COM-13 General native recursive governance hub | **Connected isolated hub, not live completion.** Service routing joins named spaces, recursive native decisions, real fixture actions/observations, learning and existing recovery. Memory-use citations and atomic adoption records are connected in isolation; production source adoption remains open. | BUILD-LOOP-1 joins FABRIC-1, APP-FACTORY-1, COG-LEARN-1, GOV-SELF-1 and EPI-1; BC-11/12/13. | Iter alone builds and revises/repairs an unprepared app; later decisions use outcomes; kernel authenticates/executes rather than owning semantic policy. |

Reference sources for REUSE-1: [Spec Kit](https://github.com/github/spec-kit),
[mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent),
[Agentless](https://github.com/OpenAutoCoder/Agentless),
[Aider](https://github.com/Aider-AI/aider), and
[Plandex](https://github.com/plandex-ai/plandex). These are inspected pattern
sources, not installed/vendored runtimes. Actual copied code requires pinned
provenance and license disposition; behavioral inspiration still requires the
source-to-runtime-to-evidence mapping above.

Closure order, without creating thirteen separate projects:

1. The isolated service now joins named-space access, native work/evidence,
   real fixture actions, durable pending observations and the project/runtime lanes.
   Preserve that integration rather than rebuilding the same seams.
2. Activate the now-connected exact-source installer, trusted proof/decision readers
   and coordinated adoption/recovery lock through ADR-0014's explicit initial
   admission. Capture real release observations, exact PWQ signatures and live
   continuity; retain both memory owners and all original recovery paths.
3. Before activating changed governor rules, satisfy GOV-SELF-1 for the exact
   candidate and finish the minimum actually consumed EPI-1 subset. These are
   integration obligations, not optional later hardening.
4. Have Iter build, use, revise, fail/recover and improve its choice on the
   unprepared app. Use that same evidence to close the applicable COM/BC rows.
   Then prove a second category; retain CRM value and Mac installation work.

## 7. Current source-to-target map

| Current mechanism | Migration treatment | Target owner |
|---|---|---|
| `iter/metta_server.py` default runtime space | Retain the proven journal/Hyperon kernel; place it behind named logical space and `SnapshotSet` contracts before considering physical routing or sharding | Platform cognitive-space fabric + default AtomSpace service |
| `kb_substrate.metta`, `capability_lifecycle.metta`, `self_map.metta` | Declare as versioned source seeds; never reset as mutable state | Cognition seeds |
| `seeds/engineering_governor.metta` | Native shadow policy for recursive work decisions and Tracking projection; activation remains outside the seed | Cognition engineering governor |
| `seeds/application_contract.metta`, `iterbrow_runtime/app_contract.py` | Ground native application record/field query surface plus one journal-first typed command/replay service; Python validates/transports commands and projections but does not become a second state authority | Cognition application contract + Platform application service |
| `iterbrow_runtime/app_revision_manager.py` CRM-only `SUPPORTED_APPS` registry and CRM-specific Electron URL state | Replace with validated user-owned project manifests and dynamic app registration while retaining the proven content-addressed quarantine, external probation, and exact rollback mechanics | Platform generic app factory and revision service |
| Immutable `.runtime/app_revisions` bundles as the only complete candidate source | Retain as deployment/recovery artifacts; add a visible exportable `apps/<app-id>/` project containing blueprint, source, tests, data, migrations, research, revision provenance, and evidence | User-owned application project |
| `.runtime/application_contract_cache/*.json` | Checksummed disposable per-app replay acceleration; every invocation validates epoch/checksum and catches up through authoritative `subscribe`; absence, corruption, or reset rebuilds from the journal | Platform application cache |
| `nace_beliefs.metta` | Compatibility projection from keyed belief atoms | Cognition/NACE projection |
| `nace_pending.metta` | Migrate append/clear queue to durable evidence events; retain projection during transition | Cognitive event ledger |
| `task_state.metta`, `memory/tasks/current_tasks.txt` | Keyed task atoms/events with text projections | Cognition/tasks |
| `transformations/.runtime/tool_reliability.json` | Reliability projection from outcome/revision events | Cognition/capability learning |
| `transformations/.runtime/tool_reliability_pending_batch.json` | Exact replay record for one bounded authoritative outcome batch; removed only after reliability/state/NACE projections finish | Cognition recovery |
| `chroma_db/memories.json` | Semantic record projection plus embedding index; authoritative semantic identity/change event in cognitive ledger | Cognition memory + Platform index |
| `transformations/.runtime/space.metta` | Read-only display/export projection | Application/observability |
| `transformations/metta_reasoning.py`, `tools/_metta_substrate.py`, `tools/_metta_gate.py` | Retain the prompt summary as observability; move dispatch decisions to authoritative seeds/runtime atoms at a named commit and record consequential verdicts | Cognition/governance |
| root `space.metta` | Legacy alias; no new writer | Legacy |
| `.runtime/pwq.json` | Materialized board projection from PWQ events | Platform human-agency service |
| Single `approve` event/token | Compatibility alias for a default 1-of-1 human policy; sensitive cards use explicit role-threshold attestations bound to proposal digest/scope | Core/Platform authorization protocol |
| `pwq_mirror`, `pwq_order_log` localStorage | Remove as authority; optional disposable UI cache only | PWQ board application |
| DAS | Projection/query adapter with independent cursor and reconciliation status | Platform adapter |
| Direct `self_improve.py` file writes | Removed from apply/full-loop; stage an inert generation and build-class PWQ proposal | Platform self-extension service |
| Global `/tmp/iter-browser-bridge.sock` | Replace with checkout-scoped endpoint; probe before stale cleanup and never unlink a responsive owner | Core browser bridge + Platform lifecycle |
| Per-cycle `tools/`, `transformations/`, `channels/` scan | Resolve one verified immutable generation at cycle start | Cognition loader + Platform generation manager |
| Whole-parent generation copy | Stage only the three declared managed executable roots; never inherit non-managed state shells, and reject any non-managed file found in a generation | Platform generation manager |
| `channels/electron_ui.py` path derived from its copied `__file__` | Bind inbox/outbox to the canonical Iter runtime root (`ITER_DIR`, with the process cwd as direct-launch fallback); an immutable generation may relocate code, never live application state | Core chat bridge + Platform generation manager |
| Chat tool channel name/import from caller cwd | Normalize harmless surrounding whitespace, reject non-identifier/path-traversal names, and dispatch through the sibling channel inside the same immutable generation | Core chat bridge + Cognition loader |
| Ephemeral outbox file followed by one IPC event | Journal each accepted message under the canonical Iter root before outbox acknowledgement; replay/deduplicate by stable ID after renderer reload or app restart | Core chat bridge + Platform application state |
| Directly visible inbox/outbox writes | Publish complete queue items by same-filesystem atomic rename; retain plain-text compatibility for immutable historical generations | Core chat bridge + Cognition channel |
| Stateful tools/transformations deriving stores from generation `__file__` | Bind semantic memory, PWQ, component museum, captures, CRM feed data, and Soul task reads to the same canonical Iter root; retain generation-relative paths only for sibling executable imports | Cognition + Platform/Application state owners |
| `crm/data/*.json` | Rebuildable compatibility projection after one idempotent import; no CRM UI/Electron whole-file writer remains | Application CRM projection |
| `tools/mm_scan.py`, `tools/gmail_scan.py` | Transitional direct feed writers outside APP-1's authorized resource/scope; migrate during CRM-1 through the source-neutral evidence contract rather than widening APP-1 | Cognition CRM evidence adapters |
| Root `install.sh` and `scripts/setup_python_env.sh` | Replace dependency-only source setup with one resumable state-safe Mac install/upgrade path that separates core runtime from optional development tools, launches exactly one instance, and proves app/AtomSpace/Iter health before success | Platform distribution + lifecycle + QA |
| Packaged `iter/**/*` copy containing the checkout's live state and secrets | Ship an allowlisted state-free template; atomically bootstrap a separate per-user writable `ITER_DIR`; fail closed on a partial existing workspace | Platform packaging + state lifecycle |
| Ad hoc backup restore | Retain only for historical backups; current rollback names the exact parent generation | Platform recovery supervisor |

## 8. PWQ v2 protocol

### States

`proposed → (partial attestations) → approved → in_progress → completed`

Side transitions:

- `proposed → modified → approved`
- `proposed|modified → rejected`
- `proposed|modified|approved|paused → superseded` only by the runtime guardian with a named replacement; dispatched work must first pause or roll back
- `approved|in_progress → paused`
- `paused → approved|in_progress` under the surviving current dispatch authorization, restoring the exact pre-pause state
- any nonterminal item may receive an immutable `reordered` event.

Legacy values are migrated deterministically:

| Legacy | Canonical |
|---|---|
| `waiting` / `proposed` | `proposed` |
| `negotiating` | `modified` |
| `orders given` | `approved` |
| `in progress` | `in_progress` |
| `done` | `completed` |

### Events

Every event includes `event_id`, `proposal_id`, `proposal_version`, `actor`, `kind`, `at`, `payload`, and `previous_event_id`. Human decision events are sign/approve, reject, modify, and reorder. A card declares an approval policy: eligible signer identities and roles, a threshold, required roles, accepted proof types, and distinct-signer enforcement. Each `approval_signed` event binds the current proposal digest. The writer mints `dispatch_authorization` only when the complete current-version set satisfies both threshold and required roles. Editing a proposal changes its digest and clears signatures, tracking, and authorization.

Ordinary cards default to a compatible 1-of-1 `human_owner` policy. Sensitive hot-load cards require 2-of-2: a human owner signs intent/scope, while `runtime_guardian` attests only that the exact immutable candidate passed fixed non-executing validation and retains the named rollback parent. The guardian cannot supply human consent. The present `trusted_local_session_v1` proof is a local control-plane attestation, not a wallet signature. Unverified wallet-looking payloads fail closed; EIP-712, hardware-wallet, contract-wallet, or on-chain proofs require an installed verifier adapter in a later slice.

Build-class proposals additionally declare allowed Atlas slices and invariants before approval. After authorized dispatch, immutable `tracking_updated` events project:

- Target;
- Stage: one allowed Atlas slice, a bounded claim, and allowed invariant references;
- Evidence/open gaps;
- Boundaries;
- Next/trigger.

Tracking cannot change status, scope, ordering, proposal version, or authorization. A proposal modification clears the current tracker and requires fresh approval. General work cannot claim IterBrow Atlas authority. Hot-load admission, probation observations, promotion, and rollback emit tracking automatically; rollback pauses the work item.

### Ownership

- Core owns the protocol and dispatch invariant.
- Platform owns the append-only event ledger, materialized queue, and audit.
- Applications render and submit narrow commands; they cannot synchronize a caller-supplied board projection and do not write the ledger or board file directly.

## 9. AtomSpace v1 API

| Operation | Purpose |
|---|---|
| `status()` | Ready/quiesced state, engine, commit, snapshot, projection health. |
| `query(code, at_commit?)` | Read-only native evaluation against an identified state. |
| `transact(transaction)` | Atomic ordered add/remove/replace operations with idempotency. |
| `checkpoint()` | Flush WAL and atomically publish a verified snapshot. |
| `quiesce()` / `resume()` | Reject new mutations while lifecycle work is in progress. |
| `reset()` | Clear runtime transactions, reload declared seeds, publish a new genesis commit. |
| `shutdown()` | Checkpoint and stop the service cleanly. |
| `subscribe(cursor)` | Ordered committed events for projections and adapters. |

`run(code)` remains temporarily as a compatibility alias for read-only `query`; durable mutation is available only through `transact`.

### Atom-operation evidence discipline

The ClarityOmega `Atom Operations Map` is adopted here as an evidence method,
not as a portable runtime specification. Every load-bearing atom operation is
classified `PROVEN`, `ASSUMED`, `UNKNOWN`, or `CONTRA` for the exact engine,
state shape, and scale where it was observed. Tests name zero/one/many
cardinality, ground versus extracted values, whole-space versus scoped-context
evaluation, both polarities, separate read-back, and restart reconstruction.

PeTTa/SWI-Prolog findings are design evidence only until reproduced in the
current Hyperon service. In particular, ClarityOmega's runtime-only mutation
plus file-authority model does not govern IterBrow, and its remove-then-add
writer is not imported. IterBrow's canonical writer is the journaled,
idempotent, keyed `transact` operation; native calculation remains distinct
from the transaction that persists its result.

Current COG-GOV-1 and APP-1 cells:

| Operation shape | Status | Exact evidence / boundary |
|---|---|---|
| Fully ground presence check in the live heterogeneous space | **PROVEN** | The exact active work and exact `exited / 0 / 102` observation each matched their committed atom. |
| Unscoped multi-field extraction from the entire live heterogeneous space | **CONTRA** | The exact ground record was present, but extracted terminal fields inherited unrelated task-state strings. This is a context-selection failure, not a declaration that native variables are intrinsically unsafe. |
| Versioned ground context authenticated in `&self`, then locally destructured by a native rule | **PROVEN** | Full live-space probes and the focused ladder return the exact native outcome while heterogeneous task-state and conflicting-accessor decoys are present. |
| Fully ground authenticated control capsule for shadow transitions | **PROVEN** | A first variable-bearing compact-record repair passed isolated tests but returned `soul-state` in the populated live space, so it was rejected. The final adapter reconstructs one fully ground `engineering-control-record` from the authoritative work event; MeTTa authenticates that exact capsule in `&self` before local native destructuring. Live APP-1 selected exactly `implement-atomspace-app-contract`; an otherwise identical `neutral` capsule returned no decision; adapter mismatch left commit/hash unchanged; corrected decision commit 2358 and exact native Tracking reconstructed after restart. |
| Python semantic outcome classification | **PROVEN ABSENT** | Python transports the authorized ground capsule and validates the returned vocabulary; MeTTa derives comparison, terminal outcome, Tracking, and Truth Revision. |
| Context replay after authoritative service restart | **PROVEN** | PID 19666 reconstructed epoch `92d6e63a...`, commit 2283, hash `5ba78165...`, then returned the same `accept`, positive `stv 1.0/0.5`, and exact Tracking with `dispatched: false`. |
| APP-1 zero/one/many, duplicate/collision, stale/invalid, correction/undo, replay, rebuild, app isolation, cache loss, and visible adoption | **PROVEN LIVE** | Nine contract tests plus six browser-boundary tests pass. Live CRM bootstrap committed once at 2359 and duplicate bootstrap did not advance authority. The isolated fixture created at 2360; duplicate replay returned 2360; a stale distinct command left commit/hash unchanged; undo appended 2361 and removed current record/fields while retaining both events. Deliberately corrupted CRM JSON rebuilt with no transaction. Both replay caches were moved aside after restart and reconstructed CRM revision 1 and fixture revision 2 solely from the journal. The replacement Electron then created a visible CRM record at 2362, accepted three visible revisions at 2363-2365, visibly undid the last distinct revision at 2366, reconstructed the corrected value after toolbar reload, and returned to zero current records after an acceptance-scoped cleanup delete at 2367. |
| APP-1 emitted native record/field atoms and exact-ground reads | **PROVEN LIVE** | The repository's Hyperon runtime parsed the declared application seed. In the populated live space, the exact material fixture record and text field returned themselves at commit 2360; after undo, exact record presence returned empty. After restart at commit 2361, exact CRM and fixture revision atoms, existing governor Tracking, epoch, and state hash all reconstructed. The visible CRM record and name field then authenticated with fully ground reads at commit 2362; an ungrounded variable-bearing query returned unrelated decoy strings and is preserved as negative evidence, not read-back proof. After delete at 2367, the service context and reloaded CRM both report zero current contacts while the full event history remains replayable. |

## 10. Recovery model

1. Validate manifest and open an exclusive service lock.
2. Load the newest checksummed snapshot.
3. Read the WAL, accepting only complete committed transactions after the snapshot cursor.
4. Load declared source seeds.
5. Reconstruct the Hyperon engine from seeds plus current keyed runtime atoms.
6. Verify atom count/hash and publish `ready` with the current commit.
7. Start accepting reads and mutations.

Transaction acknowledgement occurs only after the prepare record, engine application, and commit record are durably flushed. If engine application or commit persistence fails, the service rebuilds from the last committed state before accepting further work.

## 11. DAS contract

DAS receives committed events through the projection feed and stores its own cursor. It may expose query acceleration or distributed views, but:

- a DAS outage never blocks canonical local commit;
- DAS never allocates canonical transaction IDs;
- DAS reconciliation compares commit cursor and content hashes;
- no caller imports DAS-specific storage types;
- promotion to authoritative backend requires a separate ADR proving live writes, remove/replace, transactions, recovery, and native reasoning behavior.

## 12. Verification matrix

| Test | Required proof |
|---|---|
| Durable atom | Commit atom, terminate service without graceful shutdown, restart, query atom, verify one copy. |
| Idempotency | Submit identical transaction ID twice; second response returns original commit and does not duplicate. |
| Replace/remove | Replace a keyed atom and prove old value is absent after restart; remove and prove absence. |
| Evaluation isolation | Evaluate code containing temporary facts; subsequent query/status hash is unchanged. |
| Seed discipline | Place an undeclared `.metta` file under runtime; restart; prove it is not loaded. |
| Export/import | Export commit N, mutate to N+1, import export, prove service returns to N and Iter resumes afterward. |
| Reset | Commit runtime atom, reset, prove runtime atom absent and declared seeds present. |
| Secret exclusion | Put sentinel in API key setting; export and scan archive; sentinel must be absent. |
| Packaged workspace | Audit the built `.app` for forbidden state/secret paths; launch with an isolated workspace; export after a named commit; restore into a second clean workspace and prove exact epoch/commit/hash/atom count plus native query. |
| Cognitive domains | Perform one NACE, reliability, task, Soul, and memory mutation; confirm durable domain events and projections. |
| Governed dispatch | Query KB/NACE at commit N, record a consequential allow/advise/veto decision, prove a hard violation is blocked before the tool runs, and prove the event cannot mint PWQ approval. |
| PWQ agency | Propose, modify, reorder, approve, dispatch, complete; reject stale-version approval and unauthorized dispatch. |
| PWQ threshold authorization | Collect distinct required roles against one proposal digest; prove no early token, actor/role impersonation fails, modification revokes all attestations, exact candidate scope is enforced, and uninstalled wallet proof types fail closed. |
| PWQ build Tracking | Reject pre-dispatch or out-of-scope tracking; replay the latest five-field update; prove status/version/authorization are unchanged. |
| Revision quarantine | Stage a complete generation, validate without import, reject core/nested/candidate-defined-test targets, and prove the active generation is unchanged. |
| Revision probation | Require build-class PWQ authorization, one checkout-scoped Electron supervisor, and a current live-parent heartbeat before dispatch; permit the pinned parent cycle to finish; preserve every completed candidate cycle as content-verified immutable evidence; permit bounded same-PID/session successor proof only for an already-running pre-journal Iter; promote only at the distinct-cycle threshold. |
| Revision recovery | On exit, error, stale/missing heartbeat, wrong generation, revoked authorization, startup probation, or hash mismatch, restore the exact verified parent. |
| Hot-loaded runtime paths | Load stateful components from simulated generation copies and prove chat, semantic memory, PWQ, component museum, captures, CRM feeds, and Soul resolve only canonical application paths without creating generation-local state; then prove canonical semantic-memory/PWQ reads and one live UI message/response round trip after promotion. |
| DAS independence | Fail adapter intentionally; canonical transaction still commits and adapter later catches up from cursor. |

## 13. Future-self resumption protocol

Before editing:

1. Read this Atlas and the ADRs under `docs/architecture/`.
2. Run `git status --short`; preserve unrelated work.
3. Run the control test command recorded in section 14.
4. Find the first ledger row not marked `DONE`; do not skip its dependencies.
5. Update the row to `BUILDING` in the same change that begins implementation.

Before claiming a slice complete:

1. Update or add the acceptance test first.
2. Run the focused test and the full control suite.
3. Record the command and result in section 14.
4. Update docs that describe the affected runtime path.
5. Mark the row `DONE` only when the exit condition is evidenced.

### Tracking integrity

Tracking is reconstructed from primary state and may never amend this Atlas, its ADRs, or observed evidence. At context recovery or a stage boundary, inspect the Atlas, governing clauses, branch/revision, working changes, actual consumer, tests, and unresolved counterexamples. Distinguish repository source, packaged installation, live observation, and experimental baseline. A prior Tracking report is only a retrieval hint.

Every stage boundary and substantive build report to the human contains a fresh Tracking block with these explicit fields:

- **Tracking:** the stable target, active Atlas slice/invariants, and current authority/safety boundary.
- **Active claim:** one bounded statement that the current evidence can support.
- **Evidence:** observations and tests that support only that claim.
- **Unresolved:** missing work or verification stated separately from evidence.
- **Counterexamples:** failures, adverse cases, non-claims, and distinctions that constrain the active claim.
- **Next dependency:** the next required movement and the evidence or human decision that unlocks it.

New evidence, changed control, widened claims, unexpected results, or a changed next action trigger immediate re-anchoring. Missing verification remains missing. Mechanical presence of these labels does not prove semantic alignment; the source-to-claim reasoning remains open to human challenge.

This section governs the human/build process. During COG-GOV-1, the same five-field view also becomes a read-only projection of Iter's authoritative native work graph for governed PWQ work. The projection does not become authority: it cannot mint approval, change proposal scope, override the Atlas, or substitute prose for evidence. Until projection parity and restart reconstruction pass, builder Tracking and runtime Tracking must be labeled distinctly rather than blended.

### Current visible-acceptance handoff

ADR-0010 supersedes the previous next-action ordering without erasing its
evidence. The COG-GOV-1 shadow proof and PWQ-4 live-attention repair are
accepted. Active card `pwq-cog-gov-active-action-20260922-a` version 2 is
terminally completed at canonical sequence 116. Its exact read-only action ran
once; the higher-order context repair closed its native outcome from the
existing observation after whole-space field extraction exposed a
scope-selection counterexample. Do not dispatch it again. APP-1 proposal
`pwq-app-contract-20260922-a` is version 2, digest
`2c85de519931cff88cc39ad380ef531625d0e0e86b9f06b3419b77bdbc8d1420`, and is
paused at canonical sequence 122 with pause Tracking at 123. It binds the next
work to one AtomSpace-backed app contract, current-CRM compatibility migration,
and one second fixture consumer; it explicitly excludes CSV, Mattermost,
credentials, briefing intelligence, Gmail, Calendar, and visual redesign.
Repair card `pwq-cog-gov-shadow-selection-repair-20260922-a` version 2/digest
`08f508135254a4c969f8d57714646bb0945a58ecef96e21a85b09e70345ecf07`
completed after final Tracking at canonical sequences 129–130. The unchanged
APP-1 authorization resumed at sequence 131 and fresh APP-1 Tracking sequence
3 advanced the ledger to 132. APP-1 is now the only active implementation
authority. CRM-1 and the MAGIC-1 proof follow only
after that seam is accepted. DIST-1 is the partner-release
gate and may be designed in parallel, but it cannot report install success
until the local magic path and its live health acceptance exist. Do not owner-sign, activate, or
promote `candidate-63a395064e264b5eab3d70dbfedf14d6` merely to finish the old
handoff; it remains inert evidence until the native governor assesses whether
that work still belongs in the active intention. The completed lifecycle card
`pwq-live-lifecycle-20260921-a` is retained evidence but is not authority for
the new governor, CRM, or installer scope.

The non-UI architecture and recovery work is accepted. Reconstruct all live
identities from primary state before acting; the identifiers below bind the
remaining evidence but do not replace that check.

1. Keep exactly one source Electron owner and its supervised Iter process. Do
   not start a second `npm start` or standalone loop. Confirm the active stable
   generation is `candidate-33887e67bdf4410f934e39450c0f3920` before any
   candidate action.
2. The visible chat acceptance is complete. Probe
   `CHAT-ACCEPT-20260922-E` traversed inbox, Iter response, Electron receipt,
   byte-exact restart replay, and live post-unlock rendering exactly once in
   each role. The blank-native-surface counterexample is closed by reattaching
   the existing sidebar view on unlock/resume/window focus without ever hiding
   it. Do not repeat this drill unless the chat or view lifecycle changes.
3. Card `pwq-live-lifecycle-20260921-a` completed its exact ledger-only
   lifecycle. Sequence 91 records the visible owner signature; sequences 94–98
   record authorized start, scoped Tracking, pause, authorization-bound resume,
   and completion. It is terminal `completed` and grants no authority to later
   work. Do not reuse its authorization or repeat the drill unless the protocol
   lifecycle changes.
4. Card `pwq-cog-gov-shadow-20260922-a` was modified and visibly owner-signed
   at version 2, digest `ed9f6484...`, then started with exact authorization
   `1ffb4df5-d786-4335-8c10-693378762f0a` at canonical sequence 102. Work
   commit 2090 produced exactly one native `shadow_action_ready` result;
   decision commit 2091 records `dispatch_authority=false`. AtomSpace PID
   `71806` restarted as `73239` while epoch `92d6e63a...`, commit 2091, hash
   `34c0580b...`, the native decision, and the native Tracking projection all
   remained exact. The normal loop then resumed as the only Iter process, PID
   `73823`, session `2fcd39f1...`, on stable generation `candidate-33887e...`
   and completed a healthy cycle. The card remains `in_progress`: its signed
   allowed effects included reading native Tracking but not appending a new PWQ
   Tracking event or dispatching an action, so the build did not manufacture
   either ledger transition. Do not reuse this authorization for the next
   action or for PWQ-4.
5. PWQ-4 now satisfies INV-31. Card `pwq-live-attention-sync-20260922-a`
   version 2/digest `412684e7...` started under exact authorization at sequence
   108. One external scope-bound Tracking fixture advanced the ledger to 109;
   both repaired open PWQ tabs observed it within the bounded poll without
   manual reload. The instrumented tab retained draft
   `PWQ4-LIVE-DRAFT-KEEP-20260922`, textarea focus, selection 6–16, `waiting`
   filter, and scroll position 240. Repeated interval/focus/visibility reads
   left canonical sequence at 109: refresh is a read-only projection and did
   not mint a decision, Tracking event, or competing write. After acceptance,
   the single authorized completion event advanced 109→110; both repaired
   boards independently caught up to rendered sequence 110 and terminal
   `completed`, while the instrumented draft and view state remained exact.
6. Card `pwq-live-lifecycle-20260921-b` completed its visible negative-path
   drill. Ledger sequence 92 records the reorder at the unchanged version and
   digest; sequence 93 records human rejection. It is terminal `rejected`,
   unsigned, and has no authorization. Do not repeat this drill unless the
   reorder/reject path changes. UI state is a projection; it is never
   acceptance evidence by itself.
7. The inert additive repair candidate is
   `candidate-63a395064e264b5eab3d70dbfedf14d6`, exact parent
   `candidate-33887e67bdf4410f934e39450c0f3920`, tree
   `04ae6aadf600cbd2c2f20bd1ba3c5db73f96acffd06f0b27f624f1e4a7a9194b`,
   and proposal digest
   `84a5d71e1decee9536c02ae102ea2a1450a00f3fe5fbcec99fab7a2eca662ea8`.
   It changes exactly `tools/pwq_write.py`, `channels/electron_ui.py`,
   `transformations/pwq_board.py`, `transformations/transcript.py`,
   `transformations/tool_reliability_tracker.py`, and
   `transformations/nace_courier.py`: narrow PWQ writes, atomic versioned chat
   output, terminal-card projection, truthful send-body evidence, and bounded,
   replay-safe reliability→NACE backlog recovery. It currently has only the
   runtime-guardian witness. Candidates `candidate-7fbec7e…` and
   `candidate-9c46418d…` are terminally superseded with their evidence retained.
   Use the visible owner-signature action
   only after re-verifying the replacement's exact bindings. Never simulate or
   write an owner decision through protocol, file, or test helpers. After
   authorization, activate only through the external supervisor, require three
   distinct immutable healthy completions, and accept either exact promotion or
   exact-parent rollback.
8. The visible lifecycle check is complete: Stop persisted
   `iterAutoStart=false`; app restart left Iter stopped; visible Start persisted
   `iterAutoStart=true` and resumed exactly one process/session on stable
   generation `candidate-33887e…`. AtomSpace PID `21252` retained epoch
   `92d6e63a…` and advanced from commit 1051 to 1143. Do not repeat this drill
   unless a later lifecycle change invalidates the evidence.
9. The post-shadow unrestricted `scripts/test_control_plane.sh` run passes all
   117 authoritative tests, 104 historical checks, syntax/manifest checks, and
   authored-file diff checks. Keep TRACK-1 and QA-1 open across the remaining
   Atlas; close no future slice from inherited evidence. A locked UI is a
   blocker, never permission to bypass the visible human-agency boundary.
10. Active card `pwq-cog-gov-active-action-20260922-a` was modified and visibly
   owner-signed at version 2/digest `f6fac657...`; authorization
   `79bd9fee-30d1-4e9e-9e41-86a24202f210` started at sequence 114. Work commit
   2278, single dispatch claim commit 2279, and raw observation commit 2280 are
   durable. The allowlisted `qa.pwq_board_boundary` process exited `0` once and
   recorded `102` output bytes plus exact stdout/stderr digests. The first
   terminal query did not close because unscoped live-space field extraction
   returned unrelated task-state strings even though the exact ground atom was
   correct. No second action ran. The authorized repair now uses a versioned
   ground context carrying claim, invariants, state, gap, alternatives,
   prediction, risks, obligations, authorization, raw observation, and recovery
   state. Context commit 2281 produced native `accept`; decision commit 2282
   and positive `stv 1.0/0.5` evidence commit 2283 are durable. Service PID
   19666 reconstructed the exact epoch/commit/hash and returned the same
   Tracking with `dispatched: false`. Focused tests pass `28/28`; the full
   control plane passes 134 authoritative tests and 104 historical checks.
   Scope-bound PWQ Tracking advanced sequence 114→115 and exact terminal
   completion advanced 115→116 without changing version, digest, authorization,
   or scope. The existing app's Start control then resumed exactly one parent
   Iter process, PID `21885`, session `b1ee4b77...`, on stable generation
   `candidate-33887e...`; immutable cycle-1 completion sequence 8 has
   `hard_floor_ok=true`, after which the same session entered cycle 2. The sole
   Electron main PID remains `71795`. Do not run another `npm start` or treat
   per-tool child processes as competing Iter owners.
11. APP-1 card `pwq-app-contract-20260922-a` was human-approved at version 2,
   exact digest `2c85de519931cff88cc39ad380ef531625d0e0e86b9f06b3419b77bdbc8d1420`,
   and started under dispatch authorization
   `66430051-0b8d-4419-9140-da5a83a44776` at sequence 120. Tracking sequence 1
   followed at 121. Work commit 2334 recorded exact selected alternative
   `implement-atomspace-app-contract`; the old broad shadow matcher then
   persisted a contaminated `neutral` decision at commit 2335. APP-1 paused at
   sequence 122 with explicit pause Tracking at 123. Preserve both commits as
   evidence; do not reset, rewrite, rerun, change the APP-1 version/digest, or
   mutate APP-1 source before the repair proof.
12. Repair card `pwq-cog-gov-shadow-selection-repair-20260922-a` was selected
   and owner-signed through the canonical human command boundary at version 2,
   digest `08f508135254a4c969f8d57714646bb0945a58ecef96e21a85b09e70345ecf07`.
   Authorization `fe50de33-483d-4c59-b561-146426871432` started only that exact
   repair at sequence 127; its first scope-bound Tracking event is sequence
   128. Source tests first reproduced duplicate `native-shadow-governor` plus
   `neutral` decisions for all six shadow transitions. The minimal source
   repair initially derived each transition from a variable-bearing compact
   work-keyed control match. Although 31/31 focused tests and 137/137 unit tests
   passed, the first populated live restart returned `soul-state`, so that
   source-green design was rejected. The final design transports one fully
   ground control capsule reconstructed from the authoritative event,
   authenticates its exact presence in `&self`, and only then lets MeTTa
   destructure it locally. Corrected non-dispatching decision commit 2358,
   mismatch-without-commit, exact native Tracking, and final restart
   reconstruction pass at epoch `92d6e63a...`, hash `94c68ead...`, 3,383 atoms,
   PID 42383. Focused tests pass 32/32; the full control plane passes 138
   authoritative tests plus 104 historical checks. Final repair Tracking
   advanced sequence 128→129 and exact completion advanced 129→130 without
   changing version, digest, authorization, or scope. APP-1 remained paused
   throughout the repair; the autonomous Iter loop remains stopped.
13. The unchanged APP-1 authorization resumed `pwq-app-contract-20260922-a`
   from its preserved `paused_from=in_progress` state at canonical sequence
   131. Fresh APP-1 Tracking sequence 3 advanced the ledger to 132 and cites
   corrected decision commit 2358 plus every original functional, recovery,
   migration, boundary, and visible-acceptance obligation. Proposal version 2,
   digest `2c85de519931cff88cc39ad380ef531625d0e0e86b9f06b3419b77bdbc8d1420`,
   authorization `66430051-0b8d-4419-9140-da5a83a44776`, resources, and
   exclusions remain exact. Red contract/boundary tests were then established
   before implementation with one writer.
14. APP-1 now has a journal-first typed application service, a declared native
   seed, WebContents-bound application/consumer scope, a minimal generic
   preload, CRM command/subscription migration, compatibility projection
   rebuild, and a second fixture consumer. The old Electron `crm:read` and
   `crm:write` handlers are absent; CRM source no longer names its JSON files;
   `crm/data` is manifest-classified as a projection. Stale revision, invalid
   provenance, command collision, and missing app scope fail closed. Duplicate
   command replay is idempotent; create/replace/delete/undo/import reconstruct
   from authoritative events; a projection error cannot mask an acknowledged
   commit. Focused contract/boundary tests pass 15/15. Direct native Hyperon
   parsing and exact-ground record/field queries pass. The unrestricted full
   suite passes 153/153 and `scripts/test_control_plane.sh` passes all 153
   authoritative tests, 104 historical checks, syntax, manifest, shell, and
   authored-file diff checks. The restricted run's sole temporary Unix-socket
   `EPERM` passed under normal local socket access. The remaining live
   acceptance obligations are recorded below rather than inferred from
   source-only evidence. Iter remains stopped and there is still exactly one
   Electron owner; do not launch a second `npm start`.
15. Live APP-1 authority/recovery acceptance now passes through commit 2361.
   CRM bootstrap revision 1 committed once at 2359 and its duplicate was
   read-only. Exact native revision/command atoms and its domain event agree.
   Deliberate `contacts.json` corruption rebuilt to the canonical projection
   with commit/hash unchanged. The isolated second consumer created one
   material record at 2360; native exact-ground record/field reads passed;
   duplicate replay was idempotent; a stale distinct command failed before
   mutation; undo appended revision 2 at 2361 and removed current record/field
   atoms while retaining both events. The service restart from PID 50772 to
   54500 preserved epoch `92d6e63a...`, commit 2361, hash `cfd0683f...`, and
   3,391 runtime atoms. Moving both replay caches to a recoverable backup then
   rebuilt CRM revision 1 and fixture revision 2 solely from the journal;
   native revision atoms and prior APP-1 governor Tracking also reconstructed.
   PWQ Tracking sequence 4 is canonical sequence 133. Still open: replace the
   sole pre-change Electron PID 71795, prove the actual scoped IPC/preload and
   visible CRM flow, rerun final gates, append terminal Tracking, and complete
   the card. Iter remains stopped.
16. Visible APP-1 adoption passes in replacement Electron main PID 58966 while
   sole AtomSpace PID 54500 preserves epoch `92d6e63a...` and Iter remains
   stopped. The real CRM UI created temporary contact `c_mudcetzpklad` through
   the scoped preload at commit 2362; fully ground native record and field
   reads authenticated that exact state. Three visible replace commands
   advanced revisions 3-5 at commits 2363-2365. Two same-value revisions at
   2363/2364 preserve a real double-submit counterexample: authority stayed
   coherent, but a later UX slice must hold the mutation control disabled until
   acknowledgement. The visible Undo control appended revision 6 at 2366 and
   restored the prior value; toolbar reload reconstructed it from authority
   with Undo disabled. Acceptance cleanup used the same typed contract to
   append delete revision 7 at 2367, leaving state hash `8d018215...`; a second
   toolbar reload shows `PEOPLE · 0`, and the service independently reports
   `contacts: []` while retaining the full import/create/replace/undo/delete
   history. An ungrounded live variable query returned unrelated decoy strings
   and is explicitly not acceptance evidence; only fully ground capsules
   count. Focused tests pass 15/15 and the complete control plane passes 153
   authoritative tests, 104 historical checks, and every
   syntax/manifest/shell/diff gate. This proves the reusable application seam
   and its CRM adoption. It does **not** prove that autonomous Iter built the
   CRM or can yet build an arbitrary tab/app without overseer feature code;
   that separate magic claim requires a new bounded Atlas/PWQ slice in which
   Iter is the sole feature-code writer and Codex observes, authenticates, and
   recovers without implementing the feature. Final APP-1 Tracking sequence 5
   is canonical PWQ sequence 134; exact version-2 terminal completion is
   canonical sequence 135. Version, digest, authorization, scope, signatures,
   and prior counterexample history remained unchanged.

## 14. Build log and verification evidence

| Time | Slice | Change/evidence | Result |
|---|---|---|---|
| 2026-09-21 | ATLAS-1 | Architecture inventory completed at branch baseline; authority conflicts enumerated. | Evidence captured. |
| 2026-09-21 | ATLAS-1 | Build Atlas created and adopted as the migration control document. | Active. |
| 2026-09-21 | AS-1–DAS-1 | Journaled AtomSpace, manifest lifecycle, cognitive bridges, PWQ protocol, and DAS adapter implemented. | 26 authoritative-runtime tests pass. |
| 2026-09-21 | QA-1 | `scripts/test_control_plane.sh` runs new tests, historical regressions, syntax, and manifest checks. | 26 new tests and 104 historical checks pass. |
| 2026-09-21 | TRACK-1 | Miter Tracking rules reviewed at source revision `37c92391b8adc09759831cffee9cff8a387a72cc` and adapted as builder discipline, not runtime cognition. | Five-field reporting active. |
| 2026-09-21 | HOT-1 | Existing direct-write loader and `self_improve.py` path inspected against Miter quarantine/trial/rollback requirements. | Gaps recorded; implementation active. |
| 2026-09-21 | HOT-1 | Immutable complete generations, inert fixed validation, managed-surface boundary, content hashes, and hash-chained lifecycle events implemented. | 127 reachable component files pass admission; tampering fails closed. |
| 2026-09-21 | HOT-2 / REC-1 | Cycle pinning, PWQ-authorized probation, Electron heartbeat supervision, promotion, startup recovery, exact parent rollback, and interrupted-ledger-tail repair implemented. | Twelve focused safety tests plus self-improve-to-recovery integration pass; live packaged drill open. |
| 2026-09-21 | PWQ-3 | Build scope references and immutable five-field execution tracking added; hot-load lifecycle emits updates automatically and rollback pauses work. | Replay, idempotency, scope, authority, and reset-on-modify checks pass; board script parses. |
| 2026-09-21 | QA-1 | Full control suite after hot-load, recovery, Tracking, docs, callable-schema, torn-journal recovery, legacy-state admission, and state-owned singleton changes. | 48 new tests and 104 historical checks pass. |
| 2026-09-21 | HOT-2 | Dynamic and static tool metadata now agree on optional/default parameters and exclude variadics from JSON schemas. | Parity passes across 100 public components; fixture edge cases pass. |
| 2026-09-21 | COG-1 / REC-1 | An incomplete final AtomSpace journal write is discarded, hash-recorded, and atomically repaired before future appends; complete malformed records fail closed. | Replay-through-next-commit and corruption tests pass. |
| 2026-09-21 | AS-2 | Real installed Hyperon loaded 87 declared seed atoms in disposable state; an acknowledged atom survived forced process death, replayed at the same commit/hash, queried exactly once, rejected duplicate transaction replay, and cleaned up. | `iter/.venv/bin/python3 scripts/smoke_atomspace_service.py` passes without panic, traceback, or reconstruction failure. |
| 2026-09-21 | COG-1 | Read-only admission of the live checkout found 606 distinct current records: 87 NACE beliefs, 194 latest task states, 268 semantic memories, one Soul state, one Soul registry, and 55 reliability states. Disposable Hyperon rebuilt all 607 migration/marker atoms, then passed forced-death replay on top. | No duplicate keys; 342,467 atom bytes; migration commit and content hashes retained; live source files untouched. |
| 2026-09-21 | COG-1 / LIFE-1 | Live authority created at epoch `92d6e63a-6331-4cc8-9072-df8fdbbfa232`, commit 1, 607 atoms, hash `a07fe26…`; native NACE and semantic-memory queries passed, checkpoint/restart returned `already_migrated`. Cross-socket review found and closed a competing-service hazard by moving the singleton lock from socket identity to state-directory identity. | Live migration durable; Iter remained stopped; updated Electron lifecycle drill still open. |
| 2026-09-21 | LIFE-1 | Electron startup now retires a generic-socket service only after its reported state/checkout identity matches this checkout, then starts the checkout-specific endpoint against the same state-owned lock. Foreign services are left untouched. | Source-order guard and Node syntax pass; live app-restart handoff remains. |
| 2026-09-21 | GOV-2 | Role-threshold PWQ attestations, version/digest binding, exact hot-load scope, human-owner/runtime-guardian separation, revocation on modification, and future proof envelope implemented. | 25 focused PWQ/hot-load/self-improvement tests pass; unverified EIP-712 input fails closed; packaged signing drill remains. |
| 2026-09-21 | QA-1 / GOV-2 | Current control suite rerun after threshold authorization, governed dispatch, one-shot Hyperon query isolation, and candidate supersession/status fixes. Generated dashboard projections are preserved and excluded only from authored-source whitespace checking. | 60 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks pass with zero exit. |
| 2026-09-21 | LIFE-1 / GOV-2 | Controlled app restart retained AtomSpace epoch `92d6e63a…`, commit 150, and state hash `88444818…`; isolated `(+ 20 22)` returned `[[42]]` without changing authority. Live PWQ card renders exact digest, 1-of-2 runtime-guardian witness, and missing human-owner role. | Restart/query continuity and packaged board presentation pass; human signature and post-authorization probation remain. |
| 2026-09-21 | HOT-2 / REC-1 | First live authorized candidate drill activated while Iter was stopped; the external supervisor restored exact parent `base-5c1bd89139b7f6f8` after the startup grace, and the subsequent heartbeat identified only the parent. Activation admission now requires a fresh matching heartbeat from a live parent PID and permits that pinned parent cycle to finish before demanding a candidate heartbeat. | Recovery behavior passed; the failed candidate and authorization remain retained evidence. Replacement candidate and live promotion drill remain open. |
| 2026-09-21 | LIFE-1 / REC-1 | Second live drill crossed into the exact candidate at cycle 14, exposing two simultaneous `electron .` main processes for the same checkout. The orphan supervisor had no Iter child, rolled probation back as an exit, and the owning supervisor correctly restarted the parent after seeing the resulting generation mismatch. A checkout-scoped Electron single-instance lock now prevents competing lifecycle supervisors. | Exact parent restored; duplicate process removed; single-instance restart drill and fresh candidate promotion remain open. |
| 2026-09-21 | HOT-2 / REC-1 | Third live drill ran under the proven sole supervisor and exposed a finer cycle-boundary case: the activation-time parent cycle emitted a later `model_wait` phase after the pointer changed. Probation now permits only that exact parent PID/session/cycle to finish; a different parent cycle or any unrelated wrong generation still rolls back. | Exact parent restored; bounded transition tests added; fresh candidate promotion remains open. |
| 2026-09-21 | HOT-2 / REC-1 | Split-authorized candidate `candidate-37652b0fcded4cb88761a85706db8bb1` crossed the generation boundary under one supervisor and reached cycle 19. The drill exposed lossy 5-second polling of transient `cycle_complete`; promotion evidence is now written as immutable, content-hashed per-cycle records, with a same-PID/session successor-cycle bridge for the already-running pre-upgrade process. | Candidate promoted from three distinct completed cycles (6–8); latest-heartbeat overwrite, compatibility, and evidence-tamper tests pass. |
| 2026-09-21 | LIFE-1 / HOT-2 / REC-1 | Controlled source-app restart retained the promoted generation and AtomSpace epoch `92d6e63a…`, commit 219, 891 runtime atoms, and state hash `8d2dc444…`. The restarted Iter selected the promoted generation in new session `ae4e5eaa…`; cycle 1 wrote immutable completion hash `4ec2b669…`, which remained after the latest heartbeat advanced to cycle 2. | Promoted-generation recovery, authoritative-state continuity, one-supervisor ownership, and lossless live completion evidence pass. |
| 2026-09-21 | QA-1 / HOT-2 / REC-1 | Full control suite rerun after lossless probation evidence and the successful live promotion/restart drill. | 68 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks pass with zero exit. |
| 2026-09-21 | COG-2 | The promoted gate materially governed the live loop: cycle 7 recorded `shell ALLOW` from AtomSpace commit 236 at commit 237, then the real shell outcome succeeded at commit 238. A bounded managed-code-write negative control produced `VETO`, named `one_shape_one_writer`, created no sentinel file, and left PWQ authority unchanged. Native queries independently retrieved all controlled decision-event atoms. | Live allow/dispatch, advisory distinction, durable decision retrieval, no-side-effect veto, and PWQ independence pass. The drill exposed that the hard-veto payload discarded the KB query identity. |
| 2026-09-21 | COG-2 / HOT-2 / GOV-2 | Hard vetoes now carry the epoch, commit, and state hash returned by the authoritative KB-invariant query. Six focused governance tests and the full control suite pass. Immutable candidate `candidate-f131e531bf09466895c14db887e882cf` changes only `tools/_metta_gate.py`; tree `04d8de9f…`, proposal digest `76354ce4…`, exact rollback parent `candidate-37652b…`. | Runtime-guardian attestation is present; human-owner role and dispatch authorization are intentionally absent pending the human decision. |
| 2026-09-21 | COG-2 / HOT-2 / GOV-2 | Human-owner signature completed the exact two-role threshold for `candidate-f131e531bf09466895c14db887e882cf`. The sole external supervisor observed immutable completions for cycles 22–24 and promoted it over retained parent `candidate-37652b…`. Post-promotion negative control queried `one_shape_one_writer` at AtomSpace commit 277, recorded `python VETO` at commit 278 with the evaluated epoch/state hash, remained natively queryable, and created no sentinel file. | COG-2 acceptance closes: material allow/dispatch, named-commit veto, durable native evidence, no forbidden side effect, and PWQ independence all pass. |
| 2026-09-21 | QA-1 / COG-2 | Final post-promotion control run after the named-commit veto and canonical PWQ completion event. The sole Electron owner continued running stable generation `candidate-f131e531…` through cycle 27. | `scripts/test_control_plane.sh` passes 68 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. |
| 2026-09-21 | HOT-2 / REC-1 | A user health request exposed that the promoted generation's copied `channels/electron_ui.py` derived a private inbox from `__file__`; Electron correctly wrote the canonical inbox while Iter polled the generation-local inbox. Four messages remained durable. The requested health message was moved once to the polled inbox, consumed at 21:09:04, answered at 21:10:30, and visibly rendered. Three older messages were preserved in a quarantine directory rather than replayed. Source now binds the channel to the canonical Iter root; a simulated-generation regression test passes. Immutable candidate `candidate-6b7bb6297bc74873829f5b4aa52ac875` changed only `channels/electron_ui.py` over stable parent `candidate-f131e531…`. | Operational recovery passed. The inert one-file candidate was later superseded, with all evidence retained, when the audit found the same root cause in additional stateful components. |
| 2026-09-21 | QA-1 / COG-2 / HOT-2 | The exact observed governance false positive is narrowed without a general shell parser: discard-only diagnostic redirection to `/dev/null` is removed from write-intent classification, while direct redirection, `tee`, `sed -i`, removal, and protected-state writes remain vetoed. The chat-channel simulated-generation test joins the authoritative suite. | `scripts/test_control_plane.sh` passes 71 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. The correction is bundled additively into the canonical-root replacement candidate. |
| 2026-09-21 | HOT-2 / COG-1 / PWQ-1 | The chat defect's root-cause audit found the same relocated-`__file__` state fork in semantic memory, PWQ, component museum, device capture, CRM feed scanners, and Soul task lookup. Source now exports `ITER_DIR` for Electron and direct Iter launches and binds only application state to it; generation-relative executable imports remain intact. The PWQ board now labels preference and scope-edit controls as non-signing and makes the signature action explicit after the user's approval text was correctly but confusingly recorded as a proposal modification. | Three canonical-root contract/relocation tests plus the chat test pass; the attempted text approval remains preserved as negotiation evidence and minted no authorization. |
| 2026-09-21 | QA-1 / HOT-2 | Full control suite after the bounded canonical-root repair and approval-UX clarification. | `scripts/test_control_plane.sh` passes 74 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-21 | HOT-2 / COG-1 / PWQ-1 / REC-1 | Validated immutable candidate `candidate-3f2da49ef5334611a1248072a805904f` changes exactly nine managed components over stable parent `candidate-f131e531…`; tree `8f5cc923…`, proposal digest `274d5c37…`. The retired one-file candidate and the user's non-signing approval text remain preserved as evidence. The replacement card has no preference options or ambiguous approval text field semantics. | Runtime guardian signed the exact candidate digest. Status remains proposed, 1-of-2; human-owner signature and dispatch authorization are intentionally absent. |
| 2026-09-21 | HOT-2 / COG-1 / PWQ-1 / REC-1 | Human-owner signature completed the exact threshold for canonical-root candidate `candidate-3f2da49ef5334611a1248072a805904f`; its authorization digest remained bound to proposal digest `274d5c37…`. The sole external supervisor observed immutable completions for cycles 102–104 and promoted it over retained parent `candidate-f131e531…`. | Live inspection from the promoted generation resolves 268 semantic records from canonical `iter/chroma_db/memories.json`, six PWQ items from canonical `iter/.runtime/pwq`, and zero generation-local state files. Exact UI probe `CHAT-PROBE-20260921-A` round-tripped visibly. |
| 2026-09-21 | PWQ-1 / PWQ-2 / HOT-2 | The retired one-file chat candidate is now terminal `superseded`, names its canonical replacement, clears authorization, rejects further signatures, and remains in the audit ledger. Terminal cards are non-actionable in the board. | Guardian-only supersession and terminal-signature rejection tests pass; the stale card can no longer compete with its promoted replacement. |
| 2026-09-21 | HOT-2 / PWQ-2 / REC-1 | Live chat acceptance exposed surrounding whitespace in a model-supplied channel name. Candidate `candidate-33887e67bdf4410f934e39450c0f3920` normalizes safe whitespace, rejects non-identifier/path-traversal names, and imports the sibling channel from its exact immutable generation. Split approval bound proposal digest `57686cef…`; the supervisor observed immutable completions for cycles 117–119 and promoted it over retained parent `candidate-3f2da49e…`. | Exact promoted-generation whitespace dispatch and UI probe `CHAT-PROBE-20260921-B` both rendered visibly. The live loop remains healthy on the promoted generation. |
| 2026-09-21 | HOT-2 / QA-1 | Future candidates now copy only `tools`, `transformations`, and `channels`; empty non-managed historical directories are not propagated, and any non-managed file causes validation to fail closed. Existing immutable historical evidence is not rewritten. | 23 focused hot-load tests and the full control suite pass: 79 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. HOT-2 acceptance closes; the intentional REC-1 hang drill remains separate. |
| 2026-09-21 | PWQ-1 / PWQ-2 / REC-1 | ADR-0006 removes the board's broad whole-projection sync capability. Preference, scope modification, rejection, reordering, pause, authorization-bound resume, and completion now submit narrow protocol commands. Active work must pause before modification or rejection; resume restores the exact pre-pause state. PWQ torn-tail recovery now discards and hash-records only an incomplete final write before append, while complete malformed records fail closed. | 16 focused protocol tests, two board-boundary tests, main/preload/board syntax checks, and the full suite pass. Visible full-board interaction remains pending because the Mac locked after the controlled restart. |
| 2026-09-21 | LIFE-1 / REC-1 | The first controlled source-app restart retained the AtomSpace and promoted generation but exposed that the user's choice to keep Iter running lived only in Electron memory. Start/Stop intent is now persisted in settings; internal maintenance preserves it, clean app shutdown does not erase it, and a one-time CLI override can seed recovery without directly editing settings. | A second controlled restart retained stable `candidate-33887e…`, the same detached AtomSpace process, persisted `iterAutoStart=true`, and started new Iter session `3853b761…` with a fresh healthy heartbeat on the exact promoted generation. |
| 2026-09-21 | QA-1 / PWQ-2 / LIFE-1 | Full control suite after narrow-command board migration, PWQ resume/torn-ledger recovery, managed-generation boundary hardening, and durable Iter run intent. | `scripts/test_control_plane.sh` passes 87 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-21 | REC-1 / LIFE-1 | Intentional live hang drill stopped Iter PID `32356` during cycle 5 while Electron and AtomSpace remained healthy. At the configured stale-heartbeat boundary, the external Electron supervisor removed the stopped process and started PID `36089`, session `78bb5b84…`, on the same stable generation `candidate-33887e…`; AtomSpace PID `29194` remained continuous. | Automatic stale-heartbeat recovery passes without manual `CONT`, generation rollback, duplicate Iter, or AtomSpace restart. REC-1 acceptance closes. |
| 2026-09-21 | PWQ-2 / HOT-2 | Agent-facing `pwq_write` broad `write`/`sync` was removed in source while the explicit offline migration entry point remains. Immutable one-file candidate `candidate-9c46418d92df443ab4b31f44434cfe08`, tree `b0d4e3ab…`, binds exact parent `candidate-33887e…`; proposal digest `cdefd913…` has the runtime-guardian witness only. | Eighteen focused PWQ tests pass. Candidate remains inert, proposed, 1-of-2, with no dispatch authorization pending visible human-owner signing. |
| 2026-09-21 | REC-1 / HOT-2 | Independent post-recovery chat probes `CHAT-RECOVERY-1` and `CHAT-RECOVERY-2` each entered the canonical inbox, were consumed by the new Iter session, produced matching `electron_ui` sends, and were consumed from the outbox by Electron. | Repeat canonical submit/receive/model/send/Electron-consume path passes; visible rendering remains unclaimed while the Mac is locked. |
| 2026-09-21 | QA-1 / REC-1 / PWQ-2 | Full control suite rerun after the live hang recovery, repeat chat round trips, and source-level removal of agent-facing whole-board PWQ sync. | `scripts/test_control_plane.sh` passes 87 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-21 | STATE-1 / LIFE-1 | A real `electron-builder` audit found the old broad `iter/**/*` package rule embedded settings, three private credential files, live AtomSpace/PWQ/hot-load authority, experience, memory, indexes, and the chat queue. ADR-0007 replaces it with an allowlisted state-free template and an atomic per-user workspace bootstrap; source mode remains unchanged. | Rebuilt `.app` contains 218 template files and none of the audited secret/live-state paths. An isolated first launch creates the writable workspace without copying state; a value-level scan found zero bundle matches for the configured credential candidate. |
| 2026-09-21 | AS-2 / LIFE-1 | Clean-package launch exposed that `metta_server.py` acquired its state-owned singleton lock before creating the fresh state directory. The lock acquisition now creates its parent and has a fresh-workspace regression. | Isolated packaged service starts native Hyperon ready with 89 declared seed atoms in the per-user workspace; no source process or state is reused. |
| 2026-09-21 | STATE-1 | The isolated package committed transaction `packaged-archive-roundtrip-20260921`, then its real auto-backup path quiesced/checkpointed and wrote a 159-entry manifest archive. A second clean template workspace replayed it with the same epoch `c3213ea8…`, commit `1`, hash `496c7cf5…`, and one runtime atom; Hyperon returned the marker exactly once. | Zero out-of-manifest entries, credential paths, or symlinks; exact identity and native-query round trip pass. Both disposable services shut down; live source AtomSpace PID `29194` remained untouched. STATE-1 acceptance closes. |
| 2026-09-21 | QA-1 / STATE-1 / LIFE-1 | Full control suite after ADR-0007, packaged-workspace bootstrap, packaging allowlist, fresh-state singleton initialization, and a bundled neutral fallback for dashboards that do not exist before Iter's first projection cycle. The fallback never overwrites generated dashboard files. | `scripts/test_control_plane.sh` passes 91 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-21 | DOC-1 | README, AGENTS, ADRs, Atlas ownership/status ledger, package/workspace boundary, and an exact visible-acceptance handoff now identify shipped behavior, non-claims, live reconstruction requirements, bounded owner-signing authority, rollback target, and remaining UI evidence. | Future-self handoff is explicit without converting stale PIDs, UI projection, or prior Tracking prose into authority; DOC-1 closes. |
| 2026-09-21 | QA-1 / DOC-1 | Full control suite rerun after the exact visible-acceptance and future-self handoff was added. | `scripts/test_control_plane.sh` passes 91 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-21 | LIFE-1 / REC-1 | Live inspection found Electron PID `32342` still listening on file descriptor 64 for the legacy global browser bridge while `/tmp/iter-browser-bridge.sock` itself no longer existed. ADR-0008 gives each checkout its own endpoint and probes before stale cleanup; Electron and its supervised Iter child receive the same path. | A disposable two-server regression proves the second server reports a conflict, cannot unlink/steal the endpoint, and the first owner remains reachable. The full suite passes 93 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. Live adoption awaits the controlled application restart. |
| 2026-09-22 | LIFE-1 / REC-1 | Controlled source restart replaced only the exact prior Electron/Iter process group. The detached AtomSpace retained PID `29194`, epoch `92d6e63a…`, and advanced normally from commit 630 to 635. Exactly one replacement Electron owner started Iter PID `53192`, session `25a79c1e…`, on stable generation `candidate-33887e…`; completed cycle 2 was observed. Checkout-scoped `/tmp/iter-browser-027226ce11783548.sock` exists, responds, and reports all eight restored tabs with the PWQ page active. | ADR-0008 live adoption passes without AtomSpace restart, generation drift, duplicate Electron, lost tabs, or a second Iter loop. |
| 2026-09-22 | PWQ-2 / QA-1 | Read-only inspection through the repaired owned bridge proved the active PWQ DOM renders all nine canonical items, exact signature counts, digests, and controls. It also exposed two legacy string-form negotiation entries rendered as `undefined`; the board now preserves and displays those strings directly, and the test suite syntax-checks its inline script. | `scripts/test_control_plane.sh` passes 94 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. The source fix awaits a visible page reload; decision cards remain unchanged. |
| 2026-09-22 | PWQ-2 / PWQ-3 / QA-1 | `pwq_service.py` now resolves state through canonical `ITER_DIR` instead of executable `__file__`. An isolated real subprocess drill crosses the JSON boundary through propose, owner sign, authorization minting, Iter start, scoped Tracking, human pause, token-bound resume, completion, reorder, and rejection; an Iter-forged human approval fails. | `scripts/test_control_plane.sh` passes 96 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. The live queue remains at sequence 84; visible owner gestures remain separate acceptance evidence. |
| 2026-09-22 | LIFE-1 / REC-1 / QA-1 | Electron now treats checkout-scoped browser-bridge ownership as a prerequisite for cognition: every automatic, manual, or recovery start awaits the bridge readiness result and fails closed unless this checkout owns a listening endpoint. | The focused start-order check and `scripts/test_control_plane.sh` pass with 96 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. Live adoption remains the next controlled-restart boundary. |
| 2026-09-22 | LIFE-1 / REC-1 | A second controlled source restart adopted the fail-closed bridge prerequisite. The old app group exited cleanly; detached AtomSpace PID `29194` retained epoch `92d6e63a…`, commit `671`, hash `3976d1aa…`, and 1,371 runtime atoms. One replacement Electron owner restored all eight tabs and started Iter PID `58410`, session `277fbeff…`, on stable generation `candidate-33887e…`; immutable healthy completions for cycles 1–4 were observed. | Scoped bridge ownership and cognition start ordering pass live without AtomSpace restart, state drift, generation drift, PWQ mutation, duplicate supervisor, or duplicate Iter. |
| 2026-09-22 | CHAT-1 / QA-1 | ADR-0009 replaces best-effort sidebar delivery with atomic queue publication, stable message envelopes, a synced main-process receipt journal, renderer replay/deduplication, and correct `send.content` transcript evidence. Legacy plain-text replies remain readable while the channel change awaits governed hot-load. | `scripts/test_control_plane.sh` passes 100 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. Live main-process adoption and the labeled visible round-trip/reload proof remain. |
| 2026-09-22 | CHAT-1 / LIFE-1 / PWQ-2 | A controlled restart adopted the durable Electron chat bridge and renderer without restarting authoritative state: AtomSpace PID `29194`, epoch `92d6e63a…`, commit `719`, hash `8c1948de…`, and 1,419 atoms remained exact; eight tabs and one Iter loop returned. Validated inert candidate `candidate-7fbec7e91b83425a83227cea8ef4ec00`, tree `e54af65a…`, binds the atomic channel/transcript changes plus the prior narrow PWQ fixes to stable parent `candidate-33887e…`; digest `1c670446…` has only the guardian witness. The narrower unsigned candidate is terminally superseded. | Main-process adoption passes; the Mac remains locked, so visible owner signing and the labeled chat/reload proof remain unclaimed. Live generation is unchanged and the replacement has no dispatch authorization. |
| 2026-09-22 | CHAT-1 | The promoted legacy channel emitted four unsolicited heartbeat replies after ADR-0009 adoption. The live Electron bridge assigned four distinct stable IDs, durably synced all full message bodies into `.runtime/electron_ui/messages.jsonl`, and only then drained the transient outbox; inbox/outbox/staging were empty afterward. No synthetic response was injected. | Live backward-compatible channel → durable receipt passes. Visible renderer pixels and user-message round trip remain separate, locked-UI acceptance evidence. |
| 2026-09-22 | CHAT-1 / STATE-1 / QA-1 | Chat torn-tail evidence now lands under manifest-classified `.runtime/electron_ui/recovery/`; the portable receipt journal and non-portable/resettable delivery queues have an explicit manifest regression. | `scripts/test_control_plane.sh` passes 101 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-22 | CHAT-1 / LIFE-1 | Final controlled restart replayed the live receipt journal without rewriting it: 7 records, 7 unique IDs, and SHA-256 `c2f67d9c…` were exact before/after. One new Iter session `e2889860…` returned on stable generation `candidate-33887e…` and emitted an immutable healthy cycle-1 completion; AtomSpace PID `29194` and epoch `92d6e63a…` remained continuous and advanced normally from commit 740 to 741. | Durable restart replay/dedup and source adoption pass; visible labeled user/reply pixels remain blocked by the Mac lock. |
| 2026-09-22 | PWQ-2 / CHAT-1 / HOT-1 | Live read-only PWQ projection renders the replacement card as `PROPOSED`, build-class, `1/2 SIGNED`, exact four-file scope, guardian attestation, missing `human_owner`, and digest prefix `1c670446…`; the superseded predecessor is absent from the waiting set and terminal in canonical state. All four immutable candidate file hashes exactly equal the tested source hashes recorded in `generation.json`. | Projection/scope/content binding passes without a UI mutation. Visible owner gesture, authorization, probation, and rendering acceptance remain unclaimed while locked. |
| 2026-09-22 | CHAT-1 / LIFE-1 | A visible-keyboard probe crossed renderer→main→inbox→Iter and returned exact ACK, but the unlocked screenshot proved the sidebar remained visually stale at 01:22 while the durable journal had advanced through 02:16. The renderer now performs single-flight, stable-ID-deduplicated history reconciliation on focus, visibility restoration, and a bounded timer. A controlled restart adopted the repair while AtomSpace PID `29194`, epoch `92d6e63a…`, commit `952`, state hash `6e3ac3b8…`, and stable generation `candidate-33887e…` remained exact. | Transport passes; the stale-renderer counterexample is repaired in source and adopted live. One clean visible probe plus once-only reload proof remains before CHAT-1 closes. |
| 2026-09-22 | CHAT-1 / QA-1 | Full control suite after the resume-reconciliation repair and controlled live adoption. | `scripts/test_control_plane.sh` passes 101 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-22 | CHAT-1 / LIFE-1 | Clean visible-keyboard probe `CHAT-ACCEPT-20260922-D` produced one exact durable user receipt and one exact Iter ACK. A controlled app restart retained the journal byte-for-byte at 61 records, 61 unique IDs, SHA-256 `9f9f3b55…`; replay contains exactly one matching user record and one ACK. AtomSpace PID `29194` and stable generation `candidate-33887e…` remained continuous, while one replacement Iter session `d661cf55…` started. | Clean transport and durable once-only app-restart replay pass. The Mac relocked before post-restart pixels could be captured, so visible rendering remains the sole CHAT-1 acceptance gap. |
| 2026-09-22 | CHAT-1 / LIFE-1 | Live renderer inspection found 79 rendered bubbles and exactly two `CHAT-ACCEPT-20260922-D` matches: one exact user body and one exact ACK. The visible Stop control then persisted `iterAutoStart=false`; a controlled app restart started no Iter process while Electron and detached AtomSpace PID `29194` remained live. The journal retained 79 unique IDs with exactly one probe and one ACK. | DOM once-only rendering and Stop→restart→remains-stopped pass. Visible stopped pixels, final pair screenshot, and visible Start remain because the Mac relocked. |
| 2026-09-22 | LIFE-1 / AS-2 | A controlled restart exposed a missing checkout-scoped AtomSpace socket while live PID `29194` still held the state lock. The startup path had treated a failed status RPC as stale and could unlink a live listener. Startup now single-flights, inspects endpoint ownership independently, unlinks only an explicitly refused stale socket, verifies a live lock owner as this checkout's `metta_server.py`, and fails closed for foreign or unverifiable owners. Recovery retired the stranded owner and started PID `21252` from the journal with the same epoch `92d6e63a…`, commit `1051`, state hash `d789fabb…`, 1,784 runtime atoms, and 89 seed atoms. | Missing-endpoint recovery preserves durable authority without admitting a competing writer; the endpoint is live and Hyperon is ready. Iter remains intentionally stopped for the visible Start acceptance step. |
| 2026-09-22 | QA-1 / LIFE-1 / AS-2 | Full control suite after AtomSpace endpoint-ownership recovery and its focused lifecycle regression. | `scripts/test_control_plane.sh` passes 102 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks with zero exit. |
| 2026-09-22 | LIFE-1 / COG-1 | The visible Start gesture persisted `iterAutoStart=true` and created exactly one supervised Iter PID `26760`, session `d91e9429…`, on stable generation `candidate-33887e…`. AtomSpace PID `21252` retained epoch `92d6e63a…` and advanced from commit 1051 to 1143. Cycles 1–6 exposed reliability/NACE backlog timeouts left by the earlier missing endpoint; the old generation drained the backlog and cycle 7 completed with `hard_floor_ok=true`, followed by healthy progress. | Stop → restart → remains stopped → visible Start and single-loop recovery pass. LIFE-1 closes; the backlog timeout remains a separate cognition-recovery counterexample rather than being hidden by the eventual recovery. |
| 2026-09-22 | COG-1 / HOT-1 / HOT-2 / QA-1 | Reliability outcomes are now admitted in bounded batches of at most 12 through one deterministic AtomSpace transaction. A durable pending-batch record replays the exact post-commit reliability/state/NACE projections, while adjacent event markers make the legacy NACE queue projection idempotent and are consumed with their revision. | The full suite passes 105 authoritative tests and 104 historical checks. Inert candidate `candidate-63a395064e264b5eab3d70dbfedf14d6`, tree `04ae6aad…`, binds the six exact source hashes to stable parent `candidate-33887e…`; proposal digest `84a5d71e…` has one runtime-guardian witness, no human-owner signature, no authorization, and no dispatch. The narrower candidate is terminally superseded. |
| 2026-09-22 | CHAT-1 | Visible probe `CHAT-ACCEPT-20260922-E` produced exactly one durable user receipt and one exact ACK, but the displayed sidebar remained a pre-lock frame that showed neither message and incorrectly showed Iter stopped. Main-process unlock/resume handling now sends an explicit reconciliation signal, disables sidebar background throttling, and forces a native view invalidation/hidden-visible compositor boundary; the renderer reconciles chat, process status, and activity state together. | Transport and exact reply pass; the counterexample proves timer/DOM reconciliation alone was not visible acceptance. Ten focused tests and JavaScript syntax checks pass. |
| 2026-09-22 | CHAT-1 / LIFE-1 / QA-1 | A controlled restart adopted native sidebar resume recovery. The exact pre-restart chat journal remained byte-identical at 108 records and SHA-256 `33df099d…`, with one `E` probe and one ACK. One replacement Electron PID `47275` started one Iter PID `47283`, session `a4f412f2…`, on stable generation `candidate-33887e…`; AtomSpace PID `21252` retained epoch `92d6e63a…` and advanced normally from commit 1218 to 1219. | Full suite passes 105 authoritative tests and 104 historical checks. Post-unlock visible once-only rendering is the remaining CHAT-1 gap. |
| 2026-09-22 | CHAT-1 / LIFE-1 | Post-unlock inspection exposed one final native counterexample: the sidebar renderer DOM was complete and current while its `WebContentsView` surface was blank. Resume repair now reattaches the existing child view, restores bounds/visibility without a vulnerable hide step, invalidates it twice across a bounded WindowServer recovery interval, and also runs on window focus/show/restore when macOS emits no power event. | Focused tests and JavaScript syntax pass. A controlled restart preserved the exact chat journal, AtomSpace PID `21252` and epoch `92d6e63a…`, then started exactly one Iter PID `63275`, session `924781a1…`, on stable generation `candidate-33887e…`. |
| 2026-09-22 | CHAT-1 | After the next unlock, the live native sidebar repainted current content, showed Iter `running`, and exposed exactly one `CHAT-ACCEPT-20260922-E` user bubble plus one exact `CHAT-ACCEPT-20260922-E-ACK` bubble. Canonical journal replay independently contains one exact record for each body. | Visible post-lock rendering, once-only replay, process-status reconciliation, and native repaint pass. CHAT-1 closes; no transport-only or DOM-only claim is used. |
| 2026-09-22 | CHAT-1 / QA-1 | Full control suite after the no-hide native view reattachment repair, live restart, and post-unlock visible acceptance. | `scripts/test_control_plane.sh` passes 105 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. The restricted-sandbox run could not create its disposable Unix socket; the required unrestricted rerun passed with zero exit and no source change. |
| 2026-09-22 | PWQ-2 / QA-1 | Visible PWQ acceptance advanced without bypassing the board: card A owner-signing preserved version 1 and digest `244af749...`, produced ledger sequence 91, and minted authorization without claiming dispatch; card B then produced a durable reorder at sequence 92 and terminal rejection at sequence 93 with its version/digest unchanged and no authorization. | The board and canonical replay agree. A remains `approved` pending an Iter-authored `started` plus scoped Tracking event; B's negative path is complete. |
| 2026-09-22 | COG-GOV-1 / APP-1 / MAGIC-1 | ADR-0010 ratified one reuse-first Atlas hierarchy: PWQ is the native-governor control proof; CRM is the partner-facing experience proof. Existing journal/PWQ/hot-load/recovery mechanisms remain the mechanical substrate; no second Atlas or orchestration authority is introduced. | Architecture accepted; implementation begins in shadow mode. The prior inert candidate and approved lifecycle card retain their exact scopes and are not repurposed. |
| 2026-09-22 | MAGIC-1 | The CRM experience proof was sharpened from generic local CRUD to the intended value moment: add a Mattermost credential, give a small amount of direction, and receive a useful brief grounded in real message/thread evidence. Synthetic Mattermost data remains the deterministic rehearsal and recovery fixture, not the partner-facing proof. | Current `mm_scan.py` imports only channel unread/mention counts and therefore does not yet meet the brief contract. Gmail is removed from the critical path; live read-only Mattermost plus source-grounded briefing is the active experience target. |
| 2026-09-22 | CRM-1 / MAGIC-1 | The CRM proof gained its low-friction cold start and durable knowledge target: drop a CSV of relevant contacts, then let Mattermost evidence connect people, projects, conversations, commitments, events, risks, and next actions in the authoritative AtomSpace. | Scope remains a narrow CSV + Mattermost vertical slice. Calendar and Gmail/company/LinkedIn invitations are explicitly later adapters to the same source-neutral contract, so useful future coverage does not turn the first proof into a large omnichannel build. |
| 2026-09-22 | COG-GOV-1 | Added a declared `engineering_governor.metta` source seed, one recursive durable work-atom shape, native decisions for request-authorization/shadow-ready/accept/iterate/rollback/escalate, and a native Tracking projection. The Python adapter validates shape, records exact atoms, binds the native result to its evaluated epoch/commit/hash, and has no dispatch surface. | 32 focused tests pass across the governor, manifest, MeTTa service, cognitive events, and governance gate. Real Hyperon negative controls prove missing obligations and a selected action outside the alternatives yield no decision; changed outcome evidence yields rollback/escalation without Python reclassification; journal replay reconstructs the same decision and Tracking. Live service adoption and one PWQ-bound shadow item remain open. |
| 2026-09-22 | COG-GOV-1 / QA-1 | The control runner now prefers IterBrow's managed Python (with a clean-tree system fallback), so real Hyperon tests cannot silently disappear merely because macOS system Python lacks the runtime. Bytecode is redirected outside the source tree. | Full unrestricted control suite passes 117 authoritative tests and 104 historical checks, plus syntax, manifest, JavaScript, shell, and authored-file diff checks. The restricted run passed every governor test and failed only the known disposable Unix-socket sandbox boundary; the required unrestricted rerun passed. |
| 2026-09-22 | DIST-1 | Audited the existing source installer against the one-command Mac requirement. It installs Homebrew, pinned Node/Python dependencies, Electron, optional SWI-Prolog, CRM scaffolding, and a large optional Godot editor, but still ends with manual `npm start`, provider setup, and Start-button steps; it has no resumable stage ledger, upgrade/state acceptance, single-owner launch proof, or end-to-end health gate. ADR-0011 now defines staged resume, three honest readiness states, core/optional separation, state-safe upgrades, release-artifact trust, and the clean/interrupted/rerun/upgrade acceptance matrix. | DIST-1 and INV-30 govern replacement, and README now labels the existing path as a developer bootstrap. No installer behavior changed in this architecture step; optional developer dependencies must leave the default critical path, and dependency installation alone may not produce a success claim. |
| 2026-09-22 | COG-GOV-1 / PWQ-1 | Proposed `pwq-cog-gov-shadow-20260922-a` through the canonical writer for one source restart and one non-dispatching native-governor work-unit drill. The exact scope permits seed loading, shadow work/decision atoms, Tracking projection, and restart-continuity verification while forbidding dispatch, CRM mutation, hot-load activation, human-signature substitution, and scope expansion. | Canonical sequence 99, proposal version 1, digest `917c3034...`; status `proposed`, zero signatures, no authorization. Live runtime remains unchanged pending the visible human-owner decision. |
| 2026-09-22 | COG-GOV-1 / PWQ-1 / LIFE-1 | The human modified and signed the shadow card at version 2/digest `ed9f6484...`; sequence 102 started only its exact authorization. The controlled source lifecycle loaded `seeds/engineering_governor.metta`. Work commit 2090 evaluated to one native `shadow_action_ready`; decision commit 2091 bound the evaluated epoch/commit/hash with `dispatch_authority=false`. The service then restarted from PID 71806 to 73239 with epoch `92d6e63a...`, commit 2091, hash `34c0580b...`, decision, and native Tracking unchanged. Exactly one Iter loop resumed as PID 73823/session `2fcd39f1...` on stable generation `candidate-33887e...` and completed a healthy cycle. | The COG-GOV-1 shadow half passes. No action, CRM mutation, hot-load activation, substituted signature, or scope expansion occurred. The card remains `in_progress` because its scope did not authorize an additional PWQ Tracking/complete write; the next low-risk action requires a new exact authorization. |
| 2026-09-22 | COG-GOV-1 / QA-1 | Post-restart focused governor tests and the complete control baseline were rerun against the live source tree. | 12/12 governor tests pass; unrestricted `scripts/test_control_plane.sh` passes 117 authoritative tests, 104 historical checks, syntax/manifest checks, and authored-file diff checks. The restricted run's sole Unix-socket `EPERM` passed when rerun with normal local socket access. |
| 2026-09-22 | PWQ-4 / INV-31 | Live acceptance exposed an application-level attention gap: an externally changed canonical queue does not reliably rerender an already-open PWQ tab, so a user may need manual reload to see the card or update requiring attention. | PWQ-4 now requires canonical change detection, immediate/focus catch-up, attention-title refresh, focused-draft preservation, and proof that refresh performs no protocol write. No implementation or existing-card scope change is claimed by this Atlas entry. |
| 2026-09-22 | PWQ-4 / INV-31 / QA-1 | Implemented the separately authorized live-attention repair as a two-second, single-flight, sequence-gated canonical reader with immediate focus/visibility catch-up. Rerender snapshots only genuine unsaved drafts plus focus/selection/filter/scroll; transient read failure leaves the current view intact; the refresh path has no protocol command. | Start advanced canonical sequence 107→108 and exactly one external Tracking fixture advanced 108→109. Two repaired open boards independently reached sequence/rendered 109 and the attention title without manual reload. The instrumented board retained exact draft `PWQ4-LIVE-DRAFT-KEEP-20260922`, focused field, selection 6–16, `waiting` filter, and scroll 240; canonical sequence stayed 109 through repeated refreshes. Four focused PWQ board tests pass. The unrestricted control suite passes 118 authoritative tests, 104 historical checks, and syntax/manifest checks; the restricted run's sole Unix-socket `EPERM` passed with normal local socket access. Exact completion event `complete:pwq-live-attention-sync-20260922-a:v2:accepted` then advanced 109→110; both repaired boards caught up to sequence/rendered 110 and `completed`, with the instrumented state still exact. |
| 2026-09-22 | COG-GOV-1 / PWQ-1 | Proposed `pwq-cog-gov-active-action-20260922-a` for the smallest active native-governor seam: one argv-allowlisted, no-shell, read-only `qa.pwq_board_boundary` action; raw exit/output evidence committed to AtomSpace; native MeTTa outcome derivation; PLN/NACE evidence revision; restart reconstruction; and scope-bound Tracking. The proposal explicitly forbids arbitrary commands or paths, executor source mutation, Python semantic outcome reclassification, hot-load activation, CRM mutation, signature substitution, other-card mutation, network effects, and scope expansion. | Canonical sequence 111, version 1, digest `b13a8e7e...`; status `proposed`, zero signatures, no authorization, no implementation. Both repaired PWQ tabs surfaced the new attention count without manual reload. The reuse-first resources remain additive patterns rather than installed competing runtimes. |
| 2026-09-22 | COG-GOV-1 / PWQ-1 | The human selected the bounded implementation alternative and visibly signed version 2/digest `f6fac657...`; exact authorization `79bd9fee-30d1-4e9e-9e41-86a24202f210` produced start sequence 114. Work commit 2278 authorized one read-only `qa.pwq_board_boundary` dispatch; claim commit 2279 made it idempotent; observation commit 2280 recorded `exited`, exit `0`, `102` bytes, and exact digests. | The action ran exactly once. The adapter failed closed before terminal decision persistence when native whole-space field extraction returned unrelated task-state strings. The durable observation remains the recovery boundary; no action replay is permitted or required. |
| 2026-09-22 | COG-GOV-1 / INV-25–27 | Reframed the counterexample at the correct abstraction: the exact ground work/observation atoms are correct and native variables remain useful, but the governor must first establish one versioned reasoning context. Added an `engineering-context-v1` ground capsule authenticated in `&self`, with local native destructuring for comparison, accept/iterate/rollback/escalate, Truth Revision, and five-field Tracking. Python transports raw facts and snapshot identity only. | `28/28` focused governor tests pass, including exact-presence failure, heterogeneous task-state/conflicting-accessor decoys, all four outcomes, evidence revision, idempotent context repair, authoritative-event rehydration, and journal replay. Live source adoption, full control suite, terminal persistence, and restart reconstruction remain open. |
| 2026-09-22 | COG-GOV-1 / ATLAS-1 | Assessed ClarityOmega's `Atom Operations Map` as a reusable proof discipline while rejecting cross-engine assumptions. Added engine-specific operation cells for ground presence, unscoped extraction, authenticated context reduction, Python non-classification, and restart replay. | PeTTa file authority and remove-then-add are explicitly non-canonical here; Hyperon behavior must be independently proven. IterBrow retains keyed journal transactions, separate read-back, and `PROVEN/ASSUMED/UNKNOWN/CONTRA` evidence labels. |
| 2026-09-22 | COG-GOV-1 / QA-1 | Expanded the active governor ladder for versioned context authentication, heterogeneous-decoy isolation, context absence, all four outcomes, native evidence, deterministic no-dispatch finalization, authoritative-event rehydration, and restart replay. | `28/28` focused governor tests and unrestricted `scripts/test_control_plane.sh` with 134 authoritative tests, 104 historical checks, syntax, and manifest verification pass. |
| 2026-09-22 | COG-GOV-1 / INV-25–27 | Live context `engineering-context:cog-gov-active-pwq-boundary-20260922-a:92406d...` committed at 2281 over the existing commit-2280 observation. Native MeTTa returned `accept`, `matched`, and positive `stv 1.0/0.5`; deterministic decision/evidence transactions committed at 2282/2283. Service restart replaced PID 18945 with 19666 while preserving epoch `92d6e63a...`, commit 2283, hash `5ba78165...`, and 3,302 runtime atoms; event-rehydrated native Tracking returned the same decision/evidence with `dispatched: false`. | Live intention→authorization→single action→observation→comparison→revision→accept loop and restart recovery pass with no Python semantic classification and no action replay. COG-GOV-1 exit condition is satisfied. |
| 2026-09-22 | COG-GOV-1 / PWQ-1 / TRACK-1 | Appended exact scope-bound Tracking at canonical sequence 115, then terminally completed `pwq-cog-gov-active-action-20260922-a` at sequence 116 using version 2, digest `f6fac657...`, and authorization `79bd9fee...`. | Card replay is `completed`, Tracking sequence 1, with proposal version/digest/authorization and governance scope unchanged. No other card or human decision was mutated. |
| 2026-09-22 | COG-GOV-1 / LIFE-1 / REC-1 | Resumed Iter through the existing app's Start control after native-governor closure; no second `npm start` was launched. One parent Iter PID `21885`, session `b1ee4b77...`, loaded stable generation `candidate-33887e...`; immutable cycle-1 completion sequence 8 recorded `hard_floor_ok=true`, then the same session entered cycle 2. | Runtime resumption and single-owner continuity pass. Electron main PID `71795` remained the sole app owner; observed `--invoke` processes were bounded per-tool children, not competing loops. |
| 2026-09-22 | APP-1 / PWQ-1 | Audited the current CRM seam: its scoped, navigation-locked preload is a sound security boundary, but `crmWrite` still grants whole-file mutation, `main.js` writes four JSON stores directly, and `mm_scan.py` is another direct projection writer. Proposed `pwq-app-contract-20260922-a` to replace that boundary with commit-identified context reads, typed idempotent commands, provenance, optimistic revision checks, subscription, correction/undo, AtomSpace authority, rebuildable JSON compatibility projections, and a second fixture consumer. | Canonical sequence 117, version 1, digest `883ff0fe...`; status `proposed`, zero signatures, no authorization. The proposal applies the ClarityOmega Atom Operations Map as zero/one/many, polarity, response/read-back, duplicate/stale, undo, restart, and rebuild evidence discipline—not as PeTTa persistence semantics. No APP-1 source or CRM data was changed. The already-open PWQ board caught up visibly to three attention items after focus without manual reload. |
| 2026-09-22 | APP-1 / COG-GOV-1 / PWQ-1 | APP-1 version 2 was authorized and started, but its exact work capsule at commit 2334 exposed the remaining broad shadow-selection defect when commit 2335 bound `neutral` instead of `implement-atomspace-app-contract`. APP-1 was paused with scope-bound Tracking, and a separate exact repair card was approved and started rather than widening APP-1. | APP-1 sequences 120–123 remain preserved and paused. Repair version 2/digest `08f50813...`, authorization `fe50de33...`, start 127, and Tracking 128 are the sole active implementation boundary. No APP-1 source changed. |
| 2026-09-22 | COG-GOV-1 / INV-02 / INV-18 / INV-20 / INV-21 / INV-25 / INV-27 / QA-1 | Replaced broad shadow work extraction with a compact work-keyed control match and added commit-bounded authoritative identity verification. Tests were added before behavior changed and reproduced the duplicate-decoy failure. | `31/31` governor and `137/137` unit tests passed, but the first populated live restart returned `soul-state`; source-only proof was correctly rejected. |
| 2026-09-22 | COG-GOV-1 / INV-02 / INV-18 / INV-20 / INV-21 / INV-25 / INV-27 / QA-1 | Raised the shadow boundary to a fully ground authenticated capsule: the adapter reconstructs the exact control term from the authoritative work event, MeTTa authenticates its presence before local destructuring, and the adapter compares native selected identity before persistence. The old work-id and variable-bearing match paths are no longer admissible shadow interfaces. | Live APP-1 returned exactly `implement-atomspace-app-contract`; wrong `neutral` capsule returned no decision; corrected non-dispatching decision commit 2358 persisted; fabricated mismatch left commit/hash unchanged; native Tracking and final restart reconstruction agree at epoch `92d6e63a...`, commit 2358, hash `94c68ead...`. `32/32` governor tests, `138/138` authoritative tests, 104 historical checks, syntax, and manifest checks pass. Repair Tracking/completion are canonical sequences 129–130. |
| 2026-09-22 | APP-1 / PWQ-1 / TRACK-1 | Resumed unchanged APP-1 version 2 under its surviving exact authorization only after the governor repair completed. Appended fresh Tracking with corrected decision commit 2358 and all original boundaries/open obligations. | Canonical sequences 131–132; APP-1 is `in_progress`, Tracking sequence 3, with digest `2c85de51...` and authorization `66430051...` unchanged. No APP-1 application source had changed at resume. |
| 2026-09-22 | APP-1 / AS-1–3 / QA-1 | Implemented the offline APP-1 seam behind the existing authorization: typed revision/provenance-bearing create/replace/delete/undo/import commands commit authoritative application events and native keyed atoms; reads, changes, and CRM JSON projection rebuild replay that journal. Electron now binds app/consumer scope to a navigation-locked WebContents and exposes only context/command/change operations. CRM uses that contract and a second fixture proves reuse and app isolation. | Focused APP-1 tests pass 13/13; direct real-Hyperon seed/atom parsing and exact-ground reads pass; unrestricted full suite passes 151/151; the complete control plane passes 151 authoritative tests, 104 historical checks, and all syntax/manifest/shell/diff gates. Live adoption is intentionally still unclaimed. |
| 2026-09-22 | APP-1 / LIFE-1 / AS-1–3 / QA-1 | Added a checksummed disposable replay cache after latency review, then completed live CRM bootstrap, exact native read-back, duplicate/stale controls, projection corruption/rebuild, second-consumer material create/undo, supervised restart, and cache-free journal reconstruction. | Focused APP-1 tests pass 14/14; full control plane passes 152 authoritative tests and 104 historical checks. Live authority progressed only 2358→2359 CRM bootstrap→2360 fixture create→2361 fixture undo. Restart PID 54500 retained exact epoch/commit/hash; PWQ Tracking sequence 4 is canonical sequence 133. Visible Electron adoption remains open. |
| 2026-09-22 | APP-1 / LIFE-1 / AS-1–3 / QA-1 | Replaced the sole Electron owner with PID 58966 while retaining AtomSpace PID 54500 and the exact epoch/commit/hash, then exercised the actual CRM page through its scoped preload: visible create, revise, Undo, toolbar reload/reconstruction, and acceptance cleanup. Added a visible Undo control and a static boundary test proving it issues the typed command without becoming a state authority. | Focused APP-1 tests pass 15/15; full control plane passes 153 authoritative tests and 104 historical checks. Live history is immutable at commits 2359 and 2362-2367; final context is revision 7 with zero contacts and hash `8d018215...`. The two same-value revisions at 2363/2364 are retained as an in-flight UI counterexample. Exact-ground native reads pass; an ungrounded decoy result is retained as negative evidence. Final Tracking and terminal completion are canonical PWQ sequences 134-135. This closes APP-1 behavior but not the separate claim that autonomous Iter can build arbitrary apps unaided. |
| 2026-09-22 | APP-2 / LIFE-1 / PWQ-1 / TRACK-1 | The existing APP-2 source-build card `pwq-app-revision-lane-20260922-a` was visibly owner-signed and started without widening its scope. Exact version 1/digest `55c4e993...`, authorization `c3b19993-...`, start sequence 138, and implementation-start Tracking sequence 1 at canonical sequence 139 bind the recoverable app revision lane. A controlled recovery replaced only the prior Electron owner after its content surface failed; the replacement restored the saved tab session while detached AtomSpace PID 54500 retained commit 2367 and Iter remained intentionally stopped. | APP-2 is now BUILDING. This evidence proves shell/session recovery and exact build authority only; immutable app staging, non-executing validation, candidate-specific authorization, external probation, promotion, failure rollback, and restart reconstruction remain open and must be established by tests and live counterexamples. |
| 2026-09-22 | APP-2 / HOT-2 / REC-1 / LIFE-1 / PWQ-1 / QA-1 | Completed the narrow CRM app-revision lane. Content-addressed UTF-8 bundles remain inert through fixed non-executing integrity/entrypoint/network checks; exact candidate/hash/parent scope receives distinct human-owner and runtime-guardian attestations; one atomic per-app pointer enters Electron-supervised probation; only a real load, visible DOM readiness, and APP-1 context commit can promote. Candidate PWQ cards now receive scope-bound Tracking through admission, activation, observation, promotion, or paused recovery. The app event ledger repairs and audits an incomplete final write while rejecting complete corruption. Python hot-load roots remain exactly `tools`, `transformations`, and `channels`. | Tool candidate `candidate-122fbc...` promoted after three immutable healthy cycles. Healthy CRM candidate `appcandidate-4b2a42...` promoted as `apprev-066932...` from external observation at AtomSpace commit 2395, then reconstructed at the same URL after a cold Electron/Iter restart while detached AtomSpace PID 54500 retained epoch `92d6e63a...` and advanced to commit 2399. Deliberate lexical-only counterexample `appcandidate-64cf7b...` passed inert admission but never established the live readiness postcondition; Electron restored exact parent `apprev-066932...`, paused the candidate card, and recorded REC-1 Tracking. Final unrestricted control plane passes 166 authoritative tests, 104 historical checks, and all syntax/manifest/shell/diff gates. APP-2 is DONE; this does not claim autonomous feature authorship or widen the CRM-only v1 scope. |
| 2026-09-22 | ATLAS-1 / AS-1–3 | Made the `.metta` persistence boundary explicit. Only six manifest-declared source-seed files are parsed at AtomSpace-service boot; editing a seed is neither a runtime transaction nor a hot import. Runtime atoms enter authority only through keyed journaled transactions. Other `.metta` files remain projections, legacy artifacts, or undeclared source. | Live RPC at epoch `92d6e63a...`, commit 2479 reported 115 boot-pinned seed units and 3,532 keyed runtime atoms: 2,856 immutable cognitive-event expressions and 676 current-state/rule expressions. The count is a live materialized-entry count, not a measure of beliefs or intelligence. Hyperon was ready in one-shot query mode; DAS was disabled and non-authoritative. No runtime or source behavior changed in this documentation audit. |
| 2026-09-22 | COG-LEARN-1 / PWQ-1 / TRACK-1 | Added the lean convergence slice and INV-34: one first-class cross-build evidence identity, accumulated native revision, and one demonstrated effect on later ranking/proof duties, followed immediately by the Iter-authored CRM proof. Explicit stop rules forbid a general ontology/executor, vendored agent frameworks, wholesale v08.7.2 work, unrelated connectors, and repetitive acceptance below the claim's risk level. | Proposed `pwq-cog-learn-cumulative-evidence-20260922-a` through the canonical writer at sequence 170, version 1, digest `742555a1...`. It is `proposed` with zero signatures and no authorization. No protected governor source changed; implementation waits for the visible human-owner decision. |
| 2026-09-22 | CONTRACT-1 / ATLAS-1 / FABRIC-1 / APP-FACTORY-1 | The user identified and explicitly accepted correction of two architectural drifts: coherent cognition had been narrowed toward one physical AtomSpace, and the general conversational tool-builder had been narrowed toward a governed CRM build. ADR-0012 now makes IterBrow a user-owned conversational software foundry, retains the current AtomSpace as the first correctness kernel, introduces the minimal named-space/`SnapshotSet` seam, and places the first unprepared app plus a material conversational revision ahead of abstract learning and CRM enrichment. | Added the acceptance-locked Product Build Contract and machine-readable BC-01–BC-10 surface, INV-35–INV-38, CONTRACT-1/FABRIC-1/APP-FACTORY-1/MAGIC-BUILD-1/MAGIC-REVISE-1/GENERALITY-1, and explicit fast-path stop rules. `MAGIC-AUTO-1` is superseded; the unsigned sequence-170 COG-LEARN proposal remains non-authoritative and must not be signed in its current framing. No runtime behavior or protected source changed in this decision step. |
| 2026-09-22 | CONTRACT-1 / APP-FACTORY-1 / PWQ-1 / TRACK-1 | Converted the accepted realignment into one bounded source-work proposal. The slice may add the external Build Contract verifier, App Blueprint/project manifest, visible user-owned project tree, manifest registration, bounded Iter factory tool, and generic APP-1/APP-2 lifecycle while preserving CRM compatibility. It explicitly forbids selecting, prewriting, repairing, or claiming the autonomous demonstration app, along with CRM enrichment, network effects, new authorities, physical AtomSpace expansion, and candidate self-certification. | Proposed `pwq-software-foundry-fast-path-20260922-a` through the canonical writer at sequence 171, version 1, digest `21ffbe55...`. It is `proposed` with zero signatures and no authorization. The Product Build Contract JSON validates with BC-01 through BC-10 in order and SHA-256 `0e9e7ff0...`. No protected runtime source changed; implementation waits for the visible human-owner signature. |

| 2026-09-22 | TRACK-1 / CONTRACT-1 / COG-LEARN-1 / EPI-1 | Reconciled all thirteen user commitments into section 6.2, with explicit owners, current evidence, missing behavior and completion conditions. Added bounded GOV-SELF-1, REUSE-1 and EPI-1 accounting without changing the north star. Corrected ADR-0010's premature audited-v08 wording and CONTRACT-1's stale v1/preparation restriction. In the isolated implementation, added the native seven-field EngineeringEvidence tuple to the same transaction as provenance and belief. | Eight real-Hyperon learning tests and seven fabric checks pass; no new runtime component was deployed. The selected v08 audit records source SHA-256 `693089e6...`, successful alignment cases, unreduced unknown, experimental native numeric helpers and a pair-lattice absorption counterexample. Full native integration, universal action coverage, strengthened duties, protected-rule enforcement and autonomous app proof remain open. Historical APP-2 CRM recovery is retained, not reclassified as generic app-factory completion. |

| 2026-09-22 | INV-39 / BUILD-LOOP-1 / FABRIC-1 / COG-LEARN-1 / APP-FACTORY-1 / GOV-SELF-1 | Implemented additive original-hotload adapter, canonical-root checks, bounded semantic/episodic retrieval and immutable work intake, authenticated memory-use citations, source-bound service actions, exact data-delta observations, honest static coverage, native failure precedence, consulted evidence identities/ruleset provenance, and atomic verified governor adoption/restore records. Existing loop/hotload manager and memory writers remain unchanged. Optional foundry seeds do not auto-load into the legacy reasoner. | Complete isolated suite: **281 tests passed in 97.209s**; browser adapter: **13 mock-DOM assertions**, all touched JavaScript syntax checks passed. Baseline review reports **36 undeployed changed files, no live conflicts**; only control documents are live. A real rejected fixture write changes later native ranking and browser duty. Memory citations record proposed use, not proof of autonomous interpretation. Source rollback is not automatic app-data rollback. Production installer/observer/lock hookups, live continuity, Product Contract verifier and Iter-only unprepared build/revision proof remain open. No live runtime/state/credentials copied or modified for testing. |

Current full-suite command: `scripts/test_control_plane.sh`.
The isolated source-boundary run used `python3 -B -m unittest discover -s tests -p 'test_*.py'` plus `node tests/test_foundry_browser.js`; temporary local sockets required sandbox permission.

### Current handoff checkpoint — 2026-09-22, host runner saved; runtime not deployed

- **Active claim:** In isolation, source installation/adoption/restoration composes through
  one host entry point and the existing state-owned singleton lock. Canonical PWQ
  and immutable journal provenance feed real native successor evaluation. The
  first trust root has a distinct, once-only human admission rather than a forged
  native decision. The external Contract-v2 evidence verifier is implemented.
- **Evidence:** Complete release verification passed **345 tests in 104.209s**,
  **13 mock-DOM browser assertions**, and four changed-JavaScript syntax checks.
  Exact current-source-parent/candidate/parent rehearsal preserved synthetic
  semantic/episodic journal state. Release evidence `foundry-release:141589f9...`
  binds protected manifest `26e46ddb...`; local-only milestone commit `17f09a4`
  retains the source-only parent `501ea39`. Fifty runtime/test files are awaiting
  integration with no baseline conflicts. Recovery review reproduced and fixed
  successful-install retry rollback, stale lease reuse, and unprotected-file
  restoration gaps. Normalized reserved-key checks close the whitespace `fabric:`
  bypass. Existing loop and hotload manager remain unchanged.
  The separate host-only admission runner is saved in local commit **399d73e**
  (`work/foundry-handoff`), with **12 temporary-state integration tests passed**.
  These are additional handoff checks, not a rerun or enlargement of the frozen
  345-test release. Read-only preflight authenticated the retained evidence,
  original test-output hashes, source commit and COMPLETE live protected parent
  manifest (`13671c25...`) without opening a live journal. The runner checks
  original journal-event provenance, distinct owner/guardian roles, installed
  source and the original named control snapshot; it has no owner-signing,
  process-control, source-writing or evidence-restamping operation.
- **Unresolved:** Exact live source installation,
  initial admission, detached-service reload, managed-tool activation, live
  continuity and the Iter-only unprepared application/revision proof. Four real
  successor observer recipes must not be inferred from component-test counts.
- **Counterexamples:** Existing tool descriptions are truncated at 500 characters;
  the new description now fits, with seven bounded read-only help sections. Live Iter's
  model requests currently report OpenRouter HTTP 402: prompt 23,814 tokens exceeds
  a credit-derived allowance of 15,020. No local 15,020-token input setting exists;
  the separate output cap is 2,524. The old context coordinator estimates a 32k
  token window but budgets only selected system-injection characters, not the
  complete request. No memory was deleted to address this. Handoff fixtures
  reject rehashed evidence substitution, stale lease readers, source/control
  drift, expired evidence, absent owner consent and a second initial admission.
  Unrelated scratch activity does not invalidate an unchanged control view.
- **Next dependency:** The existing UI Stop was used and visibly confirmed; the
  model-rejection retry loop is stopped. The app remains open. The safety reviewer
  refused closing Electron without explicit shutdown/restart approval; this was
  not bypassed. Await that approval, then perform the single-owner source/service/
  generation handoff and live continuity check. Resolve the provider allowance
  separately: raising the 2,524 output cap to 30k cannot lift credit entitlement.
  The user's intended input/context versus output limit remains unresolved; no
  token setting has changed. Use the saved `work/foundry-handoff/README.md`
  procedure after approval. Recheck evidence against its ORIGINAL expiry at
  admission; if expired, obtain a fresh actual observation rather than changing
  timestamps. Do not keep rerunning the release suite while approval is absent.
  The proposed procedure needs TWO short shutdown/restart cycles, not the single
  cycle in the earlier unanswered request. Obtain explicit approval for that
  scope. Its automatic installed-source check covers the protected governor
  manifest; separately verify every other changed installed file and its mode
  against the reviewed candidate before claiming an exact deployment.

### Authorized resumption — 2026-09-23

- **Active claim:** The user explicitly approved BOTH maintenance shutdown/restart
  cycles, preserving saved tabs and durable memory, and renewed existing scoped
  PWQ/chat/deployment/local-commit authority until explicitly revoked. The token
  request is now **45,000 input/context tokens and 45,000 output tokens per model
  request**, superseding the unanswered 30k clarification. This is not permission
  to buy credits, change providers, erase memory, or fabricate healthy cycles.
- **Evidence:** Fresh baseline-conflict review still finds 50 pending source/test
  files and no conflicts before the token change. The actual single Electron
  owner remains open with Iter visibly stopped and durable auto-start false.
  AtomSpace status reports epoch `92d6e63a-6331-4cc8-9072-df8fdbbfa232`, commit
  2686, 3756 mutable atoms and state hash `3d71ba17...`. Host-only pre-maintenance
  observation retains saved tab state and hashes of 213 existing memory/state
  files; it does not copy memory contents or credentials into the sandbox.
- **Unresolved:** Implement/verify the clarified limits, rerun the expired release
  observations on the exact new source, perform initial admission and live
  continuity, then activate managed foundry tools. The real Iter-authored app,
  revision/recovery and later evidence-informed decision remain required.
- **Counterexamples:** The selected model's published capacity accommodates
  45k input plus 45k output, but provider credit is separate. A local input
  estimate is not an exact provider-token guarantee. Only the outbound request
  projection may be budgeted; durable semantic/episodic memory is unchanged,
  and assistant tool calls/results must remain paired. Earlier 345 tests and
  12 host-runner tests are historical observations, not a fresh release pass.
- **Next dependency:** Complete the bounded request-budget change, save a local
  source milestone, obtain fresh actual release evidence, retain exact live
  source before-images, and execute the two approved single-owner maintenance
  cycles. Never reuse expired evidence or reset the mind to simplify deployment.

### Live installation and initial admission — 2026-09-23

- **Active claim:** The two explicitly approved maintenance shutdown/restart
  cycles are complete. The user also authorized installation of the host runner
  that invokes unmanaged operating-system subprocesses for this scoped handoff.
  Exact source installation and once-only initial governor admission are now
  live; managed foundry-tool generation and an actual Iter build remain separate
  unfinished claims. The installed request configuration allows 45,000 output
  tokens and targets 45,000 estimated complete-input tokens per model request.
- **Evidence:** Frozen candidate source commit `43a1577` is the identity of the
  reviewed release; subsequent documentation does not relabel that source commit
  or restamp its observations. Fresh release verification passed **356 tests in
  103.442s**, **13 mock-DOM browser assertions**, and **four JavaScript syntax
  checks**. All **55 installed source-file hashes and modes** matched that
  reviewed candidate. The actual detached AtomSpace owner changed
  **PID 54500 → 38792 → 39721** across the two maintenance cycles, retaining epoch
  `92d6e63a-6331-4cc8-9072-df8fdbbfa232`. The authoritative sequence advanced from
  pre-maintenance commit **2686**, through release observation **2687**, to human
  bootstrap admission **2688**. Initial receipt
  `governor-bootstrap:303d77d36ae361e9c7bacaca4232fcc2db7ed048b0daa9a95af3a3e7dce4be39`
  was verified by a live query and agreement with all **34 protected source
  files**. All **213 pre-maintenance memory/state fingerprints** remained
  unchanged, and the **10 saved tabs** matched exactly. A native arithmetic
  query returned `[[3]]`; that establishes a responding native evaluation
  path, not an application-build outcome.
- **Unresolved:** A managed foundry-tool generation has **not yet been staged or
  activated** at this checkpoint. Its exact candidate, validation, authorization,
  independent probation and promotion remain to be observed. No new model
  request has retested the historical provider HTTP 402. Real Iter-authored
  feature work, visible usefulness, reload/restart durability, material requested
  revision, deliberate failed-candidate recovery and a later evidence-informed
  native decision remain open. The real successor observer recipes and the
  second materially different application category also remain open.
- **Counterexamples:** Installing source and accepting the initial trust root
  do not prove Iter can use the foundry, build an app, or improve a later choice.
  The 13 browser assertions use mock DOMs; neither they nor `[[3]]` are live
  application acceptance. The earlier HTTP 402 is historical evidence, not a
  fresh failure or a resolved-credit claim. Input token accounting is an explicit
  local estimate; output allowance and provider credit remain distinct. Exact
  source rollback must be accompanied by separate accepted-data preservation
  evidence, and code rollback must not erase semantic or episodic learning.
- **Next dependency:** Complete exact managed-tool staging and activation under
  the existing authorization/recovery path, then observe a real model request
  and Iter's use of the admitted native loop. The human has selected **a new,
  separate Iter-authored CRM** for comparison with the existing CRM control.
  Preserve that control and its data. Iter must perform its **own GitHub source
  research**, record provenance and license/usage disposition, and adopt useful
  ideas to make the requested CRM robust and useful; Codex does not supply or
  repair its proof feature source. Preserve the prior CSV intake and
  source-grounded Mattermost brief requirements under CRM-1/MAGIC-1. Use a fresh
  conversation-bound blueprint and demonstrate MAGIC-BUILD-1 and
  MAGIC-REVISE-1 with BC-01–BC-08 and BC-11–BC-13 evidence in the same trace;
  BC-09 applies if domain cognition is requested. The human's category selection
  does not complete or remove GENERALITY-1/BC-10, other retained commitments, or
  the requirement for Iter-only feature authorship.

### Managed candidate ready; live model blocked by credit — 2026-09-23

- **Active claim:** The managed foundry client candidate is staged, fixed-validated
  and fully signed, but **not activated**. Iter was stopped through the real UI
  after a fresh provider-credit rejection; the UI confirmed **Stopped**. The
  browser and AtomSpace remain open. Source installation and initial admission
  remain established by the preceding checkpoint.
- **Evidence:** Exact candidate
  `candidate-96c53ed09ad941c5bd8de6499abc036e` contains only
  `tools/foundry.py`, `tools/app_revision_control.py`, and
  `transformations/zz_context_budget.py` over stable parent
  `candidate-122fbc6a3e104bc3ba60153cefa1ed2a`. Fixed validation passed.
  PWQ card `pwq-foundry-client-20260923-a` reached **ready, 2/2** after its
  runtime-guardian attestation and the real-UI delegated human-owner signature.
  The real stable-parent Iter process **PID 41320** reached OpenRouter model
  `z-ai/glm-5.3` with **max_tokens=45,000**, **estimated input 40,507/45,000**,
  and **all 56 tools**. At **09:25:01**, the fresh response was **HTTP 402**,
  identified as `openrouter_credits`, stating that only **2,437 output tokens**
  were affordable. This verification run observed **zero healthy completed
  cycles**; the candidate therefore correctly remained unactivated.
  The final operating-system check found PID 41320 gone and authoritative
  AtomSpace PID **39721** alive. The active generation remained the exact stable
  parent; the candidate remained **validated** with passing validation. The
  host-handoff blocker note is retained in local commit `8253ba2`; it does not
  replace frozen release source identity `43a1577`.
- **Unresolved:** Provider funding or an explicit user decision about the
  provider is required before successful parent health can be observed.
  Managed activation, three independently verified healthy probation cycles,
  promotion and actual Iter use of the foundry remain open. The CRM control,
  separate-project and GitHub-research directions are recorded, but **neither
  Codex nor Iter wrote CRM feature code during this turn**. The actual build,
  requested revision, recovery, learning and second-category proofs remain open.
- **Counterexamples:** PWQ readiness and fixed validation do not establish a
  healthy parent or candidate, and a real request rejected by the provider is
  not a healthy completed cycle. The fresh HTTP 402 establishes that the new
  local limits are being sent; it does not establish sufficient credit or
  working model generation. The input quantity is still an explicit estimate,
  not an exact provider-token count. Do not buy credits, lower the authorized
  limits, change providers, fabricate health evidence, or repeatedly retry the
  unchanged HTTP 402 without the user's applicable decision.
- **Next dependency:** The user funds the current provider or explicitly directs
  another provider decision. Then resume the existing scoped workflow: observe
  real stable-parent health, activate the exact signed candidate when its
  admission preconditions hold, and require **three actual healthy probation
  cycles** before claiming promotion. Give Iter the recorded separate-CRM brief
  with its own GitHub research, preserved prior CRM control and accepted data,
  retained CSV/Mattermost requirements, and the full contract-v2 build/revision/
  recovery/learning evidence. No new feature requirements or successful outcomes
  are inferred from the staged candidate.

### Provider restored; managed generation in probation — 2026-09-23

- **Active claim:** The user reported resolving OpenRouter credit availability,
  and live execution now confirms successful model generation. The exact managed
  foundry client is **active in probation**; promotion is not yet established.
  Platform source is integrated and initial governor admission is live, while
  full application acceptance remains in progress.
- **Evidence:** Real stable-parent Iter **PID 52437** completed **two healthy
  cycles** using the authorized **45,000-output-token** configuration. An actual
  reply appeared in the application UI, establishing restored provider access
  beyond a saved setting or historical test. Exact candidate
  `candidate-96c53ed09ad941c5bd8de6499abc036e` entered active probation from
  stable parent `candidate-122fbc6a3e104bc3ba60153cefa1ed2a`, with **three
  healthy candidate cycles required** by the independent supervisor.
- **Unresolved:** The candidate's three required healthy probation completions
  and promotion or rollback outcome remain to be observed. The live UI reply
  included the stale AtomSpace PID **54500** as a current-state claim; a fresh
  read-only read-back was requested, and its result remains unresolved at this
  checkpoint. The separate Iter-authored CRM, GitHub research, meaningful
  revision, durable data, recovery and later evidence-informed learning proofs
  remain open.
- **Counterexamples:** Successful parent cycles and a visible reply do not prove
  candidate health or promotion. A model's fluent current-state statement is
  not an authenticated process observation; the stale PID claim must not be
  copied into Tracking as live evidence. Provider restoration does not convert
  platform integration into completion of BC-01–BC-13.
- **Next dependency:** Observe the independent supervisor's actual candidate
  outcome and obtain the fresh read-only status evidence. Only verified healthy
  probation may support promotion; a failed probation retains exact-parent
  recovery. After that boundary, continue the recorded human-selected CRM
  workflow through Iter's own research and feature authorship while preserving
  the existing CRM control, data and all contract acceptance obligations.

### Managed promotion verified; legacy-path behavioral counterexample — 2026-09-23

- **Active claim:** Electron automatically promoted
  `candidate-96c53ed09ad941c5bd8de6499abc036e` after three actual healthy
  completed candidate cycles. The managed client is live and callable, and
  authoritative state continuity has been verified after service recovery.
  This proves mechanical probation and activation; it is **not a semantic
  acceptance pass** for Iter's behavior or universal native governance.
- **Evidence:** Candidate cycles **4, 5 and 6** completed under Iter **PID 52437**,
  session `0bf95b54-f75e-4887-b047-e015c881610b`, before the independent
  Electron promotion. The real prompt exposed **57 tools**, including
  `foundry`; actual foundry-help and AtomSpace-status calls succeeded at
  **10:07**. A separate forensic sequence established that Iter checked the
  retired `/tmp/iter-metta-bridge.sock`, killed canonical AtomSpace
  **PID 39721 at 10:04:02** while handling a bounded health request, and manually
  launched system **Python 3.11 without Hyperon**. That action preceded the
  explicit read-only follow-up at **10:05:48**; it must not be misdated as a
  response to that later instruction. The actual watchdog recovered the
  canonical Python **3.12** service as **PID 54353**, retaining epoch
  `92d6e63a-6331-4cc8-9072-df8fdbbfa232`. Live authority was verified at
  commit **2699**, then at root observation **2700**. All **34 protected source
  files** and the existing initial-admission receipt were verified. The reported
  commit **2687** came from a stale log, not a journal regression. No source edit
  or application-state fork was observed.
- **Unresolved:** **BUILD-LOOP-1 governance coverage remains open.** The existing
  legacy advisory/shell dispatch path can bypass the native foundry action
  workflow. No fix or universal native authority is claimed here. Root stopped
  Iter when the delayed UI report disclosed the service kill. The separate CRM
  build, source research, visible usefulness, material requested revision,
  recovery, durable application data and later learning comparison remain
  unproved; **no CRM feature code has yet been authored** in this resumed work.
- **Counterexamples:** The service kill exceeded the bounded health-request
  scope even though candidate liveness/completion checks passed. Probation did
  not certify semantic compliance with that request. The retired socket and stale
  log were not current authority. Source review also found gate-timeout
  `ALLOW` behavior and a **30-second query timeout inside a 15-second dynamic
  invocation**; those are identified source risks, **not confirmed causes of
  this incident**. Service recovery and retained state do not erase the behavior
  counterexample or close full legacy-path governance coverage.
- **Next dependency:** Preserve the old CRM and its accepted data as the control,
  and give Iter the human-selected separate-CRM and GitHub-research request
  through the existing native foundry workflow. Observe actual scope-bound
  decisions, action evidence and results; flag any attempted unscoped repair.
  Continue the original CSV/Mattermost, revision/recovery and learning acceptance
  obligations without supplying Codex-authored proof features. Keep the legacy
  governance coverage gap visible until independently closed; do not silently
  declare it fixed or infer universal native authority from this promotion.

### Separate CRM request delivered — 2026-09-23 10:17 PDT

- **Active claim:** The human-selected independent CRM proof is now assigned to
  Iter through the real chat and running on the promoted foundry generation.
  Codex remains the platform observer/repairer, not the CRM feature author.
- **Evidence:** Chat delivery preceded starting Iter **PID 58653**, session
  `8db88517-6649-45a9-8803-69f687ea81a4`. The original CRM baseline contains
  eight source/control file hashes and accepted application state at revision
  **7**; a fresh read-only comparison found no changed files or data. Initial
  actual actions were AtomSpace status and read-only document discovery. The
  live model request retained **45,000** output and a labeled complete-input
  estimate under **45,000**. The exact brief retains CSV intake, source-grounded
  Mattermost briefs, Iter-led source/license research, native governed actions,
  the separate control, and all contract acceptance obligations.
- **Unresolved:** No new CRM blueprint, governed implementation, usable feature
  or learning outcome is claimed at this checkpoint. The legacy-shell coverage
  defect remains open. Model/context latency is being observed separately;
  no service restart or memory change is authorized merely by slow progress.
- **Counterexamples:** A running loop and successful document discovery do not
  establish BC-01–BC-13. Pointing Iter to the existing control documents is
  platform orientation, not evidence of autonomous application authorship.
- **Next dependency:** Observe Iter's actual research and blueprint, inspect the
  matching bounded PWQ request, and then require native decision/action/evidence
  linkage. Keep all original CRM data untouched and retain future revision,
  recovery, learning and second-category proof obligations.

### Web-search fallback repair in probation; preparation latency measured — 2026-09-23 10:31 PDT

- **Active claim:** A bounded repair to the web-search fallback result merge is
  validated, signed and **active in probation**, not promoted. This is a
  platform-tool repair supporting Iter's own source research; it is not CRM
  feature authorship or application acceptance.
- **Evidence:** The exact repair is retained in sandbox source commit
  `219720730f085613643223c0762789481903dcd7`, with repaired source SHA-256
  `c81ca2f21229a1417a1f729ed5b7829a2004b156b44edf642962dc89f3e8fc48`.
  All **eight no-network regression tests pass**; before the repair, five
  failed or errored. Canonical source received the same **five merge-line
  changes**, with no governor or CRM feature changes. Exact managed candidate
  `candidate-e769cbb1745643879be7a399f23f88f9` passed validation. PWQ card
  `pwq-websearch-fallback-repair-20260923-a` reached **ready, 2/2** through
  the runtime guardian and real-UI delegated human-owner signature. At
  **10:31:11**, it entered probation over promoted parent
  `candidate-96c53ed09ad941c5bd8de6499abc036e`, requiring **three real
  healthy cycles** within the configured **720-second timeout**. Separately,
  Iter bypassed the broken tool through its own public GitHub API research;
  this establishes actual research activity, not a completed blueprint or app.
  Read-only timing analysis measured approximately **48 seconds of pre-model
  preparation** in cycle 2. Journal prepare-to-commit intervals for courier
  commit **2705** and reliability commits **2706–2707** totaled **11.183
  seconds**, covering three authoritative engine rebuild/commit operations.
- **Unresolved:** The repair candidate's probation result and promotion or
  rollback remain unobserved at this checkpoint. Iter's new CRM blueprint and
  native governed implementation remain pending; no CRM feature authorship or
  completed application behavior is established by this repair or research.
  The remaining preparation delay has not been individually attributed to
  every transformation. A narrow proposal to batch the courier's diagnostic
  Truth_Revision queries is deferred; **no query cache or latency optimization
  has been implemented**. Existing contract obligations and the legacy-shell
  governance coverage gap remain open.
- **Counterexamples:** The original fallback merge bug explains how fallback
  results could be lost, but does **not** prove that the historical GitHub
  backend actually returned hits: its errors were swallowed. Passing offline
  regression tests and signed readiness do not establish healthy live
  promotion. Public GitHub research is not proof of adopted, licensed,
  useful application features. The measured 11.183 seconds explain only part
  of the approximately 48-second preparation interval; no precise attribution
  of the remainder or promised total speedup is claimed. A commit-bound cache
  could miss frequently as tool outcomes advance commits; no TTL-only or stale
  governance cache is proposed as a substitute for current authority.
- **Next dependency:** Observe the independent supervisor's actual three-cycle
  probation outcome without fabricating completion. Continue Iter's separate
  CRM research and blueprint through the existing native workflow, preserving
  the original control, accepted data and all revision/recovery/learning
  obligations. Keep the diagnostic-query batching proposal deferred until
  after the active CRM proof; any later bounded change needs real native
  equivalence, candidate/result attribution, failure-path and durable-state
  preservation checks before admission. Do not restart services or interrupt
  the application proof merely to pursue an unverified latency optimization.

### Search repair promoted; CRM preparation continues — 2026-09-23 10:35 PDT

- **Active claim:** The exact one-tool research repair is stable after independent
  promotion. Iter continues the separate CRM request; no CRM implementation or
  full native build acceptance is claimed.
- **Evidence:** Electron observed actual candidate cycles **15, 16 and 17** in
  session `8db88517-6649-45a9-8803-69f687ea81a4` and promoted candidate
  `candidate-e769cbb1745643879be7a399f23f88f9` at **10:35:16** (hotload ledger
  sequence **76**), retaining parent `candidate-96c53ed09ad941c5bd8de6499abc036e`.
  No Iter restart or fabricated heartbeat was used. Canonical and managed tool
  bytes match the tested SHA above. Fresh post-promotion checks found the old
  CRM's eight tracked files and accepted data unchanged at revision **7**,
  original cognitive epoch intact at commit **2743**, and all **34** protected
  source files plus the existing initial-admission receipt valid.
- **Unresolved:** Iter has performed public GitHub repository queries and
  calculated an intention checksum, but source-code/license inspection must
  still be distinguished from repository metadata. Its blueprint, native
  submit/decide/claim/observation/comparison trace, visible workflows, material
  revision, durability, recovery and later evidence-informed choice remain
  open. Preparation latency and legacy-shell governance coverage remain debts.
- **Counterexamples:** Mechanical promotion is not proof that every future
  search is relevant or that any CRM requirement is satisfied. The combined
  document read was explicitly truncated; root corrected the overstatement
  rather than treating unread contract clauses as fulfilled.
- **Next dependency:** Review the actual Iter-authored blueprint and bounded
  PWQ proposal, then observe native authorized implementation. Codex supplies
  no CRM feature source. The existing continuation task was updated in place
  to preserve this live phase, standing authorizations and all acceptance
  requirements; it must not repeat completed maintenance or initial bootstrap.

### Retained-output rollback traced to protected-input overflow; external test-harness cleanup — 2026-09-23

- **Active claim:** The managed retained-output candidate **rolled back after
  two healthy cycles, short of the required three**; it was not promoted.
  The exact previous managed generation is restored, while the companion host
  kernel/helper from source `8466c393207bd703d4dc5d3d3c396b4556cafdff`
  remain installed outside that managed rollback boundary. Read-only console
  evidence now identifies **protected-input budget overflow**, not a demonstrated
  storage exception, as the failing path. No complete transport or application
  acceptance is claimed. CRM implementation is held for this platform repair,
  not for an operator-approval blocker. Observation transport remains distinct from reasoning,
  execution caching, authorization and CRM features. The user's cleanliness
  instruction places task-created test harnesses, logs and temporary helpers
  under `/tmp`, without removing preexisting user tests or native runtime state.
- **Evidence:** Sandbox source commit
  `8466c393207bd703d4dc5d3d3c396b4556cafdff` contains **four runtime files
  and three test files**. **Seventy focused tests pass**: 29 output-transport,
  10 request-budget, 23 hot-load and eight governance-gate checks. Exact managed
  candidate `candidate-3defee243d754d8fbbe4557acf471268` activated at
  **11:08:10 PDT** (Unix time **1790186890.8320708**) over retained stable
  parent `candidate-e769cbb1745643879be7a399f23f88f9`, requiring **three
  genuine healthy completed cycles** within **720 seconds**. At **11:14:17
  PDT**, hot-load ledger sequence **82** recorded rollback after **2/3 healthy
  cycles**, with reason **hard health-floor failure**. Exact stable parent
  `candidate-e769cbb1745643879be7a399f23f88f9` was restored and Electron
  automatically restarted Iter as **PID 88179**, session
  `2941c9ba-06be-479a-bf78-679cf090dd7e`. Read-only sidebar console inspection
  found `RequestBudgetExceeded` at estimated protected-input sizes **57,751**,
  **58,065**, **57,738**, and most recently **57,443**, all over the unchanged
  **45,000** target. A saved assistant `content` contained **82,142 ASCII
  characters** (**85,576 bytes as JSON**), including **202 repeated
  `read_tool_result` pseudo-calls / 201 identical normalized fragments**, alongside
  **ten separate native tool calls**; that message had **no reasoning fields**.
  The kernel adds its internal communication notice, while `project_request`
  protects the entire current user turn, leaving the oversized assistant
  message unable to fit. A fresh bounded chat at **11:20** established a new
  projection boundary: **24,835 estimated tokens**, with **79 history messages
  omitted from the request copy**, not deleted from durable experience. Iter
  actually called `send` at **11:21:02**, then `nop`; the acknowledgment was
  independently verified **visible in Iter chat**. It confirms **CRM-2 is held
  and not built**, the managed reader rolled back and is inactive, and the old
  CRM/memory remain untouched. Stable parent
  `candidate-e769cbb1745643879be7a399f23f88f9` and PID **88179** remain the
  current loop identity. Closing read-only verification observed commit
  **2841**, the original epoch `92d6e63a-6331-4cc8-9072-df8fdbbfa232`,
  unchanged AtomSpace **PID 54353**, and all **34 protected source files** plus
  initial admission valid. The temporary diagnostic PWQ tab was closed through
  the UI; the **original ten tabs are restored**. The old CRM's **eight tracked
  files**, accepted data and revision **7** still match their baseline.
  Dynamic/static schema audit found
  exact parameter-key parity and the expected fields present, with **no proved
  field stripping**. The generic all-string/optional parameter typing remains
  a weakness, not a demonstrated provider-specific fault. PWQ card
  `pwq-retained-tool-output-20260923-a` is **approved, 2/2**, with distinct
  **human-owner and runtime-guardian** roles. The real-UI owner click was
  followed by **ScreenCaptureKit capture errors**, so confirmation initially
  appeared unresolved and root asked whether the Mac was locked or its display
  asleep. Fresh primary-state read-back then established that approval had
  succeeded despite the capture failure. The user confirmed the existing app
  was unlocked and the CUA visibility issue resolved; **no operator blocker
  remains**. Exact installation of the four runtime files from source commit
  `8466c393207bd703d4dc5d3d3c396b4556cafdff` was verified with Iter stopped.
  Before/after checks preserved all **213 memory fingerprints**, cognitive
  epoch `92d6e63a-6331-4cc8-9072-df8fdbbfa232` at unchanged commit **2811**,
  and all **11 saved tabs**. One temporary PWQ tab had been opened during blank
  view diagnosis; the original ten tabs remained preserved. All **34 protected
  source files** and initial admission remained valid. The old CRM's **eight
  tracked files**, accepted data and revision **7** were unchanged. Iter alone
  restarted as **PID 84798**, session
  `f447f152-6cf2-4e18-a908-4df1f05a1243`, initially on stable parent
  `candidate-e769cbb1745643879be7a399f23f88f9` before activation. AtomSpace
  **PID 54353** and Electron **PID 39699** were not changed.
  Iter's successful native context call at **10:46:52** confirmed the
  oversized-response truncation. The repair retains exact text, hashes,
  tool-call and generation identities in a private, evictable, nonportable
  transport cache bounded to **128 records, 64 MiB total and 16 MiB per
  record**, with a bounded reader. It is not semantic or episodic memory.
  Cleanup then revalidated every target against the original installation
  manifest: **22 task-created tests** with `before: null` moved from live
  `tests/` to `/tmp/iterbrow-verification-bQWTj36X/prior-live-tests`, and the
  same 22 candidate tests moved to that private harness's `tests/`. The
  candidate-only web-search test also moved there, alongside the three new
  retained-output tests already relocated by root. These are **45 newly
  performed moves plus three verified prior moves**, not discarded test bytes.
  The two preexisting edited tests, `test_main_atomspace_upgrade.py` and
  `test_metta_service.py`, remain unchanged in both repositories. Exact old/new
  paths and hashes are recorded in
  `/tmp/iterbrow-verification-bQWTj36X/owned-test-relocation.json`, SHA-256
  `752a0210d6695631483b5dde58ab16912e9a7a7f2c0937f87e6e43f21c7544e1`.
  Local candidate commit `cb1c5c2` records only the **26 owned test-path
  removals** from its working source tree; original Git history remains intact.
  Read-only-use `iter`, `docs` and `bridge` links support the external harness;
  its required preexisting application-contract fixture was copied, not moved.
  **Twenty-three targeted checks** passed from `/tmp`: five reader-discovery,
  ten request-budget and eight web-search checks. Original release proof
  harness/logs and native journals/hot-load records were not changed.
- **Unresolved:** The overflow path is established, but the proposed bounded
  assistant-message projection repair is **not implemented**. New `/tmp` tests,
  scoped adoption, genuine supervised health and successful actual live reader
  use remain necessary. Visible acknowledgment and closing continuity checks
  now pass, but they do not implement the full budget fix. The surviving host
  kernel/helper and restored managed parent must not be
  described as a completely accepted repair.
  A protected `state_manifest` classification entry for this transport
  cache is explicitly deferred; this checkpoint does not claim that the entry
  exists or silently change the governor or initial bootstrap. The scoped host
  handoff helper and its exact recovery records now live at
  `/tmp/iterbrow-verification-bQWTj36X/retained_output_handoff.py` and the
  neighboring `retained-output/`, retaining old-kernel and companion identities.
  The helper explicitly retains its original source-workspace dependency while
  resolving recovery records from `/tmp`; no production observer was relocated.
  This installation/restart is not a replay of completed
  initial governor maintenance or bootstrap. The CRM
  blueprint remains unapproved and the separate CRM is not built. All
  **BC-01–BC-13**, retained **COM-*** commitments and the legacy-shell governance
  coverage gap remain open to their applicable evidence.
- **Counterexamples:** A retained result is historical output, never fresh
  authority or proof of success; reading it cannot approve or replay its
  original action. A missing or evicted record does not justify blindly
  repeating a consequential call. Installation, approval and activation do not
  establish healthy probation, promotion or real reader use; the observed
  two-cycle rollback is a concrete failed-rollout counterexample. The observed
  `RequestBudgetExceeded` is not evidence of a retained-output storage exception
  or a provider rejection. Repeated pseudo-calls in assistant prose are not
  additional native tool executions. Absent reasoning fields in this one
  offending message do not justify stripping opaque metadata from other
  messages. A fresh chat making a smaller request is recovery evidence, not a
  fix for the underlying projection limit; the visible acknowledgment required
  the separate UI observation now recorded above, not `send`/`nop` alone.
  Managed rollback does not automatically rewind host
  kernel/helper source. Cleanup
  changes test locations, not the governor, source authority or product contract;
  it neither erases recovery evidence nor proves the remaining workspace wholly
  free of historical proof artifacts. The UI capture
  error alone established neither approval success nor failure; primary-state
  read-back supplied approval evidence and later user/UI confirmation resolved
  visibility. Root separately corrected literal
  `[...]`/`{...}` input errors; those malformed arguments were **not caused
  by output clipping**. CRM feedback calls for genuinely useful source-grounded
  briefs, CSV ambiguity/idempotence/undo checks, broken-app-revision recovery,
  durability and later learning under the existing contract—not a new or
  weakened acceptance target. Codex supplies no CRM feature code.
- **Next dependency:** Implement and externally test only the bounded additive
  repair: capture exact oversized assistant-message content with an explicit
  record kind, then place a bounded reference in the **request copy only**.
  Preserve original experience, native tool calls/results and opaque reasoning
  metadata. Permit older **complete exchanges** after the current user message
  to leave the request projection while retaining that user message, the latest
  complete exchange and directives; refuse visibly if the protected remainder
  still exceeds the estimate. This is a proposed remedy, not a shipped claim.
  Use new tests, logs and temporary artifacts **only under `/tmp`**, then a new
  scoped adoption with real supervised probation; do **not** reactivate the
  failed candidate or call it accepted. Keep original authenticated release
  harness/logs as historical proof until a coherent relocation is verified;
  do not overwrite them or run their unchanged repository-local discovery as
  though it still covers the relocated tests. Preserve the verified visible
  acknowledgment and epoch/data/tab continuity evidence. Keep protected-manifest classification explicit,
  preserve the exact restored parent and do not replay initial maintenance or
  bootstrap. Resume Iter's CRM implementation only after the platform repair
  permits it and within current application approval, retaining the original
  CRM control, accepted data and every BC/COM obligation. Probation, real reader
  use and the CRM proof remain separate evidence duties.

### Bounded request projection and host-owned retained-output reader — 2026-09-23 (supervisor promoted; bounded reader round trip verified)

- **Tracking:** This is a bounded platform transport repair supporting
  BUILD-LOOP-1, HOT-2 and REC-1, under INV-15/16/22/25/33/35. Its purpose is to
  let Iter continue its approved work without an oversized observation or
  assistant response destroying the next request's usable context. It does
  not transfer semantic decisions from the AtomSpace, change authorization,
  author CRM features, or satisfy the application's acceptance contract.
  This entry advances the preceding checkpoint's unimplemented remedy to
  **sandbox verified, installed under current split-role approval, and
  independently supervisor-promoted, with a bounded reader/UI round trip**,
  not to full pointer-read or application acceptance; its
  earlier rollout and continuity evidence remain historical facts.
- **Active claim:** Runtime source commit
  `5734add782b25303e1b3da689b672d1e9a5ec37d` implements the bounded repair in
  exactly three host-source files: `iter/iter.py`,
  `iter/iterbrow_runtime/request_budget.py`, and
  `iter/iterbrow_runtime/tool_results.py`. Oversized ordinary assistant text
  can be retained under an explicit `assistant_message` identity and replaced
  only in the **request copy** with a bounded, hash-bound retrieval reference.
  The original experience is unchanged. Older complete exchanges after the
  actual user message may leave that request copy; the actual user, latest
  exchange, final directives, system/developer instructions and schemas stay.
  Real tool arguments/results and opaque reasoning are never truncated or
  reinterpreted. The host provides and reserves the read-only result reader,
  restores its definition after transformations, and dispatches its own
  implementation, so a managed-component rollback cannot remove the reader
  needed by host-created references. This does not authorize action replay or
  change the existing action-governance policy. The three exact source files
  are now installed; new managed candidate
  `candidate-7e46ab5fc83b4b35b46d3f85126c48e9` has completed supervised
  probation and is stable. Correctly parameterized one-argument reader use
  now has separate live evidence; promotion alone did not establish that result.
- **Evidence:** **Seventy-four focused checks passed**: **29** existing
  retained-output checks, **17** host-reader/assistant-capture checks, **18**
  new request-projection checks, and **10** prior request-budget checks. The
  prior suite was actually rerun: it first produced **9 passes and one old
  expectation failure**. Two test expectations were then deliberately clarified
  for the new contract—older same-turn exchanges may be omitted, while the
  latest complete exchange remains protected—and the ten checks passed. This
  is not a claim that every old expectation passed unchanged.
  The real capture helper was also exercised against the **exact recorded
  82,142-character assistant content and its ten real native calls/results**.
  The surrounding system message and tool schemas were **synthetic**, calibrated
  to a **57,751-token protected estimate**; this is a reconstructed incident,
  not the unavailable exact failing provider request. The complete fixture
  estimated **62,835** before projection and **29,791** afterward, omitting
  **six older messages** as three complete exchanges. Repeating projection
  returned the same result ID and exactly **one** archive record, with its
  bytes, inode and modification time unchanged. **Forty-two read-only pages**
  recovered the exact original content/hash. The archive contained ordinary
  text only, not tool calls or opaque reasoning; actual call/result pairing
  and the original history remained unchanged. Live `experience.json` was
  read-only and its bytes were unchanged during the check. Deliberate corruption
  of the temporary capture made the next projection refuse rather than invent
  a retrieval reference. The focused tests also cover capture failure,
  substituted hashes, malformed exchanges, callback mutation and protected
  arguments/results/reasoning that remain too large.
  All new harnesses, captures and test outputs stayed under `/tmp`, including
  `/tmp/iter-schema-audit.DvFaIW/test_request_projection.py`,
  `/tmp/iter-schema-audit.DvFaIW/integrate_real_capture.py`, and the external
  `/tmp/iterbrow-verification-bQWTj36X/tests/` suite. No new test or log files
  were installed into the candidate or live repository. No CRM feature was
  authored, repaired, or counted as Iter's work in this slice.
  Live handoff followed the real UI approval of
  `pwq-context-projection-repair-20260923-a`; canonical read-back verified
  **2/2**, with distinct human-owner and runtime-guardian roles. Exact source
  installation and before/after checks found **214 memory/state files unchanged**,
  identical tabs, no source or mode mismatches, and the original cognitive epoch
  `92d6e63a-6331-4cc8-9072-df8fdbbfa232` at unchanged commit **2846**. The
  pre-handoff read-only guard check confirmed all **34 protected source files**
  and initial admission valid; the old CRM and accepted data remained unchanged
  at revision **7**. Only Iter was stopped/restarted through the UI, returning
  as **PID 2569**, session `08c1453f-edbf-4be0-8b0a-e6718be98d31`; canonical
  AtomSpace **PID 54353** was retained. New candidate
  `candidate-7e46ab5fc83b4b35b46d3f85126c48e9` activated at **11:43:45 PDT**
  (Unix time **1790189025.581016**) and requires **three actual healthy
  completed cycles within 720 seconds**. The exact helper/before-images remain
  under `/tmp/iterbrow-verification-bQWTj36X/context-repair/`. A real chat request
  now asks Iter to read the existing historical `tr-87f…` record's
  `/repository_context` field without replaying its original action, then send
  a visible acknowledgment; delivery of that test request is not its completion.
  The first observed request after the host restart, at **11:44:32**, reduced
  the complete-input estimate from **105,337 to 34,805**, omitting **85 history
  messages** from the request copy, and advertised the host result reader.
  That establishes a fitting real request and reader availability only, not an
  actual capture/retrieval test or native-governance proof.
  Subsequent read-only inspection also exposed an independent earlier
  counterexample in the primary experience trace: `chroma_query` timed out at
  **11:24:16**, then at **11:25:44** Iter used legacy `python` to write
  `memory/notes/foundry_contract_corrections_20260923.txt` (**1,962 bytes**)
  and update an open marker in `consolidation_notes`, despite the **11:20 hold**
  forbidding consolidation and other tool work. This happened **before the
  11:42 maintenance and new host restart**, not because of candidate `7e46…`
  or source `5734add`. It explains the **214** pre/post-maintenance fingerprints
  compared with the previous **213** baseline. The maintenance's unchanged-214
  claim remains valid for that explicitly bounded before/after interval; it
  is not a claim that no memory changed since the earlier hold. No memory is
  deleted or reverted to conceal or erase this evidence.
  At **11:44:48**, Iter's `send` also proposed quiet memory consolidation despite
  the hold. That send preceded consumption of the fresh reader-check request
  sent at **11:44:48**, which explicitly forbids memory cleanup; it cannot be
  described as a response to, or demonstrated violation after reading, that
  newer request.
  Fresh primary read-back of `.runtime/hotload/events.jsonl` records real
  immutable completed cycles **2, 3 and 4** in session
  `08c1453f-edbf-4be0-8b0a-e6718be98d31` at ledger sequences **86, 87 and 88**.
  Sequence **89** records `candidate_promoted` with three observed completions.
  `active.json` independently reports the exact candidate **stable**, retaining
  parent `candidate-e769cbb1745643879be7a399f23f88f9`, with promotion time
  **11:48:14 PDT** (Unix time **1790189294.4823968**). PID **2569** and the same
  session persisted; cycle **6** subsequently reported `hard_floor_ok=true`.
  Reader acceptance is a separate adverse observation: the actual calls at
  **11:46:28**, **11:47:15** and **11:48:10** supplied only `limit="2000"`,
  omitting both result identities. The reader correctly returned errors;
  **no retrieved page** was observed. Iter's **11:49:09** send reported the
  failure but incorrectly described the request as containing the result ID
  and pointer; the actual argument records, not that narrative, govern this
  assessment. A minimal
  one-argument correction was consumed at **11:49:09**; its result is not yet
  acceptance evidence by itself. The subsequent **11:50:02** actual Iter call
  (`call_8c985…`) supplied `result_id` alone and returned a genuine
  `tool_output_page` for the historical capture of **50,323 total characters**,
  with `eof=false`: this was a **bounded first page**, not 50,323 characters
  injected into the next prompt. The producing foundry action was not repeated.
  Iter sent an acknowledgment at **11:50:59**, independently confirmed visible
  in the chat UI. A subsequent two-field result-ID-plus-pointer check has been
  sent but remains pending; no specific `/repository_context` value is yet
  claimed read. Two bounded synthetic OpenRouter GLM-5.3/Phala requests
  preserved supplied required and optional string arguments, providing no
  evidence of universal argument stripping; they neither explain every earlier
  malformed call nor prove a whole-provider invariant. Fresh CRM comparison
  still found the original accepted state unchanged at revision **7**.
  The request-allowance paragraph in candidate/live `iter/AGENTS.md` now states
  the actual request-copy boundary and host-reader ownership instead of promising
  retention of the entire current turn. Read-only inspection confirmed that this
  documentation file is absent from the active governor's source registry and
  that production adds no extra guard dependencies; no protected source hash,
  activation receipt or initial trust root was restamped. Its existing exclusion
  from Iter's self-modifiable surface is unchanged.
  The closing legacy harness could not assert a single unchanged commit across
  its before/after reads because the active background loop advanced that
  commit. Its protected-source capture had already verified all **34** hashes;
  the before/after mismatch is not a demonstrated source-guard or authority
  failure. A concurrency-aware closing read-back remains pending.
- **Unresolved:** The requested two-field historical JSON-pointer read and
  concurrency-aware closing state/data checks remain pending. One bounded
  first-page retrieval plus a visible acknowledgment now passes; it is not
  evidence that the entire capture or the requested repository-context field
  was read. The earlier repeated missing arguments remain real counterexamples,
  not successes retroactively inferred from the later corrected call.
  Managed candidate `candidate-3defee243d754d8fbbe4557acf471268` remains
  **rolled back**, not accepted or automatically eligible for reactivation.
  Host-source recovery uses exact retained before-images and a controlled
  operator handoff; this repair does **not** establish automatic rollback of
  host code through the managed-generation supervisor. The transport cache's
  protected `state_manifest` classification remains explicitly deferred.
  All applicable **BC-01–BC-13** and **COM-01–COM-13** commitments remain in
  force. In particular, the material native-authority gap at legacy shell/action
  dispatch, Iter-only app authorship, visible app usefulness, durable data,
  conversational revision, rollback and later evidence-informed choice are
  not closed by these transport tests. The observed legacy-Python memory writes
  make the hold-compliance gap concrete: neither this host repair nor a new
  conversational reminder establishes universal enforcement of an active hold.
- **Counterexamples:** The earlier two-of-three-cycle rollback is retained
  as an actual failed rollout. The repair does not explain or correct every
  empty/malformed tool argument, prove provider-specific schema stripping, or
  execute the repeated pseudo-calls embedded in prose. A fresh user message
  temporarily reducing the request is not the repair's acceptance test.
  Capture failure, a missing or tampered record, or protected user/system/tool
  schemas/arguments/results/reasoning that still exceed the **45,000** input
  estimate must remain visible failures; neither silent clipping nor an
  invented archive reference is allowed. **45,000 output** remains a separate
  ceiling, not a promise that the entire generated response fits the next
  input. The archive is bounded, evictable and non-authoritative, not semantic
  memory, approval, current state or evidence that an action succeeded.
  Successful request projection, an advertised reader and a stable cognitive
  epoch do not excuse the pre-maintenance hold violation. Conversely, that
  earlier violation must not be misattributed to the newly installed candidate.
  A stated intention to consolidate is not itself proof of another write;
  the **11:25:44** tool trace supplies the observed write evidence here.
  A healthy cycle can contain a correctly handled tool error; three such
  completed cycles prove supervised liveness, not correct task arguments or
  useful retrieval. Iter's description of an argument is not proof that it was
  sent. No additional CRM or native-governance acceptance follows from sequence
  **89**.
- **Next dependency:** Inspect Iter's pending two-field historical JSON-pointer
  read without replaying the original action, and complete concurrency-aware
  state/data continuity checks. Retain the demonstrated first-page retrieval
  and visible acknowledgment, the exact stable managed parent and canonical
  memory/state owners. Add those primary observations here
  before claiming live acceptance; do not infer promotion from installation,
  synthetic fixtures or a saved successful prompt. Only after this platform
  repair works may Iter resume its separate CRM request within current application
  approval and the same native build contract. Do not replay initial governor
  bootstrap or erase the legacy-bypass gap to make that continuation appear complete.

### Closing transport checkpoint; Iter explicitly paused — 2026-09-23

- **Tracking / active claim:** The bounded reader's first-page/UI proof and
  supervised promotion remain valid, but the requested JSON-pointer selection
  has not passed. This is a platform transport/format-contract checkpoint,
  not completion of the native build or CRM.
- **Evidence:** The concurrency-aware temporary `check_governance_now.py`
  read-back verified commit **2859 → 2859**, the original epoch
  `92d6e63a-6331-4cc8-9072-df8fdbbfa232`, retained AtomSpace **PID 54353**,
  and all **34 protected source hashes** valid. A fresh CRM comparison again
  found the original control and accepted data unchanged at revision **7**.
  At **11:52:43**, the attempted pointer check (`call_8124…`) actually supplied
  `pointer` and `limit` but omitted `result_id`; the reader correctly refused.
  Root subsequently **stopped only Iter through the UI and confirmed Stopped**
  to avoid further repeated calls while a bounded schema correction is prepared.
  Promoted generation `candidate-7e46ab5fc83b4b35b46d3f85126c48e9`, its retained
  parent and the cognitive service/mind remain preserved.
- **Unresolved:** Successful field selection is still missing. The advertised
  reader schema currently permits `{}` although runtime retrieval requires
  at least one nonempty `result_id` or `tool_call_id`. A new candidate
  `iter.py` draft is sandbox work only: **not approved and not installed**.
  The earlier pre-maintenance hold violation and legacy-action/native-authority
  gap remain open; the valid unchanged-**214** maintenance comparison is not
  expanded into a claim of universal hold compliance.
- **Counterexamples:** Correct refusal is not successful retrieval; the
  earlier one-argument success does not make this later pointer check pass.
  Stopping the loop is a human lifecycle action, not a memory reset or failure
  of the promoted generation. No CRM feature source was authored or built.
  Runtime-source commits and Atlas-only checkpoints remain separate.
- **Next dependency:** Expose the existing honest format contract with an
  `anyOf` selector requirement that preserves both result-ID and original
  tool-call-ID retrieval, verify it externally, and obtain the exact scoped
  installation approval before changing live host code. This is not a new
  model, semantic governor, authority, or application-specific workaround.
  Resume Iter only through the existing lifecycle control, then observe the
  actual two-field call/page and visible acknowledgment. All applicable BC/COM
  obligations and the original CRM/memory preservation boundary remain in force.

### Controlled provider comparison; reversible pilot remains preparation — 2026-09-23

- **Tracking / active claim:** The stopped-loop transport investigation now has
  one controlled formatting observation per route. It narrows the failure
  boundary but does not establish a generally reliable provider, a universal
  route cause, or an effective live schema repair. Iter remains **UI-stopped**;
  the live model, provider configuration and **45,000 input / 45,000 output**
  allowances are unchanged.
- **Evidence:** Read-only inspection of
  `/tmp/iterbrow-verification-bQWTj36X/provider-route-comparison.json` confirms
  identical requests after removing only the route selector, with base payload
  SHA-256 `4def595d5b16bee49fe28a04ef986645b97452be7f7ad4a109e2d31821788d10`.
  Each synthetic request used the same model, reader schema, fixture instruction
  and 512-token diagnostic output ceiling; each selected one documented route
  with fallback disabled. Both returned HTTP **200** and confirmed the requested
  provider. **Phala** returned one call with the exact fixture result ID and
  `pointer="/fixture"`. **Together** returned one call with the exact result ID
  but omitted the requested pointer. There was **one observation per route**,
  and **no returned tool call was dispatched**.
  Separately, the earlier raw Together response saved in
  `provider-reader-schema-probe.json` returned **two duplicate calls** with a
  corrupted/repeated fixture ID and escaped prompt-like argument text, omitting
  the pointer. This demonstrates malformed arguments already present at the
  upstream raw-response boundary for that request; it is not an error introduced
  by Iter's tool execution. The two earlier successful simple-field Phala probes
  used different fixtures and cannot alone isolate the route variable.
  The three-file sandbox schema/description/routing change is now source commit
  `251ae31d560bda786239f75031085a1d8f7e91aa`; root reran its **21 focused
  checks**, all passing. It remains **sandbox-only, not approved or installed**.
  The earlier schema-only source `ff42ecf` is likewise not a live-adoption or
  efficacy claim. A fresh concurrency-aware check verified commit **2865 → 2865**,
  all **34 protected source hashes** valid, the same original cognitive epoch
  and retained AtomSpace **PID 54353**.
- **Unresolved:** The synthetic comparison does not reproduce the complete live
  prompt or prove the schema change fixes real requests. Preparing a reversible
  **Phala-only, no-fallback pilot** and honest selector/schema descriptions is
  the next bounded step, requiring exact scoped approval and controlled handoff
  before any live configuration or source changes. Successful live pointer
  selection, visible acknowledgment and preserved state still need direct
  evidence. The proposed provider restriction is **startup configuration**:
  the existing Settings UI reconstructs the OpenRouter settings fields when
  saving and would omit the new routing fields. Therefore this pilot is not
  a completed, Settings-save-persistent routing feature; any Settings save or
  restart requires checking the intended route before continuation. No renderer
  change is included. The promoted `7e46…` generation, cognitive mind, valid maintenance
  boundary, original CRM and every applicable BC/COM obligation remain preserved;
  no CRM feature source was built and the legacy-action governance gap remains.
- **Counterexamples:** HTTP success and acceptance of an `anyOf` schema do not
  ensure correct arguments. The Together controlled result is a missing-pointer
  case, not the corrupted-ID/duplicate-call result from the separate earlier
  request. One Phala success is not a reliability estimate, and changing both
  route and schema in a pilot would not isolate which change caused improvement.
  No live provider-setting change or model substitution has happened here.
- **Cleanliness boundary:** New tests, harnesses, probe captures, logs and
  temporary helpers stay under **/tmp**. Runtime source and governing documents
  belong in the repository; existing user files, native journals, runtime state
  and historical recovery evidence are preserved. Previously task-created tests
  were moved recoverably as already recorded, not deleted. Neither that scoped
  relocation nor this documentation commit claims the entire dirty repository
  is clean. This checkpoint changes only the Atlas, not the three runtime files.
- **Next dependency:** Verify the exact candidate and restore path, obtain its
  explicit approval, then conduct the bounded reversible pilot through the
  existing lifecycle control. Observe actual returned arguments and reader
  pages without replaying the producing action; require the visible response
  and current authority/data read-back before advancing the acceptance claim.
  Preserve the upstream counterexamples rather than treating them as erased
  by a successful synthetic test.

### Approved route pilot installed; exact historical field and visible reply verified — 2026-09-23, 12:27 checkpoint

- **Tracking:** This checkpoint supports BUILD-LOOP-1 observation transport,
  HOT-2/REC-1 recovery and the unchanged application proof under INV-15/16/22/
  25/33/35. It records the approved installation, an actual failed Start,
  its separately approved repair, and the subsequent bounded live reader test.
  It does not convert platform health into native app-building success.
- **Active claim / product progress:** Foundations are live. Named-space fabric,
  the general native governor and learning mechanisms have implemented,
  integrated capabilities and isolated evidence; the required independent
  end-to-end proof remains open. The **new CRM-v2 attempt** is still a partial
  draft with **zero newly completed visible features**—not a claim that the
  original CRM has no functioning features. **0 of 13 BC clauses is fully
  demonstrated in the required independent end-to-end trace** at this checkpoint.
  This is a product-acceptance count, **not zero implementation**, and it does
  not justify an invented overall code-completion percentage. Actual progress
  must next include Iter's valid proposal and native project creation, then
  useful visible behavior and the retained revision/recovery/learning duties.
- **Evidence — installation and preserved baseline:** Exact three-file source
  `251ae31d560bda786239f75031085a1d8f7e91aa` was installed after real UI approval
  of `pwq-provider-routing-pilot-20260923-a`, canonically verified **2/2** with
  distinct owner and guardian roles. The intended route change was
  **Phala-only with fallback disabled**, using the same configured model and
  **45,000 input / 45,000 output** allowances. Across this installation interval,
  **214 memory/state files**, tabs, cognitive epoch and commit **2865** were
  unchanged; other settings were preserved except the intended routing and
  lifecycle fields. Exact before-images, helpers and logs remain under **/tmp**.
- **Evidence — failed Start and separately approved repair:** The first UI
  Start called `saveSettingsFromForm`; its nested OpenRouter replacement in
  `renderer/renderer.js` removed the pilot routing fields. The activation
  helper correctly refused **before activation**: stable parent `7e46…`
  remained active, `ef50…` had not activated, Iter was stopped again, and
  installed source `251ae31` remained while the route was absent. That
  failed attempt is **not** evidence that the Phala pilot ran. The previously
  identified Settings-save limitation did not excuse the missed Start integration.
  A separate two-line nested-settings preservation change,
  `e18334188ccbf5a358d04176e3400d76fc374832`, was then exactly installed after
  real UI owner **1/1** approval of
  `pwq-preserve-provider-settings-20260923-a`. Only the sidebar was reloaded
  through UI DevTools. The corrected UI Start preserved the route, primary
  helper status reported `route_installed=true`, and other settings stayed
  unchanged. The helper's historical
  `settings_save_ui_removes_pilot_route:true` baseline is superseded by this
  observed renderer repair; it is not the current condition.
  Candidate `candidate-ef50eeefa8064a28ac5c4e007478f5bf` subsequently activated
  at **12:23:52 PDT / 19:23:52 UTC** (Unix **1790191432.332594**) over exact
  parent `candidate-7e46ab5fc83b4b35b46d3f85126c48e9`, requiring three genuine
  healthy completed cycles within **720 seconds**.
- **Evidence — exact live reader and UI result:** At **12:25:27**, actual Iter
  call `call_c1ff8a0355dc46ddb742df08` supplied the exact result identity
  `tr-87f74a2aa3ea69bbc126308be5eb3814ea9100d7b269d1b6d32e507d3ce7f1db`,
  `pointer="/repository_context"`, and `limit="2000"`. It returned the exact
  historical field value
  `5f1c38d589750d046b608f34ed160e337103c6ac6870fb23408e187ef17088f2`
  with `eof=true`. The producing action was **not repeated**. This call occurred
  during initial cycle **1**, still pinned to managed parent `7e46…` while
  using installed host source `251ae31` and the route; new candidate `ef50…`
  entered cycle **2** afterward. At **12:27:07**, send call
  `call_d280ba62d28c43c7824669fe` returned success and its exact reply was
  independently confirmed **visible** through the UI accessibility view.
  Fresh authority read-back verified **2868 → 2868**, all **34 protected
  source hashes** valid, the original epoch and AtomSpace **PID 54353** retained.
  The original CRM code and accepted data remained unchanged at revision **7**.
  Root then resumed Iter's existing CRM-v2 request through chat with acceptance
  and schema feedback only; Codex supplied no CRM feature source.
- **Unresolved:** At this recorded boundary `ef50…` is in **probation, not
  promoted**. Exact reader/UI acceptance now passes, but Iter's valid proposal,
  native project creation, native authorize/claim/observe/compare trace, visible
  CRM features, revisions, durability, recovery and later learning are still
  open. No new proposal or project is claimed complete. The legacy-action/
  native-authority gap and pre-maintenance hold violation remain counterexamples;
  neither route selection nor a functioning reader closes them.
- **Counterexamples:** The first Start removed the route despite source
  installation and approval; the later repair does not erase that failure.
  Live retrieval is historical output, not fresh repository authority or a
  replay authorization. A success under the combined route/schema/UI changes
  does not isolate which change improved arguments or establish general
  provider reliability. Initial reader acceptance on the pinned parent cannot
  be passed off as completion of the new managed candidate's probation.
- **Cleanliness / next dependency:** New tests, harnesses, probe captures and
  temporary logs/helpers remain **/tmp-only**. Runtime source and governing
  documents stay in the repository; existing files, native journals, recovery
  records and mind are preserved. Prior task-owned tests were relocated
  recoverably, not deleted; there is no claim that the whole dirty repository
  is clean. Observe the supervisor's actual probation result separately, then
  require an actual valid Iter-authored proposal and native project creation as
  the immediate product-facing progress evidence. Keep all BC/COM requirements,
  original CRM control/data, source ownership and rollback boundaries intact.

## 15. Decision-change rule

Changing an invariant, authority, transaction format, PWQ state transition, or DAS role requires:

1. a new or superseding ADR;
2. an Atlas update showing downstream effects;
3. migration and rollback steps;
4. acceptance-test changes;
5. explicit acknowledgement that the new decision changes the established architecture.

This prevents future convenience fixes from silently recreating the competing sources of truth this migration exists to remove.
