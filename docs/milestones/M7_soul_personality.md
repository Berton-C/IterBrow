# Milestone 7 — A personality that learns: taste from choices, a voice, briefs, forks as variants

Status: **scoped, tests written, implementation pending.** Roadmap: `docs/soul/SOUL_IN_THE_FOUNDRY.md`
(this milestone replaces the roadmap's M7 and pulls the felt channel forward from M8).
Base: M6 (`docs/milestones/M6_soul_base.md`) — cards, per-person settings, the kernel seed in the
`soul` view, `soul-choice` atoms. Tests: `tests/test_m7_*.py`, `tests/e2e/test_m7_loop.py`; helpers in
`tests/m7_support.py`. Every test starts `@pending("M7-xx")`; remove the decorator as each passes.
`M7_IMPLEMENTED` is keyed on `iter/transformations/soul_taste.py`.

## Why

M6 records what a person chose and counts it. Nothing reads it back. A personality is values
(the kernel, M6) **plus** a memory of how this person and this Iter have chosen together **plus** a
voice. This milestone adds the memory and the voice, then puts the two Foundry features that
generate choices (briefs, forks) on top of them, so that from the first week the Soul in the
sidebar is *someone who remembers you*, not a flavor in the prompt.

Principles carried from M6 and the roadmap: nothing gates, pauses or vetoes; Iter offers, the person
decides; everything a person turned off leaves no trace; pattern text enters Python only through
the lens; the soul view never mixes with NACE or kb atoms; counts on surfaces come from the authority.

## Vocabulary

- *Taste belief*: `(soul-taste "<person>" <Picked> <Over> (stv f c) <n>)` at key
  `state:soul_taste:<person>:<Picked>:<Over>` — how often `<person>` took the `<Picked>` pole when a
  card offered it against `<Over>`. `n` is the number of such forks; `f = picks/n`;
  `c = min(0.99, n/(n+1))` (NAL evidence horizon k=1, the same shape `kb_terms.statement_truth` and
  NACE use). Both orderings exist: a pick of A over B is positive evidence for `A B` and negative
  evidence for `B A`.
- *Dismissal count*: `(soul-dismissed "<person>" "<kind>" <n>)` at `state:soul_dismiss:<person>:<kind>`.
- *Card metadata*: `(soul-card "<card-id>" "<kind>" "<person>" <at-ms>)` at `state:soul_card:<card-id>`
  and, per choice, `(soul-card-choice "<card-id>" "<choice-id>" <Pattern|none> "<museum-id|->")` at
  `state:soul_card_choice:<card-id>:<choice-id>`. Written by the `card` tool when the card is sent.
- *Seen marker*: `(soul-taste-seen "<card-id>")` at `state:soul_taste_seen:<card-id>` — the reducer
  has folded that choice into taste (and cast its museum votes). Markers survive "forget", so a
  forgotten taste is never rebuilt from old choices.
- *Felt note*: an Iter message with `felt: true` — one short paragraph of what Iter found interesting,
  shown in its own style. Counted as `(soul-felt "<person>" <at-ms>)` at `state:soul_felt:<message-id>`.
- *Brief*: two lines per app — who it is for, what flourishing looks like for them.

All `state:soul_*` keys are visible **only** in the `soul` view (M6-C2 extended: the `full`/`current`/
`kb` views exclude `state:soul_card*`, `state:soul_taste*`, `state:soul_dismiss:*`, `state:soul_felt:*`
exactly as they exclude `state:soul_choice:*`).

---

## A. Taste from choices (the learning core)

**M7-A1 — The card tool records what it offered.** `card.run(kind, title, body, choices, links=None,
expires_in_s=None)` accepts per choice the optional keys `pattern` (one of the nine pattern names,
validated against `soul_lens.patterns()`, i.e. against the atoms, not a Python list) and `museum_id`
(a component-museum id, `comp-…`, ≤ 64 chars). Unknown pattern → `ERROR: unknown pattern …` and no
card is sent. After the sidebar message is published, the tool transacts (actor `iter`, source `card`)
the `soul-card` atom and one `soul-card-choice` atom per choice in a single transaction. If the service
is unreachable the card still goes out and the tool returns `CARD-SENT: <id> (unrecorded)`; such a
card yields no taste evidence. The choice line and the sidebar card are unchanged from M6; `pattern`
and `museum_id` ride along in the card JSON (the bridge's `validCard` accepts them: `pattern` a short
identifier, `museum_id` a string ≤ 64; anything else is dropped from the choice, never fails the card).
The card's `person` is `soul_settings.person()` at send time.

**M7-A2 — The reducer folds choices into taste, once each.** `iter/transformations/soul_taste.py`
runs every cycle before `soul_presence.py` (name order) and must cost one `read_atoms` call when there
is nothing new. For every `state:soul_choice:<card>` without a `state:soul_taste_seen:<card>` marker and
with a `state:soul_card:<card>` atom present:
- pick ≠ `dismiss`, picked choice has pattern P, every other choice with pattern Q ≠ P and Q ≠ none:
  revise `state:soul_taste:<person>:P:Q` with a pick and `state:soul_taste:<person>:Q:P` with a
  non-pick (n+1 both; f recomputed; c from n). The person is the one on the `soul-choice` atom.
- pick = `dismiss`: `state:soul_dismiss:<person>:<kind>` n+1. No taste evidence.
- museum votes (see D1).
- then upsert the seen marker.
All writes of one cycle go in one transaction (actor `iter`, source `soul_taste`). The reducer never
touches a key outside `state:soul_taste*`, `state:soul_dismiss:*`, `state:soul_taste_seen:*`. It never
reads the chat journal; the atoms are the record. A choice whose card has no metadata (M6 cards, or
`(unrecorded)` ones) gets a seen marker and nothing else.

**M7-A3 — The lens reads taste back; the presence block carries one learned line.**
`soul_lens.taste(person, atoms=None)` → list of `{"picked", "over", "f", "c", "n"}` sorted by `c` then
`f` descending; read with `read_atoms` over `state:soul_taste:<person>:` (exact and cheap; no MeTTa
evaluation needed), or parsed from a pre-read `{key: atom}` dict when the caller already holds one
(the dashboard). `soul_lens.dismissals(person, atoms=None)` → `{kind: n}` and `soul_lens.answered(person,
atoms=None)` → `{kind: n}` (non-dismiss choices). `soul_lens.taste_line(person, atoms=None)` →
one sentence, or `""`: it names at most two leans, each only when `n ≥ 2` and `f ≥ 0.67`, in the form
`you've leaned <Picked> over <Over> (<picks> of <n> forks)`; it adds `you dismiss most <kind> cards`
for a kind with `n ≥ 3` dismissals when dismissals exceed answered cards of that kind. Pattern names
in the line come from the atoms. `soul_presence.presence_block()` appends `Learned: <taste_line>` when
the line is non-empty — still one block, still under 900 chars — and never when every feature is off.
Transformations run in name order, so `soul_presence.py` sees the taste `soul_taste.py` wrote in the
*previous* cycle; a one-cycle lag is accepted (not a reason to rename the files).
`soul_reflect.run(situation)`: when two named patterns are a declared pair and a taste belief with
`n ≥ 2` exists for them, add `Your lean so far: … — still your call.` (no verdict words, as in M6-C3).

**M7-A4 — The person can forget.** Soul panel: a button `btn-soul-forget` ("Forget what you've learned
about me") for the selected person → IPC `soul:forget` (main.js takes the person from the **selected**
person in the saved settings, i.e. `loadSoulSettings().person`, never a renderer argument) →
`bridge/soul_choice.js forgetSoulTaste({socket, person})` deletes every `state:soul_taste:<person>:*`
and `state:soul_dismiss:<person>:*` in one transaction (actor `person`, source `sidebar`) and returns
`{deleted: n}`. Choices and seen markers remain; the reducer does not rebuild the taste. The status
line under the button says `Forgot n beliefs for <person>.`

**M7-A5 — Two M6 gaps closed.** (a) Budget reaches the prompt: the presence block says
`Up to <budget> cards or felt notes per cycle.` (`0` → `No cards or felt notes unless asked.`), advisory
only. (b) `main.js` flushes `.runtime/soul_choice_pending.jsonl` when the AtomSpace service reports
ready (the same place it logs `[atomspace] ready`), not only on the next click; `bridge/soul_choice.js`
exports `flushSoulChoices({socket, iterDir})` → `{flushed: n}`.

**Honest surfaces (A).** `dashboard_atomspace.authority_counts` adds `soul_tastes` (count of taste
atoms), `soul_felt` (count), and `soul_learned` (the current person's `taste_line` or `null`); the
Soul card shows the learned line verbatim when present.

---

## B. The felt channel (a voice)

**M7-B1 — `felt` tool.** `felt.run(text)`: one paragraph ≤ 280 chars (longer → `ERROR: keep a felt
note under 280 characters`); publishes an outbox message `{role: "iter", content: text, felt: true}`
through `electron_ui.send_felt(text)`; records `state:soul_felt:<message-id>` (best effort, like the
card); returns `FELT-SENT: <message-id>`. The bridge's message validator accepts `felt: true` (any other
value is dropped from the message, never fails it) and the journal keeps it.

**M7-B2 — Rendered as a voice, not a card.** The sidebar renders a felt message as
`.msg.row.iter.felt` with a `.felt-mark` glyph (`✦`) before the body and the body in `.body.markdown`
(same sanitizer); no buttons; the transcript/fallback is the plain text. Old journal entries without
`felt` render exactly as before.

**M7-B3 — Off means absent.** `soul_presence.transform(messages, tools)` removes the `felt` tool from
`tools` when `felt` is off for the current person (the model cannot call what it cannot see) and leaves
`tools` untouched otherwise. With `felt` on, the block's feature line for felt reads
`felt (a short note on what you found interesting; <frequency word>)`.

---

## C. Flourishing briefs

**M7-C1 — `brief` tool, two storages.** `brief.run(app, for_whom=None, flourishing=None)`:
- both given → write. Each line ≤ 200 chars. For a Foundry project (`FoundryProjects(ITER_DIR).inspect(app)`
  succeeds) the brief is stored at `blueprint.flourishing_brief = {"for", "flourishing", "by", "at"}`
  through `revise_blueprint` with the project's current context hash (so it is a checkpointed change,
  provenance `{"tool": "brief", "person": <person>}`). For a top-level app directory under `ITER_DIR`
  that holds an `index.html` (e.g. `crm`, `music`) it is `<ITER_DIR>/<app>/brief.json` with the same four
  keys. Anything else → `ERROR: no app named …`. Returns `BRIEF-SAVED: <app>`.
