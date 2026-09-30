# IterBrow: integrated build control

## Current checkpoint — working-context selection and preparation cost, September 29

**Tracking: 4/4 installed and verified.** Sequence: shared-path diagnosis,
offline reproduction, bounded repair, installed verification. Iter owns app work;
this pass changes only iter.py and request_budget.py, plus this existing document.

**Active claim / evidence:** Haley's supplied app_contract.py already accepts
arbitrary valid collections; isolated journal reopen passed. Her model request
preserved an uncorrected storage-expansion plan while relevant source was abbreviated.
The shared runtime selected root-level memory by any body-word overlap, lost task-first
ordering at the memory limit, and let older context occupy room needed to expand
already-recent evidence. The repair uses topic selection consistently, preserves
task/standing-context order, labels the LLM task record as revisable, and prefers
full recent evidence over older recency-reserve groups while retaining newer actions,
explicitly requested distinct captures, user instructions and images. Exact originals
and retrieval remain available; no new store, model call, approval rule or governor.

Budget removal also repeatedly serialized and excerpted the entire history. Exact
incremental byte accounting and bounded index construction reduce a 1,700-exchange
synthetic replay from 25.64s to 0.43s without changing selected messages or estimates.
The user's actual last-request replay retains identical evidence/44,743-token estimate,
with budgeting 0.118s -> 0.035s. These are projection timings, not total-turn or billing
savings. Content-free component/memory/transformation/handoff/projection timings now
accompany the existing log and last_prompt.json to locate other preparation delays.

**Verification:** 279 installed-source checks pass: 183 repository, 13 targeted,
35 continuity/source/image replays, 20 budget-rejection, 10 restart, 18 recovery.
The new complementary-source fixture changes from newest-only to both full results;
its tighter-budget counterexample retains latest evidence plus the earlier preview.
During installation the user launched an idle child; maintenance Stop/Start loaded
the repair as PID 36342, restored the same stable generation/event wait and issued
no model request. Final Stop leaves the loop off. 16,151 protected files match the
pre-install snapshot; the expected heartbeat is the sole change. Unrelated
dashboard_atomspace.py edits are preserved. All harnesses/logs/before-images are in
/tmp/iterbrow-context-repair.73kT1c, not the repository.

**Unresolved / counterexamples:** This does not prove Haley's complete live recovery
or autonomous CRM completion. Necessary evidence can exceed the window; missing
captures still require retrieval/reinspection. Topic selection can omit a useful
poorly named memory; search and an omission index remain available. A wrong LLM
account remains wrong until revised. Provider/tool/transform delays are not cured
by projection optimization. The separate Electron log has navigation deprecations,
network resets and media errors, not an established AtomSpace/Python crash cause.

**Next dependency:** A real user-directed work trial with the installed runtime;
compare actual actions/outcomes and preparation timings. Keep Iter stopped until
requested. No scheduled tasks or automatic model-driven monitoring.

## Previous checkpoint — request-budget retry repair, September 29

**Tracking: 1/3 diagnosis complete; 2/3 offline repair complete; 3/3 installed
and verified locally.** Publication targets are main and TheWholeEnchilada;
the user has authorized both. Earlier automatic-review connection failures are
resolved for installation. This checkpoint accompanies the two-file runtime repair.

**Active claim / evidence:** Haley's log contains fourteen local
RequestBudgetExceeded failures, including repeated 45,062-token estimates against
45,000. These requests never reached the model. Optional omitted-history previews
now yield to retained instructions/evidence; already-captured exchange previews
can fit the remaining allowance while retaining exact readers, execution facts
and omission counts. A structurally similar 45,062-token failure now fits at 44,928,
preserving all supplied user messages and its image. Original history is unchanged.

Local budget/retention failures and API input rejections (400/413/422) wait for
changed input/components rather than retrying unchanged requests. Existing heartbeat,
true health failures, rollback and transient API retries remain. Alarms/channel
errors do not repeatedly wake a rejected request. Content-free budget contribution
diagnostics and chained failure causes reach the log/heartbeat; a bounded prior-failure
observation reaches the next usable request, including after a blocked restart.
No new store, model call, model setting, NACE rule or approval workflow is added.

**Verification:** 266 checks passed offline and against installed source: 183
repository, 20 targeted, 35 continuity/source/image replays, 10 restart and 18
recovery checks. Repository tests use IterBrow's Python environment; system Python
lacks Hyperon. The old replay's expired screenshot is reconstructed from its exact
saved request image only in /tmp. Installed runtime files match the tested candidates;
the unrelated dashboard_atomspace.py edit is preserved and excluded from this commit.
Tests, logs and fixtures remain in /tmp/iterbrow-budget-repair.0sozEr, not the repo.

**Unresolved / counterexamples:** This is not an exact replay of Haley's unavailable
failed request or proof of her live recovery. Indispensable input can still exceed
capacity; unavailable retention storage can prevent projection; previews may require
retrieval. NACE learning from deduplicated recovery outcomes is a future option,
not part of this patch. Her Leadership Growth and Daily Primer browser-only stores
also remain a separate migration task; reuse the existing CRM app contract while
preserving their current records, rather than adding another storage architecture.

**Next dependency:** Verify both remote branches contain this commit. Haley then
updates with the README's Git-clone repair command, restarts Iter, and retries her
task. Host source changes take effect on the next Iter process start; installation
verification did not start the loop or spend model tokens.

## Current checkpoint — self-repair rejection and recovery continuity, September 27

**Scope:** Repair runtime behavior only; Iter owns the unfinished CRM Headlines
work. Its description-only websearch revision was automatically rolled back when
its deliberate `source="web"` negative test raised an expected validation error.
After restart its working account still called the failed revision active, while
the actual rollback event was absent from the model request.

**Repair:** Explicit ToolInputError rejects invalid arguments without labelling a
changed component broken. It remains an unsuccessful invocation, not task success.
Ordinary exceptions, loading/formatting failures, timeouts, generation verification,
heartbeat and rollback keep their existing behavior. Websearch documents auto/github
(retaining Iter's own description improvement). The current pinned generation and
its latest relevant rollback are projected from the existing journal alongside the
working account. No new store, model call, approval, task or completion inference.

**Counterexample pass:** First-pass formatting exemptions and malformed-history
crashes were reproduced and repaired before installation. Prior rollback filtering,
incomplete journal tails, promoted-code corruption, old-tool compatibility, invalid
arguments and valid search paths are covered offline. Existing durable history and
recovery records are not rewritten. Tests and before-images remain in
`/tmp/iterbrow-recovery-repair-gbZtDE`, not the repository.

**Verified checkpoint — 4/4 complete:** 246 offline checks pass (183 repository, 18 targeted,
35 prior handoff/source/image replays, 10 restart/context checks). Isolated installed
worker checks and the actual recovery-snapshot replay pass without a model call.
All 1,781 sampled protected files were identical immediately after installation,
including memory, AtomSpace, tabs, CRM, active pointer, last prompt and heartbeat.
Runtime repair commit: `8f81b6c`, pushed to main and TheWholeEnchilada.

User then authorized a bounded live check and restarts, provided Iter is OFF when
finished. At 22:52 Iter correctly reported the actual prior rollback/current state,
activated `candidate-06deea3f20b14766afc3ca50ababf8f4` itself, and deliberately called
websearch with `source="web"`. The invocation was rejected with success=false and
state=invalid_input; the completed cycle stayed healthy, with no rollback. Its next
`source="github"` query returned Berton-C/IterBrow. The external supervisor promoted
the candidate after three healthy completed cycles at 22:53:33. Iter saved a handoff
and sent the correct verdict, explicitly preserving the unfinished CRM task, then
entered nop(0). This was a guided maintenance test, NOT proof of an autonomous CRM
build. The 23 checked app/bundle/tab/dashboard files were unchanged throughout.

A controlled Stop/Start retained this stable generation and restored idle_wait
with a new PID and no new model request or usage. History, CRM and saved tabs were
identical across that restart. Final Stop was verified in the UI and by process
exit. Live proof and restart records remain in the same /tmp directory above.
**Next dependency:** User-directed resumption of Iter's unfinished CRM Headlines
work. Leave Iter OFF; no automation, background observer or scheduled resumption.

## Previous checkpoint — restart continuity and need-driven context, September 27

**C01/C02 bounded follow-up: 3/3 installed and verified.** User authorized addressing
completed work reopening after restart and unnecessarily bulky requests. Diagnosis:
startup discarded the loop's saved successful nop(0) wait; budget selection treated
days of exchanges as active demand and promoted old full captures (including a
music-app result during the later screenshot task). No semantic completion detector
or new governance layer was added. Three runtime files now restore a healthy wait
only in the same stable generation and use successful waits as request-priority
boundaries, NOT task-completion or durable-history boundaries. All supplied user
instructions, the working account, fresh evidence, history retrieval, positive
waits, input/alarm wakeups and probation/recovery remain available. Fresh large
results can still grow to the 45k ceiling; optional old expansion does not fill it.

Verification: 183 repository tests, 10 new focused checks and 43 prior continuity/
handoff/source/screenshot regressions passed. A captured small post-wait follow-up
replay estimated 43,447 -> 28,698 input tokens (34% lower); system/working account
and all user messages unchanged. The already-active replay did NOT shrink; do not
generalize the saving to every request or claim measured billing savings. Controlled
UI Stop/Start produced one new child, same stable generation, fresh idle heartbeat,
no new model request and identical hashes for 1,625 protected state files. AtomSpace
remained ready at commit 7282 / 8,965 runtime atoms; native truth revision succeeded.
No app edits, memory rewrite, new prompts, provider changes or automation. Temporary
tests/replays/before-images: /tmp/iterbrow-continuity-tyaPFl. Broader C01/C02 behavior
and next-real-request efficiency remain observations, not universally closed issues.

## Previous checkpoint — independent music-app foundry trial, September 24–25

**Current follow-up — September 25, 17:32: TRACK CURRENT HUMAN INTENT; MUSIC 3/4.**
User asked Codex to keep tracking what they are having Iter do NOW. Read-only
observation found the 17:22/17:24 requests for Iter's own system health delivered
intact to the model, but answered with app status; Iter then re-registered the old
repair task at 17:25/17:28 with person=Codex. Those are Iter tool arguments, NOT new
Codex instructions. The 17:29:54 screenshot shows the user's current composer text:
"Make a new ditty that's upbeat and fun" and a single unsaved drum-note preview.
Current composer code uses local keyword matching ("upbeat" matches "beat") and
stageEdits; it does not dispatch that text to Iter chat. However, the EXACT
screenshot bytes reached actual model requests at 17:30:09 and 17:31:48; the next
17:30 action still retrieved historical Moonlit notes. This is NOT missing image
delivery. Track latest-intent follow-through (C04), repeated recovery (C01), and
requester mislabeling (C15); the disconnected composer is an APP integration gap,
not yet a runtime defect. No coaching, app edits, Keep/Undo, reload or runtime
patch by Codex. Current evidence: /tmp/iterbrow-working-handoff-0U4PfP/current-intent-observation-1732.json.

**Monitoring recovery — September 25, 17:23.**
Codex observation was interrupted; do not claim continuous supervision. Fresh
requests and completed actions at 17:20–17:23 establish Iter running on Luna/Low,
stable d33f3be5 generation. The user's reported 401 indicates rejected credentials,
but its emitting client and cause are not established; current Iter OpenAI calls
succeed. No credential changes or paid diagnostic requests were made. The expired
read-only /tmp observer was restarted after confirming no duplicate process.
Iter independently changed recovery to v3 at 15:50:55: capture original saved/draft
bytes once without rewriting them. Offline checks of CURRENT source hash
4632eb12dc810d78bdfc58b823dca8fce991869fdfcd738470be25c8e9fc7c7c pass saved+draft,
saved-only and existing-v3-backup cases including repeat load. The older harness
initially rejected any new storage entry; that assertion was corrected to permit
an exact new backup while protecting every existing value. No app-code change by
Codex and no real browser storage read/write by these tests. This is bounded
startup evidence, not Iter's own UI/export proof or full acceptance. C01/C04 remain
open: repeated retrieval and promised-but-unexecuted tests continued after repair.
Iter switched from tab 8 to tab 4 at 15:54:05; absence of a proposal there does NOT
prove loss of tab 8's unkept sparkles proposal. Do not Keep/Undo/reload that proposal.
Latest proof: /tmp/iterbrow-shell-outcome-Y5otI8/recovery-preservation-check.json.
C17 remains complete; no new runtime patch was installed in this observation pass.

**Prior follow-up — September 25, 15:33: AUTHORIZED FEEDBACK; ITER REPAIRING.**
Music remains 3/4, Luna/Low, stable d33f3be5 generation. After verified C17 and
C02 installation, Codex resumed through Start with NO new task message or app
coaching. Thirteen responses were recorded before a protective Stop: 352,223
tokens, $0.04577 estimated standard text cost, THIS COMPARISON ONLY, not invoice
or whole-build total. Iter independently corrected its wrong composer-ID claim
at 15:15:41, then wrote a repair at 15:17:50. Its new one-time song recovery first
backs up the existing saved/draft strings, but overwrites that same backup with
the replacement strings before marking complete. Two offline counterexamples
using the actual recovery/startup code prove loss of the pre-repair values:
saved-only and saved plus valid unsaved draft. No real browser storage was read
or written by these tests, and Codex has not edited the music app. No reload was
observed after that edit before the protective Stop; child 55727 exited. The user
then explicitly approved a symptom-only failure report and independent repair.
Codex sent it once at 15:32:23; received once at 15:32:42; first actual Luna/Low
request 15:33:00. A newly staged, unkept "sparkles" proposal was visible in the
app; the report included preserving it, not permission to Keep/Undo it. Codex
clicked neither app action and supplied no code, location or implementation
advice. At 15:33:12 Iter independently identified the backup-overwrite cause and
proposed preserving originals, exposing recovery separately and testing isolated
storage without touching the live proposal. This is not yet a verified repair.
The earlier hold is superseded by this explicit approval; protect the live
proposal and do not automatically resume a later protective hold from the monitor.
Delivery record: /tmp/iterbrow-shell-outcome-Y5otI8/backup-feedback-delivery.json.
This is an app-code preservation failure, NOT a
proven C17/runtime defect. Proof: /tmp/iterbrow-shell-outcome-Y5otI8/backup-counterexample.json.

The earlier C02 hold began after repeated wrong identifiers and unsupported
"Keep has just committed" narration. At 14:33:19 the actual request lacked
draft.v2 despite its successful 14:29:20 observation; an older 33K episode result
was present. C02 selection was reproduced offline; unlike earlier samples with
evidence present, this case supplies a concrete missing-newer-evidence finding.
C03 remains installed,
loaded and verified; its bounded tracker row is checked, not reopened by C01/C04
repetition. At 14:17:26 a genuine failed browser evaluation returned the actual
TypeError (reading title of null) and file location: C11 now has live proof.
Iter repeatedly checked obsolete draft.v1 rather than actual draft.v2, and its
Keep/Undo comparison captured its baseline after staging the proposal. These
checks do not prove preservation or establish an Undo defect. It later inspected
draft.v2, but retrieved the same original-song episode at 14:21 and 14:24 again.
No app code or further coaching supplied by Codex. Tab 6 was closed around 14:10;
seven tabs remain, app 8 intact. No Iter close action observed; do not restore a
possibly human-closed tab. The five-minute monitor is backup, not a substitute
for active observation while this work is underway.

C17 is a NEW measured runtime-cost clue, not a C03 revision. Ten sampled cycles
spent 26.09–26.69s preparing context versus 2.58–5.38s waiting for the model.
Native reasoning/NACE/reliability repeatedly reconstructed the native engine,
invoking the interpreter once per stored atom. Hyperon's native parse/add API
reconstructs the identical 7,998-atom copied-state inventory 4.33 times faster.
Stages 1/4 measurement, 2/4 candidate, 3/4 offline validation and 4/4 installation/
native comparison complete. User explicitly approved updating the existing
fixture, testing and installing C17. All 171 repository + 63 focused checks and
44 real-native assertions passed: complete inventory/reasoning, query-program
load order, typed/quoted atoms, durable transaction/restart, failed-write recovery,
query isolation and cache freshness. The old mock-interface failures were fixed
in the approved existing fixture, not hidden in temporary corrected copies.
Exactly metta_server.py, metta_query_worker.py and tests/test_metta_service.py
installed. AtomSpace gracefully checkpointed/stopped; its existing watchdog
restarted pid 10666 as 50600. Same epoch, commit 6353, state hash, 7,940 atoms,
1,221 memory/state file hashes, seven tabs, music source and stable managed
generation preserved. C03 and request-budget helper hashes unchanged. All 171
tests then passed in the LIVE repository. The identical uncached full-view
Truth_Revision query took 7.679s before and 1.687s after. Thirteen resumed cycles
then measured 10.73–12.96s from components_loaded to model_wait, versus the prior
ten-cycle 26.09–26.69s sample. These are matching preparation phases, not whole
turns or proof of better decisions. First-cycle input-through-preparation was
19.05s including cold component work. Independent app success remains unproven.
No disabled learning, deferred durability, added authority, cache-policy change,
app edit or test atoms in live storage. Before-images, rollback helper and exact
installation/preservation record: /tmp/iterbrow-native-load-2xfOd6. All new tests/
logs remain in /tmp; only the approved existing fixture changed in the repo.
C02's ordering/reservation/deduplication experiments were rejected: they traded
away complementary evidence in the screenshot-heavy request. The installed
supplement instead carries an intact small recent observation when it fits the
EXISTING 4,500-character omitted-history index, with the old excerpt fallback.
No new memory, prompt, model call, selection classifier, larger token ceiling or
change to C03. Both exact failed-request replays now contain the complete
14:29:20 draft.v2 observation AND original notes; every other selected full
message is identical. Estimates: 42,609 -> 42,672 and 44,630 -> 44,578 tokens.
Tradeoff: fewer older excerpts fit that same index; durable history and the
separate working handoff are unchanged. This does not guarantee all historical
source fits every request or that the LLM will use the supplied evidence well.
171 repository + 63 focused regression checks and nine new index checks pass;
171 tests also pass in the installed repository. Only request_budget.py changed;
1,221 memory/state files, seven tabs, commit 6353 / 7,940 atoms, C17/C03, music
source and stable managed generation were preserved. No app reload or data edit
by Codex. C02's bounded four stages are complete: the initial resumed requests
at 15:14:13/15:14:52 carried exact current draft evidence and original notes
together. That older draft observation rotated out of the bounded window later;
broader long-span continuity remains open, not declared universally fixed.
Tests, negative experiments, exact before-image and installation record:
/tmp/iterbrow-shell-outcome-Y5otI8. No new test files or logs in the repo.

**Prior follow-up — September 25, 14:10: AUTHORIZED FEEDBACK-DRIVEN REPAIR.**
User explicitly approved reporting the failure and resuming Iter. At 14:05:32
Codex sent only: "User-authorized test feedback from Codex: An offline check found
that a valid unsaved note change to Moonlit Walk would be lost on reload and
replaced by the saved version. Please repair this without losing the existing
draft or saved song, then continue and finish the composer work." Exact text is
present once in the UI journal and once in received experience; the first actual
model request at 14:06:36 contains it under Luna/Low. UI running and child 28408
verified; stable d33f3be5 generation, eight tab entries, no missing baseline memory
files, same ready AtomSpace epoch at commit 6243 / 7823 atoms. C03 source still
matches. No code, location, implementation advice or solution was given. At
14:06:56 Iter identified its own broad stale-draft condition and acknowledged no
reload had been run with it. It located the startup code and independently patched
it at 14:08:59: detailed drafts take priority; existing storage entries are no
longer automatically rewritten on load. Syntax passed. Two offline checks of its
actual startup code now preserve the valid edited draft and reopen the saved-only
song without changing stored values. This is bounded source verification, NOT
full browser acceptance. Iter is doing its own reload/composer checks next.
The temporary hold is superseded, not the preservation requirement; this is a
feedback-driven trial, not unassisted. Delivery and startup-selection proofs:
/tmp/iterbrow-shell-outcome-Y5otI8/{feedback-verification,draft-repair-check}.json.

At 14:00 Iter added a startup rule classifying any differing
Moonlit Walk draft as stale, then replacing saved/draft storage with the older
saved song. An offline counterexample using the actual selection code confirms
a valid one-note unsaved edit is discarded. No real browser storage was read or
written by that test. This is a C04 app-regression counterexample, NOT a proven
runtime defect or C16 repair. Codex has not changed the app. The UI stop and child
exit were verified before sending the now-authorized feedback. Music acceptance
remains 3/4. Preserve all current drafts; do not restore an old song baseline or
quietly remove Iter's code. Continue observing its own repair and verification;
do not provide further implementation coaching or create idle paid turns.

User sent the composer feedback
directly at 13:31:51, including an invitation for creative additions, and asked
Codex to observe plus act on the C03 offline replay. Iter remains Luna/Low and
authors the application. It wrote a prompt box/chips at 13:34:31, acknowledged
the write, then described the feature as still missing after inspecting the
reference screenshot and wrote it again at 13:38:04. Read-only inspection finds
two composePrompt IDs and two composeButton IDs. The original successful edit
and its status report remained in the carried receipt window. C01/C04 therefore
have a concrete repeated-implementation counterexample, not just repeated reads;
do not assume omission is the cause. Iter reloaded the app at 13:41:20, observed
the duplicate textareas in its own screenshot/DOM, and independently diagnosed
them at 13:43:37. Its 13:45 cleanup attempt stopped before writing because its
own assertion found two remaining composeButton IDs; it then inspected those
buttons. This is useful self-checking, not yet successful repair. Codex supplied
neither the diagnosis nor app code. A compound shell command returned exit 0
despite that inner assertion failure; do not equate invocation success with repair.
Saved Moonlit Walk remains present; the draft differs, so do not overwrite it
from an older baseline. User changes and Iter work must be preserved.

C03 bounded correction is at **4/4: reproduced, repaired in workspace, offline
verified, installed stopped and verified in the live request**. The helper displays
the already-present payload head/tail from a matching outer retained-output
envelope, preserves the timestamp, exact result ID, original omission offsets,
execution facts and newer-than-account flag, and fits within the old serialized
excerpt size. No extra retrieval, file I/O, model call, authority, prompt, or
store. Unknown/malformed content and historical inner envelopes are untouched.
10 focused tests, 13 handoff checks and 234 combined regression checks pass.
Four actual captured-turn replays retained every previously included receipt
(12/12, 14/14, 15/15, 13/13), the same account and failure flags. This establishes
better representation, NOT improved behavior. User requested consideration of
pausing/installing; under the standing scoped maintenance authorization, Iter
was stopped through its UI and its child exit verified. Only
iter/iterbrow_runtime/working_handoff.py was installed, with exact before-image.
All 1,154 recorded state/memory files, eight tabs, AtomSpace epoch/commit 6183,
active generation and Iter's music source were unchanged during installation.
This is a host-helper restart, not a managed-generation hot-load: existing
heartbeat/rollback are unchanged; exact helper recovery is from the before-image.
Resumed Luna/Low without another task prompt. First live request at 13:49:20
preserved the exact account and original feedback and carried four payload-first
receipts with IDs and omission offsets. Generation d33f3be5 remains stable;
ready same-epoch AtomSpace advanced normally to commit 6190 after resumed work.
No music code or instructions were supplied by Codex. Its first repair attempt
still failed an assertion, followed by a fresh source read. At 13:51:20 Iter
removed both duplicate controls successfully (one input/button ID each, syntax
check passed) and reloaded at 13:51:49. This is actual resumed follow-through,
not proof that C03 caused it or that behavior is universally repaired. Live
composer interactions still need verification; music remains 3/4, acceptance open.

At 13:54 chip/Preview/Discard left saved storage unchanged, but Iter compared
the result with the saved song instead of the pre-action draft. At 13:56 it found
the separate draft, then inferred it was lossy. The 14:00:20 actual API request
contains the four relevant observation/account IDs and saved/draft/discard
evidence. Simple omission does not explain this instance. Its subsequent startup
change was written before a /bin/sh process-substitution error (C06 recurrence);
the following source/syntax check confirmed the write. The preservation hold
occurred before any observed subsequent music reload. Offline proof is in
/tmp/iterbrow-shell-outcome-Y5otI8/draft-counterexample.json. C01/C04 remain open.

New C15: the exact user prompt was retained, but Iter supplied "Codex (authorized
to act as the interacting user)" as the task's person. This is not a fabricated
incoming user message (the fixed C09 defect); it is a wrong LLM-supplied requester
label apparently carried from the earlier delegated trial. Investigate attribution
without guessing identities or rewriting history. At 13:41 the composer follow-up
recorded 17 responses / 456,105 tokens / $0.05935 estimated text cost, not invoice
or whole-build total. C16 offline investigation reproduced five cases using the
actual workspace shell tool: failed edit followed by a successful check, failed
dependent check, deliberate fallback recovery, benign failure text, final nonzero
exit. The shell reports the final command status faithfully; the SUCCESS headline
does not establish that earlier commands or the requested edit succeeded. The
failure text survives and task_fulfillment remains unverified. Iter subsequently
recognized its failed edit, so this is not proven to cause the repetition. Do not
introduce default fail-fast semantics or an English failure classifier: either
would change valid recovery behavior. No runtime or app code changed this pass.
Replay and actual-request evidence: /tmp/iterbrow-shell-outcome-Y5otI8.
Monitoring remains active. C03 evidence, exact helper before-image,
installation record, first-live verification, fixtures and logs are under
/tmp/iterbrow-c03-replay-xfhLnb. No application code was changed by Codex.
C15/C16 are new observations after the original C01–C14 batch, not silently
added installed repairs. Neither has a tested repair ready for installation.
The user explicitly asked about this distinction; no C16 installation is planned.

