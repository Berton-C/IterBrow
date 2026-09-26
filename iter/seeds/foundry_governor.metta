;; BUILD-LOOP-1. Only trusted source plus authenticated ground capsules enter
;; this evaluator. Python owns identity/transport, not the outcomes below.
(= (foundry-any-negative nil) False)
(= (foundry-any-negative (cons (engineering-history $evidence-id $label) $tail))
   (if (== $label negative) True (foundry-any-negative $tail)))

(= (foundry-verification-phase $action)
   (if (== $action "test.static") True
      (if (== $action "test.browser") True (== $action "app.activate"))))

;; A source-writing action predicts staged source, not working renderer output.
;; Learned renderer debt belongs to verification/activation, not an impossible
;; immediate browser proof on every individual source write.
(= (foundry-learned-browser $action $class $history)
   (if (foundry-verification-phase $action)
      (if (== $class "renderer") (foundry-any-negative $history) False) False))

(= (foundry-append nil $right) $right)
(= (foundry-append (cons $head $tail) $right)
   (cons $head (foundry-append $tail $right)))

(= (foundry-required-invariants $declared)
   (cons "source-boundary" (cons "data-preserved" (cons "authorization-current" $declared))))

(= (foundry-activation-action $action)
   (if (== $action "app.activate") True (== $action "runtime.activate")))

(= (foundry-recovery-action $action)
   (if (== $action "app.rollback") True (== $action "runtime.rollback")))

(= (foundry-action-duties $action $duties)
   (if (== $action "test.static") (cons "syntax" $duties)
      (if (== $action "test.browser") (cons "browser-workflow" $duties)
         (if (foundry-activation-action $action) (cons "activation-health" $duties)
            (if (foundry-recovery-action $action) (cons "recovery-exact" $duties)
               (if (== $action "runtime.validate") (cons "runtime-static" $duties) $duties))))))

(= (foundry-plan-local
    (foundry-plan-context $work $strategy $action $class $history $invariants $obligations $memory))
   (foundry-dispatch $work $strategy
      (cons "process-exit" (cons "prediction-match"
         (foundry-action-duties $action
            (foundry-append (foundry-required-invariants $invariants)
               (if (foundry-learned-browser $action $class $history)
                   (cons "browser-workflow" $obligations) $obligations))))) $memory))

(= (foundry-plan $capsule)
   (match &self $capsule (foundry-plan-local $capsule)))

(= (foundry-proof $name nil) unknown)
(= (foundry-proof $name (cons (proof $key $value) $tail))
   (if (== $name $key) $value (foundry-proof $name $tail)))

(= (foundry-process exited 0) aligned)
(= (foundry-process-state $state $exit)
   (if (== $state interrupted) unknown
      (if (== $state exited) (if (== $exit 0) aligned drift) drift)))

(= (foundry-prediction $predicted $observed)
   (if (== $predicted $observed) aligned drift))

(= (foundry-proof-alignment passed) aligned)
(= (foundry-proof-alignment failed) drift)
(= (foundry-proof-alignment unknown) unknown)

(= (foundry-proof-value $proof $proofs $process $prediction)
   (if (== $proof "process-exit") $process
      (if (== $proof "prediction-match") $prediction
         (foundry-proof-alignment (foundry-proof $proof $proofs)))))

(= (foundry-proof-path nil $proofs $process $prediction) aligned)
(= (foundry-merge-proof-path $head $tail)
   (if (== $head drift) drift (if (== $tail drift) drift
      (if (== $head unknown) unknown (if (== $tail unknown) unknown aligned)))))
(= (foundry-proof-path (cons $proof $tail) $proofs $process $prediction)
   (foundry-merge-proof-path (foundry-proof-value $proof $proofs $process $prediction)
      (foundry-proof-path $tail $proofs $process $prediction)))

;; A missing independent result is not a successful string claim. The same
;; comparison governs parent and child repair work. Children never close a
;; parent's unobserved acceptance criteria by implication.
(= (foundry-outcome-choice $work $action $intention $process $proofs $recovery $depth)
   (if (== $process unknown)
      (foundry-outcome $work escalate "execution-effects-uncertain")
      (if (engineering-alignment-admissible $intention $process $proofs)
         (foundry-outcome $work accept "independent-obligations-satisfied")
         (if (foundry-activation-action $action)
            (if (== $recovery ready)
               (foundry-outcome $work rollback "activation-obligation-unsatisfied")
               (foundry-outcome $work escalate "recovery-unavailable"))
            (if (< $depth 3)
               (if (== $intention unknown)
                  (foundry-outcome $work iterate "invariant-proof-outstanding")
                  (if (== $proofs unknown)
                     (foundry-outcome $work iterate "proof-obligation-outstanding")
                     (foundry-outcome $work iterate "localized-repair-required")))
               (foundry-outcome $work escalate "repair-depth-exhausted"))))))

(= (foundry-compare-local
    (foundry-observation-context $work $action $state $exit $predicted $observed
       $required $invariants $proofs $recovery $depth))
   (let* (($process (foundry-process-state $state $exit))
          ($prediction (foundry-prediction $predicted $observed))
          ($proof-path (foundry-proof-path $required $proofs $process $prediction))
          ($intention (foundry-proof-path (foundry-required-invariants $invariants) $proofs $process $prediction)))
      (foundry-outcome-choice $work $action $intention $process $proof-path $recovery $depth)))

(= (foundry-compare $capsule)
   (match &self $capsule (foundry-compare-local $capsule)))
