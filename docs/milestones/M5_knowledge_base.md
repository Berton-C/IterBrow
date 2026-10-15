# Milestone 5 — Make the memory layer a real knowledge base

Status: **implemented 2026-10-15** (all `@pending` decorators removed; 54 tests active).
Implementation notes: the planner lives at the single memory-commit choke point
(`tools/_petta_db._commit_memory_change` → `kb_terms.plan_memory_change`), so every memory
write — formalize, forget, support, contradict, link, update, merge — keeps statements and
evidence consistent in its own transaction. Premises are reported as the *stored* statements
(Hyperon prints them instantiated; `kb_inference._premise` maps them back by one-way matching).
Two test assertions written before the seed vocabulary existed assumed an empty registry and
were narrowed to non-seed terms (`bird` is a seed term, loaded `known` at service start).
Tests: `tests/test_kb_*.py` (unit + real AtomSpace service) and
`tests/e2e/test_kb_loop.py`; helpers in `tests/kb_support.py`. Every test is
decorated `@pending("M5-xx")`, which is `unittest.expectedFailure`.
Implementing an item means **removing its decorator**; the suite then fails
if the item regresses, and also fails ("unexpected success") if a
still-decorated test starts passing, so the decorators cannot silently go
stale. Until `iter/iterbrow_runtime/kb_terms.py` exists the service-backed
tests fail fast without starting a service (`kb_support.kb_root`); creating
that file switches them to the real service. Verified: with a stub
`kb_terms.py` every service-backed test starts the real AtomSpace, runs the
real tools, and fails on its own assertion (54 tests, ~1 s per service test).

## Why

Audit of 2026-10-15 (see "Finding" below): the NAL formalizations the
AtomSpace dashboard draws are strings inside each memory's JSON metadata.
They are projected to a text file (`transformations/.runtime/space.metta`)
that the Hyperon engine never loads. No code queries them, no inference runs
over them, their `stv` only moves when the model manually calls
`support`/`contradict`, and the dashboard's "links" are spelling coincidences.
The only real symbolic loop is NACE (`cap-efficacy` beliefs: revised every
turn, expectation into the prompt, gate before tool calls).

This milestone makes formalizations first-class, canonical, revised on
evidence, and *derivable* — and makes the dashboard show only what is true.

## Decisions (Berton, 2026-10-15)

- Vocabulary mode is **permissive with canonicalization** by default. Unknown
  terms are accepted, normalized, and marked `provisional`; strict mode exists
  behind one setting and the tests cover both.
- Scope is levels 1+2 of the proposal: honest dashboard + real KB. Folding KB
  beliefs into the NACE gate (level 3) is NOT in this milestone.
- Continuity-of-mind redesign stays on hold; nothing here touches episodic
  memory, recap, or handoff.
- Iter's own promoted code is not judged or rewritten by this milestone.

## Finding (what the code does today, with citations)

- Memory atom: `(semantic-memory "id" "doc" "metadata-json")`
  (`tools/_petta_db.py:_memory_atom`). The formalization is
  `metadata["formalization"]`, written by `tools/_formalize_metta.py` after a
  balanced-parens check only.
- `transformations/atom_space_update.py` writes `space.metta` from that
  metadata, keeping the most confident copy of duplicate strings. `space.metta`
  is `role: projection, format: metta_legacy` in `state_manifest.json`; the
  engine loads only `source_seed`/`metta` entries (`metta_server.py:_load_declared_seeds`).
- `transformations/dashboard_atomspace.py` counts "structure" as any
  non-operator token present in two or more statements and "links" as
  statement→shared-token edges. No link atoms exist.
- Nothing runs `match` over formalizations. `tools/chroma_query.py` prints a
  `Formalization:` line after a vector hit. `_support.py`/`_contradict.py`
  revise one memory's stv in Python; two memories with the same formalization
  are never merged.
- NACE: `seeds/nace_substrate.metta` defines `Truth_Expectation`,
  `Truth_Revision`, `should-dispatch`; `transformations/nace_courier.py` runs
  revisions in the engine; `transformations/metta_reasoning.py` applies
  `kb_substrate.metta` `==>` rules one step; `tools/_metta_gate.py` gates calls.

## Design

### A. Term registry and canonicalization — `iter/iterbrow_runtime/kb_terms.py`

Pure Python, no service needed for `canonicalize`; the registry lives in the
AtomSpace.

- `canonicalize(token) -> str`: NFKC, lowercase, every run of non
  `[a-z0-9]` → `_`, strip leading/trailing `_`, collapse `__`. Variables
  (`$…`) and the structural symbols `--> <-> ==> [] stv` and numbers pass
  through untouched. Variables are renamed positionally per statement in order
  of first appearance: `$x … $y` → `$1 … $2`. A Hyperon-decorated variable
  `$x#123` is `$x` first.
