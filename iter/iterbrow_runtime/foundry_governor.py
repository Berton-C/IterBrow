"""Durable transport for the native, action-generic engineering work grammar.

Trusted service adapters authenticate PWQ scope and independently captured raw
observations. This module does not execute tools or decide semantic outcomes.
The native seed selects proof duties and accept/iterate/escalate/rollback.
Running claims are never retried: after an uncertain interruption an external
executor reconciles effects and supplies an observation with the same identity.
"""
import json
import re

from .atomspace_store import TransactionConflict
from .cognitive_fabric import canonical, digest
from .engineering_learning import read_record, record_atom


IDENTITY = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
STRATEGY = re.compile(r'^[a-zA-Z0-9_.:-]+$')
ACTIONS = frozenset({'project.create', 'project.revise', 'source.write', 'project.inspect', 'project.research',
                     'app.stage', 'test.static', 'test.browser', 'app.activate', 'app.rollback'})
OUTCOMES = frozenset({'accept', 'iterate', 'escalate', 'rollback'})
WORK_FIELDS = frozenset({'work_id', 'project_id', 'parent_id', 'intention', 'invariants',
    'current_state', 'unresolved_gap', 'alternatives', 'obligations', 'authorization_ref',
    'repository_context', 'change_class', 'recovery_ref'})
MEMORY_USE_FIELDS = frozenset({'kind', 'source_ref', 'source_hash', 'target', 'strategy', 'rationale'})
OUTCOME = re.compile(r'^\[\[\(foundry-outcome "([^"]+)" (accept|iterate|escalate|rollback) "([^"]+)"\)\]\]$')


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 32000:
        raise ValueError(label + ' must be nonempty bounded text')
    return value


def _strings(values, label, allow_empty=False):
    if not isinstance(values, list) or (not values and not allow_empty) or len(values) > 64:
        raise ValueError(label + ' must be a bounded list')
    for value in values:
        _text(value, label)
    if len(set(values)) != len(values):
        raise ValueError(label + ' contains duplicate values')
    return list(values)


def _list(values):
    result = 'nil'
    for value in reversed(values):
        result = '(cons %s %s)' % (value, result)
    return result


def _parse_strings(expression):
    """Read only the closed native cons-of-strings return type, never eval."""
    if expression == 'nil':
        return []
    if not expression.startswith('(cons '):
        raise RuntimeError('invalid native obligation list')
    try:
        value, end = json.JSONDecoder().raw_decode(expression[6:])
    except ValueError as exc:
        raise RuntimeError('invalid native obligation string') from exc
    if not isinstance(value, str) or not expression.endswith(')'):
        raise RuntimeError('invalid native obligation value')
    remainder = expression[6 + end:-1].strip()
    return [value] + _parse_strings(remainder)