**Prior checkpoint — September 25, 13:28:** Read all 100 actual latest
user/assistant posts (68 user, 32 assistant finals, September 24 15:09 through
September 25 13:21), not compressed summaries. The scope remains: Iter authors
the app; Codex diagnoses and repairs runtime, with no app code or implementation
coaching. LLM meaning plus Iter continuity/observations, all existing memory,
AtomSpace/NACE, hot-loading, rollback, heartbeat, tabs and communication features
remain preservation requirements. No new governance or extra reasoning layer.
ACTIVE thread heartbeat `monitor-iter-music-build` remains every five minutes,
scoped to this music trial and runtime clues, not the historical broad rollout.
This supersedes historical "automatic follow-up paused" statements below.

At 13:20 Iter marked its music task complete; at 13:21 it reported completion and
entered `idle_wait`, listening for input without further model cycles. This is
Iter's claim, not independent full acceptance: music remains 3/4, with 4/4 user
workflow/interaction and audio verification open. Luna/Low, stable generation
d33f3be5, eight tab entries preserved, no missing baseline memory files, ready
same-epoch AtomSpace commit 6116 / 7686 atoms. Recorded post-C14 run: 64 responses,
1,628,176 tokens, $0.20890 estimated standard text cost, not invoice/whole-build
total. No new 15s action timeout was observed. Do not create idle paid turns just
for monitoring. Observe meaningful new input/actions and inspect captured evidence.

Real improvement: Iter performed New/Open, exact JSON import/export, proposal
Keep/Undo, MIDI/WAV blob/header checks, and independently repaired unkept-preview
Save/export isolation at 13:05. It corrected its /bin/sh process-substitution
error on the next action. Repeated episode retrieval still occurred at 12:56,
13:09 and 13:16. Fresh request inspection corrects the earlier hypothesis that
completed outcomes simply disappeared: those requests contain the LLM account
and recent successful checks. At 13:15:54 the 13:11 combined workflow result is
present alongside its account saying all disposable checks passed, yet another
original-song retrieval follows. This does not establish the cause is the model
alone; evidence presentation and the non-cumulative fallback account still need
analysis. C01/C04 remain open, without claiming all repetition is context loss.

C03 concrete remaining path: `working_context` excerpts raw retained-result
envelopes. A recent episode receipt's leading excerpt shows artifact metadata,
not the recalled event; its tail still contains escaped historical observations.
The separate decode-once episode fix does not cover this handoff excerpt path.
No speculative fix installed. Also, zero HTML audio elements is not proof that
Web Audio voices stopped; this is a verification-quality counterexample under
C04, not a demonstrated audio/runtime defect. C14's full eight-check live suite
has not been rerun; bounded timeout and installed metadata proofs remain valid.

User acceptance observation A1 (separate from runtime defects): native UI and
source confirm “03 · Compose with Iter” has no local text input. It directs users
to chat, and the separate Iter sidebar provides that input. The page exposes
song/proposal APIs, but that alone does not prove a discoverable end-to-end
conversation. User was advised to send the plain observation now, since Iter
is waiting rather than continuing discovery. Codex has NOT sent it, changed the
app, or supplied a fix. The next meaningful live comparison is how Iter handles
that genuine feedback without coaching, if the user sends it. Keep watching
while distinguishing user-facing gaps from proven runtime causes.

No runtime/app code was changed in this context-refresh/observation turn.
Evidence: /tmp/iterbrow-context-refresh-11ee9D (exact posts and handoff trace),
plus the existing eval-repair and working-handoff directories. Update this
checkpoint and the existing tracker only; do not create more control documents.

**Current follow-up — September 25, stage 4/4, C14 regression runner:**
Iter resumed Luna/Low after independently adding instrument headings and verifying the
exact Moonlit Walk notes survive a real reload. Music acceptance remains 3/4.
The LLM account refreshes correctly; repeated episode recovery still recurred at
12:34, so C01/C04 are not closed. Codex saved Iter's pending JSON export through
the native dialog into /tmp; this was a delegated user interaction, not app code.
Root causes: the aggregate regression suite was killed at the single-call 15s
ceiling; metadata parity used a nonexistent generation-local host entry point,
enumerated cwd rather than its generation, and silently skipped failed invokes.
User explicitly directed deadlines to support healthy production rather than
choke it. Workspace patch gives run actions 60s normally, composed/build actions
180s, preserves memory 75s/query 40s and metadata/transformation 15s. These are
ceilings, not waits; internal browser/AtomSpace 30s handlers can now return first.
Hard timeouts still kill owned worker groups, identify the operation, and report
possibly partial effects. Existing rollback/heartbeat/native NACE are unchanged.
Eval uses the canonical host with its exact generation, records invocation errors
and empty/missing fixtures honestly, and checkpoints per-check timing/progress in
its existing report. No new gate, prompt, service, memory authority or app changes.
Fourteen focused checks plus 234 combined regressions and 13 handoff checks pass
(261 total), including a real 15.5s worker, honest interrupted results and owned
hung-worker cleanup. Installed metadata checks load all 102 current-generation
components in 8.1s: 101 static comparisons, one supported shell-description dynamic
fallback, zero invocation errors or mismatches. Expected fallback is not failure;
actual mismatches still fail. Synthetic parser fixtures also pass installed.
The full eight-check suite was not rerun against live browser/embedding services;
do not equate the installed metadata checks with complete service health proof.
Stopped install preserved eight tabs, all baseline memory files, AtomSpace epoch
and commit 5961, and Iter's app source. Exact before-images are retained. Candidate
d33f3be5e5914a6c84890aa6412af361 replaces inert candidate 8fe85673; heartbeat and
rollback are unchanged. Restart carries the pre-pause account and newer receipts;
Iter attached its app and inspected the saved song without Codex app guidance.
At 12:49 it automatically promoted stable. All eight tab entries and baseline
memory files remain; only the active tab changed through Iter's own action. Same
ready AtomSpace epoch at commit 5970 / 7532 atoms; source matches the workspace
and the music app is unchanged by restart. Four post-install responses report
101,520 tokens / $0.01290 estimated text price (not whole-build usage or invoice).
Repair commit a16f6d9 is local only. This closes the bounded runtime correction,
not general continuity or full music acceptance. Next: observe Iter's remaining
music checks without coauthoring or coaching; C01/C04 remain open because its
latest account again says it is continuing checks already performed earlier.
Tests/logs/before-images: /tmp/iterbrow-eval-repair-5RtKLk.

**Approved meaning/continuity handoff — September 25, stage 4/4:** User approved
the pairing: the LLM supplies meaning; Iter supplies continuity and observations.
Stages: 1/4 trace (complete), 2/4 workspace implementation (complete), 3/4 combined
offline verification (247 checks passing), 4/4 installation and live handoff
delivery/refresh across restart (verified). Music acceptance remains 3/4; Iter is
running Luna/Low and performing its own remaining checks. This closes this bounded
handoff implementation, not the entire Continuity of Mind or music acceptance.
The implementation reuses explicit `pin(message, handoff=true)` notes in durable
experience, not another journal/database or task-registration side effect.
After ordinary transformations, the request carries the latest marked account
and a bounded factual view of subsequent tool results before old bulk captures
compete for space. If no explicit note exists, reuse the latest eligible LLM
communication, clearly labeled as fallback interpretation rather than a complete
work account. This reuses existing check-ins without requiring another tool call.
Recent observations from before the account remain visible too, so a new summary
cannot alone hide a recent counterexample; each receipt marks whether it is newer.
Same-response results are subsequent evidence even when an
action precedes the pin in dispatch order. Original user requests remain separate;
new input can supersede the account. Unmarked pins retain their old behavior.
No new reasoning layer, model call, approval, required phase, app code or coaching.
The account is revisable LLM interpretation, never proof or permission. Missing
accounts and projection failures do not gate ordinary work. Explicit new tasks
exclude previous accounts; existing lossless archives preserve their history.
Thirteen focused checks pass, including replay of the missing 11:05 edit in the 11:08
request with screenshot input and original composition still available under 45k.
First comparison: 17 reported responses / 16 completed action exchanges, 435,939
reported tokens, text-price estimate $0.05561. Iter reloaded its own app, verified
the corrected A/B/C/C labels and exact recovered song, created an exact /tmp copy,
then returned to episodic retrieval. No explicit handoff pins were written. This
motivated the tested fallback above, installed while stopped with exact before-image
and unchanged memory, tabs, AtomSpace and music source. The restart check verified
that the actual request carries the pre-pause LLM account and marks the first new
browser observation as newer evidence. Iter checked the apparently unlit roll,
inspected source and DOM, corrected its mistaken visual interpretation, and its
corrected report automatically replaced the old account in the next request.
At 12:15 it exercised New-cancel, New and Open on the isolated app copy: cancellation
preserved state; New cleared working notes without changing the saved entry; Open
restored the song and exact pattern counts. At 12:17 proposal preview/discard/keep/
undo preserved or restored exact saved storage as expected. At 12:18 its export
buttons generated JSON (4897 bytes), MIDI (255 bytes) and WAV (1107634 bytes), with
song data and format headers inspected. At 12:20 Play/Stop status and button reset
passed; lingering sound was not independently measured. Import observation returned
immediately after dispatching an asynchronous file event, so do not overstate that
as an independently proven round-trip. These are Iter-authored observations on an
exact isolated copy, not Codex-supplied application fixes. Main app source remains
unchanged by this comparison; broader user acceptance is still open.
Counterexamples remain: stale/poor LLM accounts and available evidence not producing
action. Iter re-read the original episode again at 12:16 despite the carried account;
C01/C04 remain open rather than treating this as universal behavioral repair.
Handoff transport is not proof of autonomous music-app completion. The more useful
result is actual progression through several previously unfinished workflow checks.
Managed generation fd5cd1517be14290a63ddaac56ceef3c promoted stable via normal
heartbeat; local-only commits ccafb6d and 5dca69f. No GitHub push or Codex app code.
12:23 preservation/usage snapshot: eight tab entries unchanged (Iter changed the
active tab during its checks), no baseline memory files missing, same ready Hyperon
epoch at commit 5910 / 7469 atoms, all six installed files match workspace, and
music source remains c191157d10c24b35a048e99b02d7a3a10d0922f0b29a7e601a15019bbaf5b3b9.
These two handoff comparisons report 1,018,926 tokens / $0.13059 estimated standard
text price through 12:23, not a whole-build total or invoice. The refined run
contributed 582,987 tokens / $0.07498. Iter recorded its repair/verification task
complete at 12:22; that is an Iter claim, not independent full music acceptance.
Iter remains running Luna/Low; automatic Codex follow-up remains paused.
Tests/logs/before-images: /tmp/iterbrow-working-handoff-0U4PfP.

**Approved full batch, September 25 — stage 4/4, partial runtime improvement:** User authorized all-clue review,
workspace repair, combined offline verification, then one installation/comparison.
The controlled comparison ran 10:46–10:53 on Luna/Low and was paused again:
14 responses, five source reads, four progress messages, zero app edits.
Browser capture/targeting worked; autonomous follow-through did not. Automatic
follow-up remains paused. After full-suite revalidation, the source-continuity
supplement was installed stopped. The bounded repeat ran 11:04–11:11: its FIRST
response edited the app, but later turns again returned to retrieval instead of
verification. Iter is STOPPED again (PID 38170 exited). The stable managed
generation is unchanged. The last 50 actual
conversation posts were read before this pass. Earlier subset installation was
not full-batch completion. No music-app code or coaching is part of this pass.
Baseline: eight tabs, 987 memory/state files, unchanged 27,016-byte music source,
AtomSpace epoch 92d6e63a-6331-4cc8-9072-df8fdbbfa232 at commit 5749, stopped child.
Tests/before-images/replays: /tmp/iterbrow-batch-WmIKla. One control document only.

