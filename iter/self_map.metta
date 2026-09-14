;; Self Map -- Service-Before-Growth Governance Rule (Item 4, added 2026-09-14)
;;
;; Ported from ClarityOmega/soul/self_map.metta's `service-before-growth`
;; priority rule: user-project state must be checked before the system
;; pursues its own growth goals, and self-directed work should only proceed
;; when no user has pending high-priority need for attention right now.
;;
;; This file is the MeTTa-side DOCUMENTATION of the rule. The actual
;; enforcement lives in two Python call sites (dormant-engine-safe, since
;; pymetta is not installed on this machine -- see tools/_metta_gate.py):
;;   - transformations/cognitive_resilience_guard.py sets the flag
;;     (memory/.service_before_growth_flag.json, 30-min TTL) when
;;     send-discipline has recurringly degraded -- see that file's
;;     docstring for the real 2026-09-14 evidence (9 nag firings in
;;     under 40 minutes during one repair session).
;;   - transformations/auto_improve.py checks the flag before writing
;;     memory/.improve_needed (the actual self-build trigger) and defers
;;     the proposal, with a note to the model, while the flag is active.
;;
;; Dormant until pymetta is installed -- documents the rule so a live-engine
;; cross-check can later confirm the Python path agrees, matching
;; nace_courier.py's established "Python computes, MeTTa validates" split
;; used throughout this registry.

(= (may-pursue-growth)
   (if (service-before-growth-flag-active) False True))

;; service-before-growth-flag-active is a placeholder predicate here -- the
;; real truth lives in memory/.service_before_growth_flag.json (a file, not
;; a belief atom, deliberately, since it needs a wall-clock expiry that
;; plain MeTTa facts don't carry on their own). This equation exists for
;; documentation and future live-engine parity, not as the enforced path.
(= (service-before-growth-flag-active) False)

(soul-value service (stv 1.0 0.9))
(soul-rule service-before-growth "self-directed building defers to demonstrated service of the current user thread")
