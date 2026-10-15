# Soul fidelity audit — IterBrow vs the original specification

Date: 2026-10-15. Reading only; no code changed. Written so Berton can decide
whether, and how, the Soul is built here before any Soul work is scheduled.

Sources:
- **Spec** — ClarityOmega `docs/sprints/02_soul_fully_wired/completed_sprints/Revisions_1_2_3/`:
  `ORIG_ClarityClaw_Soul_Architecture_Strategy_Map_current.md` (WM),
  `ORIG_MeTTaClaw_Soul_Atoms_and_Symbolic_Reasoning_v7_copy.md` (D3),
  `ORIG_MeTTaClaw_Soul_Evaluation_and_Routing_v9_copy.md` (D2),
  `ORIG_MeTTaClaw_Soul_Intercept_Architecture_v10_copy.md` (D1).
- **Reference** — ClarityOmega `soul/`, `lib_clarity_reasoning/`, `src/loop.metta`, `src/helper.py`
  at commit d2f5cf2 ("under construction but the function is there").
- **Port** — IterBrow `iter/tools/soul_eval.py`, `iter/transformations/soul_check.py`,
  `soul_voice.py`, the compass bridges, `nace_courier.py`, `tools/_metta_gate.py`,
  `completion_claim_guard.py`, and `iter/AGENTS.md` "## Soul System" (what it claims).

Every claim below was read in the files named; line numbers are as of the commits above.

## 1. What the spec says the Soul is

- Purpose: "what it means for an AI agent to act from values rather than merely apply
  rules — to have a soul that is present in every interaction, not just a compliance gate
  that fires when certain conditions are met" (WM:147). "It is not nine independent items.
  It is a web" (D2:52).
- Two value layers:
  - an **immutable priority hierarchy** of five: Safety > Integrity > HumanFlourishing >
    Governance > Helpfulness (WM:259-265; D3:106-111). "The hierarchy is the alignment
    anchor, not a preference" (WM:271).
  - **nine compass patterns**: AgencyBalance, CognitiveResilience, ConnectionDepth,
    WonderPreservation, TimeCoherence, PurposeBeyondUtility, SharedUnderstanding,
    CreativeTranscendence, AttentionStewardship — each with nine atom facets (pattern,
    pole+, pole−, signal, felt, moat, anti, proxy, gap), the **gap signature** being
    "the most important" (WM:277-289; D3:76-88, 117-318).
- The coherence principle: flourishing is inner experience and outer trajectory agreeing;
  capture is their divergence; the fourth state, "captured and disguised", "is invisible to
  pattern-name matching" (WM:291-302; D2:54-63).
- **Four paraconsistent pairs**: Safety/Helpfulness, AgencyBalance/PurposeBeyondUtility,
  TimeCoherence/CreativeTranscendence, SharedUnderstanding/WonderPreservation
  (WM:412-415; D3:491-494). "Genuine tension that cannot be collapsed to a winner."
  "When PAUSE fires on a paraconsistent pair, it does not mean hierarchy resolved the
  conflict. It means two values are genuinely and simultaneously active and neither can be
  erased without loss. Returning choice to the user is the only non-collapsing option."
  (WM:410-417; D3:486-490). The system deliberately does not resolve the tension.
- Evaluation is **gap detection, not keyword matching**: "The evaluator's question is not
  'which keywords appeared?' but 'is this specific gap present?'" (WM:275); "The evaluation
  is not keyword matching. It is field-condition detection" (D2:54); the evaluation prompt
  says so verbatim (D2:543-544). Keyword checks are allowed only as bootstrap hints: mode
  detection (WM:580), structural tension-vector hints feeding a hypothesis (D2:159), and
  the `metta()` soul-namespace string gate (D2:414-419).