| Clue | Full-batch disposition | Verification / remaining limit |
| --- | --- | --- |
| ☐ C01 repeated recovery | Bounded loss repairs and meaning/evidence handoff verified; broader clue open. | Retrieval repeats even when the latest account and successful checks remain visible. Do not attribute all repeats to missing context. |
| ☐ C02 context turnover | Small-observation supplement installed and observed live; 243 checks pass. | Both failed-request replays and initial resumed requests preserve exact current draft evidence plus original notes. Older index excerpts trade off, not durable memory; later rotation and broader long-span continuity remain open. |
| ☑ C03 evidence-presentation repair | Decode-once episode repair and payload-first outer-envelope handoff correction installed, loaded and verified. | 257 offline checks; four replays preserve prior receipts/account/failure flags; live request carries corrected receipts. Historical inner records are not rewritten. Repetition remains C01/C04; that does not reopen or unload this bounded repair. |
| ☐ C04 inspection/follow-through | Current app recovery passes three bounded offline startup cases; full app acceptance open. Latest health requests reach model but receive old-task answers; new ditty request appears in delivered screenshot yet historical retrieval repeats. | Composer input currently drives local keyword previews, not Iter chat. Separate app integration gap from runtime delivery; C05 screenshot bytes verified at 17:30/17:31. No Codex coaching or app code. |
| ☑ C05 image/recall mechanics | Original transport defects repaired and verified. | Valid image, missing/empty capture, retry, ordering and clipping regressions pass. |
| ☐ C06 platform mismatch | Actual macOS/shell/cwd reaches Iter; no command rewriting. | Wrong /bin/sh process-substitution syntax recurred at 13:05, 14:00 and 15:17:27. A nonzero compound-command exit does not establish whether an earlier edit ran; inspect the actual result. |
| ☑ C07 requested result fragmentation | Bounded explicit retained-page and consecutive-source transport verified. | Broader accumulated meaning is tracked under C02; historical captures are not current source. |
| ☑ C08 continuation boundary | Explicit optional new_work flag; continuing work preserves history. | Successful new goal archives losslessly; failed commits cannot advance the boundary. |
| ☑ C09 false human attribution | Origin correction verified; no history rewrite. | Runner, legacy controls and genuine user quotations remain distinct. |
| ☐ C10 retrieval mistakes | Canonical identifier/format hints verified; Iter corrected its wrong composer-ID diagnosis unaided at 15:15:41. | Wrong draft.v1 key previously recurred despite actual draft.v2 in source. Broader recurrence remains open; no guarantee the LLM uses supplied facts correctly. |
| ☑ C11 incomplete browser errors | Bounded diagnostic installed, offline-verified and now observed live. | At 14:17:26 the actual null-title TypeError and file location accompanied the failed evaluation. Errors without console detail remain generic and honestly labeled. |
| ☑ C12 capture/target mismatch | Display and agent target align; empty capture fails with context. | Live reference screenshots succeeded; human switching and locks preserved. |
| ☑ C13 recovery-tool starvation | Essential recovery tools discoverable; fair probes for other tools. | Live schemas and successful switching verified; native NACE and human locks unchanged. |
| ☑ C14 aggregate regression timeout | Operation-sized deadlines, truthful metadata checks and incremental reports verified. | 14 focused checks and installed 102-component diagnostics pass; full eight-check live service suite remains unrun. |
| ☐ C15 requester attribution | Genuine new user prompts retained; Iter again supplied person=Codex when re-registering the old task at 17:25 and 17:28. | These notices are not new Codex instructions. Inspect how prior delegated identity is reused. No incoming-message fabrication or authority change demonstrated; no speculative identity rewrite. |
| ☐ C16 compound-command outcome | Five offline cases reproduce ordinary final-command exit semantics; failure text and unverified fulfillment survive. | SUCCESS wording can mislead, but Iter did recognize the failed edit. No proven runtime execution defect or causal link to repetition; no classifier, forced fail-fast mode or live change. |
| ☑ C17 native reconstruction cost (bounded loading repair) | Native parse/add installed with approved existing fixture update; all 278 offline checks/assertions pass, plus 171 installed repository tests. | Identical native query 7.68s → 1.69s; live preparation phase 26.1–26.7s → 10.7–13.0s. Exact durable state/memory/tabs/app preserved during installation. Faster runtime, not proven autonomous app success; no learning/durability bypass. |

No hidden abandonment: the residuals above are stated limits/live acceptance
questions, not claims of repaired autonomous behavior. All 171 repository tests
and 60 focused image, memory, retrieval, origin, task, browser and projection
tests passed. Eight runtime source files installed; the five managed components
are candidate-b1632d1598474ae9b04a7dc9ef012a60. Before resume, source restart
preserved all eight tabs, all 987 baseline files byte-for-byte, AtomSpace epoch/
commit/state hash and music source. Stage 4 is one controlled Luna/Low resume,
checking actual inputs/actions and preservation; pause on a repeated blocker,
do not drift into endless isolated patch/restart cycles. Music build stays 3/4.

Follow-through counterexample returned to offline work, not paid observation:
keeping every repeated source read requires 52,244 estimated tokens and is not a
valid repair. Three complementary reads plus the original notes/recent actions
fit at 38,614 before the omission index, yet the old selection still previewed
the first read. The bounded recent-observation expansion fixes that exact case.
All 171 repository + 63 focused tests pass together. Source supplement installed
with exact before-image and unchanged memory, tabs, AtomSpace commit and app source;
no new prompt, store, native reasoner or provider-specific change.
First comparison reported 318,555 input + 3,002 output = 321,557 tokens; recorded
text-price estimate $0.03143, not a final invoice or whole-build total.
Repeat: 321,120 input + 3,794 output = 324,914 tokens; estimate $0.03034.
Both comparisons total 646,471 reported tokens, estimate $0.06177; excludes
Codex, canceled/unreported responses, embeddings and other services.
Iter's own 11:05:11 edit remains saved: 27,349 bytes, SHA-256
c191157d10c24b35a048e99b02d7a3a10d0922f0b29a7e601a15019bbaf5b3b9.
Final preservation: exact eight-tab session, no missing baseline memory files,
same ready Hyperon epoch, commit 5818 / 7372 atoms, generation stable. Runtime
sources match workspace. Commits 62422ef and bed7451 are local; no GitHub push.

User's continuity distinction: durable events are not yet a coherent working
account of intention, actions, observed outcomes and remaining gaps. The LLM
should do the interpretation; Iter should preserve/present it with evidence and
contradictions. Existing 17 question groups need that context. This is a design
observation, not authorization to add a journal/reasoning layer during this batch.
Existing-path diagnosis: current_tasks.txt still carries the 08:10 request,
not subsequent outcomes; last music task-phase note is September 24 23:07.
task_state note is capped at 200 characters; pin only leaves an episodic note.
Recap signals and injects summaries but leaves their authorship to the LLM.
Requested user decision: reuse existing durable task memory for an LLM-authored,
evidence-linked working account carried into relevant turns, or continue
diagnosis without that behavior. No such behavior is installed. No third run.

The user authorized a new four-stage trial: Iter creates an original music browser
tab/app, inspired by https://github.com/yurisizov/boscaceoil-blue. Keep the reference
interface; give Iter full creative control over surprising useful features and
real music-making interaction with Iter. Godot is already installed and is an
available choice, not a required implementation. Minimum result: create,
save/reopen, and export a short song. Codex is authorized to act as the interacting
user while the owner sleeps, not to author the app on Iter's behalf.
The user subsequently directed persistence through failures: log, diagnose,
repair and rerun until the app exists and the agreed build succeeds. Keep Luna;
Low is preferred. Distinguish runtime repair from Iter's application authorship.
Latest role clarification: Codex observes confusion/repetition as runtime clues,
reproduces and repairs underlying runtime defects, and does not coach Iter through
the application task or supply its implementation. No further app guidance is to
be sent to compensate for a runtime failure. App acceptance remains independent.

| Stage | Required evidence | State |
| --- | --- | --- |
| 1/4 brief and baseline | Preserve existing tabs, memory and recovery; send outcome brief without a prepared implementation. | Complete: 3 tabs, 33 cards, 672 memory/state files captured; same stable generation and ready AtomSpace at commit 5067. Request received. |
| 2/4 Iter creates | Iter researches the reference, selects its approach and builds/opens the new tab. | App exists; reference-interface acceptance still incomplete. Low baseline, Medium/High comparisons completed; preferred Low restored. |
| 3/4 make music together | Actual editing/playback and creative features; user-style musical revision through Iter. | Paused, incomplete. Original composition was recovered; Iter independently edited labels and New/Open cleanup at 11:05. Fresh loaded behavior and remaining workflows unverified. |
| 4/4 continuity and handoff | Song save/reopen/export, revision/undo or recovery, source/data ownership and comparison with request. | Pending |

### Historical investigation notes — current dispositions are in the table above

These notes retain the earlier investigation evidence; they are not a second
active tracker. The current C01–C17 table above governs status. A checked item
means its bounded defect is verified, not that the music app passes.

- [ ] **C01 — Repeated recovery of the same information.** Trace why acquired,
  acknowledged evidence is requested again. Close with observed continuity into
  the next action, not merely proof that the record exists on disk.
  Captured 09:33:23 post-reload snapshot matches the original title, tempo, key,
  bars and every note triple. Recovery-to-edit happened; broader recurrence open.
- [ ] **C02 — Large context turnover.** Trace which evidence is displaced by which
  material; 110 historical messages were omitted in one request. Close with a
  demonstrated correction or evidence that the suspect omissions are harmless.
  **Specific correction verified:** generic filename labels (proposal/notes/etc.)
  no longer count as subjects. Actual selected memory falls from 21,949 to 5,951
  characters; old socket-repair prose no longer appears in the fresh request.
  Named-topic recall, current task, standing preferences and omitted-file index
  remain. Overall working-evidence turnover is still open.
  **Second correction installed:** keep distinct explicitly requested complete
  captures together when they fit; omit redundant older pure reads of that same
  immutable capture from request copies. Three real replays retain formerly
  displaced notes alongside source at 43,143–44,088 estimated tokens. Five focused
  tests preserve pointer selections, action groups, original history and oversized
  manual paging. Live 09:43–09:45 requests carry multiple complete requested
  results under 45k. No new store, summary call or higher token ceiling.
- [x] **C03 — Observations wrapped inside observations (bounded repair verified).** Quantify nesting and
  escaping in episode/tool-result retrieval and locate unnecessary inflation.
  **Specific correction verified:** loaded episodes reader decodes the storage
  quote layer once into timestamped historical text, preserving original tool
  arguments exactly. Real five-record replay falls from 8,515 to 8,193 chars and
  373 to 95 backslashes. This is readability, not a large token-cost reduction.
  Existing retained copies are unchanged; broader nested-observation recurrence
  remains recorded as a limit, not an uninstalled repair. The later payload-first
  handoff repair was installed and live-verified at 13:49; see current C03 row.
- [ ] **C04 — Inspection without action.** Trace actual inputs between stated
  repair intention and next action. Higher Luna effort has not resolved it.
  Iter edited its app at 09:28 and 09:36, then began disposable workflow checks.
  Its localhost test URL served NodeQuest instead of the intended app; this is
  an unresolved test-setup observation, not a successful music-app test.
- [x] **C05 — Mechanical screenshot/recall failures.** Image budgeting and mixed
  result ordering repaired with live image delivery; episode clipping removed
  with complete original note data reaching the request. Broader recall is C01.
- [ ] **C06 — Platform mismatch.** Inspect environmental context behind use of a
  Linux-only file-listing option on this Mac. **Information gap corrected:**
  fresh tool schema now gives macOS, /bin/sh and canonical cwd; candidate
  candidate-c2d4571c4ce246afabd049b870271a2a promoted stable at 09:08:23.
  Shell execution/memory guard unchanged. Behavioral recurrence remains watched;
  lack of host facts is not proven the sole cause of the incompatible command.
- [ ] **C07 — Explicitly requested retained text stays fragmented.** Reopened
  for accumulated source observations; explicit reader restoration remains sound.
  One-file
  host correction tested in captured-source replay; live 08:55:36 request expands
  reader call call_yjx5OzO89wnus5hdamUDTreY to the complete 17,158-character result
  with eof=true, within 43,142 estimated tokens. Does not close C01/C04.
- [x] **C08 — Continuation treated as a new history boundary.** Explicit optional
  new_work installed; legacy/default registration preserves the existing boundary.
  Tests cover actual user matching, failed commits, continuation and lossless
  archival of explicitly separate work. Loaded live schema advertises the flag.
- [x] **C09 — Runtime controls recorded as human messages.** Reproduced in history
  logger; respect runner identity/shared control recognition, preserve genuine
  human quotations, and label legacy controls in the recall view without rewriting
  history. Three origin tests, three exact-recall tests and 171 repository tests
  pass. Candidate candidate-e5f1308a8eaf4e4aa840ab7c72c5148d promoted stable.
  Loaded reader correctly labels legacy controls; 85 legacy records identified,
  zero newly misattributed controls after 08:58. Stored history and periodic
  status check-ins are unchanged.
- [ ] **C10 — Retrieval identifiers/pointers misused.** Observed a mixed-up
  retained-result ID and literal /key applied to non-JSON output. Existing reader
  reports failures and accepts original tool-call IDs. **Misleading hint fixed:**
  new captures identify the actual original call, say to omit pointer for plain
  text, and preserve existing-field JSON selection. Fresh 09:28 request confirms
  the corrected hint. No fuzzy identifiers or substituted observations. Watch
  actual retrieval behavior before closing the broader clue.
- [x] **C11 — Browser evaluation hides actionable error detail (bounded repair verified).** Failed page
  evaluation returns only “Script failed to execute … check the renderer console.”
  Shell syntax errors have actual error text; browser errors do not. Investigate
  preserving the original exception detail, without changing what Iter executes.
  **Installed September 25 09:54:** a bounded console observer supplements generic failures,
  labels concurrent console errors as observations rather than proven causes,
  and leaves execution/results intact. Nine browser checks (including capture
  diagnostics) and 171 repository tests pass. Actual failed-evaluation delivery
  was initially unproven. The 14:17:26 live null-title exception supplied that
  missing evidence; see current C11 row.
- [x] **C12 — Reference-tab capture failure.** Closed by live existing-reference
  switch/capture at 10:47:45 and valid model delivery at 10:48:07. Earlier evidence:
  At 09:13 a screenshot of the newly
  navigated reference-image tab failed with “Current display surface not available
  for capture”; the same failure recurred at 09:31:31, while app-tab capture works.
  Attachment changes only the tool target; inactive views are removed from the
  window's view tree. This supports, but does not yet prove, an unrendered-surface
  cause. Distinct from C05's repaired image transport. Installed failure diagnostic
  reports target/displayed tab and attachment to the window. It does not switch
  tabs, claim capture works, or change successful screenshots. No tab was switched
  on Iter's behalf to mask this failure.
  **Further defect reproduced and repaired at 10:09:** reference capture returned
  zero bytes but was marked successful. Its empty base64 payload caused repeated
  model-request rejection. Iter was paused again. The capture tool now rejects
  empty/malformed bytes before saving a success marker; image preparation turns
  the existing zero-byte record into an explicit unavailable/empty observation.
  Nine image and three boundary checks pass; replay uses the exact failed file,
  preserves history, and sends no model requests. Candidate
  af84871a75d7486eaea61690f388b0e0 activated; first resumed response attached to
  tab 4, then navigated to the app. Request rejection is no longer blocking those
  actions. Native reference capture remains unverified, so C12 remains open.
  **Live recovery at 10:11–10:13:** diagnostic explicitly reported target tab 4,
  displayed tab 7, target not attached to window. Iter independently opened tab
  8 with the app; its 384,460-byte capture reached the 10:12:48 model request
  intact. No coaching or operator tab switch. This confirms a useful diagnostic
  and a valid post-repair image, not reliable capture of the existing reference.
- [x] **C13 — Hidden-tool retry starvation.** Closed by fair-probe tests and
  live observation-tool visibility/use. Earlier evidence: browser_switch_tab was loaded but
  hidden after three historical calls (one success, two failures). The periodic
  probe always chose highest-scored eval, starving other candidates and allowing
  unloaded names to consume probes. Two failing tests reproduced both errors.
  Fair rotation among loaded eligible candidates passes four tests, preserves
  beliefs/protected tools/native dispatch, and is installed in candidate
  e198c1b7aa7b49df890fd969c5380724, promoted stable at 09:56:30. Live probe state
  advanced to a different eligible tool. Actual switch-tool visibility/use is
  still unverified; tool
  availability is not itself proof of a successful switch or screenshot.

- [ ] **C14 — Aggregate regression tool timeout.** In the handoff comparison,
  `eval(test_name="all")` failed at the ordinary 15-second tool limit. It runs
  multiple tests, including external search and memory lookup, in one invocation.
  Exact slow subtest remains unisolated. Iter distinguished timeout from a proven
  app defect; no blanket timeout increase or unrelated repair was installed.

**September 25 09:55 consolidated runtime checkpoint:** At the user's suggestion,
Iter paused for one offline multi-clue pass. Working-evidence retention had just
been installed and verified in live requests. Browser-error/capture diagnostics
and fair tool-probe rotation were then tested and installed together. The single
source Electron app was quit and restarted with Iter stopped; all seven tabs,
baseline memory files, music source hash and AtomSpace identity were verified
preserved. Iter resumed its same unfinished task on Luna/Low; no new task or chat
coaching was sent. Managed candidate e198c1b7aa7b49df890fd969c5380724 promoted
normally. C08 remains explicitly unrepaired: no
text-guessing boundary rule or new administrative workflow was added. Exact
before-images and handoff evidence are in /tmp/iterbrow-music-foundry-wRh7S2/
consolidated-runtime-repair. Combined checks: 171 repository, nine browser,
four retry-rotation, five working-evidence and existing image/recall regressions.
Live outcomes, not test counts, determine clue closure and app acceptance.

**September 25 10:10 empty-capture follow-up:** The resumed batch exposed a
zero-byte screenshot poisoning requests, not a model-choice failure. Paused,
reproduced and tested the two managed-file correction described under C12;
installed with exact before-images in /tmp/iterbrow-music-foundry-wRh7S2/
empty-capture-repair. No Electron restart, history rewrite, new chat instruction
or app edit. Same seven tabs, all baseline memory files, AtomSpace epoch and
27,016-byte music source hash verified preserved. Luna/Low resumed under normal
heartbeat/rollback supervision; candidate af84871a75d7486eaea61690f388b0e0 promoted
stable at 10:10:01. The first already-pinned old-generation cycle retried the bad
image once; no such rejection observed from the repaired generation. Fresh model
responses, browser actions and a valid new screenshot followed. Sustained app
completion remains unproven. Repository regression result: 171/171 (socket fixture requires its
normal local-socket permission); focused image/boundary/working-evidence/reader
checks pass. Do not equate repaired API input with completed app acceptance.

Iter-authored application progress: two edits at 09:28 and 09:36, now 27,016
bytes, followed by a reload observation matching the original composition.
Full save/reopen/export acceptance remains pending. The temporal association
does not establish which runtime correction helped. App-revision status rejected
the unregistered standalone app; Iter independently used ordinary source editing,
so that isolated error is not currently a runtime gate. Its test localhost URL
served a different existing app; no correction or test implementation supplied
by Codex. Observe follow-through after this consolidated resume.

**Active claim:** This is a test of Iter building, not Codex building. Luna/Low is
the baseline. Existing continuity repairs and normal tools remain in place; no
new governor, question layer or approval ceremony is part of this trial.

**Unresolved:** App at iter/apps/music/index.html opens in a local-file tab.
The Low version substituted binary rows/canned edits, then added cumbersome pitch
grids and technical proposal copying. Medium repaired pitch labels, removed the
copy/paste burden and actually composed/saved Moonlit Walk (78 BPM, C4-E4-G4 rise,
quiet bass, answering phrase). Codex has authored no music-app code. The editor
still stacks 100 pitch rows; arrangement labels include a blank pattern; safe
New/Open, unsaved-proposal isolation, Stop and actual exports remain unverified.
Iter's undo check restored the earlier song, then manually reinstated saved JSON
before Open; this is not a full user recovery proof. Codex paused Iter briefly for
UI checks, then resumed with concrete outcome feedback at 23:38. Native Play/Stop
changed accessible state, but screenshots were stale and later desktop capture
failed explicitly. The song export reached a Mac save dialog with disabled Save;
Codex canceled it. No export file or audible playback is claimed yet.

The browser_click tool was vetoed by a manual quarantine in the September 14
capability lifecycle seed (predates this trial); Iter used its exposed music API.
No quarantine or NACE guard has been changed. The two-file screenshot transport
repair below is Codex-authored runtime assistance, not music-app implementation.

Research/tool observations: irrelevant academic web-search results twice; invalid
retained-memory JSON pointer corrected independently; shell syntax misuse twice
corrected independently; initial URL 404 corrected independently. Later LTM search
found prior Godot project/export details; executable still unverified. Source
checks do not establish reference-interface research. All Iter model responses
are captured for final input/output/cached-token and estimated-cost accounting;
that accounting does not include unmeasurable Codex-session cost.

**Counterexamples:** An embedded original, generic mockup, silent transport,
lost song on reload, fake Iter collaboration or an app finished by Codex fails
the intended proof. Any platform repair/operator assistance must be identified.

