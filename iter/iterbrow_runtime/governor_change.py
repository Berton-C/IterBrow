"""GOV-SELF-1: authenticate a native governor-change decision, never make one.

The activation service injects trusted journal/PWQ/candidate readers. Requests
provide IDs, not approval booleans or proof payloads. No signature is synthesized
here: current PWQ threshold verification remains owned by PWQ. Native reasoning
owns the meaning of shadow/counterexample/restart/rollback observations, and its
decision binds their exact authenticated contents.

Call verify inside the existing activation lock immediately before using an
immutable candidate. The returned receipt is NOT a reusable authorization token.
This module alone does not intercept other activation paths; those callers must
use this verifier and protect its source/dependencies from candidate mutation.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path, PurePosixPath
import re
import time

from .cognitive_fabric import Access, digest


PROOF_KINDS = ('shadow', 'counterexamples', 'restart', 'rollback')
BASE_PROTECTED = frozenset({
    # Conservative host-observer boundary, not a new host-generation system.
    # Source edits here invalidate only the optional new governor. Existing Iter
    # and its external recovery remain available; later factoring may narrow it.
    'main.js', 'bridge/foundry_apps.js', 'bridge/browser_bridge_server.js',
    'iter/seeds/', 'iter/state_manifest.json', 'iter/metta_server.py',
    'iter/metta_query_worker.py', 'iter/iterbrow_runtime/governor_change.py',
    'iter/iterbrow_runtime/engineering_governor.py',
    'iter/iterbrow_runtime/engineering_learning.py',
    'iter/iterbrow_runtime/foundry_governor.py',
    'iter/iterbrow_runtime/foundry_service.py',
    'iter/iterbrow_runtime/foundry_projects.py',
    'iter/iterbrow_runtime/foundry_runtime.py',
    'iter/iterbrow_runtime/foundry_memory.py',
    'iter/iterbrow_runtime/foundry_observation.py',
    'iter/iterbrow_runtime/platform_handoff.py',
    'iter/iterbrow_runtime/source_revision.py',
    'iter/iterbrow_runtime/governor_records.py',
    'iter/iterbrow_runtime/governor_observers.py',
    'iter/iterbrow_runtime/bootstrap_governance.py',
    'iter/iterbrow_runtime/foundry_acceptance.py',
    'iter/iterbrow_runtime/app_revision_manager.py',
    'iter/tools/foundry.py',
    'iter/iterbrow_runtime/cognitive_fabric.py',
    'iter/iterbrow_runtime/atomspace_store.py',
    'iter/iterbrow_runtime/cognitive_events.py',
    'iter/iterbrow_runtime/pwq_protocol.py',
    'iter/iterbrow_runtime/hotload_manager.py',
})
SHA256 = re.compile(r'^[a-f0-9]{64}$')


class GovernorChangeRejected(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise GovernorChangeRejected(message)


def _path(value, prefix=False):
    _require(isinstance(value, str) and bool(value), 'source path is missing')
    path = value[:-1] if prefix and value.endswith('/') else value
    parsed = PurePosixPath(path)
    _require(not parsed.is_absolute() and '\\' not in path and
             str(parsed) == path and '..' not in parsed.parts and path != '.',
             'source path is not canonical repository-relative')
    return value


def _hashes(value):
    _require(isinstance(value, dict) and bool(value), 'source manifest is empty')
    for path, sha in value.items():
        _path(path)
        _require(sha is None or isinstance(sha, str) and SHA256.fullmatch(sha),
                 'source hash must be SHA-256 or an explicit deletion')


@dataclass(frozen=True)
class VerifiedGovernorChange:
    candidate_id: str
    candidate_digest: str
    proposal_id: str
    proposal_digest: str
    decision_id: str
    decision_digest: str
    proof_digests: tuple
    protected_paths: tuple


class ActiveGovernanceGuard:
    """Check the new governor's activated source identity, not general Iter life.

    Only the foundry/native-governor entry point uses this guard. Absence or drift
    of its activation record must not disable existing tools, cognition, memory,
    hot-load, or external recovery. The platform adoption lane writes the record
    after an exact GovernorChangeVerifier receipt; this class never bootstraps,
    writes state, activates source, or interprets a file hash as human approval.

    active_reader is a trusted control-journal reader, not a caller-supplied dict.
    Record shape: schema_version=1, registry_digest, source_hashes (the complete
    protected manifest), activation_receipt (asdict(VerifiedGovernorChange)).
    A record may not be installed by ordinary tool AtomSpace mutation.

    capture returns the very bytes it verified. Native evaluators must consume
    those bytes, not reread source after a successful check. A file change after
    capture cannot substitute the evaluated seed; the next capture rejects it.
    Existing code-image generation/restart protection remains supervisor-owned.
    """
    def __init__(self, repository_root, active_reader, *, dependencies=()):
        self.root = Path(repository_root).resolve()
        self.active_reader = active_reader
        self.protected = frozenset(BASE_PROTECTED | {
            _path(path, prefix=True) for path in dependencies})
        self.registry_digest = digest(sorted(self.protected))

    def _source(self, relative):
        _path(relative)
        path = self.root / relative
        for length in range(1, len(PurePosixPath(relative).parts) + 1):
            part = self.root.joinpath(*PurePosixPath(relative).parts[:length])
            _require(not part.is_symlink(), 'governing source contains a symlink')
        _require(path.resolve().is_relative_to(self.root), 'governing source escaped its root')
        if not path.exists():
            return None
        _require(path.is_file(), 'registered governing source is not a regular file')
        return path.read_bytes()

    def inspect_sources(self):
        """Read-only manifest for preparation; this never grants activation."""
        paths = set()
        for entry in self.protected:
            if entry.endswith('/'):
                directory = self.root / entry
                for parent in (directory, *directory.parents):
                    if parent == self.root:
                        break
                    _require(not parent.is_symlink(), 'governing source directory contains a symlink')
                for path in directory.rglob('*') if directory.exists() else ():
                    _require(not path.is_symlink(), 'governing source directory contains a symlink')
                    if path.is_file():
                        paths.add(path.relative_to(self.root).as_posix())
            else:
                paths.add(entry)
        captured = {path: self._source(path) for path in sorted(paths)}
        hashes = {path: None if raw is None else hashlib.sha256(raw).hexdigest()
                  for path, raw in captured.items()}
        return {'registry_digest': self.registry_digest, 'source_hashes': hashes,
                'source_bytes': captured, 'ruleset_digest': digest(hashes)}

    def capture(self):
        record = deepcopy(self.active_reader())
        _require(isinstance(record, dict) and set(record) == {
            'schema_version', 'registry_digest', 'source_hashes', 'activation_receipt'} and
            record.get('schema_version') == 1,
            'new foundry governor awaits its separately approved activation record; existing Iter remains available')
        _require(record['registry_digest'] == self.registry_digest,
                 'active governor dependency registry differs')
        _hashes(record['source_hashes'])
        receipt = record['activation_receipt']
        if isinstance(receipt, dict) and receipt.get('kind') == 'human_bootstrap_v1':
            # Explicit HUMAN initialization is a different authority event, not
            # a forged native decision or four-proof successor receipt. Only
            # the host initial-admission writer may install this canonical record.
            from .bootstrap_governance import validate_initial_receipt
            validate_initial_receipt(receipt, record['source_hashes'], self.registry_digest)
            captured = self.inspect_sources()
            _require(captured['source_hashes'] == record['source_hashes'],
                     'initial governor source differs from its exact human-approved trust root')
            return {**captured, 'activation_receipt': receipt}
        _require(isinstance(receipt, dict) and all(
            isinstance(receipt.get(key), str) and bool(receipt[key])
            for key in ('candidate_id', 'proposal_id', 'decision_id')),
            'governor activation receipt lacks independently resolved identities')
        _require(all(isinstance(receipt.get(key), str) and SHA256.fullmatch(receipt[key])
                     for key in ('candidate_digest', 'proposal_digest', 'decision_digest')),
                 'governor activation receipt lacks exact candidate/authority/decision digests')
        try:
            proof_digests = dict(receipt['proof_digests'])
        except (KeyError, TypeError, ValueError) as exc:
            raise GovernorChangeRejected('governor activation receipt lacks proof digests') from exc
        _require(set(proof_digests) == set(PROOF_KINDS) and all(
            isinstance(value, str) and SHA256.fullmatch(value) for value in proof_digests.values()),
            'governor activation receipt lacks all independently evaluated obligations')
        captured = self.inspect_sources()
        _require(captured['source_hashes'] == record['source_hashes'],
                 'new governor source differs from its approved activation; existing Iter recovery remains available')
        return {**captured, 'activation_receipt': receipt}


class GovernorChangeVerifier:
    """All adapters and dependency registrations are host-owned, never tool args.

    candidate_reader(id) returns an immutable *complete* changed-file manifest.
    artifact_reader(id, path) returns freshly verified bundle bytes, or None for
    an absent/deleted entry. It must reject symlinks and unlisted bundle entries.
    parent_reader() returns revision, ruleset, snapshot and current source_hashes.
    authorization_reader(id) reads the current canonical PWQ item, not projection.
    proof_reader(id) resolves an immutable independently observed journal record.
    decision_reader(id) resolves a decision produced by the current trusted
    native governor, not a candidate's self-authored decision record.

    Readers must fail closed on authentication failure. Their trust provenance
    cannot be created by passing an 'authenticated': True field to this API.
    """
    def __init__(self, *, candidate_reader, artifact_reader, parent_reader,
                 authorization_reader, proof_reader, decision_reader,
                 proof_producers, native_producer, dependencies=(), clock=time.time):
        self.candidate_reader = candidate_reader
        self.artifact_reader = artifact_reader
        self.parent_reader = parent_reader
        self.authorization_reader = authorization_reader
        self.proof_reader = proof_reader
        self.decision_reader = decision_reader
        self.clock = clock
        self.native_producer = native_producer
        self.protected = frozenset(BASE_PROTECTED | {
            _path(path, prefix=True) for path in dependencies})
        self.registry_digest = digest(sorted(self.protected))
        _require(set(proof_producers) == set(PROOF_KINDS), 'all independent proof producers must be registered')
        self.proof_producers = {kind: frozenset(names) for kind, names in proof_producers.items()}
        _require(all(self.proof_producers.values()) and bool(native_producer), 'trusted producers are missing')

    def protected_paths(self, paths):
        return tuple(sorted(path for path in paths if any(
            path.startswith(entry) if entry.endswith('/') else path == entry
            for entry in self.protected)))

    def _fresh(self, record, now):
        issued, expires = record.get('issued_at'), record.get('expires_at')
        _require(type(issued) in (int, float) and type(expires) in (int, float)
                 and math.isfinite(issued) and math.isfinite(expires)
                 and issued <= now <= expires and issued < expires,
                 'proof or decision is stale or has invalid validity bounds')
        _require(record.get('revoked') is False, 'proof or decision is revoked or unconfirmed')

    def _candidate(self, candidate_id):
        candidate = deepcopy(self.candidate_reader(candidate_id))
        fields = {'candidate_id', 'parent_revision', 'parent_ruleset', 'candidate_ruleset',
                  'source_hashes', 'base_hashes', 'protected_registry_digest',
                  'snapshot', 'author_id', 'parent_work_proposal_id'}
        _require(isinstance(candidate, dict) and set(candidate) == fields, 'candidate manifest schema differs')
        _require(candidate['candidate_id'] == candidate_id, 'candidate identity differs')
        _require(all(isinstance(candidate[key], str) and candidate[key] for key in
                     fields - {'source_hashes', 'base_hashes', 'snapshot'}), 'candidate identity is empty')
        _hashes(candidate['source_hashes'])
        _hashes(candidate['base_hashes'])
        _require(set(candidate['source_hashes']) == set(candidate['base_hashes']), 'candidate before/after paths differ')
        _require(candidate['protected_registry_digest'] == self.registry_digest, 'protected dependency registry changed')
        _require(all(SHA256.fullmatch(candidate[key]) for key in
                     ('parent_ruleset', 'candidate_ruleset')), 'ruleset identity must be SHA-256')
        _require(candidate['snapshot'] and isinstance(candidate['snapshot'], dict), 'candidate lacks a named snapshot')
        protected = self.protected_paths(candidate['source_hashes'])
        _require(protected, 'governor envelope must contain a registered protected change')
        for path, expected in candidate['source_hashes'].items():
            raw = self.artifact_reader(candidate_id, path)
            _require(raw is None or isinstance(raw, bytes), 'artifact reader did not return bytes')
            actual = None if raw is None else hashlib.sha256(raw).hexdigest()
            _require(actual == expected, 'candidate source changed after evidence: ' + path)
        parent = deepcopy(self.parent_reader())
        _require(parent.get('revision') == candidate['parent_revision'] and
                 parent.get('ruleset') == candidate['parent_ruleset'] and
                 parent.get('snapshot') == candidate['snapshot'], 'candidate parent/ruleset/snapshot is stale')
        # The governing identity hashes protected sources only. A source bundle
        # may also change tests or presentation files; their frozen before-hashes
        # are separate and may never replace the protected parent manifest.
        changed_sources = parent.get('changed_source_hashes', parent.get('source_hashes')) or {}
        _require(all(changed_sources.get(path) == before
                     for path, before in candidate['base_hashes'].items()), 'candidate base source is stale')
        _require(all((parent.get('source_hashes') or {}).get(path) == candidate['base_hashes'][path]
                     for path in protected), 'protected candidate base differs from governing parent manifest')
        return candidate, protected

    def authorization_scope(self, candidate_id):
        """Read-only exact scope to present on the separate PWQ proposal."""
        candidate, protected = self._candidate(candidate_id)
        return self._scope(candidate, protected)

    def _scope(self, candidate, protected):
        return {'action': 'governor.activate', 'candidate_id': candidate['candidate_id'],
                'candidate_digest': digest(candidate), 'protected_paths': list(protected),
                'protected_registry_digest': self.registry_digest,
                'rollback_target': candidate['parent_revision']}

    def verify(self, *, candidate_id, proposal_id, dispatch_authorization,
               decision_id, proof_ids):
        """Verify exact facts under the activation lock; perform no activation."""
        candidate, protected = self._candidate(candidate_id)
        candidate_hash = digest(candidate)
        _require(isinstance(proof_ids, dict) and set(proof_ids) == set(PROOF_KINDS),
                 'shadow/counterexamples/restart/rollback references are all required')
        _require(all(isinstance(value, str) and value for value in proof_ids.values()) and
                 len(set(proof_ids.values())) == len(PROOF_KINDS), 'proof identities must be distinct')
        item = deepcopy(self.authorization_reader(proposal_id))
        _require(item.get('id') == proposal_id and proposal_id != candidate['parent_work_proposal_id'],
                 'governor changes require a separately scoped PWQ proposal')
        _require(item.get('status') in ('approved', 'in_progress') and item.get('work_class') == 'build',
                 'governor PWQ proposal is not dispatchable build work')
        _require('GOV-SELF-1' in (item.get('governance_refs') or {}).get('atlas_slices', []),
                 'PWQ proposal does not cover governor evolution')
        policy = item.get('approval_policy') or {}
        _require(policy.get('distinct_signers') is True and
                 {'human_owner', 'runtime_guardian'}.issubset(set(policy.get('required_roles', []))) and
                 (item.get('approval_status') or {}).get('ready') is True,
                 'current independent PWQ approval roles are not satisfied')
        _require(bool(dispatch_authorization) and item.get('dispatch_authorization') == dispatch_authorization,
                 'PWQ dispatch authorization changed')
        _require(item.get('authorization_scope') == self._scope(candidate, protected),
                 'PWQ scope does not bind this exact protected candidate')
        _require(isinstance(item.get('proposal_digest'), str) and
                 SHA256.fullmatch(item['proposal_digest']), 'PWQ proposal lacks its canonical digest')
        bound = {'candidate_digest': candidate_hash, 'parent_revision': candidate['parent_revision'],
                 'governing_ruleset': candidate['parent_ruleset'], 'snapshot': candidate['snapshot']}
        now = self.clock()
        proofs = {}
        for kind in PROOF_KINDS:
            record = deepcopy(self.proof_reader(proof_ids[kind]))
            _require(record.get('proof_id') == proof_ids[kind] and record.get('kind') == kind,
                     'proof reference or kind was substituted')
            _require(all(record.get(key) == value for key, value in bound.items()),
                     'proof does not bind candidate/parent/ruleset/snapshot')
            producer = record.get('producer')
            _require(producer in self.proof_producers[kind] and producer != candidate['author_id'],
                     'proof is not from an independent registered observer')
            self._fresh(record, now)
            _require(isinstance(record.get('observation'), dict) and bool(record['observation']),
                     'proof must retain its actual observation')
            proofs[kind] = digest(record)
        decision = deepcopy(self.decision_reader(decision_id))
        _require(decision.get('decision_id') == decision_id and
                 decision.get('producer') == self.native_producer and
                 decision.get('producer') != candidate['author_id'], 'native decision is not independently authenticated')
        _require(all(decision.get(key) == value for key, value in bound.items()), 'native decision binding differs')
        _require(decision.get('proposal_id') == proposal_id and
                 decision.get('proposal_digest') == item['proposal_digest'] and
                 decision.get('dispatch_authorization') == dispatch_authorization and
                 decision.get('proof_digests') == proofs, 'native decision did not evaluate these exact authority/proof records')
        self._fresh(decision, now)
        # This verifies an authentic conclusion. No Python rule interprets the
        # observations, selects a repair, or decides which counterexample matters.
        _require(decision.get('conclusion') == 'activate', 'native governor has not accepted this change')
        return VerifiedGovernorChange(candidate_id, candidate_hash, proposal_id,
            item['proposal_digest'], decision_id, digest(decision),
            tuple(sorted(proofs.items())), protected)


class GovernorAdoption:
    """Canonical control-journal writer after host-owned source installation.

    This is a platform API, NOT an Iter tool or unauthenticated RPC. Construction
    requires the existing host source-activation lock and trusted readers. The
    installer/supervisor freezes the parent generation, installs/restarts/tests
    the exact candidate and exposes its independent proofs. This writer does not
    copy code, mint PWQ approval, execute a candidate, or stop existing cognition.

    candidate_ruleset/parent_ruleset are digests of COMPLETE protected source
    manifests. parent_reader supplies that immutable active-generation manifest,
    not a reread of files already replaced by installation. Candidate snapshot
    includes the control-space version observed before adoption. No caller may
    submit a prebuilt VerifiedGovernorChange or arbitrary activation record.

    Recovery is an observation of the existing external supervisor restoring
    exact parent bytes. It is not an instruction for this writer to alter code.
    Restoring the first new-foundry adoption removes only its active receipt;
    it does not reset any AtomSpace or memory.
    """
    def __init__(self, fabric, verifier, guard, *, activation_lock,
                 rollback_reader, rollback_producers):
        _require(verifier.registry_digest == guard.registry_digest, 'activation registry differs')
        self.fabric, self.verifier, self.guard = fabric, verifier, guard
        self.activation_lock = activation_lock
        self.rollback_reader = rollback_reader
        self.rollback_producers = frozenset(rollback_producers)
        _require(bool(self.rollback_producers), 'external rollback observers are not registered')
        self.access = Access('platform.governor_adoption', frozenset({'control'}), frozenset({'control'}))

    def _lock(self):
        # Existing fcntl-based managers expose a context factory; threading
        # RLocks are repeatable contexts. Both preserve one host-owned lock.
        return self.activation_lock() if callable(self.activation_lock) else self.activation_lock

    def _read(self):
        from .engineering_learning import read_record
        snapshot = self.fabric.snapshot(['control'], self.access)
        atom = snapshot['views']['control'].get('active-governance')
        return snapshot, read_record('FoundryGovernanceActivationV1', atom) if atom else None

    def adopt(self, *, candidate_id, proposal_id, dispatch_authorization, decision_id, proof_ids):
        from .engineering_learning import record_atom
        with self._lock(), self.fabric.store.lock:
            snapshot, previous = self._read()
            # Never accept a receipt supplied by a client: all readers are
            # consulted again in the lock immediately before the single commit.
            receipt = self.verifier.verify(candidate_id=candidate_id, proposal_id=proposal_id,
                dispatch_authorization=dispatch_authorization, decision_id=decision_id,
                proof_ids=proof_ids)
            candidate, _ = self.verifier._candidate(candidate_id)
            _require(digest(candidate) == receipt.candidate_digest, 'candidate changed after verification')
            observed = candidate['snapshot']
            _require(observed.get('schema_version') == 1 and any(
                identity == snapshot['spaces'][0] for identity in observed.get('spaces', [])) and
                observed.get('root_snapshot', {}).get('epoch') == snapshot['root_snapshot']['epoch'],
                'candidate did not observe this current control-space version')
            parent = deepcopy(self.verifier.parent_reader())
            parent_sources = parent.get('source_hashes')
            _hashes(parent_sources)
            _require(parent['ruleset'] == digest(parent_sources), 'parent ruleset does not bind its complete source manifest')
            if previous is not None:
                _require(previous['registry_digest'] == self.guard.registry_digest and
                         previous['source_hashes'] == parent_sources,
                         'previous activated governor does not match the observed parent')
            expected = dict(parent_sources)
            for path, expected_hash in candidate['source_hashes'].items():
                raw = self.guard._source(path)
                installed_hash = None if raw is None else hashlib.sha256(raw).hexdigest()
                _require(installed_hash == expected_hash, 'installed candidate source differs: ' + path)
                if self.verifier.protected_paths([path]):
                    if expected_hash is None and path not in self.guard.protected:
                        expected.pop(path, None)  # Deleted directory-discovered seed.
                    else:
                        expected[path] = expected_hash
            installed = self.guard.inspect_sources()
            _require(installed['source_hashes'] == expected, 'installed protected source manifest differs from candidate delta')
            _require(candidate['candidate_ruleset'] == installed['ruleset_digest'],
                     'candidate ruleset does not bind its complete installed source manifest')
            activation = {'schema_version': 1, 'registry_digest': self.guard.registry_digest,
                          'source_hashes': expected, 'activation_receipt': asdict(receipt)}
            adoption_id = 'governor-adoption:' + digest([receipt.candidate_digest, receipt.decision_digest])
            event = {'adoption_id': adoption_id, 'activation': activation, 'previous_activation': previous,
                'parent_source_hashes': parent_sources, 'parent_revision': candidate['parent_revision'],
                'observed_snapshot': self.fabric.snapshot_set(snapshot)}
            _require(self.verifier.verify(candidate_id=candidate_id, proposal_id=proposal_id,
                dispatch_authorization=dispatch_authorization, decision_id=decision_id,
                proof_ids=proof_ids) == receipt, 'governor authorization changed during installed-source verification')
            self.fabric.transact('control', [
                {'op': 'upsert', 'key': 'active-governance',
                 'atom': record_atom('FoundryGovernanceActivationV1', activation)},
                {'op': 'add', 'key': adoption_id, 'atom': record_atom('FoundryGovernanceAdoptionV1', event)},
            ], access=self.access, expected=snapshot, transaction_id=adoption_id,
               source='governor_adoption.verified_activation', metadata={'adoption_id': adoption_id})
            return event

    def record_restore(self, adoption_id, observation_id):
        """Record already restored parent bytes, authenticated by the supervisor."""
        from .engineering_learning import read_record, record_atom
        with self._lock(), self.fabric.store.lock:
            snapshot, active = self._read()
            atom = snapshot['views']['control'].get(adoption_id)
            _require(atom is not None, 'unknown governor adoption')
            adopted = read_record('FoundryGovernanceAdoptionV1', atom)
            _require(active == adopted['activation'], 'rollback is stale for the active governor')
            observed = deepcopy(self.rollback_reader(observation_id))
            _require(observed.get('observation_id') == observation_id and
                     observed.get('adoption_id') == adoption_id and
                     observed.get('producer') in self.rollback_producers,
                     'rollback is not an independently authenticated observation')
            self.verifier._fresh(observed, self.verifier.clock())
            parent_sources = adopted['parent_source_hashes']
            _require(observed.get('parent_revision') == adopted['parent_revision'] and
                     observed.get('restored_source_hashes') == parent_sources and
                     observed.get('failed_candidate_digest') == active['activation_receipt']['candidate_digest'],
                     'rollback observation does not bind exact candidate and parent')
            _require(self.guard.inspect_sources()['source_hashes'] == parent_sources,
                     'independently observed parent is not the installed source')
            _require(self.rollback_reader(observation_id) == observed,
                     'rollback observation changed during installed-source verification')
            self.verifier._fresh(observed, self.verifier.clock())
            previous = adopted['previous_activation']
            rollback_id = 'governor-restore:' + digest([adoption_id, observation_id])
            restored = {'rollback_id': rollback_id, 'adoption_id': adoption_id,
                        'observation': observed, 'restored_activation': previous,
                        'memory_reset_performed': False}
            activation_op = ({'op': 'upsert', 'key': 'active-governance',
                'atom': record_atom('FoundryGovernanceActivationV1', previous)} if previous is not None
                else {'op': 'remove', 'key': 'active-governance'})
            self.fabric.transact('control', [activation_op,
                {'op': 'add', 'key': rollback_id, 'atom': record_atom('FoundryGovernanceRestoreV1', restored)},
            ], access=self.access, expected=snapshot, transaction_id=rollback_id,
               source='governor_adoption.observed_restore', metadata={'adoption_id': adoption_id})
            return restored
