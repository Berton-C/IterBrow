;; Lean native recursive engineering governor — COG-GOV-1.
;;
;; This seed owns the first semantic decision in MeTTa. Python may validate
;; the shape of an engineering-work atom, submit it transactionally, and
;; verify that a returned decision has the expected signed vocabulary. It may
;; not select or substitute the decision.
;;
;; The v1 work shape deliberately carries one selected alternative and one
;; counter-alternative. The full work atom remains semantic/audit context. Each
;; native transition reads the compact engineering-control-record committed in
;; the same transaction, so selection is grounded by one work-keyed state
;; projection instead of being extracted from every compatible atom in a
;; heterogeneous space. The adapter independently verifies the returned
;; selected identity against the authoritative work event before persistence.
;; Child work units use the same shape and name their parent. Active work keeps
;; this v1 shape and adds a separate raw engineering-observation atom so the
;; constitutional executor never has to classify an outcome in Python.

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        pending pending none pending pending ready shadow))
   (engineering-decision $work request_authorization $selected))

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        authorized pending none pending pending ready shadow))
   (engineering-decision $work shadow_action_ready $selected))

;; The caller supplies a fully ground control capsule reconstructed from the
;; authoritative work event. Presence is authenticated exactly in &self before
;; local native destructuring. This is the same higher-order boundary used by
;; active engineering contexts and prevents whole-space variable capture.
(= (engineering-shadow-next $capsule)
   (match &self $capsule (engineering-shadow-reason $capsule)))

;; Active readiness is mirrored into a compact ground control record. This is
;; not a second authority: it is committed in the same transaction as the full
;; work atom. The exact record is the authorization boundary for the one action
;; currently admitted by COG-GOV-1.
(= (engineering-next $work)
   (match &self
     (engineering-control-record $work "qa.pwq_board_boundary"
       authorized pending none pending pending ready active)
     (engineering-decision $work active_action_ready
       "qa.pwq_board_boundary")))

;; A completed action is represented by one versioned, fully ground cognitive
;; context. It carries the forest-level claim and obligations together with the
;; tree-level raw observation. The public context functions receive that exact
;; ground capsule, authenticate its presence in &self, and only then let native
;; rules destructure it locally. Python transports facts; MeTTa owns meaning.

(= (engineering-context-status $process $exit)
   (if (== $process exited)
     (if (== $exit 0) passed failed)
     failed))

(= (engineering-context-comparison $process $exit $bytes)
   (if (== $process exited)
     (if (== $exit 0)
       (if (> $bytes 0) matched incomplete)
       mismatched)
     unknown))

(= (engineering-context-reason
      (engineering-context-v1 $context
        (identity $work $parent)
        (authorization authorized $authorization-ref)
        (claim $intention $invariants $current $gap)
        (alternatives "qa.pwq_board_boundary" $counter)
        (prediction $prediction $risks)
        (obligations $tests $recovery-obligations)
        (observation $process $exit $stdout $stderr $bytes)
        (recovery $recovery-state)))
   (if (== $process exited)
     (if (== $exit 0)
       (if (> $bytes 0)
         (engineering-decision $work accept "qa.pwq_board_boundary")
         (engineering-decision $work iterate "qa.pwq_board_boundary"))
       (if (== $recovery-state ready)
         (engineering-decision $work rollback "qa.pwq_board_boundary")
         (engineering-decision $work escalate "qa.pwq_board_boundary")))
     (if (== $recovery-state ready)
       (engineering-decision $work rollback "qa.pwq_board_boundary")
       (engineering-decision $work escalate "qa.pwq_board_boundary"))))

(= (engineering-context-revise
      (engineering-context-v1 $context
        (identity $work $parent)
        (authorization authorized $authorization-ref)
        (claim $intention $invariants $current $gap)
        (alternatives "qa.pwq_board_boundary" $counter)
        (prediction $prediction $risks)
        (obligations $tests $recovery-obligations)
        (observation $process $exit $stdout $stderr $bytes)
        (recovery $recovery-state)))
   (if (== $process exited)
     (if (== $exit 0)
       (if (> $bytes 0)
         (engineering-evidence-revision $work "qa.pwq_board_boundary" positive
           (Truth_Revision (stv 0.5 0.0) (stv 1.0 0.5)))
         (engineering-evidence-revision $work "qa.pwq_board_boundary" incomplete
           (Truth_Revision (stv 0.5 0.0) (stv 0.5 0.25))))
       (engineering-evidence-revision $work "qa.pwq_board_boundary" negative
         (Truth_Revision (stv 0.5 0.0) (stv 0.0 0.5))))
     (engineering-evidence-revision $work "qa.pwq_board_boundary" unavailable
       (Truth_Revision (stv 0.5 0.0) (stv 0.0 0.5)))))

