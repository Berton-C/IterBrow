# ADR-0010: Lean native engineering governor and two-part magic proof

- Status: accepted
- Date: 2026-09-22
- Atlas scope: COG-GOV-1, APP-1, MAGIC-1, PWQ, CRM
- Product-proof topology amended by ADR-0012: the native governor and CRM value
  contract remain valid, but the autonomous proof now begins with the generic
  conversational app factory and a previously unprepared user request.

## Context

IterBrow has two product intentions that must remain visible above its internal
architecture:

1. A first-time user should quickly discover that IterBrow is a place where
   they can create useful tab/apps, work with Iter inside those experiences,
   and keep expanding what the environment can do.
2. A critical business audience should be able to experience that capability
   directly and reliably. The demonstration must work without an explanation
   of the underlying control plane.

The current build has strong durable-state, PWQ, quarantine, probation,
heartbeat, and rollback mechanisms. It does not yet have one native cognitive
owner for the engineering sequence from intention through observed outcome.
Important policy is still divided between AtomSpace reasoning and Python
preflight logic. Adding another workflow framework or a second Build Atlas
would recreate the competing-authority problem this build is removing.

Several mature projects already provide useful parts of the engineering
method. GitHub Spec Kit provides constitution/specification/plan/task/
implementation/convergence discipline; mini-SWE-agent demonstrates a very
small linear action/observation loop; Agentless separates localization,
candidate repair, and validation; Aider provides repository-map,
architect/editor, lint/test, and undo patterns; Plandex demonstrates pending
diff isolation and rewind. Hyperon PLN/NACE supplies the native evidence-revision
seam. A selected v08.7.2 subset is an intended alignment source, not an already
audited or functioning IterBrow integration. EPI-1 in the Build Atlas owns its
source audit, runtime compatibility, mathematical limitations and actual use.
The 2026-09-22 selected-definition audit is partial and found both missing
numeric helpers in the extracted environment and a pair-lattice absorption
counterexample; it does not justify calling the whole engine a proven quantale.

## Decision

### One control document

`docs/ITERBROW_BUILD_ATLAS.md` remains the sole build control document. This
ADR and later feature/test artifacts are subordinate evidence. There is no
second Atlas.

### Reuse patterns, not platforms

The governor adopts the proven process patterns above without installing a
second orchestration runtime, event ledger, database, or application platform.
The first implementation is deliberately one repository, one approved PWQ
work item, one active work unit, and one bounded action at a time.

The first governor does not add LangGraph, Burr, Temporal, OpenHands, a
multi-agent organization, a general planner, a new UI, or a full import of the
v08.7.2 engine. Repository mapping may begin with the existing filesystem,
search, manifest, dependency, and test surfaces; a richer syntax map remains
additive future work.

### Authority split

- PWQ establishes human intention, scope, priority, amendments, and the
  authority to begin consequential work.
- The authoritative AtomSpace owns the semantic engineering state: current
  state, unresolved gap, alternatives, predicted effects, risks, evidence,
  test/recovery obligations, decision, observed outcome, comparison, belief
  revision, and next move.
- Iter/the LLM proposes designs, candidate actions, code, explanations, and
  repairs. Its narration is never decision evidence by itself.
- Deterministic repository, compiler, test, browser, and runtime tools provide
  observations from the real system.
- A thin constitutional kernel verifies signatures, hashes, exact scope,
  replay/idempotency, the evaluated AtomSpace commit, and recovery point. It
  executes the exact authorized action but does not reinterpret the cognitive
  decision.

### Recursive work unit

Every governed build scope uses the same compact work shape, recursively:

```text
intention + invariants + current state
  -> unresolved gap
  -> alternatives
  -> predicted effects and risks
  -> test and recovery obligations
  -> bounded decision and authorization
  -> action
  -> observed outcome
  -> comparison and belief revision
  -> accept, iterate, escalate, or roll back
```

A work unit may refine into child work units. Constraints flow down from the
approved parent; verified evidence flows up. A parent cannot become complete
merely because actions ran. Its declared outcomes and acceptance conditions
must be evidenced.

Runtime Tracking for governed work is a human-readable projection of these
authoritative work atoms. Tracking cannot approve work, enlarge scope, or
replace the Build Atlas. Builder-authored Tracking remains a reconstruction
discipline until the native projection is live and verified.

### Shadow-first activation

The governor first runs in shadow mode against one bounded PWQ build item. It
must produce its reasoning state and proposed next decision without dispatch
authority. Only after the shadow path is complete, restart-recoverable, and
consistent with observed evidence may the same native decision become required
for a low-risk action. Higher-risk or scope-expanding work returns to PWQ.

### Two-part proof

PWQ and CRM have distinct roles:

1. **PWQ is the control proof.** An approved build item becomes an AtomSpace
   work graph; the native governor exposes unresolved work, alternatives,
   obligations, bounded decision, action evidence, outcome comparison, and
   the next move. This proves that Iter is not merely surrounded by an
   external Python gate.