- `canonical_statement(text) -> (statement, terms)`: parse the s-expression,
  canonicalize every term, rename variables, serialize with single spaces and
  no `stv`. Raises `ValueError` on unbalanced input, more than one top-level
  expression, a `stv` inside the statement, or a string literal. `terms` is
  the ordered unique list of non-structural, non-variable, non-numeric atoms.
- Registry atoms (state atoms, keys `state:kb_term:<canonical>`):
  `(kb-term "<canonical>" "<status>" "<definition>" "<aliases-json>")`,
  status `known` | `provisional`. `resolve(term)` returns the canonical name
  after alias lookup (aliases are canonicalized too; alias of a known term →
  that term).
- `define_term(name, definition, aliases=())` (tool `tools/define_term.py`):
  creates or upgrades a term to `known`, records aliases. Defining a name that
  is an alias of another known term is an error naming that term.
- `merge_terms(keep, drop)` (tool `tools/merge_terms.py`): `drop` becomes an
  alias of `keep`; every kb statement mentioning `drop` is rewritten to
  `keep` (re-keyed; evidence carried over; statements that collide after the
  rewrite are revised together, see C). Idempotent.
- Mode: `ITER_KB_VOCABULARY` = `permissive` (default) | `strict`. Strict:
  `formalize_metta` refuses a statement with any term that is not `known`
  (or an alias of one) and lists the offending terms; nothing is written.
  Permissive: unknown terms are registered `provisional`.
- Seed vocabulary: `iter/seeds/kb_terms.json` — a small starting list
  (`bird`, `user`, `iter_agent`, tool names from `tools/`, the `[]` property
  names already used in `kb_substrate.metta` such as `threat_pattern`,
  `undermines`, `flourishing`). Loaded by backfill (F) as `known`. Keep it
  short; growth happens through `define_term`.

### B. Statement atoms in the engine

- Key `state:kb_statement:<sha256(canonical statement)[:24]>`, atom
  `(kb <canonical statement> (stv <f> <c>))`. The statement is a real
  expression (not a string) so `match` unifies against it; `$1` is a live
  variable in the space.
- Evidence atoms: key `state:kb_evidence:<statement-hash>:<memory-id>`, atom
  `(kb-evidence "<statement-hash>" "<memory-id>")`.
- `formalize_metta(LTM_item, formalization)` now: canonicalize (A) →
  vocabulary check → in ONE AtomSpace transaction: upsert the memory atom with
  `metadata["formalization"] = <canonical statement>` and
  `metadata["formalization_hash"]`, upsert `kb-term` atoms for new terms,
  upsert the `kb-evidence` atom, upsert the `kb` statement with the stv from C,
  and remove the evidence (and the statement, if that was its last evidence)
  of the memory's previous formalization when it changes.
- `forget(memory)` removes that memory's evidence; a statement with no
  remaining evidence is removed; stv of a statement that keeps evidence is
  recomputed (C). `support`/`contradict` on a formalized memory recompute its
  statement's stv in the same transaction.
- `space.metta` is regenerated from `kb` atoms (not from metadata) by
  `atom_space_update.py`; it stays a projection and is never loaded.
- Reset/backup: kb atoms live in the AtomSpace journal like memories; no new
  manifest paths beyond `seeds/kb_terms.json` (`source_seed`, `json`).

### C. Truth: revision on write — `kb_terms.statement_truth(evidence)`

A statement's stv is the NAL revision fold over its evidence memories'
`(strength, confidence)`, in memory-id order, with the pure NAL formulas
(`w = c/(1-c)`, `f = Σ w_i f_i / Σ w_i`, `c = W/(W+1)`), **no clamping** other
than `c ≤ 0.99`. Reference values the tests assert:

| evidence | statement stv |
|---|---|
| one memory (1.0, 0.5) | (1.0, 0.5) |
| two memories (1.0, 0.5) + (1.0, 0.5) | (1.0, 0.6667) |
| (1.0, 0.5) + (0.0, 0.5) — conflict | (0.5, 0.6667) |
| (1.0, 0.9) + (1.0, 0.5) | (1.0, 0.9091) |

A second memory formalized to an already-present statement therefore adds
evidence and revises; it never creates a second statement atom. The memory
stv itself is untouched by this (that remains `support`/`contradict`'s job;
their existing clamp in `_support.truth_revision` is out of scope).

### D. Bounded forward chaining — `iter/seeds/kb_inference.metta` + `iter/iterbrow_runtime/kb_inference.py`