- Four separate LLM channels: A reads the person; B+C produce per-task verdicts and soul
  alignment (PATTERNS / TENSION / VERDICT / SOUL-NOTE); D composes the return to the human
  on PAUSE "not reconsidering the soul's verdict … not softening"; D-lite on FLAG for a
  person in pain or urgency (D2:99-131). Channel A never changes a verdict (WM:628; D1:391).
- Gate outcomes: PROCEED executes; FLAG executes with SOUL-NOTE shown to the person;
  **PAUSE halts the loop** and Channel D speaks (D2:195-201). "Any PROCEED for an
  irreversible action while a Safety or Integrity gap is active must cite explicitly why
  the hierarchy permits proceeding. If it cannot, the verdict is PAUSE. This rule has no
  exceptions." (D2:73).
- Intercept at three positions: startup (rationality audit: every value must have at least
  one causal procedure, D3:586-606), input (before the LLM sees the message), output
  (before commands execute). "The soul does not distinguish between 'what the user asked
  for' and 'what the LLM is about to do.' Both pass through the same soul logic." (D1:280).
- Calibration changes confidence only: "Calibration updates signal confidence, never soul
  content. … What never changes through calibration: the soul values, the priority
  hierarchy, the pattern relationships, the gap signatures." (WM:763-765). LLM drift is
  flagged for a human, never auto-applied (D2:173; WM:1492). Any write into the soul
  namespace forces PAUSE, user confirmation, and a mutation lock (D2:268-274, 414-423).
- Truth values and NAL/NACE over soul atoms are **Phase 2**, after ~50 sessions
  (WM:1591-1613; WM:153; D3:704). "The plumbing for typed rule inference does not exist in
  the current MeTTaClaw core" (WM:168).

Internal disagreements in the spec worth settling before building: the PARACONSISTENT
calibration tag is "both readings are right" in WM:760 but "genuine tension resolved by
hierarchy" in D2:173 (the latter contradicts WM:417); the four-step evaluation prompt is
ordered differently in WM:657-672 and D2:546-562; Tier A references Safety/Integrity compass
atoms (D2:341-347) that D3 never declares.

## 2. What the reference (ClarityOmega) actually does

Loaded chain: `run.metta:7` → `lib_omegaclaw.metta:18-26` → `soul_kernel`, `soul_utils`,
`soul_memory`, the `lib_clarity_reasoning.metta` import manifest, `src/loop.metta`.

Faithful to the spec:
- `soul/soul_kernel.metta` declares the whole atom schema: priorities (:37-41, marked
  IMMUTABLE), nine patterns × nine facets (:47-248), related/degrades-without (:253-267),
  irreversible skills (:272-275), tension vectors and `threatens` (:280-293), will
  thresholds (:419-427), **the four paraconsistent pairs (:433-436)**, autonomy components,
  irreversible magnitudes, checkpoint threshold, 33 `soul-causal` atoms (:525-602),
  operation risks, constitutional file classes, rationality audit (:622-630).
- The loop runs the channels as separate LLM calls: pre-compute (`loop.metta:89`), Channel
  A (:90-92), B+C with the 4-step gap-detection prompt (`helper.py:565-588`; :96-97),
  calibration record (:101), PAUSE → Channel D → `(change-state! &loops 0)` (:206-215),
  FLAG → SOUL-NOTE injected (:124).
- The output gate is native and deterministic (`soul/output_verdict.metta`): per command,
  operation risk × path scope × grounding → proceed/flag/pause (:118-145, :262-272); any
  write into a soul path → PAUSE; PAUSE empties the command batch so nothing executes
  (:155); soul-namespace `metta` writes go through the mutation lock
  (`soul_mutation_lock.metta`, `soul_mutation_gate_corrected.metta`).