2. **CRM is the experience proof.** It becomes the first reusable tab/app
   demonstration of Iter working with the user inside an application. The
   repeatable rehearsal is local and synthetic, while the actual value proof is
   a read-only Mattermost connection: the user supplies a credential and a
   small amount of direction, Iter performs a bounded scan, and the CRM produces
   a concise, useful brief grounded in the real messages. Natural-language
   collaboration can then correct the brief, promote a finding into a
   relationship/next step/task/event, and undo the change. A subsequent bounded
   PWQ item asks Iter to improve the CRM itself; the governor controls that
   change and the user sees the new capability appear through the existing
   hot-load path.

The synthetic dataset is the deterministic safety, recovery, and demo-rehearsal
fixture; it is not a substitute for the live value proof. The partner-facing
demonstration requires only a Mattermost server URL, a read-only-capable personal
access token, and a short user direction describing relevant people, projects,
topics, or responsibilities. Gmail, OAuth, and other accounts are not on the
critical path. Credentials remain outside prompts, AtomSpace content, portable
state, briefs, and logs.

### CRM evidence plane

The first useful vertical slice has two inputs, not an omnichannel integration
project:

1. A dropped CSV provides the initial people/organization/project vocabulary and
   removes manual CRM data entry.
2. Mattermost provides bounded live evidence about conversations, commitments,
   decisions, risks, relationships, projects, and events.

Both inputs normalize into one source-neutral AtomSpace model with stable source
identities and provenance. Contacts, projects, conversations, commitments,
meetings/events, observations, proposed next actions, and the user's corrections
are cognitive/application facts in that model. The current CRM JSON files become
compatibility projections as each domain migrates; connectors never become
parallel authorities.

Calendar and Gmail (including company and LinkedIn invitation mail) are later
evidence adapters to that same contract. Adding them must not change the CRM
reasoning or brief schema. Entity reconciliation is conservative: uncertain
matches remain explicit candidates for the user rather than silently merging
people or projects. Credentials stay in the non-portable secrets boundary and
are never converted into atoms.

### Learning from use

Each governed action records a unique evidence identity, context, strategy,
prediction, observation, test result, and outcome. PLN/NACE may revise the
reliability of strategies, tools, tests, and change classes from repeated,
source-aware evidence. No score may compensate for a missing signature,
required test, recovery path, or direct observation.

Changes to the governor itself require a separate build-class PWQ decision,
shadow comparison, negative controls, restart proof, and exact rollback. The
governor cannot amend the constitutional kernel that validates it.

## Magic acceptance surface

The first partner-ready proof is accepted only when an unfamiliar user can:

1. Open the CRM from IterBrow and immediately understand the experience.
2. Drop a CSV of contacts, see an idempotent import preview, and accept it without
   hand-entering records or editing JSON.
3. Add a Mattermost connection, provide a small direction about what matters,
   and start a visibly bounded, read-only scan without a developer terminal.
4. Receive a brief that distinguishes items needing attention, decisions and
   commitments, risks/blockers, relationship signals, and proposed next actions.
   Every material finding carries enough source identity to open or inspect the
   supporting message/thread; a channel unread count is not a finding.
5. Correct or dismiss a finding and promote an accepted finding into a
   relationship, next step, task, or event while seeing what Iter changed and
   retaining an undo path.
6. Refresh and restart IterBrow without losing or duplicating imported people,
   the brief, provenance, feedback, promoted records, or recovery point.
7. Ask for one small CRM capability improvement, review the PWQ intention, and
   observe either a tested governed activation or an exact rollback.
8. Repeat the import/scan/brief workflow from documented CSV and synthetic
   Mattermost fixtures with no network dependency, proving determinism and
   recovery separately from the live value demonstration.

The demonstration is not accepted from screenshots, prewritten final data, a
direct file edit, a channel-count import, a generic ungrounded summary, a test
helper, or an LLM claim. The visible application, source-message provenance,
durable state, AtomSpace decision/evidence, and recovery state must agree. The
user's useful/not-useful corrections are evidence for later ranking and briefing
strategy revision; they never weaken provenance, authorization, or recovery
requirements.

## Consequences

- Product magic becomes a first-class acceptance target instead of an assumed
  consequence of infrastructure work.
- The PWQ board is not burdened with being the partner-facing application; it
  remains the clearest dogfood surface for human agency and build governance.
- CRM's current direct JSON ownership is transitional. Migration must preserve
  its existing usable surface while giving each mutation one canonical writer
  and a durable provenance/undo path.
- The first result is intentionally narrow but structurally reusable by later
  tab/apps. Generalization follows the proven CRM seam rather than preceding
  it.

## Verification

- A shadow PWQ work item round-trips through native work atoms and yields a
  commit-bound decision and fresh Tracking projection without dispatch.
- A low-risk authorized item crosses the same path through action, observation,
  comparison, NACE/PLN evidence revision, and accept/iterate/escalate/rollback.
- CRM passes the eight visible magic acceptance steps above against a clean CSV
  plus synthetic Mattermost fixture and one live read-only Mattermost source.
- Existing PWQ, chat, AtomSpace, hot-load, recovery, and packaging control
  suites remain green.

## Rollback

Disable native-governor dispatch and return it to shadow-only observation.
Retain all work/evidence atoms as audit history. Existing PWQ authorization,
hot-load quarantine, external supervision, and exact rollback remain the
mechanical safety path. The CRM continues to open through its current scoped
bridge while the reusable collaboration seam is disabled.