**Next dependency:** Iter completes the revision and requested music, then actual
editing, audible/export evidence, durable reopen and undo/recovery. Evidence and temporary checks
stay in /tmp/iterbrow-music-foundry-wRh7S2; this remains the one control document.

**Paused repair checkpoint, 23:45 onward:** Three captured heartbeat errors show
screenshots rejected as roughly 197k-202k text-token estimates. browser_vision
deleted the PNG before request projection/call success; retries therefore carried
only a captured notice, not pixels. Two sandbox fixes separate typed image budget
from text bytes and retain temporary screenshots across retries without attaching
them after a later assistant response. Six focused checks and 171 repository
checks pass (socket test required normal local-socket permission). Inactive managed
candidate: candidate-e103869b1d5340f1806a4a1bea301ca6, validated.
Exact before-images, patch, baseline failures and handoff script are under
/tmp/iterbrow-music-foundry-wRh7S2/vision-repair/. Mac lock initially prevented
resume; the user confirmed unlock on September 25. The paired patch was installed
with Iter stopped, then the existing child was started and the managed candidate
activated. The supervisor promoted it after real cycles at 08:10:56. Source hashes
match the tested patch; no baseline memory files are missing, all five tabs remain,
and AtomSpace epoch is unchanged. Desktop capture works. Read-only usage
observation resumed.

**Live retry and correction, September 25:** The first fresh screenshot, between
two other tool results, exposed another transport defect: its synthetic image
message split the tool-result batch and failed exchange-integrity validation.
Stopped Iter; reproduced all batch positions and multiple-image cases. The
transformation now appends image context after the complete tool-result batch.
Eight focused tests and 171 repository checks pass. Managed candidate
candidate-3ecffdad376d4228b6f142df6b405272 was activated and promoted at 08:17:31.
Actual requests at 08:17:05 and 08:17:48 each contain one image in api_request,
and Luna returned successfully. The earlier capture remained available for retry.
No app code or durable experience was edited by Codex. This is live transport
proof, not app acceptance or proof of effective visual reasoning.

**Exact recall correction, September 25:** Iter found the original proposal with
episodes, but that tool silently clipped each history line at 500 characters.
Several subsequent pages retrieved already-truncated records. The full original
event remained in history.metta. Removed only that local clipping; the existing
retention/paging service still bounds model-visible results. Three focused checks
cover the actual song record, long Unicode archived records through exact paging,
and unavailable-time honesty; 171 repository checks pass. Candidate
candidate-525f3463bd48424b904b76b07d69b00b was installed and promoted at 08:26:26.
The fresh 08:26:08 outbound request includes the original final note-event data.
Memory contents were not rewritten. Codex notified Iter that old retrieval copies
remain truncated and to reread the same timestamp; this assistance is explicit.
The music app remains Iter-authored and not yet accepted.

**Additional song counterexample:** Iter's 23:45 storage inspection returned the
saved title/tempo/bars but no roll array. Source apply() loads roll separately,
then autosaves state without attaching it; this can erase exact pitches/lengths
after reload. Earlier save/reopen success was overstated. The exact original
Moonlit Walk proposal remains in captured tool history, so recover those notes
and have Iter repair persistence; do not reconstruct them from boolean steps.

**Resume sequence:** Installation, stable promotion and real outbound image
delivery on Luna are verified. Continue the resumed music task, with
the original proposal and remaining user-experience requirements intact. Return
to Low preference after the comparison. No extra governor or prompts are needed.

**Effort comparison checkpoint:** Stopped Luna/Low after repeated source inspection
and no app writes for roughly ten minutes. The paused actual API request retained
the musical brief, no-copy/paste requirement and relevant editor/save/proposal
code; its reasoning effort was low. This rules out complete request loss, not
all context-quality problems. Captured Low accounting: 58 responses, 1,249,785
input and 22,848 output tokens, estimated USD 0.16089505. Source, last prompt and
experience preserved under low-paused/. Trial resumes with the same Luna model
at Medium effort, unchanged source/task and no new coaching prompt, using the
user's previously permitted effort comparison. No Codex app implementation or
runtime repair was installed. Separate effort costs and any unreported usage
must remain explicit; do not call this a controlled fresh-task comparison.

**High effort comparison, September 25 08:34:** Even after screenshot/recall
repairs, Medium repeatedly inspected/retrieved without editing the app. It
invented a retrieval ID from a text hash and used an invalid /text pointer, then
reported the original payload unavailable although it had reached its request.
Stopped, preserved app/experience/last request under medium-paused/, and changed
only the existing Luna effort selector to High under the user's earlier permission.
Restarted the same task without additional coaching; app source remained 25,003
bytes, last modified September 24 23:25:22. Before High: 133 captured responses,
2,785,633 input + 51,229 output = 2,836,862 tokens, estimated USD 0.34326703.
Medium portion: 75 responses, 1,564,229 total tokens, USD 0.18237198.
Low is still the user's preferred final setting. Comparison is not a clean
fresh-task experiment; prior work and runtime fixes must remain explicit.

**Requested-source visibility repair, September 25 08:47:** The request projector
could restore an original retained result, but not a `read_tool_result` raw-text
page. Thus explicitly rereading source did not give that source the same priority
as an older retained observation. Offline replay of the actual 08:37:16 request
reproduced this; the repaired copy includes the complete requested source within
44,973 estimated tokens, prioritizes the reader call, and leaves saved experience
unchanged. Three focused tests (including wrong identity/hash, missing capture,
exact Unicode text, size fallback and pointer isolation) and 171 repository tests
pass. Installed only host `iterbrow_runtime/tool_results.py` with the child stopped
and exact before-image in /tmp; restarted the same task with no coaching message.
AtomSpace epoch, five tabs and all baseline memory files are preserved. This
proves the runtime correction in replay; fresh 08:55:36 outbound expansion also
verified a complete requested result. Independent application follow-through
remains pending. High remains the comparison effort;
Low remains the preferred final setting. No app source edited by Codex.

## Previous checkpoint — continuity repair verified; PWQ delivered with operator assistance, September 24

The approved four-stage continuity pass has finished its scoped verification. Iter
is stopped, Luna/Low remains saved, and no further paid trial is queued. The actual
history-loss defects are repaired; this does not establish complete long-term-memory
health or fully autonomous delivery. Continuity of Mind remains foundational.

| Stage | Actual result |
| --- | --- |
| 1/4 trace and reproduce | Complete. Inherited destructive rotation, runner/input confusion, memory-topic loss and evictable retained observations were reproduced. Upstream was comparison evidence, never imported code. |
| 2/4 sandbox repair and checks | Complete. 171 repository checks, 19 focused checks and all 75 captured-turn replays pass. Initiating input survives; projected requests remain within 45k. |
| 3/4 install, restart and preservation | Complete for the scoped repair. Three host files installed; existing lesson matches authoritative and search storage. A later full desktop restart preserved all 670 memory/state files exactly and the same AtomSpace epoch. |
| 4/4 Luna PWQ rerun and acceptance | Feature passes with explicit operator assistance. Luna/Low authored the missing Electron connection and its own tests; Codex performed the desktop restart and actual disposable-card button checks. Unassisted activation/full acceptance and reusable lesson formation remain unproven. |

**Active claim:** On this rerun, Luna/Low independently added Archive/Restore to
Electron's PWQ command connection, ran 22 focused tests and a disposable lifecycle
test, and inspected the live board. It then repeated activation inspection. Codex
performed the already-authorized desktop restart; no new task prompt or diagnostic
coaching followed. Iter resumed the same work, probed the running command safely,
recorded task completion and went idle. Its conclusion exceeded its actual UI
testing. Codex separately verified Archive, reload persistence, Restore, approval
without completion, Mark done, Completed membership and absence from Waiting after
reload using one labeled disposable card. All 32 original cards are unchanged;
the disposable record remains Completed with all five journal events and history.
No PWQ feature implementation was authored by Codex.

Live continuity evidence preserves all 89 baseline messages and 59 observed new
messages exactly in current experience plus three earlier-history archives. No new
tool observation was blanked. The initiating request appears in all 30 captured
outbound requests, including after restart; all stay below 45k. There were 29
recorded responses (one extra request was stopped), 594,004 input / 7,805 output
tokens, 140.68 API seconds and estimated text-token cost $0.0712188. This is neither
an invoice nor a controlled attribution of the improvement to one repair. No model
upgrade was used. The stable generation remains candidate-29d719b85a3d45cfa5d7288ae0f4b05d;
AtomSpace is ready at commit 5067 with the same epoch. Three tabs returned; Google's
page-generated URL parameter changed. No baseline memory files disappeared.

**Continuity defect, reproduced offline:** At 20:40:13 the original conversational
user message was absent from the outbound conversation history. Its request text
still appeared in the current-task system projection; intent was not wholly gone.
History had lost both the real user input and start_new_task marker through the 100-to-80 message
rotation. active_work_start then selected a temporary runner directive as the
work boundary. A small reproduction with identical observation and ample budget
expands that observation when the real request is present, but never calls the
restore reader after the request rotates out. Subsequent prompts carried two or
three recent exchanges; automatic expansion was zero. Later working history had
37 tool observations reduced to [TRUNCATED]. Persistent storage elsewhere does
not make this loss of active continuity acceptable.

**Unresolved / counterexamples:** Exact storage and improved continuity do not prove
that memory is always recalled or applied. Existing episodic tiers remain stale,
and no new reusable semantic lesson was observed in this rerun. Operator help was
needed for activation; Iter did not perform the complete real-button test. The
shutdown exposed an unfixed terminal callback error: termEmit tried to send after
the sidebar was destroyed (main.js:1710); dismissing its dialog allowed exit with
memory intact. PWQ's "all active" label still includes terminal cards. Verified
completion moves a card correctly, but automatic correspondence between arbitrary
task_state completion and its PWQ card was not demonstrated. Earlier missing
observations are not reconstructed by this repair. No new question set, approval
gate, provider-specific workaround or separate memory/governance system was added.

**Next dependency:** Address the now-explicit completion/activation and existing
memory-recall gaps in a separately bounded continuation; do not declare the whole
restoration or autonomous foundry complete, and do not add another governor or
question layer. Fixing the terminal shutdown callback is a small distinct repair.
Do not restart another paid PWQ trial from this checkpoint automatically.

**Installed continuity repair:** Changed only iter.py,
request_budget.py and tool_results.py. Exact active experience now survives the
old rollover; earlier task history is archived before rotation. Temporary runner
messages are distinguished from human input. Existing task context supplies memory
selection when legacy history lost the input. A bounded factual observation index
exposes omitted work in request copies, while retained results survive cache eviction
in the existing private memory/archive tree. No new reasoning service or prompt
question set was added. Three-cycle status participation is unchanged.

**Evidence:** 171 repository tests and 19 focused continuity checks pass; the earlier
same-task clarification counterexample is fixed. All 75 captured PWQ turns replay
with their initiating request preserved and requests within 45k (2.85s total,
maximum 0.10s per projection; no model calls). The installed files match the tested
bytes. All 513 baseline memory/state file hashes, three tabs, 32 PWQ cards, settings
and AtomSpace epoch are unchanged; service ready at commit 4987. Before-images,
patch, checks and replay evidence remain in /tmp/iterbrow-continuity-HGNEVm.

**Counterexamples / limits:** These checks do not prove live follow-through or
restore observations already blanked by the old code. Long active histories may
still affect preparation outside the measured projection. Existing episodic recap
staleness remains a distinct gap, not silently solved by exact-result retention.
The scoped live rerun above is complete; the listed limitations remain open.
Continuity source milestone: local sandbox commit 3aea252. Iter-authored PWQ
source is retained separately, including its earlier Archive/Restore work.

**Upstream comparison:** Inspected patham9/iter at
f4064d97849ecaccac7939315a3f1a68de15c3ef (August 24, 2026). Its direct
receive/context/model/tool/result loop remains the relevant baseline. Its actual
cleanup code, exercised offline on 131 messages, drops the initiating request and
blanks 35 surviving observations; the 100/80 rollover is inherited, not newly
introduced. The newer request selector interacts incorrectly with that loss.
Generation-based hot-loading deliberately differs from source-file discovery;
retain recovery, while checking that this does not strand ordinary revisions.
The original restart/nop completion assumption is already corrected locally.

**User-owned communication requirement:** The user explicitly clarified that
they added the three-working-cycle forced status update because Iter disappeared
and became non-responsive. Preserve active participation. Its absence upstream
does not make it an unwanted change or authorize removal. It appears in 14 of 75
captured PWQ requests; that is not evidence that it caused the stall. Distinguish
deliberate user improvements from inherited limitations and demonstrated defects.
Comparison source, harness and results are only in /tmp/iterbrow-continuity-HGNEVm.

**Further continuity diagnosis:** Captured source observations repeatedly change
from full text to previews before the final rollover. The live relevant_memory
selector also loses its topic when the conversational user input disappears,
despite the current-task projection retaining the request. Offline reproduction
then replaces a relevant PWQ lesson with its filename alone; captured prompts
show the corresponding narrowing of selected memory. Existing recap ends at
E74 (September 22, 08:00); all 75 trial prompts contain tiers through E74 rather
than a summary of this work. chroma_query, episodes and search_transcript were
offered in all 75 requests but never called. These are observed gaps in carrying
experience forward, not proof of deleted long-term storage or an explanation of
every stall. Trace and reproduction: continuity-trace.json in the same /tmp
directory. Diagnose the user's existing Continuity of Mind; do not import
upstream code, redefine it as a new feature, or remove their status updates.

Earlier failed trial costs (not the current rerun):

| Luna effort | Responses | Input / output tokens | API seconds | Estimated USD |
| --- | ---: | ---: | ---: | ---: |
| Low | 16 | 303373 / 1899 | 48.23 | 0.037599 |
| Medium | 9 | 205125 / 1312 | 29.17 | 0.025046 |
| High | 50 | 733306 / 15015 | 204.75 | 0.090205 |

Estimates are recorded provider text-token accounting, not invoices. Effort
phases continued the same task and accumulated context; this is not a controlled
comparison, and lower later context cost partly reflects missing continuity.

Earlier trial preservation: all 32 production PWQ cards and sequence 247 unchanged; CRM records
unchanged at revision 7; all three tabs/settings preserved; AtomSpace ready at
commit 4987 with the same epoch; no captured memory files disappeared. Experience
content truncation described above is a separate failure from file existence.
Temporary observer and disposable test server stopped. Evidence, reproduction,
before-images and unfinished source are only in /tmp/iterbrow-pwq-luna-2y0kyZ.
The existing control document remains the single build record; no GitHub push.

## Completed — CRM Pause/Resume delivered by Iter, September 24

| Stage | Scope | Observed completion |
| --- | --- | --- |
| 1/4 | Diagnose stalled follow-through without adding prompts/governance | Found three-letter topics excluded from memory matching, stale repair notes injected, and fresh source expansion crowded out by older exchanges. These are verified defects, not a complete causal explanation of stalling. |
| 2/4 | Repair context transport and preserve the runtime | Installed two bounded request_budget.py repairs; 171 repository + 15 focused checks pass. Same-conversation selected memory fell from 26,181 to 7,150 characters without deleting memory. |
| 3/4 | Iter authors, tests and installs the feature | Luna/Low still stalled with complete source. One user-approved Sol/Medium comparison produced the candidate, repaired an independently exposed race and installed a stable revision through app_revision_control. Codex supplied tests and factual feedback, not CRM implementation. |
| 4/4 | Independent behavior, preservation, durable lesson and handoff | Nine candidate behavior checks pass; disposable-data browser tests and actual live UI checks pass. Accepted source matches active bundle. Lesson verified in authoritative AtomSpace and search projection. Luna/Low restored and saved; Iter stopped. |

**Active claim:** The requested CRM control works across views and scrolling.
Pause persists through reload, stops ongoing polling/new edits and keeps navigation,
existing-data inspection and Resume usable. Resume catches up and restores edits.
Hidden-tab polling suppression remains. No new PWQ workflow was introduced.

Already-dispatched writes may finish; the UI says so rather than claiming they
were cancelled. A paused reload performs one context read to display existing
data, then performs no ongoing polling. Rapid Pause/Resume while a refresh is in
flight initially stranded stale data; Iter repaired this after Codex supplied the
reproducible sequence. Late obsolete responses are ignored and catch-up rescheduled.

The context repair now reserves space for the newest restorable observation before
trimming older exchanges, growing only by measured need within the existing 45k
ceiling. This supersedes the earlier spare-space-only expansion described below.
Oversized/missing captures keep the preview/reader; no tool replay or history
rewrite occurs. Host repair commits: 935eae1 and 22b00aa.

**Evidence:** This rerun used 10 Luna/Low responses (no feature edit; 253,391 input /
1,194 output tokens, 31.13s API time, estimated $0.03224) and 41 Sol/Medium responses
(798,608 input / 7,681 output, 195.02s API time, estimated $2.02572). These are
deduplicated provider text-token estimates, not invoices or whole-project costs.
Model and reasoning effort changed together, with accumulated context and factual
feedback: this is a behavioral contrast, not a controlled causal attribution.

Production CRM records remain unchanged at revision 7; all three tabs and lock
settings remain, with CRM selected to display the result. AtomSpace is ready at
commit 4772 with the same epoch; no captured memory files disappeared. The managed
runtime generation remains unchanged. Independent mock-I/O checks exercised races
and blocked writes; disposable browser data exercised a real form submission.
Live production UI checks exercised pause, navigation, reload and resume without
writing production CRM records. Iter's own live checks and independent checks are
distinct evidence, not interchangeable claims.

Active stable app revision: apprev-341d2bab088724661a4e6cc66ce6f5bd1ec66dc18a845d11f2cc9c5406bd2546.
Accepted iter/crm/index.html SHA-256: a9e8b8e2309df3b94cb68b5562ed14d5aef310ad820bdbfeba40f937d03ef565.
Prior revision retained: apprev-066932dad0eae448d8a2c81afe86f9efe96b324f82b3ceaea9f79890056be1cc.
Iter synchronized the accepted bundle back to source after saving its exact old
bytes. A rollback/reapply was NOT exercised in this trial.

Iter's bounded lesson e1f5479e6f9831b218995596e58701623412 records the refresh race,
source/bundle synchronization and evidence distinctions. Its authoritative
semantic-memory atom equals the search projection; one identity, zero pending
memory writes. This establishes durable lesson storage, not proof that a later
build has already applied it.

**Unresolved / counterexamples:** Luna's unaided follow-through remains unproven;
browser_click was refused by its health gate (browser_eval worked). Neither is
declared restored. This delivery does not establish universal autonomous foundry
success or complete all earlier restoration commitments.
**Next dependency:** The bounded CRM task is complete. A separately scoped future
task can test lesson reuse or investigate Luna action selection; no more paid
comparison runs are queued. Before-images, tests and observations remain only in
/tmp/iterbrow-crm-restoration-fFGLKu and /tmp/crm_pause_candidate. Source and this
existing control document are saved locally; no GitHub push.

## Previous CRM pause/resume trial stopped without delivery, September 24

User requested a persistent upper-right CRM Pause/Resume control. They explicitly
confirmed that pause makes CRM read-only while navigation and Resume remain usable;
Iter and other tabs continue. Test the real app, not a Codex-written demonstration.

| Stage | Scope | Status |
| --- | --- | --- |
| 1/4 | Capture current app/data/recovery baseline and send the behavior request through chat | Complete: before-images in /tmp/iterbrow-crm-pause-9hnMk7; CRM revision 7, AtomSpace ready at commit 4566, three tabs |
| 2/4 | Iter inspects, implements and installs the requested CRM change | Failed this bounded attempt: 25 responses, no edit/candidate/activation; stopped after repeated inspection |
| 3/4 | Independently check visible control, paused activity, read-only behavior, resume, reload and preservation | Feature not testable: actual CRM still has no pause control. Existing app source, active pointer and data unchanged; tabs and AtomSpace epoch preserved |
| 4/4 | Verify bounded lesson/report, record outcome and stop the test | Evaluation recorded, loop stopped and PID exited; no Iter-authored new lesson or completion proof, and no claim that the feature is delivered |

