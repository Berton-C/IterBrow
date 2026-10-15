;; Knowledge-base inference seed (Milestone 5, docs/milestones/M5_knowledge_base.md section D).
;; Stored statements are (kb <statement> (stv f c)) state atoms; derivations are
;; computed per query by iterbrow_runtime/kb_inference.py and NEVER written back.

;; NAL deduction truth function.
(= (Truth_Deduction (stv $f1 $c1) (stv $f2 $c2))
   (stv (* $f1 $f2) (* (* $f1 $f2) (* $c1 $c2))))

;; Modus ponens over stored statements: rule A => B and fact A give B.
(= (kb-step-mp)
   (match &self (, (kb (==> $a $b) $t1) (kb $a $t2))
          (derived $b (Truth_Deduction $t2 $t1) (==> $a $b) $a)))

;; Implication chaining: A => B and B => C give A => C.
(= (kb-step-chain)
   (match &self (, (kb (==> $a $b) $t1) (kb (==> $b $c) $t2))
          (derived (==> $a $c) (Truth_Deduction $t1 $t2) (==> $a $b) (==> $b $c))))