Seed (declared `source_seed`/`metta` in the manifest):

```
(= (Truth_Deduction (stv $f1 $c1) (stv $f2 $c2))
   (stv (* $f1 $f2) (* (* $f1 $f2) (* $c1 $c2))))
;; modus ponens over stored statements
(= (kb-step-mp)
   (match &self (, (kb (==> $a $b) $t1) (kb $a $t2))
          (derived $b (Truth_Deduction $t2 $t1) (==> $a $b) $a)))
;; implication chaining
(= (kb-step-chain)
   (match &self (, (kb (==> $a $b) $t1) (kb (==> $b $c) $t2))
          (derived (==> $a $c) (Truth_Deduction $t1 $t2) (==> $a $b) (==> $b $c))))
```

Verified on hyperon 0.2.10: a stored `(kb (==> (--> $1 ([] smokes)) (--> $1 ([] cancerous))) (stv 1.0 0.9))` and `(kb (--> anna ([] smokes)) (stv 1.0 0.5))` yield `(derived (--> anna ([] cancerous)) (stv 1.0 0.45) …)`; two chained implications at (1.0 0.9)/(0.9 0.9) yield `(stv 0.9 0.729)`.

`kb_inference.derive(query_fn, depth=2, limit=64) -> [Derivation]` runs
rounds through the normal isolated query path (`tools/_metta_substrate.run_query`
/ the service's `query` with `extra_facts` holding the previous round's
derivations as `(kb <stmt> <stv>)`): round 1 is `!(kb-step-mp)` + `!(kb-step-chain)`,
each later round only adds what is new. A derivation is
`{statement, stv, premises[], depth}` with the statement canonicalized (A) —
in particular `$x#123` → `$1`. Dedupe by canonical statement, keeping the
highest-confidence derivation. A derived statement that equals a stored one
is dropped (it is not new). Derivations are **never written** to the
AtomSpace; they are computed per query and labelled `derived`. Depth is
capped at 3 and the result count at `limit`; `derive` returns within
`ITER_KB_DERIVE_BUDGET_S` (default 5s) or returns what it has with
`truncated=True`.

Design note: a stored *fact* with a variable (`(--> $1 ([] mortal))`) is a
universal claim and unifies with everything; that is correct NAL behaviour and
the tests include it.

### E. Prompt surface

- `chroma_query` result blocks gain, after `Formalization:`, a
  `Derived:` list (depth ≤ 2, at most 5 per memory) of conclusions whose
  premises include this memory's statement, each as
  `[derived] <statement> (stv f c) ⇐ <premise>, <premise>`.
- New tool `tools/kb_query.py`: `kb_query(pattern, depth=2)`: pattern is a
  statement with variables, e.g. `(--> $1 ([] cancerous))`; returns stored
  matches with stv and evidence memory ids, then derived matches labelled
  `[derived]` with premises. Description ≤ 500 chars (tool-metadata test).
- `metta_reasoning.py`, `_metta_gate.py` and NACE are **not changed** (level 3).

### F. Backfill and migration — `kb_terms.backfill(...)`

On AtomSpace service readiness (same place legacy migration runs) and on
`reconcile_index`: for every semantic memory whose metadata has a
`formalization` but no `formalization_hash`, canonicalize it (unparseable →
leave metadata as is, add `formalization_error`, skip) and create the term,
evidence and statement atoms. Load `seeds/kb_terms.json` as `known` terms.
Idempotent: a second run performs zero transactions. Writes a one-line
summary to the service log: `kb backfill: N statements, M terms (K provisional), E skipped`.

### G. Honest dashboard — `transformations/dashboard_atomspace.py`

Numbers come from the authority (`read_atoms` with prefixes `state:kb_`,
`state:nace_belief:`), never from `space.metta` text:

- `statements` = count of `state:kb_statement:*`
- `terms` = known / provisional counts from `state:kb_term:*`
- `evidence` = count of `state:kb_evidence:*`
- `derived` = `len(derive(depth=1))` (cached per authority commit)
- `nace beliefs` = count of `state:nace_belief:*`
- header line: `loaded in engine · commit <id>`; when the service is
  unreachable the card says `authority unreachable` and shows no numbers.

The graph keeps the shared-term hierarchy, but a node is a *registry term*
(known = solid, provisional = dashed), an edge from a statement to a term
exists only if that term is in the statement's canonical term list, and
derived statements are drawn as a distinct node type. The unloaded
`space.metta` text is still shown, labelled "projection (not loaded)".

### Interfaces the tests pin (exact)

- `kb_terms.canonicalize(token) -> str`; `kb_terms.canonical_statement(text) -> (statement, terms)`;
  `kb_terms.statement_truth(pairs) -> (f, c)` (raises `ValueError` on empty).