Active claim: this test exposed continued failure to turn inspection into a real
app change on Luna/Low; it did not demonstrate the requested capability. Iter made
one task registration, ten shell calls, two revision-status calls, browser
inspection calls, seven status sends and one task-state update. None attempted
editing, staging, validating or activation. No approval veto blocked such an
attempt; there was no attempt to reject. No new lesson was written.

Elapsed observed input-to-last-result time was 693s (11m33s). Provider usage:
591,239 input / 2,177 output tokens across 25 responses; recorded text estimate
$0.074914625, not an invoice. API waits totaled 72.09s (1.72-7.94s each), preparation
median 18.31s. No paid request was made after Stop. Temporary files/logs remain in
/tmp/iterbrow-crm-pause-9hnMk7; Iter also wrote /tmp/crm_before_top.txt.

After 18 responses, Codex supplied one factual observation: broad source reads
were returning previews and the inspected 18:52:23 request had no complete CRM
implementation. No implementation or design was supplied. Iter acknowledged the
gap but repeated whole-script/multi-file reads, producing more previews. It then
recorded that it had read the full indexed source and said it was editing, without
an edit attempt. The host reader was available but never called.

Important counterexample to blaming transport alone: four earlier actual requests
(18:49:11 through 18:50:37) DID include the complete CRM core through automatic
expansion; later accumulating context no longer left room. 12/25 requests expanded
some captured output. Thus the transport fix operates, but is not sufficient for
reliable follow-through. It is not established that source visibility alone,
model capability alone, instructions, or context load caused the failure.

Unresolved: the entire pause feature, including actual paused activity, read-only
edits, all views/detail screens/scrolling, reload persistence, in-flight work and
rapid-toggle/resume behavior. The existing hidden-tab polling optimization is not
equivalent to this feature. Next dependency: distinguish task-relevant source
visibility and action selection before paying for another repeated inspection
run. No broader runtime repair, new prompts/governance or model switch was made.

Final preservation: CRM data revision 7, records hash unchanged; all captured
source files and the active app pointer unchanged except this builder document.
Three tabs preserved and original active selection restored after UI inspection.
AtomSpace ready at commit 4639, same epoch; no tracked memory files disappeared.
Normal experience/task/NACE observations remain durable. Iter is stopped, with
unfinished work retained, not falsely marked complete. No queued pause message
was added that could collide with a future user request. No GitHub push.

## Completed context repair — bounded CSV follow-through demonstrated, September 24

The approved three-stage context-transport pass is complete. Iter—not Codex—wrote
the CSV/test repairs through its ordinary loop on Luna/Low. This is evidence of
bounded follow-through with factual feedback, not general autonomous engineering
or proof that the questions alone caused improvement. No new prompts, governance,
model change, external CSV implementation or GitHub push was introduced.

| Stage | Scope | Observed completion |
| --- | --- | --- |
| 1/3 | Correct active-exchange loss and hidden source observations | Installed three host files: iter.py, request_budget.py, tool_results.py; 171 repository + 10 focused context + 7 feedback + 10 provider checks pass (198 total), all temporary checks/captures in /tmp |
| 2/3 | Local installation and preservation | Exact before-images; Iter-only controlled stops/restarts; active managed generation, tabs and AtomSpace epoch preserved; no memory changes during installation |
| 3/3 | Same CSV exercise through Iter, independent checks, lesson retrieval | Iter fixed two syntax delimiters, then the literal-quote parser defect, added one regression test and corrected the description. Original 24 checks, 21 unit tests and 18 independent cases pass; revised existing lesson retrieved and checked against authoritative state |

### What was repaired

The added two-exchange working allowance (a750c73) dropped active history even
when it fitted the existing 45k ceiling. The task registration was absent in all
three exact requests preceding repeated registration, although current_tasks
remained visible. Earlier claims that registration was visible at those repeat
points were incorrect. Replays of complete captured histories estimated
31,498 / 36,361 / 38,810 tokens. Both broad source reads hid the entire
1,909-character implementation behind 600-head/1,200-tail previews; complete
results fitted the next requests at estimates 33,003 / 34,683.

The repair sizes the allowance from active work, preserves active observations
from routine 20-message cleanup, and expands exact captured outputs in request
copies only when the complete request fits. Newest observations use spare room
first; expansion never evicts a retained exchange. Missing/oversized captures
keep the existing preview/reader. No tool replay or memory rewrite is performed.
45k remains a ceiling, not a per-cycle target; small/new-task checks verify this.

The first live clarification exposed another boundary case: a new user message
could exclude an ongoing task's registration. The follow-up uses the earlier of
the latest actual user input and latest existing start_new_task call. A newly
registered task supplies a fresh boundary without a semantic classifier or new
task system. Existing rolling 100/80 history and genuine overflow limits remain.
Source commits: 8bf9326 and f812638. Restricted testing initially hit a local
socket permission error; the same test passed with socket access, without
weakening fixtures.

### CSV result and limits

Before this repair, the preserved Luna trial used 15 responses over 417 seconds
without changing source/tests or the lesson; the preservation test could not
import. The first post-repair pass repaired that test and revised/retrieved the
lesson (18 responses, about 540 seconds). It initially received an old queued
pause together with the CSV request; Codex clarified that the newer request won.
It still missed the literal-quote counterexample and overstated the unit-test
count. That is partial progress, not a clean autonomous success.

Codex then supplied the observed case (6" screen followed by a whitespace-only
separator) and accurate count, not code. Iter diagnosed raw-quote parity, wrote
its own field-start quote tracking, added the regression and updated the same
lesson. One further documentation-only observation led Iter to correct its stale
description, rerun tests, retrieve the lesson and report/wait visibly in chat.
Its first documentation replacement made no change; it recognized and repaired
that attempt. No repeated task registration occurred during the counterexample
repair; the documentation follow-up registered once as new work. This does not
prove repetition eliminated for arbitrary tasks.

Independent checks include quoted empty/whitespace records, empty multi-fields,
multiline content, literal quotes and ten csv.writer round trips. They passed
after the final edit. Original check files were not weakened. The fixture and
Iter's temporary helper stayed in /tmp; none is installed CRM code.

Lesson 0cb5131b1ff9c84e54aef5f01f79fa8441c2 has one current identity,
preserves its original metadata and matches its authoritative semantic-memory
atom byte-for-byte. No pending memory writes remain. Its revised claim is bounded
to observed results, not universal CSV correctness. Later relevant reuse and
generalized learning remain unproven.

Measured first-pass API time was 57.35s, preparation median 18.07s, estimated
text spend $0.04852. Feedback/cleanup captured 20 usage records totaling 61.82s
API time, preparation median 18.24s and $0.05467; one intermediate final-response
usage was not captured, so $0.10319 combined is a recorded subtotal, not total
billing. Embeddings/surcharges are excluded. No model-only or prompt-only causal
comparison is justified. Preparation still dominates these short model waits;
the task is now completed, but speed remains an open improvement.

### Final preservation and next dependency

Iter is stopped in the UI and its recorded process has exited. Three tabs and
their state are exact; generation candidate-29d719b85a3d45cfa5d7288ae0f4b05d and
its rollback parent remain unchanged. AtomSpace is ready, same epoch
92d6e63a-6331-4cc8-9072-df8fdbbfa232, commit 4566. Installed sources match.
No tracked memory files disappeared; normal trial changes to experience, tasks,
lesson projection and bookkeeping are expected, not claimed hash-identical.
Heartbeat/hot-load/rollback mechanisms were not replaced or weakened.

Active claim: the two transport regressions are corrected and this bounded Iter
repair now reaches code, tests, durable lesson and visible completion.
Unresolved: independent counterexample discovery, future lesson reuse, larger
tasks exceeding context, residual preparation time and general app-building quality.
Counterexamples: external factual feedback was necessary; passing this fixture
does not demonstrate the CRM or all requested platform capabilities.
Next dependency: no additional implementation belongs to this approved pass.
Any broader quality/performance work must preserve the question-first ordinary
loop and use a separately stated, bounded target—not another governance layer.

Evidence/before-images: /tmp/iterbrow-context-repair-oGUATB/ (feedback/ is the
counterexample pass). Earlier diagnosis: /tmp/iterbrow-followthrough-diagnosis-jliDs7/;
unsuccessful baseline: /tmp/iterbrow-csv-luna-O6XYQZ/. Local commits only.

### Earlier preparation/memory pass — 4/4 complete

The attached question plan and all 17 groups are installed. Deferred SDK imports
reduced no-op worker median 0.504 -> 0.074s and live preparation roughly 36 -> 18s.
Memory deadline/status/retry corrections preserve exact identity through durable
commit and projection recovery. Iter recovered/retrieved interrupted lesson
2b2e745f81b47ce3e56f96c41f43eba0aae6 with its original 16:22:29 metadata and sole
transaction at commit 4370. The already-existing reworded duplicate was neither
deleted nor falsely claimed deduplicated. Generation promotion and preservation
passed. Implementation cd4ba17; checkpoint f1f8b2f; evidence in
/tmp/iterbrow-latency-memory-haSaFr/. This completed pass is not reopened.

## Completed provider work — direct OpenAI option, September 24

The user requested direct OpenAI GPT in Settings with cost-tiered choices, while
retaining GLM/OpenRouter, and debugging the lost-context/repetition contenders.
This is provider integration into the ordinary loop, not another governor.

| Stage | Scope | Status |
| --- | --- | --- |
| 1/4 | Inspect provider/context paths and current official model/API/pricing requirements | Complete: Responses required for GPT-6 reasoning with tools; Sol/Luna/Astra tiers verified; source inspection separates observed context loss from unproven causal explanations |
| 2/4 | Settings, separate OpenAI key, model/effort selection, transport and visible cost information | Complete and installed; GLM/local paths and memory embedding provider retained |
| 3/4 | Isolated round-trip, settings/preservation and existing regression checks | Passed: 171 repository tests, 10 provider tests including real SDK/local HTTP round trip, Settings/environment checks and JavaScript syntax; new tests and logs only in /tmp/iterbrow-openai-provider-ljhdoc |
| 4/4 | Install locally, restart only as needed, verify UI and preservation; user enters key | Complete for integration: user saved key; real Sol/Low ordinary-loop tool/result/chat round trip passed; stopped after the bounded check. Coding-quality comparison remains pending |

Active claim: model selection must change the actual endpoint/protocol and keep
tool observations/continuation intact. Unresolved: oversized-exchange projection,
hidden failure tails, mixed-task context, unbounded deliberation, provider latency
and model follow-through are separate contenders, not one proven cause. No prompt
changes or retention redesign are bundled into this model comparison. Provider
adaptation necessarily removes incompatible GLM reasoning metadata from OpenAI
request copies; all original history remains durable. Counterexample: prior prompt
tests passed while live behavior did not. Next dependency: bounded independent
work comparison; a timestamp smoke test does not establish better engineering.
No paid model request was made during installation. The old Electron process was
confirmed exited before one replacement was launched. All three tabs, their
locks/pins and active selection survived; the only serialized tab difference is
Google's refreshed `zx` URL query value. Memory hashes are unchanged; AtomSpace
is ready at the same epoch and commit 4309. Eight source/document files were
installed with exact before-images in the same /tmp directory. No GitHub push.

Live API check after user saved the key: the ordinary loop used direct OpenAI
`gpt-6-sol`, low effort, and the existing stable generation. It registered the
small task, ran the requested read-only `date` command once, and sent the exact
observed `2026-09-24T22:37:18Z` to chat; the rendered reply was visually verified.
Four responses (including its final no-op) took 5.71 / 3.72 / 3.42 / 2.81 seconds.
Reported input tokens were 20934 / 17858 / 17298 / 17459; output 178 / 34 / 52 / 19.
All reported zero cache-read tokens and zero reasoning tokens; the estimates
include reported cache writes. Estimated total $0.1864505, not an account invoice.
First three calls through the visible reply totaled $0.142676; the final no-op
completed before Stop, so it is included rather than hidden from the total.
The loop is stopped again; no paused repair/build trial was resumed. This proves
authentication, tool dispatch, result continuation and delivered chat, not the
earlier behavioral-improvement claim. Local startup/context preparation remains
separate from the measured API waits; 17–21k input tokens for this trivial check
also shows that request-size efficiency is still unresolved. No context-budget,
memory, reasoning-rule or prompt redesign was made during this live check.

### Context and follow-through diagnosis — three-stage follow-up

1/3 complete: trace saved CSV observations and the actual projection code.
2/3 evaluated, NOT passed: user selected Luna/Low; resume the unchanged preferences
fixture through chat, with no external repair supplied. Eight responses cost an
estimated $0.018323925, API waits 2.05–4.76s (24.88s total). The file remains
byte-identical and 4/11 independent checks pass. Iter twice mismatched tool
arguments, restarted the task, and reported progress without repairing it.
3/3 complete for diagnosis, not remediation: inspect captured requests, raw
response calls, outcomes and the loaded transformation sources. Trial stopped;
unfinished work retained and a pause queued. AtomSpace remains ready, same epoch,
commit 4342. Test captures remain only in /tmp/iterbrow-followthrough-uiklGu.

Confirmed distinctions: (a) the earlier 6,000-character CSV output's SyntaxError
at offset 5233 was absent from the 1,200-character beginning-only tool preview;
whole-exchange parking can shorten that envelope again; (b) Luna's current
argument errors remained visible, with correct schemas and unchanged raw/API
call names, so hiding the result does not explain those errors; (c) strict:false
unnecessarily leaves the already-compatible shell/python schemas best effort;
(d) transcript.py fails to exclude the runner's URGENT send-only instruction,
records it as [user], and append_last_transcript_lines.py reintroduces it into
later system context. This replay was verified in subsequent actual requests;
it is not proof of which individual model choice it caused. One genuine current
send-only interruption was also observed. (e) components-loaded to model-wait
cost 36.28–37.22s per request; the individual expensive step is not yet isolated.
No exchange parking occurred in the Luna trial; older history was still omitted.

### Approved feedback corrections — four stages

| Stage | Scope | Status |
| --- | --- | --- |
| 1/4 | Exclude temporary runner controls from recording and historical projection; preserve conversation/history | Installed; no stale URGENT instruction in any new-generation system prompt; genuine user quotation checks pass |
| 2/4 | Output beginning/end, observed execution facts, no second truncation of bounded results | Installed; actual offset-5233 SyntaxError is visible, exact output retrieval preserved, bounded exchange observations remain intact |
| 3/4 | Strict OpenAI arguments only for already-compatible schemas | Installed; actual outgoing shell(cmd)/python(code) schemas strict, optional/default and richer schemas unchanged; no mismatched tool arguments in this trial |
| 4/4 | Install tested changes through existing recovery; retry the same Luna/Low repair | Complete for this bounded repair: Iter authored repair, backup and tests; 3/3 own tests and 11/11 independent checks pass, previously 4/11; reported results/limits and entered idle wait |

Active claim: repair feedback delivery and argument transport, not add reasoning
or governance. 171 repository, 10 provider and seven focused checks pass; test files/captures remain only in
/tmp/iterbrow-feedback-fix-BTnyTU. Counterexamples: beginning/end excerpts can
still omit middle evidence; full output remains retrievable. Invocation success
does not establish task fulfillment. Strict argument shape cannot ensure correct
code. One small repair is not proof of general app-building reliability or of
which individual correction caused the behavioral improvement. No new questions,
model switch, memory deletion or GitHub push. Local source milestone: c14f7fc.

Live outcome, September 24: the same Luna/Low fixture was repaired by Iter alone;
no implementation or tests were supplied to it by the external builder. It
recovered from a Mac-incompatible find option, made the actual edit and backup,
ran its own tests, and reported the memory-retrieval limitation honestly. A
duplicate task-completion update and several status-only turns remain efficiency
counterexamples. It entered nop(0)/idle_wait at 16:26:39; the loop was then stopped.
Fourteen model responses, including the initial hold acknowledgment and final
no-op, cost an estimated $0.031241275 (not an invoice). API waits totaled 40.34s;
post-component context preparation still cost 35.935–37.020s per request. The
repair request was received at 16:15:01; the file was fixed/tested by 16:19:53.

Unresolved memory distinction: first remember call reported TIMEOUT after 15s,
but its transaction subsequently committed at 4370. Iter retried reworded text,
successfully committing a second semantic-memory record at 4373. Both scoped
lessons are durable; this is duplicate learning, not two independent successes.
The subsequent chroma_query also timed out; successful retrieval/reuse is NOT
proven. No duplicate was silently removed. Next dependency: narrowly profile
local preparation and make uncertain memory outcomes distinguishable from failed
writes before retrying; do not add another governor or expand the question set.

Final preservation: candidate-dc9fde1d7ea54ad8b3436b0161029536 is stable after two
real completed-cycle heartbeats; exact old generation remains its rollback target.
Eight installed source/control files match, three tabs are byte-identical, no
previous memory files are missing, and AtomSpace remains ready in the same epoch,
commit 4342 -> 4384. Ordinary task, history and lesson writes are expected changes,
not a claim of byte-identical memory. Existing control document only; all new
harnesses, trial logs, before-images and audit results remain in /tmp.

The sections below retain the preceding pass and its actual outcomes.

## Current authorized work — six-stage 80/20 pass, September 24

This section supersedes older active/parked directions below. The user approved
the six-stage plan and explicitly approved the refined Task 5: question-first,
LLM-heavy, integrated with existing durable memory, tools, observations and
recovery. All 17 question groups remain the vocabulary; the LLM interprets the
actual work context. No new native task model, inference selector, learning
architecture, executor, mandatory alternatives or routine approval gate belongs
to this PoC. More ambitious native engineering reasoning remains deferred, not
cancelled or claimed complete. Existing NACE reasoning and its repairs remain.

| Stage | Work and observable improvement | Status |
| --- | --- | --- |
| 1/6 | Restore detached-worker shutdown, interrupted history rotation, and existing stale test fixtures without reinstating removed gates | Installed; 171 repository tests and ten historical suites pass; real orphan worker/descendant cleanup preserves a same-named foreign worker |
| 2/6 | Cheaper bounded native queries with relevant-state invalidation; general/history queries retain full access | Installed; identical live answer, 5.384s full / 1.048s current; isolated event-only reuse and state/seed invalidation pass |
| 3/6 | Research returns useful partial results within one deadline; repository searches reach GitHub promptly | Installed; public GitHub result in 0.46s; partial-result and hung-backend deadline checks pass |
| 4/6 | Structured execution outcomes prevent error-text false positives; execution success is not task fulfillment | Installed; live shell carries exit code; quoted errors, actual memory exceptions, unknown results and dedup checked; phase labels no longer fabricate learning evidence |
| 5/6 | Approved contextual question PoC in the ordinary loop; existing memory retrieval/save, no extra critic loop or native expert systems | Installed; all 17 groups observed in the new-task prompt, smaller work reminders and empty idle checked; reliable behavioral improvement is not yet demonstrated |
| 6/6 | Install tested changes through existing recovery and demonstrate actual Iter behavior, preservation and lesson reuse | Installation/preservation verified; four-stage refinement evaluated below, but reliable live follow-through and learning are NOT demonstrated |

### Approved refinement within Stage 6/6 — September 24

