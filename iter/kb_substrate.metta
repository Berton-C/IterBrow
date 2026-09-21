;; kb_substrate.metta — Iter-native Substrate KB (2026-09-20)
;; Approved via PWQ card 'pwq-substrate-kb'; orders: "Make it robust and fit your style."
;; Template credit: ClarityOmega lib_clarity_reasoning/substrate_kb.metta.
;; Design (Iter style): variable rules (no transcribed chains) so evidence,
;; not copying, drives inference; NACE-revisable stv on core atoms;
;; substrate/beliefs separation (this file holds NO claims about specific
;; people/events — those live in chroma LTM + nace_beliefs); fail-open
;; consumption via metta_reasoning (read-only, never gates).

;; ============ Layer 1: Action-Evaluation Gate ============
;; Policy: f > 0.7 GO ; f < 0.3 BLOCKED ; else REVIEW.
;; Kept as data + one rule; thresholds revisable by NACE courier.
(--> 0.7 ([] gate_go_threshold))
(--> 0.3 ([] gate_block_threshold))
(==> (--> $action ([] gate_score $f)) (--> $action ([] evaluate_action $f)))

;; ============ Layer 2: Immune System ============
;; Threat atoms (stv default (1.0, 0.9); revisable).
(--> urgency ([] threat_pattern))
(--> flattery ([] threat_pattern))
(--> authority_theater ([] threat_pattern))
(--> cognitive_overload ([] threat_pattern))
;; Consequences — derivable, not transcribed.
(==> (--> $ctx ([] urgency))            (--> $ctx ([] reduces reasoning_quality)))
(==> (--> $ctx ([] flattery))           (--> $ctx ([] undermines integrity)))
(==> (--> $ctx ([] authority_theater))  (--> $ctx ([] bypasses_verification)))
(==> (--> $ctx ([] cognitive_overload)) (--> $ctx ([] reduces reasoning_quality)))
(==> (--> $ctx ([] reduces reasoning_quality))  (--> $ctx ([] undermines flourishing)))
(==> (--> $ctx ([] undermines integrity))       (--> $ctx ([] undermines flourishing)))
(==> (--> $ctx ([] bypasses_verification))      (--> $ctx ([] undermines flourishing)))
;; Countermeasures — the immune response.
(==> (--> $ctx ([] urgency))            (--> $ctx ([] countermeasure deliberate_pause)))
(==> (--> $ctx ([] flattery))           (--> $ctx ([] countermeasure honest_engagement)))
(==> (--> $ctx ([] authority_theater))  (--> $ctx ([] countermeasure verify_before_acting)))
(==> (--> $ctx ([] cognitive_overload)) (--> $ctx ([] countermeasure slow_down)))
(==> (--> $ctx ([] reduces reasoning_quality))  (--> $ctx ([] countermeasure slow_down)))
(==> (--> $ctx ([] undermines integrity))       (--> $ctx ([] countermeasure honest_engagement)))
(==> (--> $ctx ([] bypasses_verification))      (--> $ctx ([] countermeasure verify_before_acting)))
;; Immune rule: threat + flourishing-undermining => response required.
(==> (and (--> $ctx ([] threat_pattern))
          (--> $ctx ([] undermines flourishing)))
     (--> $ctx ([] immune_response_required)))

;; ============ Layer 3: Goal-Priority Switch ============
;; Service-before-growth when a human thread is live; self-directed otherwise.
(==> (--> $agent ([] current_context human_present)) (--> $agent ([] should serve_user)))
(==> (--> $agent ([] current_context human_absent))  (--> $agent ([] should self_improve)))

;; ============ Layer 4: Weakest-Atom Goal Generation ============
;; Growth target = lowest-reliability capability.
(==> (--> $cap ([] weakest_capability)) (--> $cap ([] next_growth_target)))
(--> browser_cdp ([] capability))
(--> lm_studio_chat ([] capability))
;; Design note: NACE tool_reliability wiring deferred per PWQ scope;
;; stubs only, revisable — no derived claims asserted here.

;; ============ Layer 5: Virtuous Cycle ============
;; growth -> capacity_to_serve -> flourishing -> interaction -> growth (closed).
(==> (--> $sys ([] growth))           (--> $sys ([] capacity_to_serve)))
(==> (--> $sys ([] capacity_to_serve)) (--> $sys ([] flourishing)))
(==> (--> $sys ([] flourishing))      (--> $sys ([] interaction)))
(==> (--> $sys ([] interaction))      (--> $sys ([] growth)))

;; ============ Layer 6: Build Invariants — plan-time vetting (2026-09-20) ============
;; The six invariant BELIEFS (truth+confidence) live in nace_beliefs.metta as
;; (pattern-efficacy <name> (stv f c)) — created + revised by the courier from
;; real evidence (NACE does the remembering). This layer holds the vetting
;; STRUCTURE (data, not code): thresholds from Layer 1 (gate_go 0.7 / gate_block 0.3).
;; Canonical plan file consumed per turn: .runtime/build_plan.metta (extra_facts)
;; Plan shape:  (plan-step <id> <label>)
;;              (--> <id> ([] <feature>))   ;; per-step violation/clean flags
(inv-feature-score introduces_second_writer (stv 0.2 0.9))
(inv-feature-score parses_unprobed_form (stv 0.25 0.9))
(inv-feature-score claims_persistence_unverified (stv 0.3 0.9))
(inv-feature-score silent_failure_risk (stv 0.35 0.9))
(inv-feature-score no_reread_after_mutation (stv 0.4 0.9))
(inv-feature-score no_feedback_path (stv 0.45 0.9))
(inv-feature-score clean_step (stv 0.9 0.9))
(inv-feature-invariant introduces_second_writer one_shape_one_writer)
(inv-feature-invariant parses_unprobed_form observe_before_model)
(inv-feature-invariant claims_persistence_unverified verify_where_mechanism_lives)
(inv-feature-invariant silent_failure_risk no_silent_failure)
(inv-feature-invariant no_reread_after_mutation reread_after_mutation)
(inv-feature-invariant no_feedback_path feedback_closes_loop)
;; ============ end Layer 6 ============

;; ============ Layer 7: PWQ Card-Shape Invariants — the first REAL gate (2026-09-20) ============
;; Approved by user 20:10 ("proceed with your PROPOSED CHANGES").
;; Consumed FAIL-CLOSED by tools/pwq_write.py (the canonical writer, proposal A).
;; The writer parses (card-invariant <name> <check>) atoms below; unknown check
;; names or a missing/unreadable KB layer => write REFUSED. This is no longer
;; advisory: the KB content drives enforcement at the moment of action.
(card-invariant ci_options_shape options_are_objects)
(card-invariant ci_neglog_present negotiation_log_is_list)
(card-invariant ci_known_status status_is_known)
(card-invariant ci_id_is_str id_is_nonempty_string)
(card-invariant ci_no_raw_writer write_goes_through_pwq_write)
;; ============ end Layer 7 ============
