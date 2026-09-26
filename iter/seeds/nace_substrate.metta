;; Versioned NACE reasoning seed.
;; Runtime beliefs and evidence are committed through the AtomSpace API and
;; may be projected to nace_beliefs.metta for legacy readers.

(= (Truth_Expectation (stv $f $c))
   (+ (* $f $c) (* 0.5 (- 1 $c))))

(= (Truth_Weight $c)
   (/ $c (- 1 $c)))

(= (Truth_Revision (stv $f1 $c1) (stv $f2 $c2))
   (stv
     (/ (+ (* (Truth_Weight $c1) $f1)
           (* (Truth_Weight $c2) $f2))
        (+ (Truth_Weight $c1) (Truth_Weight $c2)))
     (/ (+ (Truth_Weight $c1) (Truth_Weight $c2))
        (+ (+ (Truth_Weight $c1) (Truth_Weight $c2)) 1))))

(= (should-dispatch $cap)
   (let* (($stv (match &self (cap-efficacy $cap $v) $v))
          ($expectation (Truth_Expectation $stv)))
     (> $expectation 0.3)))

;; Capability beliefs belong to the mutable NACE state, not this rule seed.
;; A permanent neutral fact would compete with the learned AtomSpace belief.
