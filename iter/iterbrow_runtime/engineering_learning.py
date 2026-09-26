"""Cumulative engineering evidence in named learning space.

Native MeTTa owns outcome comparison, Truth Revision and candidate ranking.
Python authenticates observations, transports ground contexts and commits exact
native results. query_native and observation_reader are trusted service adapters,
never supplied by app or tool arguments. This module grants no execution rights.
"""
import json
import math
import re

from .cognitive_fabric import canonical, digest
from .atomspace_store import TransactionConflict


REVISION = re.compile(r'\(engineering-learning-result\s+"([^"]+)"\s+(positive|negative|incomplete)\s+\(stv\s+([-+\d.eE]+)\s+([-+\d.eE]+)\)\)')
RANK = re.compile(r'\(engineering-ranked\s+"([^"]+)"\s+"([^"]+)"\)')
TEXT = ('work_id', 'authorization_ref', 'observation_id', 'strategy', 'change_class',
        'repository_context', 'predicted_outcome')


def record_atom(kind, value):
    return '(%s %s)' % (kind, canonical(canonical(value)))


def read_record(kind, atom):
    prefix = '(' + kind + ' '
    if not isinstance(atom, str) or not atom.startswith(prefix) or not atom.endswith(')'):
        raise ValueError('invalid durable engineering record')
    return json.loads(json.loads(atom[len(prefix):-1]))


def evidence_atom(evidence, native_label):
    """Native-queryable tuple; the same transaction retains its full provenance.

    No outcome is classified here: native_label is the authenticated native
    comparison result, and test_result retains the observed process facts.
    """
    observation = evidence['observation']
    fields = [canonical(evidence[k]) for k in (
        'strategy', 'change_class', 'repository_context', 'predicted_outcome')]
    fields += [canonical(observation['postcondition']),
               '(EngineeringTestResult %s %s %s)' % (
                   observation['process_state'], observation['exit_code'], native_label),
               canonical(evidence['evidence_id'])]
    return '(EngineeringEvidence %s)' % ' '.join(fields)