- neither given → read: `<app>: for <for>. Flourishing: <flourishing>.` or `BRIEF-NONE: <app>`.
- one given → `ERROR: give both lines or neither`.
`by` is `soul_settings.person()`; `at` is ms.

**M7-C2 — Briefs reach the prompt when the feature is on.** `iter/transformations/soul_brief.py`
appends one block `## Briefs` with one line per app that has a brief (Foundry projects and top-level
app dirs; sorted by app id; at most 8 lines; each `<app>: for <for>. Flourishing: <flourishing>.`) to
the last system message — only when `brief` is on for the current person; nothing at all otherwise or
when no app has a brief.

**M7-C3 — Drift is a card, never a block.** With `brief` on, the presence block tells Iter: when a
change contradicts an app's brief, say so once as a `brief` card with choices `continue`, `revise`,
`drop`. The `card` tool accepts those ids for kind `brief` (they are ordinary ids; nothing special
happens on pick beyond A2). The reducer's dismissal count makes "you dismiss most brief cards"
learnable (A3).

---

## D. Forks as variants

**M7-D1 — A pick casts the museum votes.** When a choice on a card carries a `museum_id`, the reducer
(A2) on a non-dismiss pick calls `tools/museum_vote.run(museum_id, "keep")` for the picked choice and
`run(other_museum_id, "reject")` for every other choice that has one. Dismiss casts nothing. The losing
variant stays in the museum (reject is a vote, not a delete — unchanged M5 behaviour). A museum id that
no longer exists is skipped with a log line, never an exception.

