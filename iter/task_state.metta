;; Task State -- explicit phase atoms for the founder's active work.
;; Written by tools/task_state.py (run(action='set', label=..., phase=...)),
;; read by transformations/completion_claim_guard.py before letting a
;; completion-style claim go unchecked. See both files' docstrings for the
;; real 2026-09-14 episode 36 incident this exists to guard against.
;; Empty at creation -- populated as task_state is actually called.
