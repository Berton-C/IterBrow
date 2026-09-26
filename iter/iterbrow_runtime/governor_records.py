"""Host-owned proof/decision capture in the existing canonical AtomSpace journal.

This API accepts identities only. Observer callables, producer identities, PWQ
store and the approved native-root reader are injected by the host, never tools.
Immutable records use a per-candidate scratch view so gathering evidence cannot
invalidate the control-space SnapshotSet it is meant to evaluate. No second
ledger, signature scheme, or semantic approval owner is introduced.

BOOTSTRAP IS DELIBERATELY UNRESOLVED: no approved parent native root means no
decision. Candidate rule bytes cannot bless themselves. Initial installation of
the new native change rule requires an explicit separately authorized trust-root
ceremony; this module does not manufacture one from a file hash or producer name.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
import re
import time

from .cognitive_fabric import Access, canonical, digest
from .engineering_learning import read_record, record_atom
from .governor_change import PROOF_KINDS


WRITER = 'platform.governor_records'
SOURCE = 'governor_records.trusted_capture'
ID = re.compile(r'^(gproof|gdecision|ginvocation):([a-f0-9]{32}):([a-f0-9]{64})$')
CONCLUSION = re.compile(r'^\[\[(activate|reject|unresolved)\]\]$')


class GovernorRecordError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrustedObserver:
    """Host registration, not a serializable tool argument or proof payload."""
    producer: str
    observe: object


class GovernorRecords:
    def __init__(self, fabric, *, candidate_reader, parent_reader, pwq_store,
                 observers, native_root_reader, evaluate_native,
                 native_producer='platform.native_governor', clock=time.time, proof_ttl=600):
        if set(observers) != set(PROOF_KINDS) or any(
                not isinstance(value, TrustedObserver) or not callable(value.observe) or not value.producer
                for value in observers.values()):
            raise ValueError('all four proof kinds require trusted host callable observers')
        if type(proof_ttl) not in (int, float) or not math.isfinite(proof_ttl) or not 0 < proof_ttl <= 3600:
            raise ValueError('proof validity must be bounded by the host')
        self.fabric, self.candidate_reader, self.parent_reader = fabric, candidate_reader, parent_reader
        self.pwq_store, self.observers = pwq_store, dict(observers)
        self.native_root_reader, self.evaluate_native = native_root_reader, evaluate_native
        self.native_producer, self.clock, self.proof_ttl = native_producer, clock, proof_ttl

    @property
    def proof_producers(self):
        return {kind: {observer.producer} for kind, observer in self.observers.items()}

    def authorization_reader(self, proposal_id):
        # PWQStore.read replays the canonical protocol ledger, not pwq.json.
        item = next((item for item in self.pwq_store.read().get('items', []) if item.get('id') == proposal_id), None)
        if item is None:
            raise GovernorRecordError('canonical PWQ proposal is missing')
        return deepcopy(item)

    @staticmethod
    def _identity(prefix, candidate_id, request_id):
        if not isinstance(request_id, str) or not request_id or len(request_id) > 256:
            raise ValueError('capture requires a bounded idempotency identity')
        return '%s:%s:%s' % (prefix, digest(candidate_id)[:32], digest([prefix, request_id]))

    @staticmethod
    def _location(identity):
        match = ID.fullmatch(identity) if isinstance(identity, str) else None
        if not match:
            raise GovernorRecordError('invalid governance-record identity')
        space = 'scratch/governor-' + match.group(2)
        return space, Access(WRITER, frozenset({space}), frozenset({space}))

    def _candidate(self, candidate_id):
        candidate = deepcopy(self.candidate_reader(candidate_id))
        parent = deepcopy(self.parent_reader())
        if not isinstance(candidate, dict) or candidate.get('candidate_id') != candidate_id:
            raise GovernorRecordError('immutable source candidate identity differs')
        for name, field in [('parent_revision', 'revision'), ('parent_ruleset', 'ruleset'), ('snapshot', 'snapshot')]:
            if candidate.get(name) != parent.get(field):
                raise GovernorRecordError('candidate no longer matches the trusted parent ' + field)
        observed = candidate['snapshot']
        if not isinstance(observed, dict) or observed.get('schema_version') != 1:
            raise GovernorRecordError('candidate lacks an authoritative named SnapshotSet')
        spaces = [entry.get('space_id') for entry in observed.get('spaces', [])]
        if 'control' not in spaces:
            raise GovernorRecordError('candidate SnapshotSet must bind the governing control space')
        access = Access(WRITER, frozenset(spaces), frozenset())
        self.fabric._check(observed, access, self.fabric.store.state_copy())
        bound = {'candidate_id': candidate_id, 'candidate_digest': digest(candidate),
            'parent_revision': candidate['parent_revision'], 'governing_ruleset': candidate['parent_ruleset'],
            'snapshot': candidate['snapshot']}
        return candidate, parent, bound

    def _existing(self, identity):
        space, access = self._location(identity)
        atom = self.fabric.snapshot([space], access)['views'][space].get(identity)
        return self._read(identity) if atom else None

    def _write(self, identity, kind, producer, payload):
        space, access = self._location(identity)
        with self.fabric.store.lock:
            snapshot = self.fabric.snapshot([space], access)
            if identity in snapshot['views'][space]:
                raise GovernorRecordError('governance record is immutable')
            envelope = {'record_id': identity, 'kind': kind, 'producer': producer, 'payload': payload,
                'payload_digest': digest(payload), 'journal_epoch': snapshot['root_snapshot']['epoch'],
                'journal_commit': self.fabric.store.commit + 1}
            self.fabric.transact(space, [{'op': 'add', 'key': identity,
                'atom': record_atom('GovernorRecordV1', envelope)}], access=access, expected=snapshot,
                transaction_id='governor-record:' + identity, source=SOURCE,
                metadata={'governor_record': {'record_id': identity, 'kind': kind,
                    'producer': producer, 'payload_digest': digest(payload)}})
            return payload

    def _read(self, identity):
        space, access = self._location(identity)
        with self.fabric.store.lock:
            snapshot = self.fabric.snapshot([space], access)
            atom = snapshot['views'][space].get(identity)
            if atom is None:
                raise GovernorRecordError('governance record is missing')
            envelope = read_record('GovernorRecordV1', atom)
            if envelope.get('record_id') != identity or envelope.get('payload_digest') != digest(envelope.get('payload')):
                raise GovernorRecordError('governance envelope identity/content differs')
            if envelope.get('journal_epoch') != snapshot['root_snapshot']['epoch']:
                raise GovernorRecordError('governance record belongs to another journal epoch')
            commit = envelope.get('journal_commit')
            if type(commit) is not int or commit < 1:
                raise GovernorRecordError('governance envelope lacks its journal commit')
            events = self.fabric.store.events_after(commit - 1, 1)
            event = events[0] if events else {}
            expected_metadata = {key: envelope[key] for key in ('record_id', 'kind', 'producer', 'payload_digest')}
            expected_op = {'op': 'add', 'key': self.fabric.atom_id(space, identity), 'atom': atom}
            if (event.get('commit') != commit or event.get('actor') != WRITER or event.get('source') != SOURCE
                    or event.get('metadata', {}).get('governor_record') != expected_metadata
                    or expected_op not in event.get('operations', [])):
                raise GovernorRecordError('record is not authenticated by its original host journal envelope')
            return deepcopy(envelope)

    def _begin(self, candidate_id, operation, request_id, producer, bound):
        identity = self._identity('ginvocation', candidate_id, operation + ':' + request_id)
        with self.fabric.store.lock:
            if self._existing(identity):
                raise GovernorRecordError('prior capture started without a result; inspect effects before a new invocation')
            self._write(identity, 'invocation', producer,
                {**bound, 'invocation_id': identity, 'operation': operation, 'issued_at': self.clock()})
        return identity

    def capture_proof(self, candidate_id, kind, request_id):
        if kind not in self.observers:
            raise ValueError('unregistered proof kind')
        identity = self._identity('gproof', candidate_id, kind + ':' + request_id)
        if self._existing(identity):
            return self.proof_reader(identity)
        candidate, parent, bound = self._candidate(candidate_id)
        observer = self.observers[kind]
        if observer.producer == candidate.get('author_id'):
            raise GovernorRecordError('candidate author cannot be its independent proof producer')
        invocation = self._begin(candidate_id, kind, request_id, observer.producer, bound)
        observation = observer.observe({'candidate': deepcopy(candidate), 'parent': deepcopy(parent),
                                        'proof_id': identity, 'invocation_id': invocation})
        # This validates transport only. The observer, not the request, captured
        # its test facts; native rules determine whether they justify adoption.
        if not isinstance(observation, dict) or observation.get('status') not in {'passed', 'failed', 'unknown'}:
            raise GovernorRecordError('trusted observer returned no bounded test status')
        encoded = canonical(observation)
        if len(encoded.encode()) > 262144:
            raise GovernorRecordError('independent observation exceeds the bounded journal record')
        if self._candidate(candidate_id)[2] != bound:
            raise GovernorRecordError('candidate or parent changed during observation')
        now = self.clock()
        proof = {**bound, 'proof_id': identity, 'kind': kind, 'producer': observer.producer,
            'invocation_id': invocation, 'issued_at': now, 'expires_at': now + self.proof_ttl,
            'revoked': False, 'observation': deepcopy(observation)}
        self._write(identity, 'proof', observer.producer, proof)
        return proof

    def proof_reader(self, identity):
        envelope = self._read(identity)
        proof = envelope['payload']
        observer = self.observers.get(proof.get('kind'))
        if (envelope['kind'] != 'proof' or observer is None or
                envelope['producer'] != observer.producer or proof.get('producer') != observer.producer or
                proof.get('proof_id') != identity):
            raise GovernorRecordError('proof producer/kind is not host registered')
        invocation = self._read(proof.get('invocation_id'))
        if invocation['kind'] != 'invocation' or invocation['producer'] != observer.producer or any(
                invocation['payload'].get(key) != proof.get(key) for key in
                ('candidate_id', 'candidate_digest', 'parent_revision', 'governing_ruleset', 'snapshot')):
            raise GovernorRecordError('proof does not follow its authenticated observer invocation')
        return proof

    def _native_root(self, candidate):
        root = deepcopy(self.native_root_reader())
        if not isinstance(root, dict) or not root.get('root_id'):
            raise GovernorRecordError('approved parent native trust root is missing; explicit bootstrap authorization required')
        if root.get('ruleset_digest') != candidate['parent_ruleset']:
            raise GovernorRecordError('native evaluator root is not the approved parent ruleset')
        hashes, seeds = root.get('source_hashes'), root.get('seed_bytes')
        if not isinstance(hashes, dict) or digest(hashes) != root['ruleset_digest'] or not isinstance(seeds, dict) or not seeds:
            raise GovernorRecordError('native root lacks its exact approved source manifest and seed bytes')
        for path, raw in seeds.items():
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != hashes.get(path):
                raise GovernorRecordError('native seed bytes differ from the approved parent source')
        return root

    def decide(self, candidate_id, proposal_id, dispatch_authorization, proof_ids, request_id):
        identity = self._identity('gdecision', candidate_id, request_id)
        if self._existing(identity):
            previous = self.decision_reader(identity)
            supplied_digests = {kind: digest(self.proof_reader(reference))
                                for kind, reference in proof_ids.items()} if isinstance(proof_ids, dict) else None
            if (previous['proposal_id'] != proposal_id or previous['dispatch_authorization'] != dispatch_authorization
                    or previous['proof_digests'] != supplied_digests):
                raise GovernorRecordError('decision request identity reused with different approval or proof references')
            return previous
        candidate, _parent, bound = self._candidate(candidate_id)
        root = self._native_root(candidate)  # Never load the candidate's own rules.
        if not isinstance(proof_ids, dict) or set(proof_ids) != set(PROOF_KINDS):
            raise GovernorRecordError('all four independent proof references are required')
        proofs = {kind: self.proof_reader(proof_ids[kind]) for kind in PROOF_KINDS}
        now = self.clock()
        for kind, proof in proofs.items():
            if proof.get('kind') != kind or any(proof.get(key) != value for key, value in bound.items()):
                raise GovernorRecordError('proof belongs to a different candidate or observed parent')
            if not proof['issued_at'] <= now <= proof['expires_at'] or proof['revoked']:
                raise GovernorRecordError('proof is stale')
        item = self.authorization_reader(proposal_id)
        if (item.get('status') not in {'approved', 'in_progress'} or
                not (item.get('approval_status') or {}).get('ready') or
                not dispatch_authorization or item.get('dispatch_authorization') != dispatch_authorization or
                (item.get('authorization_scope') or {}).get('candidate_digest') != bound['candidate_digest']):
            raise GovernorRecordError('current canonical candidate-bound PWQ approval is required')
        invocation = self._begin(candidate_id, 'native-decision', request_id, self.native_producer, bound)
        statuses = [proofs[kind]['observation']['status'] for kind in PROOF_KINDS]
        capsule = '(governor-change-obligations-v1 %s)' % ' '.join(statuses)
        code = '!(engineering-governor-change-verdict %s)' % capsule
        atoms = {digest(capsule): capsule}
        for kind, proof in proofs.items():
            atoms['proof:' + kind] = '(governor-proof-evidence-v1 %s %s %s)' % (
                kind, canonical(digest(proof)), canonical(canonical(proof['observation'])))
        # The trusted adapter evaluates ONLY these approved-parent bytes and
        # authenticated ground atoms, with no project or candidate equations.
        seed_bytes = {path: root['seed_bytes'][path] for path in sorted(root['seed_bytes'])}
        result = self.evaluate_native(deepcopy(seed_bytes), atoms, code)
        trace = {'root_id': root['root_id'], 'ruleset_digest': root['ruleset_digest'],
            'seed_order': list(seed_bytes),
            'seed_hashes': {path: hashlib.sha256(raw).hexdigest() for path, raw in seed_bytes.items()},
            'capsule': capsule, 'query': code, 'result': deepcopy(result), 'proof_atoms': atoms}
        if not isinstance(result, dict) or result.get('ok') is not True:
            self._write(identity, 'failed-native-evaluation', self.native_producer,
                        {**bound, 'invocation_id': invocation, 'native_trace': trace})
            raise GovernorRecordError('approved-parent native evaluator is unavailable')
        match = CONCLUSION.fullmatch(str(result.get('result', '')))
        if not match:
            self._write(identity, 'failed-native-evaluation', self.native_producer,
                        {**bound, 'invocation_id': invocation, 'native_trace': trace})
            raise GovernorRecordError('approved parent has no unambiguous governor-change rule; bootstrap remains unresolved')
        if self._candidate(candidate_id)[2] != bound or self.authorization_reader(proposal_id) != item:
            raise GovernorRecordError('candidate/parent/approval changed during native deliberation')
        if self._native_root(candidate) != root:
            raise GovernorRecordError('approved native root changed during deliberation')
        now = self.clock()
        if any(now > proof['expires_at'] for proof in proofs.values()):
            raise GovernorRecordError('proof expired during native deliberation; no decision was authorized')
        decision = {**bound, 'decision_id': identity, 'producer': self.native_producer,
            'invocation_id': invocation, 'proposal_id': proposal_id, 'proposal_digest': item['proposal_digest'],
            'dispatch_authorization': dispatch_authorization,
            'proof_digests': {kind: digest(proof) for kind, proof in proofs.items()},
            'issued_at': now, 'expires_at': min(now + self.proof_ttl, *[p['expires_at'] for p in proofs.values()]),
            'revoked': False, 'conclusion': match.group(1),
            'native_trace': {**trace, 'result': result['result']}}
        self._write(identity, 'decision', self.native_producer, decision)
        return decision

    def decision_reader(self, identity):
        envelope = self._read(identity)
        decision = envelope['payload']
        if (envelope['kind'] != 'decision' or envelope['producer'] != self.native_producer or
                decision.get('producer') != self.native_producer or decision.get('decision_id') != identity):
            raise GovernorRecordError('native decision producer differs')
        invocation = self._read(decision.get('invocation_id'))
        if invocation['kind'] != 'invocation' or invocation['producer'] != self.native_producer or any(
                invocation['payload'].get(key) != decision.get(key) for key in
                ('candidate_id', 'candidate_digest', 'parent_revision', 'governing_ruleset', 'snapshot')):
            raise GovernorRecordError('decision does not follow its authenticated native invocation')
        return decision

    def diagnostic_reader(self, identity):
        """Authenticated raw trace, including non-decision native failures."""
        return self._read(identity)
