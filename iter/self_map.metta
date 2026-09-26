;; Self Map -- Service-Before-Growth Governance Rule (Item 4, added 2026-09-14)
;;
;; Ported from ClarityOmega/soul/self_map.metta's `service-before-growth`
;; priority rule: user-project state must be checked before the system
;; pursues its own growth goals, and self-directed work should only proceed
;; when no user has pending high-priority need for attention right now.
;;
;; This file is a declared native-reasoning seed and documents the rule.
;; Fail-safe enforcement also lives in two Python call sites:
;;   - transformations/cognitive_resilience_guard.py sets the flag
;;     (memory/.service_before_growth_flag.json, 30-min TTL) when
;;     send-discipline has recurringly degraded -- see that file's
;;     docstring for the real 2026-09-14 evidence (9 nag firings in
;;     under 40 minutes during one repair session).
;;   - transformations/auto_improve.py checks the flag before writing
;;     memory/.improve_needed (the actual self-build trigger) and defers
;;     the proposal, with a note to the model, while the flag is active.
;;
;; Hyperon can cross-check the Python enforcement path; neither path writes
;; the other's state.

(= (may-pursue-growth)
   (if (service-before-growth-flag-active) False True))

;; service-before-growth-flag-active is a placeholder predicate here -- the
;; real truth lives in memory/.service_before_growth_flag.json (a file, not
;; a belief atom, deliberately, since it needs a wall-clock expiry that
;; plain MeTTa facts don't carry on their own). This equation exists for
;; native reasoning parity, not as the wall-clock authority.
(= (service-before-growth-flag-active) False)

(soul-value service (stv 1.0 0.9))
(soul-rule service-before-growth "self-directed building defers to demonstrated service of the current user thread")