- stv rendering everywhere: `(stv <f> <c>)` with each value `repr(round(x, 6))`
  (so `1.0`, `0.5`, `0.666667`, `0.909091`).
- Tool results: `define_term` / `merge_terms` / `formalize_metta` answer
  `SUCCESS: …` or `ERROR: …` (errors name the offending term(s)).
  `define_term(name, definition, aliases=())` accepts `aliases` as a list or a
  comma-separated string. `merge_terms(keep, drop)`.
- `kb_query(pattern, depth=2)` output: one `[stored] <statement> (stv f c) evidence: <id>[, <id>]`
  line per stored match, then one `[derived] <statement> (stv f c) ⇐ <premise>, <premise>` line per
  derivation, stored before derived; a bad pattern answers `ERROR: …`; no match answers
  `No stored or derived statement matches <pattern>.`
- `chroma_query`: after the `Formalization:` line, `Derived:` then up to five
  `  [derived] <statement> (stv f c) ⇐ <premise>, <premise>` lines and, when more exist,
  `  (+N more derived; use kb_query)`. Memories without a formalization get no `Derived:` section.
- `kb_inference.derive(run_query, depth=2, limit=64, budget_s=None) -> Derivations`:
  `run_query(code: str) -> str` evaluates MeTTa in the isolated query path (the caller
  wraps `tools/_metta_substrate.run_query` or the service socket); `Derivations` is a
  `list` of dicts `{"statement", "stv": (f, c), "premises": [...], "depth"}` with a
  `.truncated: bool` attribute. Engine errors propagate (never swallowed into `[]`).
- Backfill log line (service log): `kb backfill: N statements, M terms (K provisional), E skipped`.
  Unparseable legacy formalizations keep their text and gain `formalization_error`.
- `dashboard_atomspace.authority_counts(read_atoms, derive) -> dict` with keys
  `status` (`"ok"` | `"authority unreachable"`), `loaded` (bool), `statements`, `terms_known`,
  `terms_provisional`, `evidence`, `derived`, `nace_beliefs` (ints, or all `None` when unreachable).
  The rendered page embeds `<!--counts:{json}-->` and `<!--graph:{json}-->`; graph nodes are
  `{"id", "kind": "statement"|"derived"|"term", "label", "status"?}` (terms carry
  `known`/`provisional`), links carry `"type": "mentions"` for statement→term edges.
  Text markers in the page: `loaded in engine · commit <n>`, `projection (not loaded)`,
  `authority unreachable`.

### Out of scope (explicitly)

NACE gate consumption of KB beliefs; rewriting `_support.truth_revision`;
any change to episodic memory, recap, handoff; judging Iter's own code;
foundry governance.

## Test map

| id | test | asserts |
|---|---|---|
| M5-A1 | `test_kb_canonical.CanonicalizeTests` | normalization rules, variable renaming, `$x#123`, structural passthrough |
| M5-A2 | `…CanonicalStatementTests` | parse/serialize, term list, rejections |
| M5-A3 | `test_kb_registry.RegistryTests` | provisional on first use, `define_term` → known, alias resolution, strict refuses |
| M5-A4 | `…MergeTests` | merge rewrites statements, carries evidence, idempotent |
| M5-B1 | `test_kb_statements.StatementAtomTests` | `(kb …)` atoms exist and `match` finds them; evidence atoms; metadata hash |
| M5-B2 | `…LifecycleTests` | reformalize moves evidence; forget removes; last-evidence removes statement |
| M5-B3 | `…ProjectionTests` | `space.metta` regenerated from kb atoms |
| M5-C1 | `test_kb_canonical.TruthTests` | the four reference stv values |
| M5-C2 | `test_kb_statements.RevisionTests` | same statement twice → one atom, revised stv; conflict → (0.5, 0.667) |
| M5-D1 | `test_kb_inference.DeductionTests` | modus ponens value, chain value, variable fact |
| M5-D2 | `…BoundsTests` | depth cap, dedupe, stored-equals-derived dropped, nothing written, budget |
| M5-E1 | `test_kb_prompt.ChromaQueryTests` | `Derived:` lines in chroma_query output |
| M5-E2 | `…KbQueryTests` | `kb_query` tool stored + derived, description length |
| M5-F1 | `test_kb_backfill.BackfillTests` | legacy metadata → atoms; idempotent; unparseable skipped |
| M5-G1 | `test_kb_dashboard.CountTests` | counts equal authority atoms, not spelling; unreachable shows no numbers |
| M5-H1 | `e2e/test_kb_loop.py` | real loop: remember → formalize → second memory → kb_query shows revised + derived |