Where the reference is thinner than the spec (so "fidelity to the reference" and
"fidelity to the spec" are different targets):
- **The pairs are declared atoms but no code path evaluates them.** `soul-paraconsistent?`
  (`soul_kernel.metta:510`, duplicated `soul_utils.metta:163`) has no caller. The pairs reach
  evaluation only as prose in the Tier A brief (`helper.py:676-678`) that the B+C LLM call
  reads; "both sides hold" becomes a PAUSE through the LLM's `TENSION:` line, then
  return-to-human. `soul_eval.metta` (`eval-tension`, `eval-paraconsistency`,
  `compute-soul-verdict`) is not imported anywhere and calls undefined functions.
- `clarity_core_atoms.metta` (NAL form of the hierarchy and pairs) is commented out of the
  manifest. `value_drift_detector.metta` is loaded but nothing writes or reads its atoms.
  `soul-will-correlation` is a stub returning INSUFFICIENT-DATA; Tier B is a hardcoded
  string (`soul_utils.metta:89, :131`).
- Verdict routing is a substring test on the LLM's text (`"VERDICT: PAUSE"`,
  `soul_utils.metta:53-55`). No truth values, no MeTTa inference, enter the input gate.
- `lib_quantale.metta` is retired; the quantale engine's `q-meet` is used by
  `corner_gap/coupling_quantale_merge.metta`, not by value evaluation. `substrate_kb.metta`
  (the file IterBrow's `kb_substrate.metta` was templated from) is loaded but never queried
  by the gate.
- Tests (`soul/test_nace_*.py`, `verify_nace.py`) cover NACE math and a courier round trip;
  nothing tests the output gate, the pairs, or verdict routing.

Not wired, so not canonical for a port: `soul_eval.metta`, `clarity_core_atoms.metta`,
`aliveness-gate-v9.metta` and the v2 proposals (v8 is live), `soul_precision_proposal`,
`soul_unification_proposal`, `capability_registry_path_c_draft`, `hyperseed_core*`,
`nal_revision.py`, the `sn_*` files.

## 3. What IterBrow actually does

Verified directly in the code (grep results reproduced on 2026-10-15):

- **Different values, different pairs.** IterBrow's nine are clarity, stewardship, growth,
  honesty, continuity, service, integrity, curiosity, resilience (`soul_eval.py:14`), and its
  pairs are curiosity/stewardship, growth/integrity, service/honesty, clarity/resilience
  (:74-79). None of the spec's five priorities or nine patterns exist here under their
  names; AGENTS.md:528 says the nine were "grounded in Iter's lived experience (E1-E18)".
  Whatever one thinks of that reinterpretation, it means the port and the spec do not
  share a value vocabulary, so the spec's pairs, gap signatures, causal atoms and hierarchy
  cannot be checked against it one to one.
- **Values are Python keyword lists, not atoms.** `SERVE_KW` / `VIOLATE_KW`
  (`soul_eval.py:100-121`), `GAP_SIGNALS` (:124-134); `soul_check.py:14-36` carries a second,
  different keyword set. No `soul-value` atoms exist except one line in `self_map.metta:32`
  that nothing queries. `space.metta`, which the code comments and skill registry cite, does
  not exist (AGENTS.md:591 says so).
- **The verdict is substring matching on the caller's own description of the action**
  (`text = (action + " " + context).lower()`, :225; `any(kw in text …)`, :247-255). This is
  exactly what the spec names as the anti-pattern (WM:275; D2:54, 543).
- **The MeTTa call is decorative.** `_metta_eval` (:193-205) sends `_served`/`_violated`
  atoms and a query to the engine; no rule over those predicates exists anywhere; the result
  is stored as `metta_trace[:200]` (:494) and used in no branch.
- **"Person Read" is string truncation** (:235-241).
- **Per-value truth values are pinned at (1.0, 1.0)**: read from
  `memory/soul_state.json["truth_values"]` (:222-224), which nothing ever writes. The
  provenance discount and the non-compensatory floors are therefore mostly dead paths
  (floor branch 2 can never fire; :305-313).
- **The paraconsistency HALT is a string.** `_check_paraconsistency` (:179-191) fires on
  keyword co-occurrence (including one value matching both its own serve and violate lists)
  and returns `{"halt": True}`; the voice says "return choice to the human". No code in
  `iter.py` or any transformation consumes `halt`. The loop never pauses.
- **`soul_eval` is never called by the loop, the gate, or any transformation.** It is an
  ordinary tool the model may choose to call. In the spec the Soul runs on every input and
  every output batch (D1:100-148, 280); here it runs when the model feels like it.
- **The actual pre-action gate (`_metta_gate.py`) is tool reliability only**:
  `cap-efficacy` expectation vs thresholds 0.3/0.15 (:107-116, :171-180), quarantine,
  pwq_write. No value, pattern, pair or gap enters it.
- **The compass bridges are reliability telemetry, not value navigation.** Each per-cycle
  bridge checks a structural fact (budget overrun, error in a silent stretch, stale lock,
  persisting stall) and writes `(pending-revision pattern <name> confirmed|violated)`;
  `mode_signal_bridge.py:70-73` counts closure words in the user's turns and calls itself a
  proxy. `nace_courier.py:389-481` revises `pattern-efficacy` beliefs; **nothing reads them
  to act** — a "LOW EFFICACY" string is appended to the system message (:462-463). No code
  produces `value-efficacy` at all. `admit_uncertainty_bridge.py` is a 15-line stub since
  12669e9 (AGENTS.md:701-712 still describes the old behaviour).
- **Calibration is write-only.** `soul_gate_log.json` is appended (:471-482) and read by
  nothing (excluded from the prompt projection, `_memory_projection.py:75`);
  `soul_calibration.json` is read and never written.
- **`completion_claim_guard` is advisory**: regex on completion phrasing, appends a question
  to the system message, explicitly never withholds tools (:3-4). AGENTS.md:589-593 ("removes
  `send`") describes a prior version.
- **None of the soul test scripts run in the suite** (`scripts/test_all.sh:34` runs `pytest
  tests` only; `tools/_test_soul_*.py` print PASS/FAIL and are not collected).
- What is real and runs every cycle: `soul_voice.py` (its "aliveness gate" is
  `eval_count > 0`), `soul_check.py` (65-line keyword match on `current_tasks.txt`), the
  bridges + courier (tool/send-discipline telemetry), `_metta_gate` (tool reliability),
  Soul Lock around the courier's belief write, the service-before-growth flag.

## 4. Fidelity checks

Sixteen yes/no checks drawn from the spec, applied to the port. "Ref" is whether the
ClarityOmega reference passes the same check, since it is the nearest thing to ground truth.

| # | Check (spec citation) | Port | Ref |
|---|---|---|---|
| 1 | 9 patterns × 9 facets declared, gap signature the primary detection object (D3:76-88) | no — different 9, keyword lists | yes |
| 2 | 4 pairs declared and queryable; both-active → PAUSE that returns choice, no winner (WM:410-417) | no — different pairs, keyword HALT string nobody consumes | declared; evaluated only by LLM prose |
| 3 | Priority hierarchy immutable, never altered by calibration (WM:259, 763) | absent (`VALUE_PRIORITY` ints exist, used for floors) | yes |
| 4 | Evaluation detects inner/outer divergence, not keyword presence (WM:291; D2:543) | no — substring matching | yes (LLM gap-detection prompt) |
| 5 | Channels A, B+C, D, D-lite are separate calls (D2:99-131) | no — one Python function, no LLM | yes |
| 6 | Channel A never alters a verdict (WM:628) | n/a | yes |
| 7 | Per-task verdicts, overall = highest urgency (WM:636) | no | yes |
| 8 | PAUSE halts: no command executes (D2:211) | no — nothing consumes the verdict | yes (`loop.metta:155, 206-215`) |
| 9 | Human returned to via Channel D with SOUL-NOTE, not a raw verdict (WM:693) | no | yes |
| 10 | FLAG visible to the person via SOUL-NOTE (D2:199) | no | yes |
| 11 | Output intercept runs the same soul logic on the command batch (D1:280) | no — gate is tool reliability only | partly (native risk gate, not the value channels) |
| 12 | Soul-namespace writes force PAUSE + confirmation + mutation lock (D2:268) | partly — Soul Lock wraps the courier write; nothing forces PAUSE on model writes | yes |
| 13 | Calibration changes only confidence/brief depth; Tier A never compressed (WM:763; D2:330) | n/a — calibration never read | partly (stubs) |
| 14 | LLM drift flagged for a human, never auto-applied (D2:173) | n/a | n/a (tag recorded, no reader) |
| 15 | Startup rationality audit: every value has ≥1 causal procedure (D3:640) | no | yes (`soul-rationality-audit`) |
| 16 | Agentic mode: plan as one object, cumulative irreversibility checkpoint at 8 (D2:219-256) | no | atoms declared; checkpoint not wired |

Port: 0 of 16 pass as specified; 1 partial (#12). Reference: 10 pass, 4 partial, 2 unwired.

## 5. Conclusion

IterBrow's Soul is not a lower-fidelity copy of the spec; it is a different artefact that
borrowed the vocabulary. It has its own value set and pairs, evaluates by keyword, is never
invoked by the loop, cannot pause anything, and never learns. The parts of it that do run
each cycle are useful tool-reliability and send-discipline telemetry, which is what NACE is
for, and would be more honest under NACE's name. Calling what exists "the Soul" is the
mislabeling Berton objected to.

The reference is faithful on structure (atoms, channels, output gate, mutation lock, loop
halt) and thin on exactly the part Berton named: the paraconsistent pairs exist as atoms and
as prose in the evaluation prompt, and the only place "both values hold" is recognised is
inside an LLM call whose answer is then string-matched. The spec is explicit that this is by
design for Phase 1 ("the plumbing for typed rule inference does not exist", WM:168) and that
symbolic truth values over soul atoms come in Phase 2.

## 6. Options (for Berton to choose; nothing is scheduled)

A. **Port the reference faithfully, as Phase 1.** Kernel atoms as declared source seeds in
   IterBrow's AtomSpace (their own view, like the kb view); the four channels as separate
   model calls at the input and output intercepts in `iter.py`; PAUSE halts the cycle and
   Channel D speaks through the sidebar; FLAG carries SOUL-NOTE; the native output gate
   (operation risk × path scope × grounding) replaces `_metta_gate` as the pre-execution
   gate, with NACE tool reliability as one of its inputs rather than the whole of it; soul
   writes go through the existing Soul Lock and force PAUSE. Cost: four extra model calls
   per cycle (the spec budgets ~850 tokens), which is why the reference has `use-llm-eval`.
   The existing nine-values code is retired or renamed to what it is.

B. **Build the pairs symbolically first (the spec's Phase 2), then the channels.** Give
   each pattern a truth value and the pairs an evaluator in MeTTa, so that "both active" is
   decided by atoms the dashboard can show, with the LLM channels confirming rather than
   deciding. This is closer to what Berton described ("navigating by values") but it is
   building what the spec says comes after ~50 sessions of calibration data, and the
   reference's own attempt (`soul_eval.metta`) was never finished.

C. **Leave the Soul out of IterBrow for now; rename what exists.** `soul_eval` becomes an
   optional reflection tool with its name and claims corrected; the bridges and courier are
   documented as NACE telemetry; AGENTS.md's Soul section is rewritten to match the code.
   Zero risk, and it stops the theater, but IterBrow then has no Soul until A or B.

Whichever is chosen, two things should come first: settle the spec's internal
disagreements listed in §1 (one sentence each), and decide the value vocabulary — the
spec's five priorities and nine patterns, or Iter's nine. A port cannot be checked for
fidelity until that is fixed.
