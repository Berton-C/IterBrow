"""Named cognitive views over the existing journal, without another authority.

The service constructs Access from authenticated caller identity; callers must
never supply their own access object over RPC. This adapter is not an OS sandbox.
Snapshots carry exact per-space identity and one physical read cut. Application
atoms must not be evaluated as governance rules: native governing code evaluates
trusted seeds and an authenticated ground context separately.
"""
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import quote

from .atomspace_store import TransactionConflict


SPACE = re.compile(r'^(default|control|personal|learning|(?:project|scratch)/[a-z0-9][a-z0-9_-]{0,63})$')
PREFIX = 'fabric:'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def space_name(value):
    if not isinstance(value, str) or not SPACE.fullmatch(value):
        raise ValueError('invalid cognitive space')
    return value


@dataclass(frozen=True)
class Access:
    """Server-owned capability; no implicit wildcard, elevation, or inheritance."""
    principal: str
    reads: frozenset
    writes: frozenset

    def require(self, space, write=False):
        space_name(space)
        permitted = self.writes if write else self.reads
        if space not in permitted:
            raise PermissionError('%s cannot %s %s' % (self.principal, 'write' if write else 'read', space))
        if space == 'default' and write:
            raise PermissionError('default compatibility writes use the existing transaction API')


class CognitiveFabric:
    def __init__(self, store, rebuild_engine=None):
        self.store = store
        self.rebuild_engine = rebuild_engine

    @staticmethod
    def _meta_key(space):
        return PREFIX + 'space:' + quote(space, safe='')

    @staticmethod
    def _prefix(space):
        return PREFIX + 'atom:' + quote(space, safe='') + ':'

    @classmethod
    def atom_id(cls, space, key):
        space_name(space)
        if not isinstance(key, str) or not key or len(key) > 512:
            raise ValueError('atom key must be a nonempty bounded string')
        return cls._prefix(space) + quote(key, safe='')

    def _view(self, state, space):
        from urllib.parse import unquote
        if space == 'default':
            atoms = {k: v for k, v in state['atoms'].items() if not k.startswith(PREFIX)}
            revision = state['commit']
        else:
            prefix = self._prefix(space)
            atoms = {unquote(k[len(prefix):]): v for k, v in state['atoms'].items() if k.startswith(prefix)}
            raw = state['atoms'].get(self._meta_key(space))
            revision = 0
            if raw:
                if not raw.startswith('(fabric-space ') or not raw.endswith(')'):
                    raise RuntimeError('invalid space descriptor')
                descriptor = json.loads(json.loads(raw[len('(fabric-space '):-1]))
                if descriptor['space_id'] != space or descriptor['state_hash'] != digest(atoms):
                    raise RuntimeError('space descriptor does not match committed atoms')
                revision = descriptor['commit']
        identity = {'space_id': space, 'epoch': state['epoch'], 'commit': revision, 'state_hash': digest(atoms)}
        return {'identity': identity, 'atoms': atoms}

    def snapshot(self, spaces, access):
        spaces = list(spaces)
        if not spaces or len(set(spaces)) != len(spaces):
            raise ValueError('SnapshotSet requires unique named spaces')
        for space in spaces:
            access.require(space)
        state = self.store.state_copy()
        views = {s: self._view(state, s) for s in sorted(spaces)}
        return {'schema_version': 1,
                'root_snapshot': {k: state[k] for k in ('epoch', 'commit', 'state_hash')},
                'spaces': [views[s]['identity'] for s in views],
                'views': {s: views[s]['atoms'] for s in views}}

    @staticmethod
    def snapshot_set(snapshot):
        return {k: snapshot[k] for k in ('schema_version', 'root_snapshot', 'spaces')}

    def _check(self, expected, access, state):
        if not isinstance(expected, dict) or expected.get('schema_version') != 1:
            raise ValueError('an exact SnapshotSet is required')
        identities = expected.get('spaces')
        if not isinstance(identities, list) or not identities:
            raise ValueError('SnapshotSet has no spaces')
        names = [i.get('space_id') for i in identities]
        if len(set(names)) != len(names):
            raise ValueError('SnapshotSet repeats a space')
        if expected.get('root_snapshot', {}).get('epoch') != state['epoch']:
            raise TransactionConflict('SnapshotSet epoch changed')
        for identity in identities:
            space = identity['space_id']
            access.require(space)
            if identity != self._view(state, space)['identity']:
                raise TransactionConflict('stale cognitive space: ' + space)
        return set(names)

    def transact(self, space, operations, *, access, expected, transaction_id, source, metadata=None):
        access.require(space, write=True)
        access.require(space)
        if not isinstance(transaction_id, str) or not transaction_id or not source:
            raise ValueError('transaction identity and provenance are required')
        # Normalization is shared with the proven journal; the adapter adds
        # namespace ownership and compare-and-swap over all observed spaces.
        operations = self.store._normalise_operations(operations)
        body = {'space': space, 'operations': operations, 'actor': access.principal,
                'source': source, 'metadata': metadata or {}}
        fingerprint = digest(body)
        receipt_key = PREFIX + 'receipt:' + quote(space, safe='') + ':' + digest(transaction_id)
        with self.store.lock:
            state = self.store.state_copy()
            receipt = state['atoms'].get(receipt_key)
            if receipt:
                stored = json.loads(json.loads(receipt[len('(fabric-receipt '):-1]))
                if stored['fingerprint'] != fingerprint:
                    raise TransactionConflict('transaction ID reused for different content')
                return {**stored, 'duplicate': True}
            named = self._check(expected, access, state)
            if space not in named:
                raise ValueError('write target must occur in SnapshotSet')
            before = self._view(state, space)
            after = self.store._apply_operations(before['atoms'], operations)
            identity = {'space_id': space, 'epoch': state['epoch'],
                        'commit': before['identity']['commit'] + 1, 'state_hash': digest(after)}
            translated = [{**op, 'key': self.atom_id(space, op['key'])} for op in operations]
            receipt = {'fingerprint': fingerprint, 'transaction_id': transaction_id,
                       'identity': identity, 'root_commit': state['commit'] + 1}
            translated += [
                {'op': 'upsert', 'key': self._meta_key(space), 'atom': '(fabric-space %s)' % canonical(canonical(identity))},
                {'op': 'add', 'key': receipt_key, 'atom': '(fabric-receipt %s)' % canonical(canonical(receipt))},
            ]
            self.store.transact(translated, actor=access.principal, source=source,
                transaction_id='fabric:' + digest([space, transaction_id]), rebuild_engine=self.rebuild_engine,
                metadata={**(metadata or {}), 'cognitive_fabric': {
                    'space_id': space, 'observed': self.snapshot_set(expected), 'fingerprint': fingerprint}})
            return {**receipt, 'duplicate': False}
