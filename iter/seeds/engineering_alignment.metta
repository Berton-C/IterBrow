;; EPI-1: minimal, bounded categorical path subset from ClarityOmega v08.7.2.
;; Source: lib_clarity_reasoning/
;; lib_quantale_autopoietic_epistemic_dynamics_engine_v08_7_2_SOUL_EVOLUTIONARY_CANONICAL_TOPOLOGY.metta
;; Source SHA-256: 693089e6b69d3b40c0772e3a068e337bb325048f39f9e0a4f8bd9e6f66012851
;; Original rule: q-alignment-path-status?, eight aligned/drift combinations.
;; Adaptations: namespaced symbols; total explicit unresolved behavior for unknown
;; inputs. Pure native comparison only: no authorization, persistence or mutation.
;; This is NOT the full engine or a quantale/lattice claim. Numeric pbit meet/join
;; are intentionally not imported: the audited pair operators fail absorption.
;; Inputs are authenticated ground observations supplied by the governor capsule;
;; project atoms and candidate code cannot add equations to this trusted seed.
;;
;; MIT License
;; Copyright (c) 2026 Patrick Hammer
;; Copyright (c) 2026 Berton Bennett
;; Permission is hereby granted, free of charge, to any person obtaining a copy
;; of this software and associated documentation files (the "Software"), to deal
;; in the Software without restriction, including without limitation the rights
;; to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
;; copies of the Software, and to permit persons to whom the Software is
;; furnished to do so, subject to the following conditions:
;; The above copyright notice and this permission notice shall be included in all
;; copies or substantial portions of the Software.
;; THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
;; IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
;; FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
;; AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
;; LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
;; OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
;; SOFTWARE.

(engineering-alignment-provenance-v1
 "693089e6b69d3b40c0772e3a068e337bb325048f39f9e0a4f8bd9e6f66012851"
 "MIT" categorical-path-only)

(= (engineering-alignment-path aligned aligned aligned) integrating-alignment)
(= (engineering-alignment-path aligned drift aligned) disintegrating-middle-drift)
(= (engineering-alignment-path aligned aligned drift) disintegrating-outcome-drift)
(= (engineering-alignment-path drift aligned aligned) disintegrating-origin-drift)
(= (engineering-alignment-path drift drift aligned) accidental-landing-not-bankable)
(= (engineering-alignment-path aligned drift drift) blocked-cascade-drift)
(= (engineering-alignment-path drift aligned drift) unstable-cross-current)
(= (engineering-alignment-path drift drift drift) disintegrating-alignment)

(= (engineering-alignment-known $state)
   (if (== $state aligned) True (== $state drift)))

(= (engineering-alignment-status $intention $action $outcome)
   (if (engineering-alignment-known $intention)
     (if (engineering-alignment-known $action)
       (if (engineering-alignment-known $outcome)
         (engineering-alignment-path $intention $action $outcome)
         unresolved)
       unresolved)
     unresolved))

;; A correct outcome reached by a drifting action is not accepted as aligned.
;; This comparison can constrain the native build decision but cannot mint
;; execution authorization or weaken the governor's fixed proof obligations.
(= (engineering-alignment-admissible $intention $action $outcome)
   (== (engineering-alignment-status $intention $action $outcome)
       integrating-alignment))

;; IterBrow constitutional obligation composition (new, NOT attributed to v08).
;; Independent trusted observers report these statuses; candidate self-reports
;; are not inputs. Authorization and proof authenticity stay outside this rule.
;; The native result alone has no activation authority.
(= (engineering-change-proof-pair $left $right)
   (if (== $left failed) failed
     (if (== $right failed) failed
       (if (== $left passed)
         (if (== $right passed) passed unknown)
         unknown))))

(= (engineering-change-proof-verdict $status)
   (if (== $status passed) activate
     (if (== $status failed) reject unresolved)))

(= (engineering-governor-change-verdict
     (governor-change-obligations-v1 $shadow $counterexamples $restart $rollback))
   (engineering-change-proof-verdict
     (engineering-change-proof-pair
       (engineering-change-proof-pair $shadow $counterexamples)
       (engineering-change-proof-pair $restart $rollback))))
