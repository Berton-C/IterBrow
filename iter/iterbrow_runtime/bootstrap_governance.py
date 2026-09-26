"""One-time, explicitly HUMAN-authorized initial native-governor trust root.

This is not a native successor decision or four-proof self-evolution. The new
governor cannot certify its own first installation. The separate canonical PWQ
scope names the exact protected source and seed hashes; an independent runtime
guardian attests a real source/test/recovery observation bundle. This host-only
writer records that human initialization truthfully in the existing journal.
No Iter tool/RPC exposes it, no signatures are created, and no source is copied.
The existing lifecycle owner must hold the stopped source-adoption lease/lock.
"""
from copy import deepcopy
import math
import time

from .cognitive_fabric import Access, digest
from .engineering_learning import read_record, record_atom
from .governor_change import ActiveGovernanceGuard, GovernorChangeRejected, SHA256
from .pwq_protocol import HOTLOAD_GUARDIAN_PROOF, LOCAL_HUMAN_PROOF


ONCE_KEY = 'initial-governance-admission'
RECEIPT_KIND = 'human_bootstrap_v1'
SEED_PATHS = ('iter/seeds/nace_substrate.metta', 'iter/seeds/engineering_learning.metta',
              'iter/seeds/engineering_alignment.metta', 'iter/seeds/foundry_governor.metta')


def _require(condition, message):
    if not condition:
        raise GovernorChangeRejected(message)


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value)


def validate_initial_receipt(receipt, source_hashes, registry_digest):
    """Structural validation by the read-only active guard, not initialization."""
    expected = {'kind', 'bootstrap_id', 'proposal_id', 'proposal_digest',
        'dispatch_authorization_digest', 'authorization_evidence_digest', 'manifest_digest',
        'registry_digest', 'seed_hashes', 'native_root_id', 'guardian_evidence_id',
        'guardian_evidence_digest', 'native_decision_performed', 'successor_proofs_performed'}
    _require(isinstance(receipt, dict) and set(receipt) == expected and receipt['kind'] == RECEIPT_KIND,
             'initial governor receipt has an invalid explicit bootstrap shape')
    _require(receipt['native_decision_performed'] is False and receipt['successor_proofs_performed'] is False,
             'human initialization cannot claim native successor deliberation or proof')
    _require(all(isinstance(receipt[key], str) and receipt[key] for key in
                 ('bootstrap_id', 'proposal_id', 'native_root_id', 'guardian_evidence_id')),
             'initial governor receipt lacks traceable identities')
    _require(all(_sha(receipt[key]) for key in ('proposal_digest', 'dispatch_authorization_digest',
        'authorization_evidence_digest', 'manifest_digest', 'registry_digest', 'guardian_evidence_digest')),
        'initial governor receipt lacks exact authority/source/evidence digests')
    _require(receipt['manifest_digest'] == digest(source_hashes) and receipt['registry_digest'] == registry_digest,
             'initial governor receipt does not bind its activated source manifest')
    seeds = receipt['seed_hashes']
    _require(isinstance(seeds, dict) and bool(seeds) and all(
        _sha(sha) and source_hashes.get(path) == sha for path, sha in seeds.items()),
        'initial native seeds differ from the human-approved source manifest')


