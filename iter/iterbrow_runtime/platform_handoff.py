"""Host-only source handoff access to the EXISTING cognitive authority.

No RPC or Iter tool exposes this lease. The lifecycle owner must stop its Iter
child and AtomSpace service first. The state-owned service.lock is acquired
nonblocking before even opening/recovering the journal, so offline adoption can
never race the normal service as a second writer. This helper does not stop or
start processes, erase state, reset memories, or infer authorization from a lock.
"""
from copy import deepcopy
import fcntl
import hashlib
import os
from pathlib import Path
import stat

from .atomspace_store import AtomspaceStore
from .cognitive_fabric import Access, CognitiveFabric, digest
from .engineering_learning import read_record
from .governor_change import ActiveGovernanceGuard, GovernorAdoption, GovernorChangeVerifier
from .governor_records import GovernorRecords
from .source_revision import SourceRevisionManager


class HandoffUnavailable(RuntimeError):
    pass


class OfflineCognitiveAuthority:
    """A stopped service's existing store, never a newly initialized mind.

    The lifecycle_owner_check callable is trusted host code and must verify
    that no Iter child/supervisor can resume writing during this handoff. It is
    not a caller-provided approval flag. The OS service lock is independently
    mandatory even when that callback reports a stopped lifecycle.
    """
    def __init__(self, repository_root, *, lifecycle_owner_check):
        raw = Path(repository_root).absolute()
        for part in [raw, *raw.parents]:
            if part.is_symlink():
                raise HandoffUnavailable('repository path must not contain symlinks')
        self.repository_root = raw.resolve()
        self.iter_root = self.repository_root / 'iter'
        self.state_dir = self.iter_root / '.runtime' / 'atomspace'
        self.owner_check = lifecycle_owner_check
        self.store = None
        self.fabric = None
        self._handle = None

    def _assert_root(self):
        for path in (self.iter_root, self.iter_root / '.runtime', self.state_dir):
            if path.is_symlink() or not path.is_dir():
                raise HandoffUnavailable('canonical existing AtomSpace directory is unavailable')
        # Do not treat missing authority as permission to create an empty one.
        if not (self.state_dir / 'snapshot.json').is_file():
            raise HandoffUnavailable('existing AtomSpace snapshot required; refusing a new epoch')
        for name in ('snapshot.json', 'journal.jsonl', 'service.lock'):
            path = self.state_dir / name
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise HandoffUnavailable('authority paths must be regular, unaliased files')

    def __enter__(self):
        if self._handle is not None:
            raise HandoffUnavailable('offline authority lease is not reentrant')
        self._assert_root()
        if self.owner_check() is not True:
            raise HandoffUnavailable('lifecycle owner has not confirmed a stopped handoff')
        path = self.state_dir / 'service.lock'
        descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CREAT, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise HandoffUnavailable('service lock is not a regular file')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise HandoffUnavailable('live AtomSpace owner still holds the state lock') from exc
            self._assert_root()
            if self.owner_check() is not True:
                raise HandoffUnavailable('lifecycle ownership changed before handoff')
            # Do not overwrite the service PID: an offline lease is not an
            # independently killable AtomSpace-service identity.
            self._handle = descriptor
            self.store = AtomspaceStore(self.state_dir)
            self.fabric = CognitiveFabric(self.store)
            return self
        except BaseException:
            self._handle = None
            self.store = self.fabric = None
            os.close(descriptor)
            raise

    def __exit__(self, exc_type, exc, traceback):
        descriptor, self._handle = self._handle, None
        self.store = self.fabric = None
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _require_lease(self):
        if self._handle is None or self.fabric is None:
            raise HandoffUnavailable('offline cognitive authority lease is not held')

    def active_governance(self):
        self._require_lease()
        access = Access('platform.source_handoff', frozenset({'control'}), frozenset())
        snapshot = self.fabric.snapshot(['control'], access)
        atom = snapshot['views']['control'].get('active-governance')
        return read_record('FoundryGovernanceActivationV1', atom) if atom else None

    def capture_parent(self):
        """Frozen preparation facts, not permission to activate candidate code."""
        self._require_lease()
        access = Access('platform.source_handoff', frozenset({'control'}), frozenset())
        guard = ActiveGovernanceGuard(self.repository_root, self.active_governance)
        captured = guard.inspect_sources()
        snapshot = self.fabric.snapshot_set(self.fabric.snapshot(['control'], access))
        active = self.active_governance()
        if active is not None and (active['registry_digest'] != captured['registry_digest']
                                  or active['source_hashes'] != captured['source_hashes']):
            raise HandoffUnavailable('current governing source differs from the activated parent')
        return {'revision': 'source-parent:' + captured['ruleset_digest'],
            'ruleset': captured['ruleset_digest'], 'source_hashes': captured['source_hashes'],
            'snapshot': snapshot, 'registry_digest': captured['registry_digest'],
            'active_governance': active, 'initial_trust_root_required': active is None}