**M7-D2 — The recipe is in the prompt, the mechanics in the tool.** With `forks` on, the presence block
says: when a design decision holds a declared pair, build both poles with `browser_tab_variants`, then
send a `fork` card whose choices carry `pattern` and `museum_id` and whose `links` point at the two
tabs. The `card` tool's DESCRIPTION mentions `pattern` and `museum_id` (≤ 500 chars total).

---

## E. End-to-end (real loop, real service, fake model)

**M7-E1** — Script: two fork cards with patterns and museum ids (museum entries pre-seeded in the run
root), a simulated pick on each (bridge `sendChoice` + `recordSoulChoice`, as in M6-E1), one `felt`
call, then an idle cycle. Assert: `soul-card`/`soul-card-choice` atoms present after each card; after
the next cycle the seen markers, the taste belief `n=2`, both museum records voted (`keep`/`reject`);
the felt message is in the outbox journal with `felt: true` and a `soul-felt` atom exists; the request
after the second pick carries `Learned: you've leaned …` in a system message; `full`/`current`/`kb`
views contain none of the `soul-*` atoms; the NACE belief count is unchanged across the run.

---

## Out of scope (next)

Soul-absent test / critique mode, person-read and tempo, modes (M8); Iter in the tab (M9); the wonder
jar and the browsing ally (M10). Context-conditioned taste (`soul-taste-in "<person>" "<ctx>" …`) is
deferred until two weeks of real choices show whether pair-level taste is too coarse.
