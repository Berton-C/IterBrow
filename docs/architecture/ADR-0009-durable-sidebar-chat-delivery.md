# ADR-0009: Durable, replayable sidebar chat delivery

- Status: accepted and live-verified
- Date: 2026-09-22
- Atlas scope: IterBrow Core chat bridge, Platform lifecycle/state, QA-1

## Context

The sidebar chat previously treated transient inbox/outbox files and a single
Electron IPC event as sufficient delivery. Iter could successfully call
`send`, Electron could delete the outbox file, and the reply could still be
lost if the sidebar listener was loading or reloading. `Path.write_text()` also
published the outbox filename before the payload was guaranteed complete, so a
poll could observe an empty or partial file. App restart erased the visible
conversation. Finally, the transcript projection looked for a nonexistent
`message` argument even though the send tool's argument is `content`, leaving
blank delivery evidence.

These are delivery-boundary defects, not failures of the language model or the
AtomSpace. A healthy `send` tool result alone therefore cannot prove that the
human received a reply.

## Decision

1. Electron's main-process chat bridge is the sole writer of
   `.runtime/electron_ui/messages.jsonl`, a durable application-state journal
   containing stable message IDs, roles, timestamps, and content.
2. User input is published to the cognition inbox by same-filesystem atomic
   rename. The current plain-text inbox payload remains compatible with every
   retained generation.
3. Iter publishes a versioned JSON message envelope to the outbox by
   same-filesystem atomic rename. Electron continues to accept legacy plain-text
   outbox files from retained generations.
4. Electron does not remove an outbox item until its message has been appended
   and synced to the journal. An unreadable or unjournaled item remains queued
   for a later poll.
5. The sidebar registers its live listener before requesting history, merges
   both streams by stable message ID, and renders in timestamp order. Reload and
   app restart replay history without duplicating a message.
6. Focus, visibility restoration, and a bounded two-second timer reconcile the
   visible sidebar with main-process history, Iter process status, and activity
   state. The timer is idempotent, permits only one reconciliation at a time,
   and performs no chat redraw when all stable IDs and bodies already match.
   macOS can suspend a `WebContentsView` at screen lock without delivering a
   useful renderer focus/visibility transition, and a current renderer DOM can
   then remain displayed as a stale native frame. The sidebar therefore
   disables background throttling; the main process sends an explicit resume
   signal, reattaches the existing child view, restores its bounds and
   visibility, and invalidates it on `unlock-screen`, `resume`, and window
   focus/show/restore. Reconciliation never hides the view because a lost
   follow-up compositor task can otherwise leave a live DOM behind a blank
   native surface. A second bounded pass covers the interval in which macOS has
   emitted focus/unlock but WindowServer has not yet restored the surface.
   Timer/DOM reconciliation alone is not accepted as visible proof.
7. A final incomplete journal record is preserved under the manifest-classified
   `.runtime/electron_ui/recovery/` log and truncated before replay. A malformed
   complete record is surfaced in the system log and skipped because chat
   history is a replay aid, not cognitive authority.
8. The transcript projection records `send.content`, retaining `message` only
   as a compatibility fallback for historical episodes.
9. The durable journal is portable application state. Inbox, outbox, and
   staging directories remain transient caches and are excluded from export.

## Consequences

- Electron consumption now proves durable receipt by the UI subsystem, even if
  the sidebar is not ready at that instant.
- Renderer readiness or temporary suspension is no longer an unobservable
  message-loss boundary; a resumed view repairs its data from durable history
  and crosses an explicit native compositor repaint boundary.
- Old immutable generations continue to communicate while a new channel
  implementation moves through PWQ authorization and hot-load probation.
- Visible acceptance is separately evidenced by one labeled round-trip in the
  unlocked native sidebar after restart and lock/unlock; journal receipt alone
  was not used as visual evidence.
- Chat content becomes portable state and should be handled with the same care
  as other exported user application state.

## Verification

- Real Node bridge test: atomic user queue publication, legacy and versioned
  Iter replies, journal-before-delete, stable-ID deduplication, restart replay,
  and incomplete-tail recovery.
- Channel test: a hot-loaded channel publishes one complete versioned envelope
  and leaves no staging residue.
- Renderer boundary test: live listener registration precedes history replay,
  both paths merge by stable ID, focus/visibility/timer reconciliation is
  single-flight and idempotent, and Electron owns the OS resume/repaint hook.
- Transcript test: a real `send(channel, content)` tool call preserves the body.
- Final acceptance: probe `CHAT-ACCEPT-20260922-E` and its exact ACK each occur
  once in the durable journal across restart and once in the live native
  sidebar after unlock. The same view reports the current `running` process
  state, closing the stale-frame and blank-surface counterexamples.

## Rollback

Restore the prior bridge, preload, renderer, channel, and transcript source.
Legacy plain-text queue compatibility means cognition can continue using the
same inbox/outbox directories. Leave `messages.jsonl` intact as evidence; the
old bridge will ignore it. No AtomSpace rollback is required.
