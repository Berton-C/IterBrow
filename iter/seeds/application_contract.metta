;; APP-1 native application collaboration contract.
;;
;; Application commands commit one authoritative event plus keyed record and
;; field atoms. JSON files are projections only. Public native reads take a
;; fully ground capsule and authenticate its exact presence in &self before
;; returning it, following the populated-space lesson proven by COG-GOV-1.

(application-contract-version v1)
(application-command-type create)
(application-command-type replace)
(application-command-type delete)
(application-command-type undo)
(application-command-type import)

(= (application-ground-record $record)
   (match &self $record $record))

(= (application-ground-field $field)
   (match &self $field $field))