| Stage | Scope | Status |
| --- | --- | --- |
| 1/4 | Exact approved conditional cue and three concise question replacements; preserve all 17 groups, intake/completion/self-repair reminders and empty idle | Complete: focused checks and 171/171 repository tests pass; ordinary cue 1820 → 256 chars; local commit 2e66078 |
| 2/4 | Correct only the false CSV test lesson through existing memory; preserve history and identify external authorship | Complete: exact readback, metadata preserved and semantic retrieval verified; external correction, not Iter learning |
| 3/4 | Install the tested helper, then let Iter finish the known repair through chat/tools | Evaluated, partial/not passed: requested behavior passes 24 original + seven independent checks, but a later added test file is syntactically invalid; no Iter lesson revision or final report; trial stopped after a >10-minute model wait |
| 4/4 | Different small task with independent checks; assess actual follow-through, useful learning and costs | Initial GLM run failed; subsequent Luna + feedback-repair run passed 11/11 independent checks, saved a scoped lesson and entered wait. Memory retrieval timed out and caused a duplicate write; later reuse remains unproven. See current work above |

The active-work cue is exactly: "When uncertain, pursue the question whose answer
would most change your next action. Use the available tools to test it, then act
on the result. Otherwise, continue the work. A plan or progress message is not
completed work." Failure/repair/learning entries become, respectively: "What
plausible case would show this approach is wrong?", "What observation would
distinguish the competing explanations?", and "Under what conditions is this
lesson supported?" The other 14 entries are unchanged. Actual tool observations
remain in context; Python does not select an inference type, grade an answer,
add a critic call or impose a turn count. Existing completion and recovery
reminders remain. No model settings, reasoning service, memory format or
authorization mechanism changes. Track this follow-up as N/4 within Stage 6/6.

Live refinement counterexample: the original /tmp example shared a directory
with the external builder's diagnostic utilities. Iter read all Python files and
attempted test-named scripts there, producing oversized retained output rather
than a repair. This contaminates that trial; it must not be credited as a clean
prompt comparison. The example and Iter-authored tests were copied unchanged
into `/tmp/iterbrow-question-refinement-Vhyc9C/csv/`, apart from the harnesses,
and Iter received the corrected scope through chat. No repair code was supplied.
The active follow-up prompt contained only the 225-character cue text (256 with
heading/newlines), confirming ordinary question-bundle replacement is live.

The next isolated turn wrote a repair rather than repeating inspection, and its
six added checks passed. A subsequent turn rewrote that repair to preserve raw
line endings and added another test file with a syntax error. The original 24
and seven independent requested-outcome checks still pass; the whole test set
does not. No external repair code was supplied. Independent checks establish the
requested cases, not universal parsing correctness or a causal prompt-only gain.
Multi-minute model latency and repeated large reasoning responses remain.
After a progress-only chat response, the next model wait exceeded ten minutes.
The loop was stopped and restarted for the queued preferences task; AtomSpace
was not stopped. Readback confirms the CSV lesson remains the external correction
from Stage 2, not an Iter-authored update. Stage 3 is partial, not passed; its
incomplete verification/learning is not silently accepted as success.

Cost observations: nine captured request snapshots estimated 26,889–29,516 input
tokens (local estimates, not provider usage). Ordinary inquiry text was only 225
characters; completed responses nevertheless included 75K–114K-character reasoning
payloads. Two later model waits exceeded ten minutes without a new tool action.
The preferences intake retained system context, 57 tool schemas and 11 user
messages while projecting out prior assistant/tool exchanges. The existing
budget code permits this on new input; oversized current exchanges instead get
bounded observation previews plus retrieval references. Original history remains
durable. This is a concrete context/cost finding, not proof that projection or
model settings alone caused the failures. No model setting was changed.

Task 5 includes request fidelity, recall/reuse, creative choice and removable
flair, failure/alternatives, recovery, bounded use of existing NACE, repair,
fulfillment, visual/nonvisual use, durability, self-revision, learning and explicit
preference feedback. Broad questions must not be replaced by narrow precomputed
failure guesses. Use ordinary model turns, avoid idle payloads and repeated
question dumps. The LLM investigates with existing tools and saves useful lessons
through existing memory; a shown prompt or confident answer is not success.
Demonstrate a useful self-check and later relevant reuse; do not claim independent
native engineering intelligence. Any gap requiring expansion is reported first.

Installation checkpoint: local sandbox commits `852ee4a` and `06a10d7`; no GitHub push.
Generation `candidate-ec7b00238a7e4551a320571b82fbfc7f` was externally promoted
after two healthy completions, with its exact prior generation retained. The
service restart preserved epoch, commit 4240 and state hash; all fingerprinted
memory was unchanged before the verification session. Three tabs/order/locks/pins
and CRM/PWQ URLs survived; Google regenerated only its reload parameter. Iter
then resumed for the bounded test. Cold generation startup and active-turn
context/model latency remain measurable costs; the query speedup is not proof
of instant chat. Generic tools returning an error as ordinary data still report
invocation return, not semantic success; shell/Python provide execution outcomes.
The disposable CSV fixture is a controlled repair test, not the CRM deliverable
and not a causal comparison proving all gains came from these prompts.
Live counterexamples: Iter's first repair passed its 19 checks and eight
independent requested-outcome checks, but an additional whitespace-separator
case regressed. Iter reproduced that regression, then went idle after a status
message without applying its planned correction. The question selector had
omitted reminders after send-only turns; it now retains a fulfillment/follow-
through question there, keeps actual nop idle empty, and asks for proportional
deliberation instead of exhaustive speculation. No tool is blocked. Malformed
prior argument values are also tolerated. These focused checks pass. After an
Iter-only restart, Iter applied a second repair and passed its expanded 24 checks;
the eight independent requested-outcome checks and separator counterexample also
passed. However, quoted-empty and quoted-whitespace single-field records still
disappear. Passing the existing tests did not establish fulfillment.

Current stopping point: both disposable trials are PAUSED, not completed. A hold
was sent through Iter chat so a future Start does not silently resume them. Iter
authored the CSV repair, but external review supplied the counterexamples and
follow-through requests; this is not independent completion or proven prompt-only
improvement. No external implementation was supplied for either trial.

Test lesson `0cb5131b1ff9c84e54aef5f01f79fa8441c2` retains the Stage 2 external
qualification, with original metadata/history preserved and semantic retrieval
verified. Final direct readback confirms Iter did not revise it during Stage 3.
Do not call the external correction native learning or use the older filter claim.

The app is open and Iter is stopped with automatic start off; no loop/invocation
process remains. AtomSpace is ready in the same epoch at commit 4309, 5623 atoms
(this refinement began at 4291/5595). Managed generation
`candidate-ec7b00238a7e4551a320571b82fbfc7f` remains stable with its parent retained.
All installed source hashes match. No preexisting fingerprinted memory file
disappeared. All three tabs/order/locks/pins exactly match this refinement's
baseline. Memory/history changes are retained, not reset. New harnesses, logs,
test fixtures and before-images are only in /tmp. The 171 repository tests and
focused question checks pass; they do not override the live failures.

Next dependency: agree on the smallest response-cost/context-continuity correction
or runtime configuration experiment supported by these observations. The approved
prompt change is installed, but the desired live outcome has not been achieved.
Do not add more questions, another reasoner, workflow gates or unsolicited model
changes to compensate. The more ambitious native-reasoning option remains deferred.

Tracking names stage N/6, active claim, evidence, unresolved, counterexamples,
next dependency and remaining stages. Prepare code in the existing sandbox;
new harnesses/logs/before-images stay in /tmp. Correct existing repository tests
in place. Preserve source/data, both memories, tabs/locks, native cognition,
hot-load/heartbeat/rollback and the user's stopped state until a deliberate
runtime verification. No GitHub push and no additional control document.

The sections below retain historical decisions/evidence, not competing orders.

## Follow-up correction — stopped-state lifecycle and quiet polling

September 24: the user approved three narrow corrections to the repair pass.
1/3: keep AtomSpace startup/failure/recovery messages, suppress unchanged healthy
availability messages. 2/3: inactive/minimized app tabs do no change-query work;
visible-tab polling is limited to once per five seconds without advancing a
hidden tab's cursor; saves and explicit reads remain immediate. 3/3: reconcile
surviving Python Iter loops by verified command, process birth identity and
actual workspace cwd before displaying a new window or starting another loop;
Quit waits for its child to exit, including Start/Stop races. Preserve user
Start/Stop intent, AtomSpace, memory, tabs, hot-load heartbeat and rollback.

Completed 3/3 and installed locally. Isolated checks passed for all three,
including Start/Stop races, the actual quit handler awaiting a real /tmp child,
and a same-named process in another workspace that remained untouched. Nine
existing AtomSpace lifecycle checks also passed. Live restart retired orphan
Iter PID 69404 before showing stopped; a subsequent Quit/reopen exited cleanly
and remained stopped with no Iter loop. The sidebar retained one connection
message across healthy checks; the existing CRM still opened normally. All
three saved tabs/order/locks/pins and checked memory file hashes were preserved;
AtomSpace PID 68840, epoch and commit 4240 were unchanged. Current end position:
app open, Iter stopped, automatic start off. Health monitoring, hot-load and
rollback remain enabled. Tests, logs and before-images remain in /tmp, not the
repo. No CRM feature work or new reasoning/governance procedure was introduced.

## Active repair pass — September 24, 2026

This section supersedes the older delivery sequence below. The user approved
eight direct, additive repair stages. The question-driven PoC and CRM feature
work remain parked; Gmail and Mattermost defects are explicitly deferred.
No new governor, workflow gate, card requirement, or parallel control document.

| Stage | Repair and observable result | Position |
| --- | --- | --- |
| 1/8 | Event-driven idle with heartbeat/timed wake; context scales with actual need; 45k ceilings remain | Installed; 92 seconds of live idle with heartbeat and no new model request; timed/alarm wakes passed isolated checks |
| 2/8 | Only the canonical PWQ main frame receives approval privileges | Installed; exact-page/sender/subframe/navigation checks passed; board reads work live |
| 3/8 | Independent evidence has independent identity; retries are idempotent; missing-snapshot replay preserves committed state | Installed; six live discrepancies reconciled with both versions retained; ABA/retry/replay checks passed |
| 4/8 | Native MeTTa computes committed NACE revisions; KB rules/thresholds affect results; intentional idle is not negative evidence | Installed; three native revision events observed; all 87 projected beliefs match authority |
| 5/8 | Atomic chat envelopes, multiline dedup, archive-aware episodes/recap, exact tier source retention | Installed; targeted checks passed; native UI health reply visibly delivered |
| 6/8 | Inline app JSON works; ordinary app repair needs no card; selected cards remain binding; exact rollback remains | Installed; targeted and 13 existing app checks passed, including exact-parent recovery |
| 7/8 | Versioned read caches, bounded quota scans, native repair installation recipe, aligned runtime reference | Installed; cache 5.30s cold / 0.013s repeat; current reference verified in the live prompt; clean-Mac build not yet proven |
| 8/8 | Install exact tested changes; verify running code, native learning, idle/chat wake, and preservation | Both generations externally promoted; both chat replies visibly delivered; resumed quiet waiting with healthy heartbeat |

Tracking must name the current N/8, active claim, evidence, unresolved items,
counterexamples and next dependency, with remaining stages explicit. Completion
means observed useful behavior, not source merely saved. All diagnostic tests,
logs and before-images remain in /tmp; only runtime code and this existing
control document/reference belong in the installation. Preserve all current
tabs/locks, source, data, memory and recovery. No GitHub push.

Verification checkpoint: main generation candidate-8d3e7b82f8784ac8b511bb6a5a3e7a55
was externally promoted. Reference-only correction candidate-fd1dd4ac0510463eaf1c74aebc9a17fb
was also externally promoted and is now stable. The same AtomSpace epoch survived the service restart at commit
4224; subsequent commits are new ordinary observations, not a reset. All three
currently open tabs, their order/locks/pins and app URLs survived (Google alone
regenerated its zx reload parameter). No pre-maintenance memory file disappeared.
The isolated copy passed 171 existing checks after stale ceremony expectations
were aligned there; those test edits and all diagnostic artifacts stay in /tmp.
Source before-images and exact installation observations are retained there too.
This establishes a working bounded native revision path, not generalized software
engineering learning. Cold full-loop transformation latency still exists; no
claim of instant chat or a verified fresh-Mac installation is made.
Idle model-call waste is fixed. Active turns still carry substantial fixed context
and tool-schema overhead (the final UI-visible provider report showed 23,442 input
tokens); further reduction is remaining efficiency debt, not a completed claim.
The runtime milestone is committed locally in the existing sandbox as a750c73;
the live dirty checkout was not broadly staged or reset. No new diagnostic files
were installed in it. End position: Iter running, heartbeat healthy, waiting for
the user's next request; CRM, Gmail/Mattermost and the question-driven PoC remain
outside this pass. Do not silently resume them.

## Active direction — corrective recovery and question-driven PoC

Updated September 23, 2026. Target: a useful demonstration by late September 24,
not a claim that every long-term commitment is complete.

The user's latest direction resumes work on THIS correction: preserve useful Iter,
remove the added administrative burden, THEN implement the question-driven PoC.
It does not resume the superseded foundry/governor rollout. The previous pause
checkpoint and older handoff below are historical evidence, not execution orders.

This is the one active delivery plan, at docs/ITERBROW_INTEGRATED_BUILD_CONTROL.md
in the live repository. Do not maintain output/workspace mirrors as parallel
authorities. The Build Atlas remains historical inventory, not a runtime gate.

### Intention → action → observed outcome

**Intention:** improve what Iter already does. Preserve its ability to build many
kinds of tools, revise itself, hot-load, recover, remember, and reason. Make Iter
ask the useful questions the user currently has to ask, actually investigate the
answers, and reuse what it learns. A new CRM alone does not establish improvement.

**Action:** restore useful ordinary-loop behavior; remove the imposed foundry
procedure and document-label gates; connect a small native question-selection and
evidence-feedback path to that same loop and existing memory. No second executor,
second memory authority, or new mandatory approval ceremony.

**Planned observable outcome:** Iter catches a requirement omission or plausible
failure without the user's reminder, exercises the actual result, repairs the
problem while preserving working behavior, records a supported lesson, and uses
that lesson in a later relevant choice. The same discipline applies to its own
repairs and revisions. Code authored by Codex is platform work, not proof that
Iter authored or repaired the demonstration application.

The 80/20 rule reduces mechanism depth, not the completeness of this cycle:
intention → current state/invariants → gap → meaningful alternatives → predictions
and risks → checks/recovery → existing bounded authorization → action → observation
→ comparison → belief/capability revision → accept, iterate, escalate, or recover.
No fixed number of alternatives. No requirement to fill twelve forms per action.

### Preservation is implicit and non-negotiable

Keep user/Iter changes, tools, tabs/apps, source and data, chat, both semantic and
episodic memories, Soul/NACE, the durable AtomSpace and named-space capability,
hot-loading, usable self-repair, recovery/rollback, PWQ human agency, and beneficial
transport/settings/search fixes. Preserve subsequent experience, not just a prior
snapshot. Code rollback never means memory rollback. DAS remains an adapter.

Use live Git snapshot 1acd044 as a behavioral comparison, NOT a reset target.
Candidate snapshot 501ea39 already includes earlier assistant additions and is
not the user's original baseline. Do not reset the checkout, replace it with
upstream, erase ledgers, or overwrite concurrent work.

Keep mechanical measures that provide utility: atomic saves, known working
revisions, scoped data ownership, user Stop/tab locks, current user authorization,
and externally supervised recovery. Remove bookkeeping that does not help the
work. Do not delete checks merely because they use hashes; distinguish verifying
the correct recovery bytes from requiring Iter to administer certificates.

### Questions used throughout ordinary work, including self-repair

These are prompts for investigation and evidence, not a new form or gate. Adapt
them to the work. Ask at useful transitions; reuse still-applicable answers.
A factual answer already available from memory/tools should be retrieved rather
than asked rhetorically. Contradictory new evidence reopens the relevant question.

**A. Understand the actual request, at intake and material clarification**

- What exactly did the user ask to be able to do, and why?
- Which outcomes and constraints did they state? Which details am I assuming?
- What observable result would demonstrate each requested outcome?
- Am I substituting an easier adjacent task, adding unwanted work, or silently
  dropping a requirement? Ask the user only about consequential ambiguity.

Retain the request and agreed clarifications in existing work memory. A plan or
summary cannot silently replace the user's request. Child work inherits the
relevant parent intention; finishing a child does not finish its parent.

**B. Recover continuity, at start/resume and before a relevant decision**

- What have we already tried or built here? What worked, failed, or remains open?
- What relevant lessons are in semantic memory, episodes, and current task state?
- What has changed since those lessons were recorded? Inspect current reality.
- Can existing code, a tool, or a sound source example satisfy this need?

Use actual retrieval; no invented memory. Link useful lessons to the work and
observations. Consult NACE about bounded supported claims, not an unrestricted
English design problem it has no rules or facts to solve.

**C. Challenge the proposed action, before consequential changes**

Creative inquiry below supplements the requested work; it never replaces these
failure, preservation and evidence questions.

- Under what circumstances does this fail?
- What assumptions about inputs, dependencies, timing, environment, and current
  behavior could be wrong? What else could this change affect?
- Which alternatives are genuinely useful, and what do I predict will differ?
- What should I exercise, observe, or preserve to find out? How would I recover?

For self-revisions, include the repair mechanism and continuity of mind among
the affected behavior. Do not build a second recovery system.

**D. Break a failed approach, when evidence contradicts it or attempts repeat**

- What observation contradicts my explanation?
- Have I made this mistake or tried this repair before?
- Am I treating a symptom? What inspection distinguishes the remaining causes?
- Should I repair, use another approach, gather evidence, or restore working code?

**E. Verify fulfillment, before any completion claim**

- Re-read the actual request and agreed changes: what did it require?
- For each requested outcome, where is it implemented and what did I actually
  observe demonstrating it? Is this the current result, not a mock or old revision?
- What was omitted, weakened, substituted, disconnected, or only described?
- Can the intended user accomplish the requested task without hidden manual help?
- Have I used the relevant controls and workflows, inspected the rendered result,
  and taken screenshots where visual behavior matters? What happened?
- Does saved work reopen correctly where persistence is part of the request?
  Did the change preserve existing behavior and integration?
- What counterexample remains? What was not verified? Report that honestly
  instead of calling the whole request complete.

A screenshot is appearance evidence, not proof a control works. Exercise behavior
with safe test data, including appropriate failure cases. For non-visual work,
use its real output and consequences instead. For self-repair, distinguish source
on disk from the loaded revision and verify the repaired capability actually runs.
Known counterexamples to the request prevent completion; unrelated speculative
possibilities do not create endless work.

**F. Learn, after observed outcomes and before leaving the work**

- What changed my understanding? What evidence supports the lesson?
- When does it apply, and what should trigger remembering it?
- What did this question or check uncover that I otherwise missed?
- What remains unfinished, and what should the next session do?

Store a concrete lesson, linked evidence, and applicable context through existing
memory/NACE mechanisms. Do not revise a belief merely because a prompt was shown
or a confident explanation was written. Re-reading one observation is not new
independent evidence. Keep claims, observations, and unknowns distinct.

### Creative latitude, user agency, and exact recovery — added September 23

At intake, use the user's explicit current preference, or retrieve an applicable
remembered one. If creative latitude is unknown and would materially affect the
result, offer a lightweight choice in the existing conversation: **follow the
request closely**, **helpful touches within its footprint**, or **explore bolder
options**. Do not build a settings wizard or make this a prerequisite for doing
the necessary requested work. No-flair instructions suppress creative additions.

During planning ask:

- What can I add within the requested footprint that makes this version materially
  better, more useful, more fun, or more interactive?
