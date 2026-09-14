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
;; lifecycle values:
;;   active      (default, no line needed)   -- normal gate behavior
;;   new                                     -- grace period; not used yet,
;;                                              reserved for a capability
;;                                              that's freshly self-built and
;;                                              has too little data to judge
;;                                              (see task_state.metta phase
;;                                              atoms / AGENTS.md "Extending
;;                                              Iter" convention for how new
;;                                              capabilities get registered
;;                                              here with lifecycle=new)
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
(= (current-lifecycle $cap) active)

(= (current-priority $cap)
   (match &self (cap-priority $cap $p) $p))
(= (current-priority $cap) normal)

(= (gate-floor $cap)
   (if (== (current-priority $cap) critical) 0.15 0.3))

(= (registry-gate-verdict $cap $expectation)
   (if (== (current-lifecycle $cap) quarantined)
       VETO
       (if (>= $expectation (gate-floor $cap))
           ALLOW
           ADVISE)))

;; Item 2/3 self-built capabilities registered per AGENTS.md's
;; "Instrument everything" policy (2026-09-14).
(cap-lifecycle idle_cycle_detector new)
(cap-lifecycle cognitive_resilience_guard new)
(cap-lifecycle task_state new)
(cap-lifecycle completion_claim_guard new)