class InitialGovernanceAdmission:
    def __init__(self, fabric, guard, pwq_store, *, evidence_reader, evidence_producers,
                 required_tests, activation_lock, seed_paths=SEED_PATHS, clock=time.time):
        self.fabric, self.guard, self.pwq = fabric, guard, pwq_store
        self.evidence_reader, self.evidence_producers = evidence_reader, frozenset(evidence_producers)
        self.required_tests, self.seed_paths = frozenset(required_tests), tuple(seed_paths)
        _require(bool(self.evidence_producers) and bool(self.required_tests) and bool(self.seed_paths),
                 'initialization needs registered external observers, tests and native seeds')
        self.activation_lock, self.clock = activation_lock, clock
        self.access = Access('platform.initial_governance_admission', frozenset({'control'}), frozenset({'control'}))

    def _lock(self):
        return self.activation_lock() if callable(self.activation_lock) else self.activation_lock

    def _state(self):
        return self.fabric.snapshot(['control'], self.access)

    def _initial_only(self, snapshot):
        view = snapshot['views']['control']
        _require('active-governance' not in view, 'an active governor exists; use native successor adoption')
        _require(ONCE_KEY not in view, 'initial trust root was already admitted; rollback cannot reopen bootstrap')

    def _capture(self):
        captured = self.guard.inspect_sources()
        seeds = {path: captured['source_hashes'].get(path) for path in self.seed_paths}
        _require(all(_sha(sha) for sha in seeds.values()), 'initial native seed source is missing')
        return captured, seeds

    def _evidence(self, evidence_id, captured, seeds):
        evidence = deepcopy(self.evidence_reader(evidence_id))
        _require(isinstance(evidence, dict) and evidence.get('evidence_id') == evidence_id and
                 evidence.get('producer') in self.evidence_producers,
                 'bootstrap guardian bundle is not from an authenticated independent observer')
        issued, expires, now = evidence.get('issued_at'), evidence.get('expires_at'), self.clock()
        _require(type(issued) in (int, float) and type(expires) in (int, float) and
                 math.isfinite(issued) and math.isfinite(expires) and issued <= now <= expires and
                 issued < expires and evidence.get('revoked') is False, 'bootstrap guardian bundle is stale')
        _require(evidence.get('manifest_digest') == captured['ruleset_digest'] and
                 evidence.get('seed_hashes') == seeds, 'bootstrap evidence is for different source or native seeds')
        source = evidence.get('source_observation') or {}
        _require(bool(source.get('observation_id')) and source.get('observed_manifest_digest') == captured['ruleset_digest'],
                 'independent observed source hash is missing or mismatched')
        tests = evidence.get('tests')
        _require(isinstance(tests, list) and bool(tests), 'independent test observations are missing')
        by_id = {test.get('test_id'): test for test in tests if isinstance(test, dict)}
        _require(len(by_id) == len(tests) and self.required_tests.issubset(by_id),
                 'registered bootstrap test observations are missing or repeated')
        _require(all(bool(test.get('observation_id')) and test.get('process_state') == 'exited' and
                     type(test.get('exit_code')) is int and test['exit_code'] == 0 for test in tests),
                 'bootstrap test observations did not complete successfully')
        recovery = evidence.get('recovery_observation') or {}
        _require(bool(recovery.get('observation_id')) and _sha(recovery.get('parent_manifest_digest')) and
                 recovery.get('restored_manifest_digest') == recovery['parent_manifest_digest'] and
                 _sha(recovery.get('memory_before_hash')) and recovery.get('memory_after_hash') == recovery['memory_before_hash'],
                 'independent exact-parent restoration and memory-preservation observation is missing')
        return evidence

    def prepare_scope(self, evidence_id):
        """Prepare an explicit PWQ request; preparation grants no authority."""
        snapshot = self._state()
        self._initial_only(snapshot)
        captured, seeds = self._capture()
        evidence = self._evidence(evidence_id, captured, seeds)
        return {'action': 'governor.bootstrap_initial', 'contract_id': 'software-foundry-magic-v2',
            'initial_only': True, 'native_decision_performed': False, 'successor_proofs_performed': False,
            'registry_digest': captured['registry_digest'], 'source_hashes': captured['source_hashes'],
            'manifest_digest': captured['ruleset_digest'], 'seed_hashes': seeds,
            'guardian_evidence_id': evidence_id, 'guardian_evidence_digest': digest(evidence),
            'observed_snapshot': self.fabric.snapshot_set(snapshot)}

    def _proposal(self, proposal_id):
        item = next((entry for entry in self.pwq.read().get('items', []) if entry.get('id') == proposal_id), None)
        _require(item is not None, 'separate canonical initial-governor PWQ proposal is missing')
        return deepcopy(item)

    @staticmethod
    def guardian_proof_value(proposal_digest, scope):
        """Digest for the actual runtime-guardian attestation; does not sign it."""
        return digest({'kind': 'initial-governance-guardian-v1', 'proposal_digest': proposal_digest,
                       'scope_digest': digest(scope), 'evidence_digest': scope['guardian_evidence_digest']})

    def admit(self, proposal_id, dispatch_authorization):
        with self._lock(), self.fabric.store.lock:
            snapshot = self._state()
            self._initial_only(snapshot)
            captured, seeds = self._capture()
            item = self._proposal(proposal_id)
            scope = item.get('authorization_scope') or {}
            evidence = self._evidence(scope.get('guardian_evidence_id'), captured, seeds)
            expected = {'action': 'governor.bootstrap_initial', 'contract_id': 'software-foundry-magic-v2',
                'initial_only': True, 'native_decision_performed': False, 'successor_proofs_performed': False,
                'registry_digest': captured['registry_digest'], 'source_hashes': captured['source_hashes'],
                'manifest_digest': captured['ruleset_digest'], 'seed_hashes': seeds,
                'guardian_evidence_id': evidence['evidence_id'], 'guardian_evidence_digest': digest(evidence),
                'observed_snapshot': scope.get('observed_snapshot')}
            _require(scope == expected, 'initial trust-root scope does not exactly bind installed source and evidence')
            self.fabric._check(scope['observed_snapshot'], self.access, self.fabric.store.state_copy())
            _require(any(value == snapshot['spaces'][0] for value in scope['observed_snapshot'].get('spaces', [])),
                     'initial approval did not observe the current control space')
            policy = item.get('approval_policy') or {}
            _require(item.get('work_class') == 'build' and item.get('status') in {'approved', 'in_progress'} and
                not item.get('legacy_approval') and 'GOV-SELF-1' in (item.get('governance_refs') or {}).get('atlas_slices', []) and
                policy.get('distinct_signers') is True and int(policy.get('threshold', 0)) >= 2 and
                {'human_owner', 'runtime_guardian'}.issubset(policy.get('required_roles', [])) and
                (item.get('approval_status') or {}).get('ready') is True,
                'initial trust root requires current, separate, split-role canonical PWQ approval')
            _require(bool(dispatch_authorization) and item.get('dispatch_authorization') == dispatch_authorization,
                     'initial trust-root dispatch approval changed')
            signatures = item.get('approval_signatures') or []
            humans = [s for s in signatures if s.get('role') == 'human_owner' and s.get('actor') == 'human' and
                      s.get('proposal_digest') == item.get('proposal_digest') and
                      (s.get('proof') or {}).get('type') == LOCAL_HUMAN_PROOF]
            guardians = [s for s in signatures if s.get('role') == 'runtime_guardian' and
                s.get('actor') == 'platform.hotload_guardian' and s.get('proposal_digest') == item.get('proposal_digest') and
                (s.get('proof') or {}).get('type') == HOTLOAD_GUARDIAN_PROOF and
                (s.get('proof') or {}).get('value') == self.guardian_proof_value(item['proposal_digest'], scope)]
            _require(humans and guardians and all(h['signer_id'] != g['signer_id'] for h in humans for g in guardians),
                     'human consent and independently observed guardian evidence are both required')
            bootstrap_id = 'governor-bootstrap:' + digest([proposal_id, item['proposal_digest'], digest(scope)])
            receipt = {'kind': RECEIPT_KIND, 'bootstrap_id': bootstrap_id, 'proposal_id': proposal_id,
                'proposal_digest': item['proposal_digest'], 'dispatch_authorization_digest': digest(dispatch_authorization),
                'authorization_evidence_digest': item['authorization_evidence_digest'],
                'manifest_digest': captured['ruleset_digest'], 'registry_digest': captured['registry_digest'],
                'seed_hashes': seeds, 'native_root_id': bootstrap_id,
                'guardian_evidence_id': evidence['evidence_id'], 'guardian_evidence_digest': digest(evidence),
                'native_decision_performed': False, 'successor_proofs_performed': False}
            validate_initial_receipt(receipt, captured['source_hashes'], captured['registry_digest'])
            activation = {'schema_version': 1, 'registry_digest': captured['registry_digest'],
                          'source_hashes': captured['source_hashes'], 'activation_receipt': receipt}
            event = {'bootstrap_id': bootstrap_id, 'activation': activation, 'human_authorization': item,
                     'guardian_observation': evidence, 'memory_reset_performed': False}
            _require(self._proposal(proposal_id) == item and self._capture()[0]['source_hashes'] == captured['source_hashes'] and
                     self._evidence(evidence['evidence_id'], captured, seeds) == evidence,
                     'source, evidence or authorization changed during initial admission')
            self.fabric.transact('control', [
                {'op': 'add', 'key': ONCE_KEY, 'atom': record_atom('FoundryInitialGovernanceAdmissionV1', event)},
                {'op': 'add', 'key': bootstrap_id, 'atom': record_atom('FoundryInitialGovernanceAdmissionV1', event)},
                {'op': 'add', 'key': 'active-governance', 'atom': record_atom('FoundryGovernanceActivationV1', activation)},
            ], access=self.access, expected=snapshot, transaction_id=bootstrap_id,
               source='bootstrap_governance.explicit_human_initialization', metadata={'bootstrap_id': bootstrap_id})
            return event

    def native_root(self):
        """Host root reader for GovernorRecords after real initial admission."""
        captured = self.guard.capture()
        seeds = {path: captured['source_bytes'].get(path) for path in self.seed_paths}
        _require(all(isinstance(raw, bytes) for raw in seeds.values()), 'activated native seed bytes are missing')
        return {'root_id': 'active-governance:' + digest(captured['activation_receipt']),
                'ruleset_digest': captured['ruleset_digest'], 'source_hashes': captured['source_hashes'],
                'seed_bytes': seeds}