(= (engineering-context-project
      (engineering-context-v1 $context
        (identity $work $parent)
        (authorization authorized $authorization-ref)
        (claim $intention $invariants $current $gap)
        (alternatives "qa.pwq_board_boundary" $counter)
        (prediction $prediction $risks)
        (obligations $tests $recovery-obligations)
        (observation $process $exit $stdout $stderr $bytes)
        (recovery $recovery-state)))
   (tracking $work
     (context $context v1)
     (active-claim $intention)
     (invariants $invariants)
     (current-state $current)
     (unresolved $gap)
     (selected "qa.pwq_board_boundary")
     (counterexamples $counter $risks)
     (prediction $prediction)
     (test-obligation $tests)
     (recovery-obligation $recovery-obligations)
     (authorization $authorization-ref)
     (raw-observation $process $exit $stdout $stderr $bytes)
     (comparison (engineering-context-comparison $process $exit $bytes))
     (next-dependency $tests)
     (engineering-context-reason
       (engineering-context-v1 $context
         (identity $work $parent)
         (authorization authorized $authorization-ref)
         (claim $intention $invariants $current $gap)
         (alternatives "qa.pwq_board_boundary" $counter)
         (prediction $prediction $risks)
         (obligations $tests $recovery-obligations)
         (observation $process $exit $stdout $stderr $bytes)
         (recovery $recovery-state)))
     (engineering-context-revise
       (engineering-context-v1 $context
         (identity $work $parent)
         (authorization authorized $authorization-ref)
         (claim $intention $invariants $current $gap)
         (alternatives "qa.pwq_board_boundary" $counter)
         (prediction $prediction $risks)
         (obligations $tests $recovery-obligations)
         (observation $process $exit $stdout $stderr $bytes)
         (recovery $recovery-state)))))

(= (engineering-context-next $capsule)
   (match &self $capsule (engineering-context-reason $capsule)))

(= (engineering-context-evidence $capsule)
   (match &self $capsule (engineering-context-revise $capsule)))

(= (engineering-context-tracking $capsule)
   (match &self $capsule (engineering-context-project $capsule)))

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        authorized completed observed passed matched ready shadow))
   (engineering-decision $work accept $selected))

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        authorized completed observed passed mismatched ready shadow))
   (engineering-decision $work iterate $selected))

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        authorized $action $observation-state failed $comparison ready shadow))
   (engineering-decision $work rollback $selected))

(= (engineering-shadow-reason
      (engineering-control-record $work $selected
        authorized $action $observation-state failed $comparison unavailable shadow))
   (engineering-decision $work escalate $selected))

;; Tracking is a read-only projection of the same authoritative work atom and
;; its native decision. It does not mint authorization or alter scope.
(= (engineering-shadow-project
      (engineering-work $work
       (parent $parent)
       (intention $intention)
       (invariants $invariants)
       (current-state $current)
       (unresolved-gap $gap)
       (alternatives $selected $counter)
       (selected $selected)
       (predicted-effects $prediction)
       (risks $risks)
       (test-obligations $tests)
       (recovery-obligations $recovery)
       (authorization $authorization $authorization-ref)
       (action $action)
       (observation $observation)
       (test-result $test-result)
       (comparison $comparison)
       (recovery-state $recovery-state)
       (execution-mode shadow))
      $control)
   (tracking $work $intention $gap $selected $observation $comparison
     (engineering-shadow-reason $control)))

(= (engineering-shadow-tracking $work-capsule $control-capsule)
   (match &self $work-capsule
     (match &self $control-capsule
       (engineering-shadow-project $work-capsule $control-capsule))))