class FoundryGovernor:
    def __init__(self, fabric, access, learning, query_native,
                 authorization_verifier, observation_reader, action_registry=None, memory_reader=None):
        self.fabric, self.access, self.learning = fabric, access, learning
        self.query_native = query_native
        self.authorization_verifier = authorization_verifier
        self.observation_reader = observation_reader
        self.memory_reader = memory_reader
        # The host injects its executable capability catalogue. This is schema
        # validation, not a universal limit on Iter's existing tools or future
        # abilities. Extending transport never grants authorization or changes
        # native policy; unrelated legacy tool surfaces are untouched.
        self.actions = frozenset(ACTIONS if action_registry is None else action_registry)
        if any(not isinstance(name, str) or not STRATEGY.fullmatch(name) for name in self.actions):
            raise ValueError('invalid trusted action registry')

    @staticmethod
    def _space(work_id):
        if not isinstance(work_id, str) or not IDENTITY.fullmatch(work_id):
            raise ValueError('work_id must be a safe lower-case identifier')
        return 'scratch/' + work_id

    def _read(self, work_id):
        space = self._space(work_id)
        snapshot = self.fabric.snapshot([space], self.access)
        raw = snapshot['views'][space].get('work')
        if raw is None:
            raise KeyError('unknown engineering work: ' + work_id)
        return read_record('FoundryWorkV1', raw), snapshot

    def status(self, work_id):
        record, snapshot = self._read(work_id)
        return {**record, 'snapshot_set': self.fabric.snapshot_set(snapshot)}

    def _save(self, record, snapshot, stage):
        space = self._space(record['work']['work_id'])
        work = record['work']
        # Ground source records are separately native-queryable. JSON retains
        # complete payload/provenance; neither representation is executable code.
        grammar = '(FoundryWork %s %s %s %s %s %s %s)' % (
            canonical(work['work_id']), canonical(work['parent_id']), canonical(work['intention']),
            _list([canonical(v) for v in work['invariants']]), canonical(work['current_state']),
            canonical(work['unresolved_gap']), canonical(record['state']))
        self.fabric.transact(space, [
            {'op': 'upsert', 'key': 'work', 'atom': record_atom('FoundryWorkV1', record)},
            {'op': 'upsert', 'key': 'grammar', 'atom': grammar},
            {'op': 'add', 'key': 'event:' + stage + ':' + digest(record),
             'atom': record_atom('FoundryEventV1', record)},
        ], access=self.access, expected=snapshot,
           transaction_id='foundry:' + stage + ':' + digest(record),
           source='foundry_governor.' + stage,
           metadata={'work_id': work['work_id'], 'parent_id': work['parent_id'], 'stage': stage})
        return record

    def submit(self, work):
        if not isinstance(work, dict) or not WORK_FIELDS.issubset(work) or set(work) - WORK_FIELDS - {'memory_uses'}:
            raise ValueError('engineering work requires its fixed fields and optional memory_uses: ' + ', '.join(sorted(WORK_FIELDS)))
        work = json.loads(canonical(work))
        self._space(work['work_id'])
        if not isinstance(work['project_id'], str) or not IDENTITY.fullmatch(work['project_id']):
            raise ValueError('invalid project identity')
        for name in ('intention', 'current_state', 'unresolved_gap', 'authorization_ref',
                     'repository_context', 'change_class'):
            _text(work[name], name)
        work['invariants'] = _strings(work['invariants'], 'invariants')
        work['obligations'] = _strings(work['obligations'], 'obligations', True)
        if not isinstance(work['recovery_ref'], str) or not isinstance(work['parent_id'], str):
            raise ValueError('parent and recovery references must be strings')
        alternatives = work['alternatives']
        if not isinstance(alternatives, list) or len(alternatives) != 2:
            raise ValueError('a bounded decision requires two alternatives')
        for alternative in alternatives:
            if not isinstance(alternative, dict) or set(alternative) != {'strategy', 'action', 'predicted_outcome', 'risks'}:
                raise ValueError('invalid engineering alternative')
            if not isinstance(alternative['strategy'], str) or not STRATEGY.fullmatch(alternative['strategy']):
                raise ValueError('invalid strategy identity')
            _text(alternative['predicted_outcome'], 'predicted_outcome')
            _strings(alternative['risks'], 'risks', True)
            action = alternative['action']
            if not isinstance(action, dict) or set(action) != {'type', 'payload'} or action['type'] not in self.actions:
                raise ValueError('unregistered typed engineering action')
            if not isinstance(action['payload'], dict) or len(canonical(action['payload'])) > 2000000:
                raise ValueError('action payload must be a bounded object')
        if alternatives[0]['strategy'] == alternatives[1]['strategy']:
            raise ValueError('alternatives need distinct strategy identities')
        self._memory_basis(work)
        depth = 0
        spaces = [self._space(work['work_id'])]
        if work['parent_id']:
            if work['parent_id'] == work['work_id']:
                raise ValueError('work cannot be its own parent')
            parent, _ = self._read(work['parent_id'])
            if parent['work']['project_id'] != work['project_id'] or parent['work']['authorization_ref'] != work['authorization_ref']:
                raise PermissionError('child work cannot change project or authorization')
            if not set(parent['work']['invariants']).issubset(work['invariants']):
                raise ValueError('child work cannot drop parent invariants')
            if not set(parent['work']['obligations']).issubset(work['obligations']):
                raise ValueError('child work cannot drop parent proof obligations')
            depth = parent['depth'] + 1
            spaces.append(self._space(work['parent_id']))
        snapshot = self.fabric.snapshot(spaces, self.access)
        previous = snapshot['views'][spaces[0]].get('work')
        if previous:
            record = read_record('FoundryWorkV1', previous)
            if record['work'] != work:
                raise TransactionConflict('work identity is immutable; use a new child or revision identity')
            return {**record, 'duplicate': True}
        return self._save({'work': work, 'state': 'submitted', 'depth': depth}, snapshot, 'submit')

    def _snapshot(self, work):
        return self.fabric.snapshot(['control', 'personal', 'learning',
            'project/' + work['project_id'], self._space(work['work_id'])], self.access)

    def _query(self, capsule, function):
        result = self.query_native({digest(capsule): capsule}, '!(%s %s)' % (function, capsule))
        if not isinstance(result, dict) or not result.get('ok'):
            raise RuntimeError('native foundry governor unavailable')
        return str(result['result'])

    def _memory_basis(self, work):
        """Authenticate citations, never interpret retrieved prose as policy.

        A citation says how Iter proposes using an observed memory in its work;
        source verification cannot by itself prove the natural-language claim.
        Native ranking continues to use measured EngineeringEvidence only.
        """
        uses = work.get('memory_uses', [])
        if not isinstance(uses, list) or len(uses) > 16:
            raise ValueError('memory_uses must be a bounded list')
        captured = self.memory_reader(work['work_id']) if self.memory_reader else None
        if uses and not isinstance(captured, dict):
            raise ValueError('memory citations require a trusted captured intake')
        captured = captured or {}
        if captured and (not isinstance(captured.get('version_key'), str) or not captured.get('projection_only')):
            raise ValueError('memory intake is not a versioned read projection')
        known = {}
        for item in captured.get('semantic', []):
            known[('semantic', item['atom_key'])] = item['atom_hash']
        for kind, group in [('episode', 'episodes'), ('excerpt', 'excerpts')]:
            for item in captured.get(group, []):
                known[(kind, item['source_path'])] = item['source_hash']
        strategies = {a['strategy'] for a in work['alternatives']}
        verified = []
        for use in uses:
            if not isinstance(use, dict) or set(use) != MEMORY_USE_FIELDS:
                raise ValueError('invalid memory-use citation schema')
            if use['kind'] not in {'semantic', 'episode', 'excerpt'} or use['target'] not in {'gap', 'alternative', 'prediction', 'obligation'}:
                raise ValueError('invalid memory-use kind or target')
            for field in ('source_ref', 'source_hash', 'rationale'):
                _text(use[field], 'memory use ' + field)
            if len(use['rationale']) > 2000:
                raise ValueError('memory-use rationale is too long')
            if use['strategy'] not in strategies | {''} or (use['target'] in {'alternative', 'prediction'} and not use['strategy']):
                raise ValueError('memory use does not identify a declared alternative')
            if known.get((use['kind'], use['source_ref'])) != use['source_hash']:
                raise ValueError('memory citation was not present in the captured intake')
            verified.append({**use, 'citation_id': 'memory-use:' + digest([captured['version_key'], use])})
        if len({item['citation_id'] for item in verified}) != len(verified):
            raise ValueError('duplicate memory-use citation')
        return {'version_key': captured.get('version_key'), 'verified_references': verified,
            'available_sources': {'semantic': len(captured.get('semantic', [])),
                'episode': len(captured.get('episodes', [])), 'excerpt': len(captured.get('excerpts', []))},
            'natural_language_effect_is_proposed': True, 'memory_text_grants_authority': False}

    def _authorize(self, work, alternative, snapshot):
        auth = self.authorization_verifier(work, alternative, self.fabric.snapshot_set(snapshot))
        if not isinstance(auth, dict) or auth.get('valid') is not True or auth.get('authorization_ref') != work['authorization_ref']:
            raise PermissionError('current action-bound authorization required')
        _text(auth.get('scope_digest'), 'scope_digest')
        return auth

    def decide(self, work_id):
        record, _ = self._read(work_id)
        if record['state'] != 'submitted':
            return record
        work = record['work']
        snapshot = self._snapshot(work)
        memory_basis = self._memory_basis(work)
        rank = self.learning.rank(work_id, [a['strategy'] for a in work['alternatives']],
                                  work['change_class'], work['repository_context'])
        # Ranking and duties must read the same learning version.
        ranked = next(i for i in rank['snapshot_set']['spaces'] if i['space_id'] == 'learning')
        if ranked != next(i for i in snapshot['spaces'] if i['space_id'] == 'learning'):
            raise TransactionConflict('learning changed while ranking')
        selected = next(a for a in work['alternatives'] if a['strategy'] == rank['selected'])
        auth = self._authorize(work, selected, snapshot)
        history = []
        for atom in snapshot['views']['learning'].values():
            if atom.startswith('(EngineeringEvidenceV1 '):
                prior = read_record('EngineeringEvidenceV1', atom)
                evidence = prior['evidence']
                if evidence['change_class'] == work['change_class'] and evidence['repository_context'] == work['repository_context']:
                    # Labels originate in native revision, not a Python outcome classifier.
                    history.append({'evidence_id': evidence['evidence_id'], 'native_label': prior['native_label'],
                                    'strategy': evidence['strategy'], 'observation_id': evidence['observation_id']})
        history.sort(key=lambda item: item['evidence_id'])
        memory_atom = '(foundry-memory-basis %s %s)' % (canonical(memory_basis['version_key'] or 'none'),
            _list([canonical(item['citation_id']) for item in memory_basis['verified_references']]))
        capsule = '(foundry-plan-context %s %s %s %s %s %s %s %s)' % (
            canonical(work_id), canonical(selected['strategy']), canonical(selected['action']['type']), canonical(work['change_class']),
            _list(['(engineering-history %s %s)' % (canonical(e['evidence_id']), e['native_label'])
                   for e in history]), _list([canonical(v) for v in work['invariants']]),
            _list([canonical(v) for v in work['obligations']]), memory_atom)
        raw = self._query(capsule, 'foundry-plan')
        prefix = '[[(' + 'foundry-dispatch ' + canonical(work_id) + ' ' + canonical(selected['strategy']) + ' '
        suffix = ' ' + memory_atom + ')]]'
        if not raw.startswith(prefix) or not raw.endswith(suffix):
            raise RuntimeError('native decision identity is ambiguous')
        proofs = list(dict.fromkeys(_parse_strings(raw[len(prefix):-len(suffix)])))
        decision = {'selected': selected, 'action_digest': digest(selected['action']),
            'required_proofs': proofs, 'ranking': rank, 'native_result': raw, 'history_evidence': history,
            'memory_basis': memory_basis,
            'authorization': auth, 'evaluated_snapshot': self.fabric.snapshot_set(snapshot)}
        decision['decision_id'] = 'foundry-decision:' + digest([work_id, decision])
        return self._save({**record, 'state': 'decided', 'decision': decision}, snapshot, 'decide')

    def claim(self, work_id, decision_id):
        with self.fabric.store.lock:
            record, _ = self._read(work_id)
            if record['state'] != 'decided':
                raise TransactionConflict('only an unclaimed decision may execute; reconcile effects instead of retrying')
            decision, work = record['decision'], record['work']
            if decision['decision_id'] != decision_id:
                raise TransactionConflict('decision identity mismatch')
            snapshot = self._snapshot(work)
            own_space = self._space(work_id)
            expected = decision['evaluated_snapshot']
            for identity in expected['spaces']:
                if identity['space_id'] != own_space and identity not in snapshot['spaces']:
                    raise TransactionConflict('decision dependency changed: ' + identity['space_id'])
            if expected['root_snapshot']['epoch'] != snapshot['root_snapshot']['epoch']:
                raise TransactionConflict('decision epoch changed')
            auth = self._authorize(work, decision['selected'], snapshot)
            if auth != decision['authorization']:
                raise TransactionConflict('authorization changed since native decision')
            action_id = 'foundry-action:' + digest([work_id, decision_id])
            claim = {'action_id': action_id, 'observation_id': 'foundry-observation:' + digest(action_id),
                'work_id': work_id, 'authorization_ref': work['authorization_ref'],
                'action': decision['selected']['action'], 'action_digest': decision['action_digest'],
                'required_proofs': decision['required_proofs'], 'evaluated_snapshot': expected,
                'dispatch_snapshot': self.fabric.snapshot_set(snapshot)}
            self._save({**record, 'state': 'running', 'claim': claim}, snapshot, 'claim')
            return claim

    def observe(self, work_id, observation_id):
        record, snapshot = self._read(work_id)
        if 'claim' not in record or record['claim']['observation_id'] != observation_id:
            raise ValueError('observation is not bound to a claimed action')
        if record['state'] in OUTCOMES:
            return record
        if record['state'] not in {'running', 'uncertain', 'observed'}:
            raise ValueError('work is not awaiting an observation')
        if record['state'] == 'observed':
            observation = record['observation']
        else:
            observation = self.observation_reader(observation_id)
            if not isinstance(observation, dict):
                raise ValueError('independent observation is not yet available')
            claim = record['claim']
            for field in ('action_id', 'observation_id', 'work_id', 'authorization_ref'):
                if observation.get(field) != claim[field]:
                    raise ValueError('independent observation identity mismatch: ' + field)
            if observation.get('process_state') not in {'exited', 'spawn_failed', 'timed_out', 'interrupted'}:
                raise ValueError('invalid raw process state')
            if type(observation.get('exit_code')) is not int or not isinstance(observation.get('postcondition'), str):
                raise ValueError('invalid raw process observation')
            if not isinstance(observation.get('proofs'), dict) or any(v not in {'passed', 'failed', 'unknown'} for v in observation['proofs'].values()):
                raise ValueError('proofs must be independently observed named results')
            if len(observation['proofs']) > 128 or any(not isinstance(k, str) or not k.strip() for k in observation['proofs']):
                raise ValueError('proof identities must be bounded nonempty strings')
            if not isinstance(observation.get('snapshot'), dict) or any(observation['snapshot'].get(k) in (None, '') for k in ('epoch', 'commit', 'state_hash')):
                raise ValueError('observation lacks authoritative snapshot')
            record = self._save({**record, 'state': 'observed', 'observation': observation}, snapshot, 'observe')
        work, decision = record['work'], record['decision']
        selected = decision['selected']
        learned = self.learning.record({'work_id': work_id, 'authorization_ref': work['authorization_ref'],
            'observation_id': observation_id, 'strategy': selected['strategy'],
            'change_class': work['change_class'], 'repository_context': work['repository_context'],
            'predicted_outcome': selected['predicted_outcome']})
        if learned['evidence']['observation'] != observation:
            raise TransactionConflict('authenticated observation changed between capture and evidence revision')
        capsule = '(foundry-observation-context %s %s %s %s %s %s %s %s %s %s %s)' % (
            canonical(work_id), canonical(selected['action']['type']), observation['process_state'],
            observation['exit_code'], canonical(selected['predicted_outcome']), canonical(observation['postcondition']),
            _list([canonical(v) for v in decision['required_proofs']]),
            _list([canonical(v) for v in work['invariants']]),
            _list(['(proof %s %s)' % (canonical(k), v) for k, v in sorted(observation['proofs'].items())]),
            'ready' if work['recovery_ref'] else 'unavailable', record['depth'])
        raw = self._query(capsule, 'foundry-compare')
        match = OUTCOME.fullmatch(raw)
        if not match or match.group(1) != work_id:
            raise RuntimeError('native outcome identity is ambiguous')
        latest, snapshot = self._read(work_id)
        if latest['state'] in OUTCOMES:
            return latest
        if latest != record:
            raise TransactionConflict('work changed while comparing observation')
        return self._save({**record, 'state': match.group(2), 'reason': match.group(3),
            'native_outcome': raw, 'evidence_id': learned['evidence']['evidence_id']}, snapshot, 'compare')

    def reconcile(self, work_id):
        record, snapshot = self._read(work_id)
        if record['state'] in OUTCOMES or 'claim' not in record:
            return record
        identity = record['claim']['observation_id']
        if record['state'] == 'observed' or self.observation_reader(identity) is not None:
            return self.observe(work_id, identity)
        if record['state'] == 'running':
            return self._save({**record, 'state': 'uncertain',
                'recovery_requirement': 'executor must reconcile original effects and publish original observation identity'},
                snapshot, 'uncertain')
        return record
