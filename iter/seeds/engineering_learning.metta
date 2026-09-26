;; COG-LEARN-1: authenticated ground contexts, native evidence comparison,
;; cumulative PLN revision, and native selection. No authority is learned.
(= (engineering-learning-process-label $process $exit $predicted $observed)
   (if (== $process interrupted) incomplete
    (if (== $process exited)
     (if (== $exit 0)
       (if (== $predicted $observed) positive negative)
       negative)
     negative)))

(= (engineering-learning-proofs nil) passed)
(= (engineering-learning-merge-proofs $left $right)
   (if (or (== $left failed) (== $right failed)) failed
     (if (or (== $left unknown) (== $right unknown)) unknown passed)))
(= (engineering-learning-proofs (cons $head $tail))
   (engineering-learning-merge-proofs $head (engineering-learning-proofs $tail)))
(= (engineering-learning-label $process $exit $predicted $observed $proofs)
   (if (== $process interrupted) incomplete
     (let $process-label (engineering-learning-process-label $process $exit $predicted $observed)
       (if (== $process-label negative) negative
         (if (== (engineering-learning-proofs $proofs) failed) negative
           (if (== (engineering-learning-proofs $proofs) unknown) incomplete $process-label))))))

(= (engineering-learning-stv positive) (stv 1.0 0.5))
(= (engineering-learning-stv negative) (stv 0.0 0.5))

(= (engineering-learning-update $prior $label)
   (if (== $label incomplete) $prior
     (Truth_Revision $prior (engineering-learning-stv $label))))

(= (engineering-learning-reason
     (engineering-learning-context-v1 $evidence $strategy $class $repository
       $process $exit $predicted $observed $proofs $prior))
   (engineering-learning-result $evidence
     (engineering-learning-label $process $exit $predicted $observed $proofs)
     (engineering-learning-update $prior
       (engineering-learning-label $process $exit $predicted $observed $proofs))))

(= (engineering-learning-revise $capsule)
   (match &self $capsule (engineering-learning-reason $capsule)))

(= (engineering-learning-expectation (stv $f $c))
   (+ (* $c (- $f 0.5)) 0.5))

;; Alternatives are already scope-admissible. Ranking does not mint consent
;; or remove fixed proof duties. Tie order follows the declared alternatives.
(= (engineering-learning-rank-local
     (engineering-ranking-context-v1 $work $left $left-belief $right $right-belief))
   (if (> (engineering-learning-expectation $right-belief)
          (engineering-learning-expectation $left-belief))
     (engineering-ranked $work $right)
     (engineering-ranked $work $left)))

(= (engineering-learning-rank $capsule)
   (match &self $capsule (engineering-learning-rank-local $capsule)))