- Are there good GitHub examples that could inspire a compatible implementation
  in Iter's style? Inspect relevant source and licensing, not just screenshots.
- Is the improvement worth its complexity, and does it preserve every requested
  outcome? Distinguish within-footprint additions from larger proposals.
- Have I explained optional additions upfront and made them straightforward to
  remove on request without damaging the requested work or user data?

Meaningful expansion of scope, cost, dependencies, privacy exposure, or external
effects is offered before building it. Making an unwanted change reversible is
not itself consent. Use simple separable changes; no general feature-flag framework
is required. Existing approval can cover the creative latitude the user chooses.

After feedback ask what the user actually welcomed, removed, or found excessive.
Use existing memory and NACE evidence revision to learn a context-specific
preference with uncertainty. An explicit instruction overrides a learned preference;
silence is not approval. A preference for playful game features does not imply the
same preference for business briefs or self-repair. The learning connection remains
implementation work, not a capability established merely by this question text.

Before completion and when resuming/removing a feature ask:

- Has this work really been saved, and can the intended result and context be
  faithfully reopened or reconstructed?
- Which saved source/data revision and memory links would restore it?
- Can the requested feature be removed or rolled back without undoing unrelated
  changes, losing user data, or breaking dependencies?
- Which persistence or restoration behavior was actually exercised, and which
  remains unverified?

Memory locates exact saved artifacts and explains their history. Exact rollback
uses those artifacts, not LLM regeneration from a summary. Source, domain data,
and cognitive memory have different recovery requirements; never rewind the mind
to undo a feature. Do not claim exact recovery when the needed artifact is absent.

The user wants the question set prepared and introduced coherently, but explicitly
reaffirmed that restoration comes FIRST. The question pack was prepared too early.
It is now parked: no further PoC code, tests, integration or activation until R1
is completed. Retain its saved source, but exclude it from the R1 live handoff.
After restoration, select relevant questions at meaningful boundaries; do not
inject every question into every turn. Sandbox checks establish selection and
interface behavior; only real Iter work can establish better outcomes.

### Small native role, integrated with the existing loop

Native rules select useful questions from work state, unresolved evidence, and
relevant learned experience. The LLM and existing tools investigate. Observations
return to existing durable cognition; supported outcomes revise beliefs and affect
later questions/choices. A native result of "unknown; investigate" is useful.

Start with a few comprehensible rules, not a general ontology or new scheduler.
Use existing loop/transformations, task state, semantic/episodic retrieval, and
NACE seams where possible. Do not require the separate foundry tool to obtain this
discipline. Apply it to applications, research, writing, and Iter's self-revisions,
with checks appropriate to the activity, not a software-only checklist.

### Ordered implementation and honest stage accounting

**Only R1 restoration is active.** This is a work-order correction, not another
runtime gate or approval process for Iter. "Remaining recovery cleanup" understated
the position: the promised restoration has not been completed. Do not count
question-pack preparation as restoration progress or let it displace that work.

| Stage | Action | Observable exit | Current status |
|---|---|---|---|
| R0 — align control | Publish this plan; supersede conflicting instructions; retain history. | One clear active direction, questions, preservation boundary and work position. | Complete: repository/candidate/output copies synchronized; Atlas points here. |
| R1 — recover useful Iter | Remove the introduced mandatory foundry workflow, fixed alternatives, Atlas-label prerequisites and repeated routine approval burden; retain/extract useful services. Restore effective authorized self-repair. | Ordinary chat/tools/work operate; a scoped repair can complete; hot-load/recovery and memory still function. No merely disabling one tool and declaring recovery. | Managed restoration promoted; chat/AtomSpace round trip passed. The second context correction is installed and live request flow is restored. Self-repair and app/memory demonstrations remain in progress. |
| R2 — wire the questions | Add the small native question/observation/learning connection to the ordinary loop, using existing memory. | Relevant question occurs without user prompting, causes real investigation, and leaves retrievable outcome evidence. Self-repair uses the same cycle. | PARKED until R1 is completed. Previously prepared/tested question pack retained; no further PoC work or deployment. |
| R3 — demonstrate improvement | Iter performs the CRM build/change, checks fulfillment, catches/repairs an actual issue, then uses the lesson in a later change. Include a self-repair demonstration. | Visible user value plus an attributable improvement in self-checking or lesson reuse, with surrounding behavior/data preserved. | Not demonstrated. |

R1 removal is selective code surgery, not a historical reset. Candidate targets:
- The model-facing mandatory foundry submit/decide/execute protocol and its fixed
  two-alternative requirement.
- Atlas/invariant label checks used as runtime prerequisites.
- Treating a PWQ progress-report failure as grounds to undo otherwise healthy code.
- Making every routine revision seek fresh approval inside already-approved work.
- Obsolete instructions that turn self_improve apply into "stage and stop."

Shared project/app storage, cognitive-fabric access, and revision helpers must be
separated from the retiring workflow before deleting dependent modules. Preserve
old work/evidence as history. Retire obsolete source from the runnable product only
after references are resolved; Git history is the recovery record, not a new dump
of legacy files in the live tree. Existing user-authored controls are not blanket
removal targets.

Approvals govern user intent and scope, not ordinary bookkeeping. Reuse existing
PWQ work authority for subordinate actions; scope expansion, destructive data
changes, or materially different external effects still require the appropriate
user decision. This plan does not create a perpetual unrestricted permission.
Do not forge signatures or rewrite historical receipts to pretend the new design
was previously approved. Do not replay the old governor bootstrap.

### Reuse commitments: effect, not labels

Retain the useful patterns: Spec Kit's request-to-result continuity; mini-SWE's
simple action/observation loop; Agentless's reproduce/localize/repair/check;
Aider's relevant context and immediate feedback; Plandex's recoverable pending
changes; the small actually-used v08.7.2 comparison subset; native NACE truth
revision; IterBrow's existing persistence and recovery. Installing five competing
agents is not the objective. A pattern is not fulfilled merely by mentioning it.
Broader mathematics and sophisticated generalization remain deferred, not silently
completed. Mac portability and other product commitments remain in the Atlas.

### Execution hygiene and progress reports

Prepare source changes in the existing candidate checkout; compare with the live
dirty tree before installation. Do not start another IterBrow. Inspect actual
lifecycle state before a maintenance change; preserve saved tabs and durable state.
Keep all new harnesses, logs, and temporary evidence in /tmp. Record compact durable
results and limitations here; commit source milestones locally. No remote push is
implied. The old continuation automation stays paused until explicitly configured
for this plan; old queued continuation instructions are not current authority.

Tracking reports name the current stage, active claim, observed evidence,
unresolved work, counterexamples, and next dependency. This reporting discipline
is for the builder; it must not become required runtime paperwork for Iter.
Distinguish planned, implemented, isolated-tested, installed, and observed-live.
No invented completion percentages or claim that a passed fixture proves the PoC.

### Restoration acceptance and repository comparison — September 23, resumed

The user rejected the incomplete restoration checklist and explicitly renewed the
instruction to document the findings and actually complete restoration. R1's
completed result is recorded below; R2/R3 remain parked. This checkpoint supersedes the earlier instruction
to finish a particular /tmp repair exercise or build a small demonstration app.
Those were verification methods chosen by Codex, not the user's product contract.

Verified remote reference tips:
- main: a7d0f6742dc192db7102087a2290a3a13df4da80.
- TheWholeEnchilada: 1acd0448ea178e72f97e5c8a29b0898ac71d2847.
The latter is the fuller behavioral baseline, not a reset target. Current user and
Iter changes, state and beneficial additions must be retained.

**Earlier evidence — September 23, before the completed restoration below**
- Earlier source installation candidate-f86655061f944168af5e4933febf4d99 was
  rolled back automatically after the unchanged NACE courier timed out. Iter
  restarted on candidate-5d35cf7cd920433e9764336f60d5b1c1. Installed source did
  not establish active restoration; the earlier 60% estimate is withdrawn.
- Iter independently retrieved a semantic UI-verification lesson, used retained
  tool-output pagination, listed ten tabs and read the existing CRM unchanged.
  AtomSpace remained available with the same reasoner/epoch. Preserve those gains.
- Local-only workspace commit f238b4a restores ordinary self-repair without
  mandatory cards, original file-backed apply/full_loop/revert and regression
  checks; fixes PWQ JSON/context; batches native courier checks; adds status.
  Native NACE vetoes, Soul/memory protection and external recovery remain.
- 18 focused temporary-state tests, 23 existing recovery tests, 3 runtime-path
  tests, 4 chat tests and 5 episodic-reader tests passed. A read-only native
  ten-belief batch completed in 4.39s against the live AtomSpace. These are
  bounded checks, not yet successful installation or a finished restoration.
- evaluated_commit and recorded_commit are different operations: evaluating
  a state then recording the decision advances the journal. That alone is not drift.
- Original history.metta is a rolling log. A timestamp leaving that log is not
  proof of a retrieval bug; the reader was checked against current real records.

**R1 completion conditions**
1. Ordinary chat/research/inspection/editing/execution/browser/app work operates
   through Iter's existing loop without mandatory foundry stages, fixed
   alternatives, Atlas-label prerequisites or repeated routine approvals inside
   already-approved work.
2. Tools, transformations and channels can actually hot-load and self-repair.
   Installed behavior, not just saved source, establishes success. Any narrowing
   of previously supported repair paths is explicit and has a usable recovery route.
3. Failed hot-load recovery leaves or restores the exact working revision:
   invalid admission, changed-component failure, process exit/stall and abandoned
   probation are distinct cases. Recovery does not depend on broken candidate code.
4. The heartbeat and external supervisor detect relevant loss of progress and
   restore operation. Healthy waiting is not failure; explicit Stop stays stopped;
   recovery creates no duplicate Iter/supervisor. MeTTa recovery remains effective.
5. Behavioral degradation can be compared and reversed, not just crashes.
   Explicit component reversion preserves unrelated working changes; automatic
   failure recovery and subsequent authorized repair remain usable.
6. Semantic and episodic retrieval, task continuity, Soul/NACE/native reasoning
   and the durable AtomSpace remain effective. Code rollback never rewinds the mind.
7. Existing tabs/apps/source/data, sessions/groups/locks/pins, browser operations,
   screenshots, museum, dashboards, PWQ, CRM and integrations remain available.
8. Backups, export/import/restore and ordinary startup remain usable; restored disk
   state and live cognition agree. Provider settings, durable chat and the agreed
   45k input/output request limits are retained.
9. Keep useful persistence, memory, transport and recovery improvements. Remove
   imposed administration, not original capability or genuine human agency.

Evidence is proportional: exercise actual affected behavior and recovery paths,
reuse relevant existing evidence, and compare preserved state. Isolated failure
checks belong in /tmp and must not be passed off as a live demonstration. Do not
create test apps or test components in the user's source tree. A heartbeat alone,
a changed generation pointer or a successful signature is not completion.
Unrelated pre-existing defects do not expand R1 into an unlimited rebuild.
No invented percent complete.

**Resumed work position**
- R1 restoration is complete as scoped, September 23, approximately 22:07 PDT.
  Local workspace commits f238b4a, e2f617b and 5d6594c are installed. R2/R3,
  the question-driven PoC and independent CRM demonstration remain parked.
  Await user direction; this is not a claim that the larger build is finished.
- Final generation candidate-020df3208bee447694fed65ec23a28da is stable after
  three genuine completed cycles (2, 3, 4), promoted at 22:03:34 PDT. Parent:
  candidate-6dc8b861918b4fe99c0cd3837df9b526. Iter PID 42983; no duplicate
  Electron/Iter, fabricated heartbeat, mandatory ordinary-repair card or label.
- Iter actually ran ordinary self_improve full_loop on the prepared tracker
  repair; candidate-6dc8b861918b4fe99c0cd3837df9b526 promoted and its existing
  fitness log accepted it. The tiny positive fitness delta is not an intelligence
  claim. This proves repair execution, not independent Iter authorship of a CRM.
- Iter then reverted that component: candidate-58fea887309e4020b984ce43e2cd27a0
  completed cycle 12 on the old implementation. A provider connection failure in
  cycle 13 caused external rollback/restart to the healthy parent. Iter did NOT
  manually invoke rollback_probation. The host now distinguishes transient
  provider errors from component failure, without masking an actual health failure.
- Heartbeat, external rollback/restart, original file-backed repair/revert,
  regression checks, native NACE vetoes, Soul/memory protections and explicitly
  selected PWQ consent remain. Added mandatory foundry/PWQ ceremony and direct-write
  text detection are removed from ordinary work. Retained-output reads remain.
- Reliability batches now have an 8-second total transport deadline and retain
  their exact transaction for retry; timeout/offline deferral cannot advance
  projections. Native courier batching remains. Final live checks found neither
  recurring tracker/courier timeout nor tripped native circuit breakers.
- Multiline history dedup is now restart-safe; old history was not rewritten.
  Nop-only waiting no longer increments the host's silent-work reminder counter.
  Iter corrected the false consolidation task once through start_new_task and
  journaled that correction. Its current intention is verification, then waiting.
- A real Hyperon trie key-decoding precedence defect corrupted variable bindings
  at the current atom count. Reused the existing local one-line fix and rebuilt
  the native library, retaining DAS/pkg_mgmt/git features. All 63 native belief
  expectations passed against the full snapshot. Tagged summary results preserve
  known tools when one lacks a belief; a duplicate neutral source prior was removed,
  not learned beliefs. Seven known expectations plus one unavailable is not a reset.
- The native service restarted coherently: PID 54353 -> 42772, same epoch
  92d6e63a-6331-4cc8-9072-df8fdbbfa232 and reconstruction commit 3064; later
  ordinary activity reached 3081. No memory files changed during maintenance.
  The reported Python SIGABRT was isolated diagnostic PID 33950, not live Iter.
- Final UI reply was visually verified. Iter retrieved a real semantic lesson and
  recent episode. All ten tab URLs/order/pins and the existing CRM bundle remain;
  the user confirmed unlocking PWQ tab 2 during the check. No memory/data rewind.
  Later changes are the authorized task/journal and ordinary loop bookkeeping;
  the original resilience guard cleared its transient service-before-growth flag.
- PWQ read answered successfully (sequence 247, 32 items); no cards were changed.
  The old timeout string remained in a hidden toast, not a fresh visible failure.
  The bounded prompt-memory view is explicitly described as a projection, not an
  instruction to consolidate/delete notes. The 45k request allowances remain.
- Verification includes 12 residue tests, 18 restoration tests, 23 recovery tests,
  native full-state checks and the live results above. Prior archive CRC/replay
  evidence reconstructed 4,017 atoms at commit 2876; no live backup restore was
  performed. This is proportional restoration proof, not recertification of all apps.
- Native patch is tracked at scripts/patches/hyperon-0.2.10-trie-key.patch.
  Fresh-Mac installer integration remains part of the separate packaging commitment,
  not completed by this local-library repair. All new tests/logs/native build and
  before-images are under /tmp/iterbrow-context-restore-rj2eUr and
  /tmp/iter-hyperon-repair-WdhSR3. No GitHub push or control-document mirror.

### Historical work positions — superseded by the completed R1 checkpoint above

#### Latest handoff — September 23, 2026, after live restoration promotion

R1 is NOT complete. Do not start the question PoC.

The installed restoration candidate candidate-5d35cf7cd920433e9764336f60d5b1c1
promoted after externally observed completed cycles. Exact parent:
candidate-ef50eeefa8064a28ac5c4e007478f5bf. The approved repair work is
restoration-r1-20260923; its named paths are tools/self_improve.py,
tools/foundry.py and tools/revision_control.py. No new signature is needed for
revisions inside that scope. The user's latest request is restoration proof,
not resumption of the CRM or question-driven PoC.

Live evidence: Iter queried current AtomSpace status and visibly replied.
Independent checks preserved all ten tabs, reasoner PID 54353 and epoch
92d6e63a-6331-4cc8-9072-df8fdbbfa232. All 213 before-state files remain; only
experience/history and six routine loop-bookkeeping files changed. Semantic
memory files and saved episodes were unchanged. All 145 prior managed Python
sources were compared: only self_improve changed and foundry was retired.
Original CRM files and accepted data still match the control at revision 7.
This is preservation evidence, not proof of every original function.

Iter received a scoped request to reproduce and repair revision_control's
long-inline-JSON/path confusion using a /tmp harness and self_improve under
the existing approval. It registered the task, read source, and called
self_improve(action=status), which correctly reported unsupported action.
No repair has been authored/applied yet. Do not write its demonstration repair
for it or claim its task registration is an engineering result.

The next model turn could not fit: the preceding reply contained roughly
93,000 characters of reasoning. Exact duplicate removal alone was insufficient.
Candidate commit 77d5dc5 corrects this by retaining a WHOLE completed exchange
in the existing retained-output store and projecting bounded, explicitly
historical observations plus retrieval references. Original calls, results,
reasoning and experience are not rewritten; unfinished exchanges cannot be
parked and failed retention cannot silently discard the exchange.

The actual exchange reproduced 50,712 estimated tokens even with tool schemas
omitted; the corrected request-only replay used 16,966. No model was called
by that replay. Eleven focused restoration, 17 retained-output and ten request-
budget tests passed; seven durable-store tests also passed earlier. All new
harnesses/results are under /tmp/iterbrow-restoration-yf1oQr.

INSTALLED after the user's renewed proceed instruction: exactly iter/iter.py,
iter/iterbrow_runtime/request_budget.py and iter/iterbrow_runtime/tool_results.py
from candidate 77d5dc5. Desktop control was available; UI Stop succeeded.
All three live files matched the expected pre-change versions. Exact before-images
are in /tmp/iterbrow-context-restore-rj2eUr. Eleven focused checks passed again;
Iter was started once through the UI. The same self-repair task resumed.
At 18:47:59 PDT, the real request reached model_wait at 28,302 estimated tokens,
with one completed exchange retained rather than blocking the request.
This proves request flow, not completed self-repair.
The request-budget docstring and AGENTS description now accurately describe
whole-completed-exchange retention.

The independent preservation check retained all ten tabs, the same reasoner
PID/epoch, and all 213 before-state files. Only experience, history, current task
and five routine loop bookkeeping files changed. Original CRM source/control files
and accepted data were unchanged at revision 7. AtomSpace advanced naturally to
commit 2890. No browser/reasoner restart or reset.
The candidate-only app_revision_control description/client convenience remains
optional/uninstalled; the live manager resolves approved app work itself.

Live counterexample at 18:52: Iter read the retained output successfully, then
registered an unrelated memory-consolidation task. The runner had injected
"TASK COMPLETED" merely because the process restarted. The same incorrect
instruction also followed nop; it exists in pre-build snapshot 1acd044.
UI Stop succeeded before any consolidation tools executed. No memory rewrite
or promotion was requested or accepted as restoration evidence.

Candidate 7848fea replaces that false completion declaration with continuation
of unfinished user work and preserves autonomous work when genuinely idle.
Four /tmp tests exercise the actual loop branch: restart, nop/subsequent tick,
fresh user input, and ordinary task continuation. Installed with exact before-image
iter.py.before-resume under /tmp/iterbrow-context-restore-rj2eUr.
The existing repair was explicitly resumed through chat; no demonstration repair
code has been authored by Codex. This is R1 continuity repair, not R2 question wiring.

Next: verify the loaded Iter-authored repair and exact recovery, actual memory
retrieval, and an Iter-authored small app kept under /tmp. Only then assess R1
completion. Do not claim loaded self-repair from a source-copy test alone.
The old automation stays paused; no second Electron and no deployment of
iter/seeds/work_inquiry.metta.

The checkpoint below is retained context; this latest handoff takes precedence.

