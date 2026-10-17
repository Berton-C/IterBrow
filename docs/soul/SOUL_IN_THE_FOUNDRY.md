# Soul in the Foundry — roadmap

Date: 2026-10-15. Status: **agreed in direction, milestones to be specced one at a time**
(Berton, 2026-10-15: "I like all of these ideas and want to do them all").
Companion to `SOUL_FIDELITY_AUDIT.md` (what the spec says, what exists) and to
`docs/milestones/M5_knowledge_base.md` (the working method: spec → failing tests → implement).

## The proof

ClarityOmega proved a Soul can govern an agent's own actions. That proof does not need
repeating. IterBrow's proof is different:

> **A collaborator with a Soul makes the person more creative, and the software it builds
> can carry that Soul to its own users.**

Who benefits, in order: the person building (Berton, Bright, Haley), then the people who use
what gets built, then Iter (it learns from every choice), then the research (real calibration
data, which the spec's Phase 2 needs anyway).

What proves it: people choose at forks, correct the person-read, keep features on, and say the
builds got better. Not a score; a record of choices.

## Principles (hold for every milestone)

1. **Ally, not gate.** No ClarityOmega-style PAUSE/veto in IterBrow. The browser is well
   behaved already. The Soul offers; the person decides. (Berton, 2026-10-15.)
2. **Never nag.** Anything the Soul says is rare, once, and earned by a real tension or a real
   moment. Silence is the normal state and the dashboard shows it honestly.
3. **Choice returned, never collapsed.** A live paraconsistent pair becomes a fork with both
   poles built, not a verdict. The person's pick is the calibration record.
4. **Off and tunable, per person.** Every feature has an on/off, a frequency dial
   (whisper / occasional / chatty), and a tone; settings are per person. Off leaves no trace in
   the prompt and costs nothing.
5. **Lens, not rules.** The spec's nine patterns and four pairs are the lens Iter reads through
   (as kernel atoms, as in the reference). Keyword matching is bootstrap only, never a verdict.
   No Python keyword lists are called "the Soul" again.
6. **Honest surfaces.** Every Soul surface shows what is real (as the AtomSpace dashboard now
   does). Nothing claims a mechanism it lacks.
7. **Fun comes from taste and restraint**, plus named modes and small named moments, not
   decoration.

## Decisions pinned (defaults; Berton can override any of them)

| Question | Default |
|---|---|
| Value vocabulary | The spec's nine patterns (AgencyBalance, CognitiveResilience, ConnectionDepth, WonderPreservation, TimeCoherence, PurposeBeyondUtility, SharedUnderstanding, CreativeTranscendence, AttentionStewardship) and its four paraconsistent pairs, as `soul_kernel.metta` declares them. Iter's nine values are retired (their keyword code goes with them). |
| Priority hierarchy | Declared as atoms for fidelity, **not used for routing** (no gates). |
| PARACONSISTENT calibration tag | "Both readings are right" (WM:760), not "resolved by hierarchy" (D2:173). |
| How tension is detected | As in the reference: an LLM gap-detection channel reading the pattern lens (not keywords); the pair atoms are queried natively to confirm a named tension is a declared pair. Phase 2 (symbolic truth values over patterns) comes from calibration data, later. |
| Where Soul atoms live | AtomSpace source seeds in their own query view (`soul`), like the kb view; never loaded with NACE atoms (Hyperon 0.2.10 corruption, see M5). |
| Calibration record | One event type for every human choice: fork pick, read correction, museum vote from the UI, card dismissal, feature toggle. Append-only, per person, in the AtomSpace journal. Read by nothing that changes Soul content (WM:763); read by the dashboard and, in Phase 2, by truth-value revision. |
| Cost | Soul channels run only when a feature needs them (a fork, a brief check, a read). Budget per cycle is a setting; default favours fewer, better moments. |
| Existing Soul code | `soul_eval` becomes a plainly named reflection tool; `soul_check`/`soul_voice` prompt blocks are removed (the lens is injected by the new Soul transformation when a feature is on); the bridges + courier are documented as NACE telemetry; AGENTS.md's Soul section is rewritten to match the code. |

## Milestones (sequence; each gets its own spec + failing tests before implementation)

### M6 — Honest base and the choice plumbing
Everything later depends on being able to *ask the person something and record the answer*.
- Interactive sidebar messages: a `card` message type (title, body, 2–3 choices, optional
  variant links) rendered by the sidebar; a click writes a `choice` event to the inbox that
  Iter receives like a message. Text messages unchanged.
- Calibration event: `(soul-choice "<person>" "<kind>" "<card-id>" "<pick>" <stv-free>)` in the
  AtomSpace, written by main.js on click, readable by the dashboard.
- Soul settings panel (sidebar dock): per feature on/off, frequency, tone; a "who is here"
  selector (Berton / Bright / Haley / guest) that scopes settings and calibration per person.
  Iter reads the settings file directly (no env plumbing).
- Soul kernel atoms as source seeds (`seeds/soul_kernel.metta`, ported from the reference:
  patterns × facets, pairs, related/degrades, tension vectors) in a `soul` query view.
- Theater removed/renamed (see Decisions). Dashboard gains a Soul card: features on, choices
  recorded (count per kind), last moment, "no Soul activity" when silent.
- Tests: card round-trip through the real chat bridge and sidebar (Playwright, as the nav fix
  was tested); settings scoping; seeds load in the `soul` view and never in `current`;
  `soul_check`/`soul_voice` gone from the prompt; AGENTS.md section matches code.

### M7 — A personality that learns (spec: `docs/milestones/M7_soul_personality.md`)
Superseded in scope by the M7 spec: taste beliefs from choices first (`soul-taste`, NAL-revised in the
soul view, read by the lens, one learned line in the presence block, forgettable), the felt channel
pulled forward from M8, then briefs and forks as variants. Soul-absent test moves to M8. Original:
- **Flourishing brief**: `blueprint.json.flourishing_brief` (who this is for; what flourishing
  looks like for them), two lines, editable from the sidebar; for apps without a blueprint
  (CRM, Little Orbit, NodeQuest) a `brief.json` beside the entrypoint. Iter reads it into the
  prompt whenever it works on that app. Drift check: when a proposed change contradicts the
  brief, Iter names it once as a card (continue / revise brief / drop change). Never blocks.
- **Forks as variants**: when the gap-detection channel reports a live declared pair in a
  design decision, Iter builds both poles with `browser_tab_variants`, saves both to the
  museum, and sends a fork card (one line per pole on what it protects). The pick records a
  calibration event, casts the museum vote (user-cast votes become possible), and the losing
  variant is kept in the museum, not deleted.
- **Soul-absent test** (`soul_absent_test` tool + "critique" mode): walks the app as its brief's
  intended user and reports moments that are technically correct and dead, each tied to a
  pattern's gap signature. Output is a short list in the sidebar; nothing is changed.
- Tests: brief round-trip; drift card appears exactly once per contradiction; fork card carries
  two real museum ids and the pick lands as `soul-choice` + vote; soul-absent output cites
  patterns from the kernel atoms, not keywords.

### M8 — Presence: the Soul in the tab, modes, critique, museum night (spec: `docs/milestones/M8_soul_presence.md`)
Merges this entry's modes and soul-absent test with M9's "Iter in the tab" (the margin glyph). The
person-read, tempo and the twin are parked as a separate later build ("the Muse"). Original:
- **Channel A port**: a person-read (state, active need, tone) from message cadence
  (`messages.jsonl` timestamps), edit rhythm (app command provenance), stall/idle signals,
  and the last few messages. Shown as one correctable line in the sidebar; a correction is a
  calibration event and tunes that person's read.
- **Tempo**: the read sets collaboration tempo, not verdicts: flow → quiet; stuck → one
  "what if"; tired → offer a stopping point and save the thread.
- **Modes** switchable by a word or the panel: *jam* (riffs, playful variant names), *quiet*,
  *critique* (M7's test), *museum night* (walk kept vs rejected with Iter telling the why).
- **Felt channel**: once per build, briefly, what Iter found interesting. Frequency dial applies.
- Tests: read is never a verdict (no routing depends on it); corrections change the next read;
  quiet mode produces zero Soul lines; cadence features computed from real timestamps.

### M9 — Iter in the tab
- A corner glyph injected into app tabs via `app_preload.js` that opens a margin: ask about the
  element under the cursor; "jam on this" → three riffs on that component as variants; the
  margin talks to Iter through the existing bridge, not a new socket.
- Locked tabs (🔒) never get the glyph. Non-app web tabs get it only if the person turns on
  "ally while browsing" (M10).
- Tests: glyph absent on locked tabs; margin round-trip through the real bridge; a riff produces
  museum entries tied to the element.

### M9 — Wonder, the voice of growth, the browsing ally, find-in-page (spec: `docs/milestones/M9_soul_wonder_ally.md`)
This entry (the old M10) pulled forward, plus the first browser-track item. Original:
- **Wonder jar** per app and per person: "what ifs" cut from a build are kept; one is offered
  back occasionally (frequency dial). Not a backlog; no due dates.
- **Service before growth, with a voice**: the existing deferral speaks as a card ("I'd like
  to work on X for myself. Now, or later?").
- **Browsing ally (off by default)**: the pause card for live pairs in a browsing session
  (curiosity/time; wonder/shared-understanding), lock suggestions ("looks like your bank;
  lock it?"), a compass glyph that lights only when a pair is live.
- Tests: jar never surfaces more than the dial allows; lock suggestion never acts, only asks;
  compass dark when no pair is live.

### M11 — The app inherits the ally
- A small margin SDK Iter can build into an app, so the app's own users get the noticing and
  the returned choice (NodeQuest first). The app's `flourishing_brief` is its Soul.
- Tests: a built app with the SDK runs the person-read and fork card without IterBrow present
  (static page + its own model key), and records its own calibration file.

### Browser track (independent, can run alongside any milestone)
Find-in-page, downloads, bookmarks, reader mode, history search, zoom, picture-in-picture.
Each is small in Electron; together they make IterBrow something people leave open, which is
what the Soul needs to be worth having.

### Out of scope until Berton says otherwise
Gates/vetoes of any kind; NACE consuming Soul or kb conclusions (the parked "stage 1"
remains available); continuity-of-mind; judging Iter's own promoted code.

## Order and dependencies

M6 → M7 → M8 → M9 → M10 → M11. M7 is the first milestone that *feels* like something; M6 is
the plumbing it needs. The browser track has no dependencies. M8 can start as soon as M6's
settings exist if M7 is still in review.