class EngineeringLearning:
    def __init__(self, fabric, access, query_native, observation_reader):
        self.fabric = fabric
        self.access = access
        self.query_native = query_native
        self.observation_reader = observation_reader

    @staticmethod
    def belief_key(strategy, change_class, repository_context):
        return 'belief:' + digest([strategy, change_class, repository_context])

    def _belief(self, snapshot, strategy, change_class, repository_context):
        raw = snapshot['views']['learning'].get(self.belief_key(strategy, change_class, repository_context))
        if raw:
            belief = read_record('EngineeringBeliefV1', raw)
            if [belief['strategy'], belief['change_class'], belief['repository_context']] != [strategy, change_class, repository_context]:
                raise RuntimeError('belief context mismatch')
            return belief
        return {'strategy': strategy, 'change_class': change_class,
                'repository_context': repository_context, 'frequency': 0.5,
                'confidence': 0.0, 'evidence_count': 0}

    @staticmethod
    def _truth(belief):
        return '(stv %s %s)' % (belief['frequency'], belief['confidence'])

    def _query(self, capsule, function, snapshot):
        # Only the trusted seed plus this authenticated ground context enters
        # native evaluation; arbitrary application rules cannot shadow it.
        response = self.query_native({digest(capsule): capsule}, '!(%s %s)' % (function, capsule))
        if not isinstance(response, dict) or not response.get('ok'):
            raise RuntimeError('native engineering learning unavailable')
        ruleset = response.get('ruleset_digest')
        if ruleset is not None and (not isinstance(ruleset, str) or not re.fullmatch(r'[a-f0-9]{64}', ruleset)):
            raise RuntimeError('native ruleset provenance is invalid')
        return str(response['result']), ruleset

    def record(self, supplied):
        if not isinstance(supplied, dict) or set(supplied) != set(TEXT):
            raise ValueError('evidence requires exactly its identity, strategy and prediction fields')
        if any(not isinstance(supplied[k], str) or not supplied[k].strip() for k in TEXT):
            raise ValueError('evidence fields must be nonempty strings')
        evidence = dict(supplied)
        observation = self.observation_reader(evidence['observation_id'])
        for key in ('work_id', 'authorization_ref', 'observation_id'):
            if observation.get(key) != evidence[key]:
                raise ValueError('observation does not authenticate evidence identity')
        snapshot_id = observation.get('snapshot') or {}
        if any(snapshot_id.get(k) in (None, '') for k in ('epoch', 'commit', 'state_hash')):
            raise ValueError('observation has no authoritative snapshot')
        if observation.get('process_state') not in ('exited', 'spawn_failed', 'timed_out', 'interrupted'):
            raise ValueError('observation process state is invalid')
        if type(observation.get('exit_code')) is not int or not isinstance(observation.get('postcondition'), str):
            raise ValueError('observation lacks raw test and postcondition facts')
        proofs = observation.get('proofs', {})
        if not isinstance(proofs, dict) or any(v not in ('passed', 'failed', 'unknown') for v in proofs.values()):
            raise ValueError('observation proof facts are invalid')
        proof_atoms = 'nil'
        for status in reversed(list(proofs.values())):
            proof_atoms = '(cons %s %s)' % (status, proof_atoms)
        evidence_id = 'engineering-evidence:' + digest([snapshot_id['epoch'], evidence['observation_id']])
        evidence.update(evidence_id=evidence_id, observation=observation)
        # Idempotency identity excludes the selected strategy: reclassifying
        # one observation cannot count it again as another strategy's outcome.
        key = 'evidence:' + evidence_id
        snapshot = self.fabric.snapshot(['learning'], self.access)
        existing = snapshot['views']['learning'].get(key)
        if existing:
            previous = read_record('EngineeringEvidenceV1', existing)
            if previous['evidence'] != evidence:
                raise TransactionConflict('evidence identity reused with different claims')
            return {**previous, 'duplicate': True}
        prior = self._belief(snapshot, evidence['strategy'], evidence['change_class'], evidence['repository_context'])
        capsule = '(engineering-learning-context-v1 %s %s %s %s %s %s %s %s %s %s)' % (
            canonical(evidence_id), canonical(evidence['strategy']), canonical(evidence['change_class']),
            canonical(evidence['repository_context']), observation['process_state'], observation['exit_code'],
            canonical(evidence['predicted_outcome']), canonical(observation['postcondition']), proof_atoms, self._truth(prior))
        raw, ruleset = self._query(capsule, 'engineering-learning-revise', snapshot)
        matches = REVISION.findall(raw)
        if len(matches) != 1 or matches[0][0] != evidence_id:
            raise RuntimeError('native evidence revision identity is ambiguous')
        _, label, frequency, confidence = matches[0]
        frequency, confidence = float(frequency), float(confidence)
        if not all(math.isfinite(n) and 0 <= n <= 1 for n in (frequency, confidence)):
            raise RuntimeError('native evidence truth value is invalid')
        revised = {**prior, 'frequency': frequency, 'confidence': confidence,
                   'evidence_count': prior['evidence_count'] + int(label != 'incomplete'),
                   'last_evidence_id': evidence_id}
        record = {'evidence': evidence, 'native_result': raw, 'native_label': label,
                  'prior': prior, 'revised': revised, 'evaluated': self.fabric.snapshot_set(snapshot),
                  'native_ruleset_digest': ruleset}
        self.fabric.transact('learning', [
            {'op': 'add', 'key': key, 'atom': record_atom('EngineeringEvidenceV1', record)},
            {'op': 'add', 'key': 'native:' + key, 'atom': evidence_atom(evidence, label)},
            {'op': 'upsert', 'key': self.belief_key(evidence['strategy'], evidence['change_class'], evidence['repository_context']),
             'atom': record_atom('EngineeringBeliefV1', revised)},
        ], access=self.access, expected=snapshot, transaction_id=evidence_id,
           source='engineering_learning.native_revision', metadata={'evidence_id': evidence_id})
        return {**record, 'duplicate': False}

    def rank(self, work_id, strategies, change_class, repository_context):
        if len(strategies) != 2 or len(set(strategies)) != 2:
            raise ValueError('one bounded decision compares two distinct alternatives')
        if any(not isinstance(s, str) or not re.fullmatch(r'[a-zA-Z0-9_.:-]+', s) for s in [work_id, *strategies]):
            raise ValueError('invalid ranking identity')
        snapshot = self.fabric.snapshot(['learning'], self.access)
        beliefs = [self._belief(snapshot, s, change_class, repository_context) for s in strategies]
        # Preserve the actual evidence identities behind the consulted beliefs.
        # Incomplete observations remain discoverable but carry no truth weight.
        # This projection classifies no outcome: labels are native ledger facts.
        evidence_basis = []
        for atom in snapshot['views']['learning'].values():
            if not atom.startswith('(EngineeringEvidenceV1 '):
                continue
            prior = read_record('EngineeringEvidenceV1', atom)
            evidence = prior['evidence']
            if (evidence['strategy'] in strategies and evidence['change_class'] == change_class
                    and evidence['repository_context'] == repository_context):
                evidence_basis.append({'evidence_id': evidence['evidence_id'], 'strategy': evidence['strategy'],
                    'observation_id': evidence['observation_id'], 'native_label': prior['native_label']})
        evidence_basis.sort(key=lambda item: item['evidence_id'])
        capsule = '(engineering-ranking-context-v1 %s %s %s %s %s)' % (
            canonical(work_id), canonical(strategies[0]), self._truth(beliefs[0]),
            canonical(strategies[1]), self._truth(beliefs[1]))
        raw, ruleset = self._query(capsule, 'engineering-learning-rank', snapshot)
        matches = RANK.findall(raw)
        if len(matches) != 1 or matches[0][0] != work_id or matches[0][1] not in strategies:
            raise RuntimeError('native ranking identity is ambiguous')
        return {'work_id': work_id, 'selected': matches[0][1], 'beliefs': beliefs, 'evidence_basis': evidence_basis,
                'snapshot_set': self.fabric.snapshot_set(snapshot), 'native_result': raw,
                'native_ruleset_digest': ruleset,
                'dispatch_authority': False, 'proof_obligations_may_be_weakened': False}