R0 is complete. The first R1 source milestone is candidate commit f0569ba:
Atlas labels are optional descriptive metadata in runtime/app revision contracts,
PWQ proposals and progress updates; their spelling no longer grants or withholds
execution permission. Existing approval scope, consent, candidate validation,
heartbeat supervision and rollback are retained.

Verification: 23 existing hot-load tests, 8 app-revision tests, 16 PWQ tests and
3 focused label-free activation/reporting/recovery checks passed (50 total).
The corrected PWQ suite now lives ONLY in
/tmp/iterbrow-correction-366Gwc/test_pwq_protocol_corrected.py. The repository's
prior test file was restored in commit 39a3787, following the user's reminder
that test files belong in /tmp. Its two old label-as-authorization expectations
are superseded by this plan; do not claim the untouched legacy suite passes the
new behavior. The /tmp suite was rerun successfully after relocation.
Focused checks exercise both runtime and app
activation without document labels, reject invalid approval tokens, restore the
parent revision, replay PWQ state, and show progress metadata cannot grant or
expand authority. Temporary harness/fixtures are under
/tmp/iterbrow-correction-366Gwc; no new harness or log was put in the repository,
and this correction leaves no test-file changes relative to the pre-correction
candidate. New and revised test code, logs and bytecode must stay outside the repo.
The first combined suite invocation failed to resolve test module names; direct
test-file invocations then ran all three intended suites successfully.

September 23 live restoration checkpoint (17:10 PDT):

- Source milestones 29b7d5b, ea33e1a and 8907e70 separate progress-report failure
  from runtime health, reuse approved runtime/app work across revisions, restore
  effective self_improve apply/full_loop and exact component reversion, and retire
  the model-facing foundry tool. Shared services and historical state remain.
- A fresh inspection found Iter running but unable to send requests: protected
  context estimated 56,039 tokens. The provider had returned the same reasoning
  both as plain text and structured text. Request projection now omits only exact
  duplicate fields, preserving structured reasoning and stored experience; a new
  actual user message can also release the preceding completed exchange.
- The loop was stopped through its UI, source conflicts checked, eight source
  before-images saved under /tmp/iterbrow-restoration-yf1oQr, and restoration source
  installed selectively. No second Electron, memory reset or reasoner restart.
  The parked work_inquiry seed was NOT installed.
- Managed candidate candidate-5d35cf7cd920433e9764336f60d5b1c1 changes self_improve
  and retires foundry; exact parent candidate-ef50eeefa8064a28ac5c4e007478f5bf retained.
  PWQ work restoration-r1-20260923 was approved through the UI under the user's
  standing delegation. Its named paths cover this restoration and Iter's repair
  of revision_control. The work does not authorize CRM/PoC feature changes.
- Actual live tool result: atomspace status at commit 2877, Hyperon ready.
  The visible chat reply was observed. A subsequent request estimated 28,821
  tokens; foundry was absent from its tool list. This proves the round trip, not
  the entire restoration.
- Independent CRM comparison: no changed control files, accepted data unchanged,
  revision 7. Before-state captured 10 tabs and 213 memory/state fingerprints,
  epoch 92d6e63a-6331-4cc8-9072-df8fdbbfa232 at commit 2876.
- Eight focused restoration tests, 23 existing hot-load tests, eight app tests,
  ten request-budget tests and three label-removal tests passed. New tests and
  all temporary evidence remain in /tmp. The app multi-revision fixture initially
  used the old parent on its second revision; correcting its parent reference
  made the intended two-revision check pass.

Next: observe promotion; let Iter reproduce and repair revision_control's long
inline-JSON/path handling defect, verify the active implementation and recovery
artifact, then demonstrate memory retrieval and a small app in /tmp. Do not call
R1 complete merely because source is installed. App work-scope resolution is in
the live manager; the optional shorter app-tool description/client convenience
is candidate-only, not yet in the active managed generation.
R2 preparation occurred before R1 completion; the user has corrected that sequence.
The following is retained, parked work, NOT the active implementation stage:
candidate source iter/seeds/work_inquiry.metta contains 17 question groups and
native selection for intake/resume/planning/change/failure/verification/learning.
It covers creative latitude, request fulfillment, real use, exact recovery, and
self-revision. It is deliberately NOT registered in the live seed manifest.

Fourteen actual-Hyperon isolated tests pass. Checks cover preference-conditioned
selection, visual/nonvisual work, self-revision, no idle prompt dump, addressed-
question suppression and complete prompt resolution. The first attempted old
sandbox interpreter had no Hyperon; verification then used the installed Python
environment in a separate process rooted in /tmp, without contacting live services.
The harness and all temporary native working directories are under
/tmp/iterbrow-inquiry-LnUE6b. No tests or logs were added to the repository.

Limits: addressed-question suppression currently consumes caller-supplied coverage;
automatic work/context invalidation, loop-event wiring, memory retrieval, NACE
preference learning, and evidence of improved live work are NOT yet established.
R1 corrective code is now installed/under live observation as described above;
R2 question code remains parked and unactivated. Processes/generations in the
historical sections below are not current observations. The old continuation
automation remains paused.

---

## Historical pause checkpoint — September 23, 2026 (superseded by the active plan above)

The following is retained evidence, not an instruction to resume the old rollout.

### Former position — PAUSED FOR DISCUSSION

**The user explicitly paused the build. Do not resume implementation, approve
further build cards, restart Iter, or follow the older continuation instructions
until the user explicitly resumes after discussion.** This current checkpoint
supersedes the historical September 22 handoff below.

### Reason for the pause

The user wants native reasoning equipped to build tools that work, fit IterBrow,
and improve it additively. Iter already had tool-building ability before this
effort. The concern is that the build has prioritized approvals, hashes,
certificates and compliance work over useful engineering capability, burdening
Iter with instructions rather than enabling its native reasoning. That concern
is a design issue to examine, not another requirement to encode as a new gate.
No architecture change or new implementation plan is approved by this checkpoint.

### Pause state and operational caveat

- Codex's `continue-iterbrow-build-atlas` heartbeat is **PAUSED**, confirmed by
  the automation tool and persisted configuration. Old queued heartbeat messages
  do not override the user's pause.
- Codex implementation work has stopped. The final documentation agent hit a
  usage limit; the primary agent is saving this checkpoint directly.
- **Iter's own loop is not confirmed stopped.** The UI stop attempt was blocked
  by an automatic-review usage limit. The user has been asked to click **Stop**
  in IterBrow. Do not claim a successful stop or bypass the rejected UI action.
  Last read-only observation: Iter PID **17957**, generation `ef50…`, cycle 12.
- Do not close or restart Electron/AtomSpace, reset memory, undo accepted data,
  replay bootstrap, or restore an older source tree merely to pause work.

### Exact saved implementation position

Live checkout: the user's local `IterBrow` checkout,
branch `TheWholeEnchilada`, with existing user changes preserved.
Candidate checkout: `work/foundry-integrated` in this Codex task,
branch `foundry-integration`. Do not recreate it.

| Item | Last verified state |
|---|---|
| Foundry platform | Frozen platform release `43a1577` installed; both previously authorized maintenance cycles completed. |
| Initial governor admission | Existing `human_bootstrap_v1` receipt remains historical authority. It is not a native successor proof; no production four-proof successor observer recipes have been installed. Never bootstrap again. |
| Protected sources | Last live guard read verified all **34**, at commit **2868**, same AtomSpace epoch `92d6e63a-6331-4cc8-9072-df8fdbbfa232`, PID **54353**. These are last observations, not perpetual current facts. |
| Host transport repair | `5734add` installed bounded request-copy projection, exact retained assistant/tool text and a host-owned reader. Original experience and opaque reasoning are preserved; oversize protected input still refuses explicitly. |
| Explicit reader/routing pilot | `251ae31d560bda786239f75031085a1d8f7e91aa` installed. Model remains `z-ai/glm-5.3`, estimated complete input/output allowances **45k/45k**; route preference is Phala-only with fallback disabled. No credential changes. |
| Settings preservation | `e18334188ccbf5a358d04176e3400d76fc374832` installed two nested-object merges in `renderer/renderer.js`; real Save/Start function checks passed. A sidebar-only reload picked it up. |
| Managed generation | `candidate-ef50eeefa8064a28ac5c4e007478f5bf` is **stable** in the actual active pointer, promoted at **12:30:31 PDT**. Exact previous generation is `candidate-7e46ab5fc83b4b35b46d3f85126c48e9`. Promotion is runtime-health evidence, not CRM completion. |
| Approval scope | Pilot `pwq-provider-routing-pilot-20260923-a` had genuine UI owner + runtime guardian **2/2**. Renderer follow-up `pwq-preserve-provider-settings-20260923-a` had genuine UI owner **1/1**. Guardian validation covers the managed wrapper, not the separate host/settings repair. |
| Original CRM | Last source/data comparison unchanged, revision **7**. It remains the immutable comparison control. |
| Independent CRM-2 | No new working CRM is demonstrated. Last PWQ read contains only unsigned `crm-two-proof-v1`, **0/1**, blueprint `f930614d779de9ba6bb19a38efa41cb603e5cee9316749de6567f0e775fd59f9`. No corrected v2 proposal or native-created project was verified. |
| Documentation checkpoint | Candidate commit `5b0173e` records the pilot and real reader acceptance in the Atlas. This pause entry is the newer control position. |

### What actually improved, and what did not

At **12:25:27**, Iter's actual `read_tool_result` call included both the retained
result ID and `/repository_context`, returning the exact historical selected
value with `eof=true`. At **12:27:07**, it sent an acknowledgment that was
independently visible in chat. The producing action was not replayed. This proves
one real multi-argument retrieval, not generally reliable reasoning or engineering.

The first pilot Start failed because Start also saved the Settings form and
discarded the route. Activation refused correctly. The separate two-line renderer
repair fixed that integration defect. The successful trial changed route, schema
and guidance together, so it does not isolate which change improved behavior.
The controlled provider comparison was only one synthetic observation per route.

Before installation, **214** memory/state file hashes, the **10 saved tabs**,
AtomSpace epoch and commit **2865** matched after the stopped-loop source/config
handoff. This is that exact maintenance boundary, not a claim that no later
experience or cognitive state was written. Preserve all subsequent learning.
Host/settings recovery is manual from private before-images; managed rollback
does not automatically restore those host files and must never rewind the mind.

Platform foundations have live evidence. Named-space, general native-loop and
learning mechanisms have integrated/isolated evidence, but the required complete
Iter-authored build trace is still missing. The reported **0/13 fully demonstrated
product clauses** is an end-to-end acceptance count, not a claim of zero code or
zero useful platform work. No defensible overall implementation percentage was
established. Zero new CRM functional workflows have been demonstrated.

### Iter's last work and unresolved material

The last chat direction resumed Iter's existing CRM draft with acceptance and
API-shape feedback, not Codex-authored feature code. At 12:30 it registered the
task, searched for its prior draft and called actual foundry help with an explicit
operation. No later proposal or build success is inferred from those calls.

The first stored v2 draft already includes most CSV, useful brief, durability and
recovery requirements. A later full-JSON variant dropped required invariants and
made research strings instead of records. Preserve this work; do not start over
or declare a failed/omitted-operation call accepted. Remaining acceptance gaps
include a material conversational revision, optional app cognition versus mandatory
builder named spaces, and evidence causally changing a later native choice.
The Mattermost connector remains a real dependency; a list of posts is not a
useful synthesized brief. Earlier source-inspection claims have mixed evidence:
PapaParse source/header is retained, while some other license/source results were
truncated. None of these outstanding checks authorizes continuing during the pause.

The wider architectural issue remains open: native governance is not universal
over existing shell/Python tools, and successful mechanical admission does not
prove improved engineering reasoning. More checks around a weak engineering
capability cannot by themselves establish that capability. Conversely, the
observed malformed calls and settings bug are real transport defects; the causal
share of transport, interface complexity and missing cognitive skill is not yet
measured. Discuss that distinction rather than claiming one proven root cause.

### Discussion boundary and resumption condition

Discuss how to preserve Iter's existing ability while providing a small, useful
engineering toolset: system knowledge, reusable examples, a fast build/run/observe/
repair path, recoverable changes and learning from concrete outcomes. Determine
which mechanical checks can be handled invisibly by tools, which complexity is
unnecessary, and what one observable improvement will justify the next slice.
This is a discussion agenda, not permission to build or remove safeguards.
Implementation resumes only after the user explicitly agrees to the revised plan.

All new temporary tests, harnesses, diagnostics and logs remain under
`/tmp/iterbrow-verification-bQWTj36X` (including private repair before-images).
Runtime journals remain in their existing ignored canonical locations. Preserve
user files and dirty changes; do not treat `/tmp` evidence as permanent storage or
claim the whole repo is clean. Source milestones are committed locally; no remote
push was performed by this handoff.

---

## Historical handoff — September 22 (superseded; do not execute)

Updated September 22, 2026. Governing decisions: ADR-0013/0014; contract:
software-foundry-magic-v2; preservation requirement: INV-39.

## Required result

A user discusses something they want with Iter. Iter researches, builds, shows
working behavior, preserves user-owned source/data, and handles revisions and
failed candidates. Named cognitive spaces, native engineering governance and
accumulated learning support that work. Codex develops the platform; Iter authors
the unprepared demonstration app. A passing platform fixture is not that proof.

The foundry is additive, not a replacement for Iter or a whitelist of allowed
products. Its first deployment adapters cover renderer apps and existing managed
Python self-repair. Source storage is language-neutral. Other build/test/deployment
adapters remain coverage gaps, not prohibitions on Iter's existing tools.

## Preserve the mind and existing capabilities

- The original agent loop and hot-load manager remain unchanged. The new runtime
  adapter uses the original canonical roots, quarantine, PWQ, supervisor and rollback.
- Semantic memory retains its authoritative atom identities and existing Chroma
  search projection. The new bounded lexical reader does not replace vector search.
- Episodic memory retains experience/history, recaps, tiers and the existing writers.
  Code rollback must not rewind the mind or discard the evidence of the failure.
- Work context returns both memories before alternatives are constructed. Work keeps
  a reproducible intake; a new work intake or explicit recall reads current sources.
  Hashes, coverage, truncation and unresolved links are visible—not hidden by a TTL.
- Optional memory-use citations bind source identity, hash, purpose and intake version
  into the native decision trace. They show proposed use, not independently proven
  interpretation. Recalled prose cannot grant authority or impersonate outcome evidence.
- Measured EngineeringEvidence changes native beliefs, ranking and proof requirements.
  It retains action/observation/evidence identities and the interpreting ruleset digest.

## Current evidence and gaps

| Commitment | Implemented and checked in isolation | Still required |
|---|---|---|
| Named cognitive fabric | Existing journal, named access/snapshots, stale-read rejection, replay | Actual live Iter build use |
| General native loop | Tool/RPC/service, recursive work, durable claims, independent observations, native comparison | Live adoption; remaining executor coverage; autonomous build/repair |
| Memory and learning | Both-memory intake/citations; failed actual fixture action changes later native ranking and browser proof duty | Real Iter's remembered experience improving its later work |
| Generic project/app lane | Language-neutral projects/history, blueprint/research, generic registration, original APP-2 recovery, external Contract-v2 verifier | Real Electron use, actual acceptance receipts and Iter-only feature authorship |
| Existing self-repair | Additive adapter over original hot-load/recovery manager | Before/after live capability and memory continuity |
| Protected governor evolution | Exact-source installer/guard; existing state-lock handoff; journal-authenticated proof/decision readers; native successor adoption/restore; explicit once-only human initial admission | Actual initial admission, live service/tool activation and four real successor observer recipes |
| Reuse and epistemics | Concrete isolated process/repair/context/rewind mechanisms; consumed, pinned native alignment subset | Real source-to-action-to-evidence trace; no full-quantale claim |
| Proof of magic | Not demonstrated | Iter builds an unprepared app, user uses/revises it, data survives, recovery works, later choice improves |

Known distinctions: a static check reports its exact file scope and unknown coverage;
it cannot pass an empty or unsupported scope. Browser testing can declare exact
expected app-record changes while checking that unrelated records remain intact.
This is observation, not an automatic data rollback mechanism. Source rollback and
domain-data recovery require separate evidence.

## Verification and deployment boundary

Focused native and integration checks cover fabric, learning, governor, service,
memory, adoption, source contexts, app/runtime adapters and mechanical observations.
Legacy application, hot-load/recovery and cognitive-domain regressions are retained.
The complete isolated suite passed: **345 tests in 104.209 seconds**, plus **13
mock-DOM browser checks** and four changed-JavaScript syntax checks.
The conflict-checked patch contains 50 undeployed runtime/test
files; no touched live-source conflicts were found at this handoff.
Mock browser checks are labeled as such; they are not visible Electron acceptance.

The exact source-parent/candidate/parent rehearsal preserved its synthetic memory.
That is a recovery rehearsal, not a claim that live memory/restart has passed.
The milestone is saved in local-only sandbox commit **17f09a4**, atop retained
source baseline **501ea39**. No GitHub push occurred. Release observation identity:
`foundry-release:141589f944bb150d3c38cc93f2021c56555c1cd0bda800bac2379db11dd2f41a`.

The separate host admission procedure is saved in local commit **399d73e**.
Its **12 temporary-state integration tests passed**, separately from the frozen
345-test release above. Read-only preflight verified the original evidence,
process-output hashes, source commit and complete live protected parent manifest;
it opened no live journal and wrote no live state. The procedure cannot sign for
the owner, control processes, edit source or renew expired evidence. Original-event
provenance and named control snapshots prevent substituted evidence and stale
approvals without treating unrelated memory activity as control drift.

Only control documents are integrated into the live checkout. New runtime code
remains isolated. No live memories or credentials were copied into the sandbox,
and no second live IterBrow was started. Baseline hashes preserve concurrent edits
during handoff. No activation signature or evidence has been fabricated.

## Next dependency, not a new project

The handoff implementation is connected. Initial admission is explicit human
trust-root initialization, not an invented native successor decision. It requires
its own exact PWQ scope and separately observed guardian evidence; a permanent
once-only journal marker prevents later bootstrap bypasses.

The existing UI Stop was used and verified. Electron remains open: the safety
reviewer refused closing it without explicit shutdown/restart approval, which has
been requested and was not bypassed. After approval, use the inspected single-owner
lifecycle, merge the conflict-checked source patch, activate through
the existing authorization boundary, and prove memory/capability continuity with
one Electron/Iter owner. Next use Iter's chat to obtain an unprepared app and a
material requested revision; Codex must not author or repair its features.
The proposed handoff actually requires two short shutdown/restart cycles, so
approval must explicitly cover both. Admission verifies the installed protected
governor manifest; all other installed changed files and modes need a separate
comparison against the reviewed candidate.

Live model participation separately encounters OpenRouter credit rejection
(HTTP 402). The reported input allowance is not a local setting. Iter's output
cap is 2,524; increasing it to 30,000 does not increase available credits. No model,
credit or memory setting has been changed pending the user's clarification.
The existing context coordinator is only a character budget for selected system
injections; its estimated 32k window is not a whole-request token allowance.
Managed tool probation requires genuine healthy cycles, never fabricated heartbeats.
Saved release evidence retains its original expiry. Obtain a fresh observation
when admission can proceed if needed; do not restamp it or repeatedly run the
suite while shutdown approval is missing.

The first proof closes BC-01–BC-08 plus BC-11–BC-13 together. Application-domain
cognition is optional BC-09; a second materially different category proves BC-10.
All thirteen COM commitments remain open until their stated evidence exists.
CRM CSV/Mattermost value and one-command Mac installation are retained obligations,
not cancelled work. The existing continuation schedule has been updated to preserve
this scope and the current isolated/live distinction.
