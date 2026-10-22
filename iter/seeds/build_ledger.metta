; M15-C3: the build ledger's rules (docs/milestones/M15_build_ledger.md section C).
; Facts are written by iterbrow_runtime/build_ledger.py from what the ask literally names and from what the
; running app shows (the contract check and probes); these rules only derive. Every name is ledger-* so the
; rules sit harmlessly in any view. Conclusions are computed when facts change, never per cycle.

; the selectors the ask names (persist is a requirement, not a selector)
(= (ledger-asked $app) (match &self (ask-requires $app $sel) (if (== $sel persist) (empty) $sel)))

(= (ledger-has $app $sel) (not (== (collapse (match &self (app-has $app $sel) $sel)) ())))
(= (ledger-visible $app $sel) (not (== (collapse (match &self (app-visible $app $sel) $sel)) ())))

; newest open (none: every run counts) and newest run: the one with no greater
(= (ledger-newest-open $app)
   (if (== (collapse (match &self (app-opened $app $o) $o)) ()) 0
       (match &self (app-opened $app $o)
         (if (== (collapse (match &self (app-opened $app $o2) (if (> $o2 $o) $o2 (empty)))) ()) $o (empty)))))

(= (ledger-newest-run $app)
   (if (== (collapse (match &self (probe-run $app $s $p $f) $s)) ()) 0
       (match &self (probe-run $app $s $p $f)
         (if (== (collapse (match &self (probe-run $app $s2 $p2 $f2) (if (> $s2 $s) $s2 (empty)))) ()) $s (empty)))))

; a run since the newest open with nothing failed
(= (ledger-passing-run $app)
   (let $open (ledger-newest-open $app)
     (match &self (probe-run $app $s $p 0) (if (> $s $open) $s (empty)))))

(= (ledger-covered $app $sel)
   (not (== (collapse (let $s (ledger-passing-run $app) (match &self (probe-covers $app $s $sel) $sel))) ())))

;; Audit 2026-10-22: an element that only exists once the person acts (a .card after Add) is absent on a fresh
;; page but proven by a passing probe that touched it — covered counts as present and visible.
(= (ledger-missing $app)
   (let $sel (ledger-asked $app) (if (ledger-has $app $sel) (empty) (if (ledger-covered $app $sel) (empty) $sel))))

(= (ledger-hidden $app)
   (let $sel (ledger-asked $app)
     (if (ledger-has $app $sel) (if (ledger-visible $app $sel) (empty) (if (ledger-covered $app $sel) (empty) $sel)) (empty))))

(= (ledger-unproven $app)
   (let $sel (ledger-asked $app) (if (ledger-has $app $sel) (if (ledger-covered $app $sel) (empty) $sel) (empty))))

; failed in the newest run, passed in an earlier one
(= (ledger-regressed $app)
   (let $now (ledger-newest-run $app)
     (match &self (probe-assertion $app $now $label failed $got)
       (if (== (collapse (match &self (probe-assertion $app $e $label passed $g)
                           (if (< $e $now) $e (empty)))) ())
           (empty) $label))))

;; data-iter-ready is reported, never required (M13-C4): a missing flag is not a breach (audit 2026-10-22 — it
;; held every app at next: build and taught NACE that probe_before_report is worthless).
(= (ledger-contract $app) (match &self (app-stores $app other) storage))
(= (ledger-contract $app) (match &self (app-placeholder $app present) placeholder))
(= (ledger-contract $app) (match &self (app-form $app $sel unguarded) (form $sel)))
(= (ledger-contract $app) (match &self (app-script $app external $host) (script $host)))

; the newest run: (run passed failed) and its failures (label detail)
(= (ledger-probe $app)
   (let $now (ledger-newest-run $app) (match &self (probe-run $app $now $p $f) (run $p $f))))
(= (ledger-failure $app)
   (let $now (ledger-newest-run $app) (match &self (probe-assertion $app $now $label failed $got) (failure $label $got))))
(= (ledger-run-failed $app)
   (let $now (ledger-newest-run $app)
     (not (== (collapse (match &self (probe-run $app $now $p $f) (if (> $f 0) $f (empty)))) ()))))

; report when nothing is missing, hidden, regressed, failing or in breach and every named selector is
; proven by a passing run since the newest open; probe when only proof is lacking; else build
(= (ledger-next $app)
   (if (and (== (collapse (ledger-missing $app)) ())
            (and (== (collapse (ledger-hidden $app)) ())
                 (and (== (collapse (ledger-regressed $app)) ())
                      (and (== (collapse (ledger-contract $app)) ()) (not (ledger-run-failed $app))))))
       (if (and (== (collapse (ledger-unproven $app)) ()) (not (== (collapse (ledger-passing-run $app)) ())))
           report probe)
       build))
