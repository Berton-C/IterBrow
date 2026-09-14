;; Capability Lifecycle & Priority Registry -- IterBrow
;; Added 2026-09-14 as part of the capability_registry wiring (Item 1).
;;
;; Read directly by tools/_metta_gate.py as PLAIN TEXT via regex (see that
;; file's docstring) -- NOT evaluated through the pymetta engine, because
;; pymetta is not currently installed on this machine (tools/metta.py falls
;; back to its stub, ENGINE_AVAILABLE=False). The equations below exist so
;; the exact same pipeline is expressible in MeTTa once the engine dependency
;; (SWI-Prolog 9.3+ and `pip install 'pymetta[engine]'`) is installed -- at
;; that point they become a live cross-check against the Python path, the
;; same "Python computes, MeTTa validates" split nace_courier.py already
;; uses for Truth_Revision.
;;
;; ─── TRUST LIFECYCLE (4 stages, added 2026-09-14 Stage 3 of the "theater to
;; governance" pass) ───────────────────────────────────────────────────────
;; `cap-lifecycle` now names a manual OVERRIDE, not the whole story. Only two
;; values are ever written here by hand:
;;
;;   candidate                               -- declare this the moment a
;;                                              capability is self-built and
;;                                              registered (AGENTS.md
;;                                              "Instrument everything").
;;                                              Forces the most conservative
;;                                              treatment regardless of
;;                                              whatever efficacy number
;;                                              shows up later -- remove the
;;                                              line yourself once you trust
;;                                              it enough to let it graduate
;;                                              on evidence like everything
;;                                              else. (Replaces the old
;;                                              single "new" value -- same
;;                                              idea, now actually enforced;
;;                                              see _metta_gate.py.)
;;   quarantined                             -- confirmed repeated real
;;                                              failure (f=0.0 across
;;                                              multiple genuine attempts,
;;                                              not just low confidence).
;;                                              Manual override: always
;;                                              flagged regardless of the
;;                                              live efficacy number. Lift by
;;                                              editing this file after the
;;                                              underlying bug is fixed and
;;                                              re-verified.
;;
;; Every OTHER capability (no line here at all) has its trust stage derived
;; automatically by _metta_gate.py from the confidence `c` already tracked in
;; nace_beliefs.metta -- no separate bookkeeping, no hand-edited numbers:
;;
;;   candidate        (no cap-efficacy belief atom yet at all)  -- treated
;;                    the same as a manually-declared candidate: always
;;                    ADVISE, never a silent fail-open ALLOW, so a truly
;;                    untested capability is never invisible.
;;   probe_eligible   (c < 0.4)   -- has SOME real evidence but not enough to
;;                    earn priority treatment yet: the flat 0.3 threshold
;;                    applies even if cap-priority=critical (no floor
;;                    discount while still probing).
;;   authoritative    (0.4 <= c < 0.8)  -- normal behavior, unchanged from
;;                    the old single "active" stage: critical floor discount
;;                    applies if declared critical, flat 0.3 otherwise.
;;   durable          (c >= 0.8)  -- sustained, well-evidenced track record.
;;                    Gets a small additional floor discount (0.05, never
;;                    below an absolute 0.10 floor) on top of whatever its
;;                    priority already earns -- reflects genuinely earned
;;                    trust, not a default.
;;
;; This list is intentionally not a MeTTa fact for each capability: it's a
;; live function of already-accumulated confidence, so it can't drift out of
;; sync with nace_beliefs.metta the way a hand-maintained parallel list would.
;;
;; priority values:
;;   normal      (default, no line needed)   -- flat 0.3 threshold applies
;;   critical                                -- load-bearing infrastructure;
;;                                              uses a lower floor (0.15,
;;                                              see _metta_gate.py) so noisy-
;;                                              but-real efficacy doesn't
;;                                              trip a veto the way a flat
;;                                              threshold would (this is not
;;                                              hypothetical -- websearch's
;;                                              real logged expectation is
;;                                              ~0.296, under the old flat
;;                                              0.3 line, despite ~1000 real
;;                                              calls and c=0.98 confidence)
;;
;; Evidence for the 2026-09-14 classifications below: real cap-efficacy
;; values pulled from this machine's live nace_beliefs.metta, all showing
;; f=0.0 (zero successes) with meaningful confidence (c >= 0.25, i.e. not
;; just "never tried") -- see gate_simulation.py in the project notes for
;; the full old-vs-new verdict comparison across all 47 live capabilities.

(cap-lifecycle browser_cdp quarantined)      ;; f=0.0 c=0.3077
(cap-lifecycle lm_studio_chat quarantined)   ;; f=0.0 c=0.3571
(cap-lifecycle browser_click quarantined)    ;; f=0.0 c=0.25
(cap-lifecycle browser_type quarantined)     ;; f=0.0 c=0.3077
(cap-lifecycle museum_vote quarantined)      ;; f=0.0 c=0.3077

;; Manually-declared candidates -- see "TRUST LIFECYCLE" note above. Remove a
;; capability's line here once you're satisfied it should graduate to having
;; its stage derived from evidence like everything else.
(cap-lifecycle idle_cycle_detector candidate)
(cap-lifecycle cognitive_resilience_guard candidate)
(cap-lifecycle task_state candidate)
(cap-lifecycle completion_claim_guard candidate)

(cap-priority websearch critical)
(cap-priority send critical)
(cap-priority shell critical)
(cap-priority python critical)
(cap-priority memory_update critical)
(cap-priority remember critical)
(cap-priority episodes critical)
(cap-priority chroma_query critical)
(cap-priority self_improve critical)
(cap-priority metta critical)
(cap-priority screenshot critical)
(cap-priority search_transcript critical)

;; ─── MeTTa-side parity equations (dormant until pymetta is installed) ───
;; Same pipeline as tools/_metta_gate.py's Python implementation, expressed
;; in MeTTa for when the live engine becomes available as a cross-check.

(= (current-lifecycle $cap)
   (match &self (cap-lifecycle $cap $l) $l))
(= (current-lifecycle $cap) auto)  ;; no manual override -> stage derived from evidence, see Python

(= (current-priority $cap)
   (match &self (cap-priority $cap $p) $p))
(= (current-priority $cap) normal)

;; NOTE: `trust-stage`/`gate-floor` below are the MeTTa-side parity sketch of
;; the 4-stage trust lifecycle. The confidence-driven derivation (candidate /
;; probe_eligible / authoritative / durable from nace_beliefs.metta's `c`) is
;; the actual live logic and lives in tools/_metta_gate.py's
;; `_determine_trust_stage`, since that's the path this repo actually runs
;; today (pymetta not installed) -- this equation is the cross-check target
;; for when the live engine is available, not a second live implementation.
(= (trust-stage $cap $c)
   (if (== (current-lifecycle $cap) candidate) candidate
       (if (< $c 0.4) probe_eligible
           (if (< $c 0.8) authoritative
               durable))))

(= (gate-floor $cap $stage)
   (let $base (if (== (current-priority $cap) critical) 0.15 0.3)
     (if (== $stage probe_eligible) 0.3
         (if (== $stage durable) (max 0.10 (- $base 0.05))
             $base))))

(= (registry-gate-verdict $cap $stage $expectation)
   (if (== (current-lifecycle $cap) quarantined)
       VETO
       (if (== $stage candidate)
           ADVISE
           (if (>= $expectation (gate-floor $cap $stage))
               ALLOW
               ADVISE))))