class GovernedSourceHandoff:
    """Connected host entry point for a successor, while the service is stopped.

    Preparation stages an immutable candidate before constructing this object.
    This is not an RPC and cannot bootstrap its parent. Observer registrations,
    the canonical PWQ store and parent native bytes come from trusted host code.
    Only identities are passed to capture/decide/install. A failed adoption
    restores the exact retained source; a successful adoption can be restored
    under the original exact rollback scope. Neither path restores old memory.
    The caller still owns process restart and independently observing health.
    """
    def __init__(self, authority, candidate_id, *, pwq_store, observers,
                 native_root_reader, evaluate_native, clock=None):
        import time
        self.authority, self.candidate_id = authority, candidate_id
        # A reopened authority owns a different in-memory journal projection.
        # Never let an object retaining the old fabric write through a new lease.
        self._lease_fabric, self._lease_store = authority.fabric, authority.store
        self.clock = time.time if clock is None else clock
        self._require_lease()
        self.manager = SourceRevisionManager(authority.repository_root, verifier=self._authorize_source)
        # Resolve now, not after any source was changed; the artifact owns the
        # complete frozen parent manifest and the exact original recovery target.
        self.manager.parent_reader(candidate_id)
        self.records = GovernorRecords(authority.fabric,
            candidate_reader=self.manager.candidate_reader,
            parent_reader=lambda: self.manager.parent_reader(candidate_id), pwq_store=pwq_store,
            observers=observers, native_root_reader=native_root_reader,
            evaluate_native=evaluate_native, clock=self.clock)
        self.verifier = GovernorChangeVerifier(candidate_reader=self.manager.candidate_reader,
            artifact_reader=self.manager.artifact_reader,
            parent_reader=lambda: self.manager.parent_reader(candidate_id),
            authorization_reader=self.records.authorization_reader,
            proof_reader=self.records.proof_reader, decision_reader=self.records.decision_reader,
            proof_producers=self.records.proof_producers, native_producer=self.records.native_producer,
            clock=self.clock)
        self.guard = ActiveGovernanceGuard(authority.repository_root, authority.active_governance)
        self._restore_observations = {}
        self.adoption = GovernorAdoption(authority.fabric, self.verifier, self.guard,
            activation_lock=self.manager._locked,
            rollback_reader=self._restore_observations.__getitem__,
            rollback_producers={'platform.source_handoff'})

    def _require_lease(self):
        self.authority._require_lease()
        if (self.authority.fabric is not self._lease_fabric or
                self.authority.store is not self._lease_store):
            raise HandoffUnavailable('handoff belongs to a closed authority lease')
        if self.authority.owner_check() is not True:
            raise HandoffUnavailable('lifecycle ownership changed during handoff')

    def _authorize_source(self, candidate_id, operation, request):
        self._require_lease()
        if candidate_id != self.candidate_id:
            raise HandoffUnavailable('handoff cannot substitute a different candidate')
        if operation == 'apply':
            parent = self.manager.parent_reader(candidate_id)
            current = self.authority.capture_parent()
            if (current['source_hashes'] != parent['source_hashes'] or
                    current['snapshot']['spaces'] != parent['snapshot']['spaces'] or
                    current['snapshot']['root_snapshot']['epoch'] != parent['snapshot']['root_snapshot']['epoch']):
                raise HandoffUnavailable('live parent source or control identity changed before installation')
            return self.verifier.verify(candidate_id=candidate_id, **request)
        # Recovery is mechanical execution of the retained-parent scope in the
        # previously verified installation. It must remain possible when the
        # new governor cannot run, or the old proof TTL has elapsed.
        journal = self.manager._read_journal()
        receipt = journal.get('verification_receipt', {}) if journal else {}
        candidate = self.manager.candidate_reader(candidate_id)
        if (operation != 'restore' or not journal or journal.get('candidate_id') != candidate_id or
                receipt.get('candidate_id') != candidate_id or receipt.get('candidate_digest') != digest(candidate) or
                request != {'restore_installation': journal.get('operation_id')}):
            raise HandoffUnavailable('recovery does not bind the verified source installation')
        active = self.authority.active_governance()
        parent_active = self.manager.parent_reader(candidate_id).get('active_governance')
        if (digest(active) != digest(parent_active) and
                (active or {}).get('activation_receipt', {}).get('candidate_digest') != receipt['candidate_digest']):
            raise HandoffUnavailable('another governor now owns the installation')
        return {'candidate_id': candidate_id, 'original_verification_digest': digest(receipt),
                'rollback_target': candidate['parent_revision'], 'operation_id': journal['operation_id']}

    def authorization_scope(self):
        self._require_lease()
        return self.verifier.authorization_scope(self.candidate_id)

    def capture_proof(self, kind, request_id):
        self._require_lease()
        return self.records.capture_proof(self.candidate_id, kind, request_id)

    def decide(self, proposal_id, dispatch_authorization, proof_ids, request_id):
        self._require_lease()
        return self.records.decide(self.candidate_id, proposal_id, dispatch_authorization, proof_ids, request_id)

    def install(self, *, proposal_id, dispatch_authorization, decision_id, proof_ids):
        self._require_lease()
        request = {'proposal_id': proposal_id, 'dispatch_authorization': dispatch_authorization,
                   'decision_id': decision_id, 'proof_ids': deepcopy(proof_ids)}
        previous = self.manager._read_journal()
        previous_operation = previous.get('operation_id') if previous else None
        try:
            installation = self.manager.apply(self.candidate_id, request)
            self._require_lease()
            adopted = self.adoption.adopt(candidate_id=self.candidate_id, **request)
            return {'installation': installation, 'adoption': adopted, 'restart_performed': False}
        except Exception as error:
            journal = self.manager._read_journal()
            if (journal and journal.get('candidate_id') == self.candidate_id and
                    journal.get('operation_id') != previous_operation and
                    journal.get('phase') in {'applying', 'applied', 'restoring'}):
                # Only unwind an installation begun by THIS call. A rejected
                # retry must not roll back a prior successfully adopted build.
                try:
                    self.restore()
                except Exception as recovery_error:
                    raise HandoffUnavailable('installation failed and recovery needs host attention: '
                        + str(recovery_error)) from error
            raise

    def restore(self):
        """Restore source and reconcile its receipt, including after a crash.

        If the source was restored before a host interruption, replay only the
        missing control record. Exact source identities are always re-observed.
        The original installation ID binds recovery; no fresh approval is minted.
        """
        self._require_lease()
        journal = self.manager._read_journal()
        if not journal or journal.get('candidate_id') != self.candidate_id:
            raise HandoffUnavailable('candidate is not the current recoverable installation')
        request = {'restore_installation': journal['operation_id']}
        if journal['phase'] != 'restored':
            journal = self.manager.restore(self.candidate_id, request)
        else:
            self._authorize_source(self.candidate_id, 'restore', request)
        # A recovered source journal may precede this reconciliation by a
        # process restart. Recheck EVERY changed source, not only governing
        # files: an intervening unprotected user edit must not be certified as
        # an exact restore or silently overwritten.
        manifest = self.manager.manifest(self.candidate_id)
        for path, expected in manifest['base_hashes'].items():
            raw = self.manager._live(path)
            observed = None if raw is None else hashlib.sha256(raw).hexdigest()
            if (observed != expected or (raw is not None and
                    stat.S_IMODE((self.authority.repository_root / path).stat().st_mode)
                    != manifest['base_modes'][path])):
                raise HandoffUnavailable('retained parent source was not exactly restored: ' + path)
        parent = self.manager.parent_reader(self.candidate_id)
        if self.guard.inspect_sources()['source_hashes'] != parent['source_hashes']:
            raise HandoffUnavailable('retained protected parent was not exactly restored')
        receipt = journal['verification_receipt']
        active = self.authority.active_governance()
        if digest(active) == digest(parent.get('active_governance')):
            return {'installation': journal, 'governance_restore': None, 'memory_reset_performed': False}
        adoption_id = 'governor-adoption:' + digest([receipt['candidate_digest'], receipt['decision_digest']])
        now = self.clock()
        observation_id = 'source-restore-observation:' + digest([adoption_id, journal['operation_id']])
        self._restore_observations[observation_id] = {
            'observation_id': observation_id, 'adoption_id': adoption_id,
            'producer': 'platform.source_handoff', 'issued_at': now, 'expires_at': now + 60,
            'revoked': False, 'parent_revision': parent['revision'],
            'restored_source_hashes': parent['source_hashes'],
            'failed_candidate_digest': receipt['candidate_digest']}
        self._require_lease()
        restored = self.adoption.record_restore(adoption_id, observation_id)
        return {'installation': journal, 'governance_restore': restored, 'memory_reset_performed': False}
