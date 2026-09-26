"""Actual Iter action/observation boundary, owned by the AtomSpace service.

This is not a second reasoner or journal. Callers can propose work, never submit
observations, capabilities or approvals. Native rules decide; typed executors
return raw process/DOM facts. Background dispatch outlives an Iter tool timeout.
An interrupted service never automatically repeats a claimed side effect.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import threading
import time

from .cognitive_fabric import Access, CognitiveFabric, canonical, digest
from .engineering_learning import EngineeringLearning, read_record, record_atom
from .pwq_protocol import PWQStore


IDENTITY = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
ACTIONS = frozenset({'project.create', 'project.inspect', 'project.research',
    'project.revise', 'source.write', 'app.stage', 'test.static', 'test.browser',
    'app.activate', 'app.rollback'})
SEEDS = ('seeds/nace_substrate.metta', 'seeds/engineering_learning.metta',
         'seeds/engineering_alignment.metta', 'seeds/foundry_governor.metta')
SUPPORTED_INVARIANTS = ('source-boundary', 'data-preserved', 'authorization-current')


def identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise ValueError('project and work identities must be bounded lowercase slugs')
    return value


def _browser_call(method, **params):
    path = os.environ.get('ITER_BRIDGE_SOCKET')
    if not path:
        raise RuntimeError('the canonical browser endpoint is unavailable')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(30)
        connection.connect(path)
        connection.sendall((canonical({'method': method, 'params': params}) + '\n').encode())
        data = b''
        while b'\n' not in data:
            chunk = connection.recv(65536)
            if not chunk or len(data) > 4 * 1024 * 1024:
                raise RuntimeError('browser observation response incomplete or oversized')
            data += chunk
    response = json.loads(data.partition(b'\n')[0])
    if not response.get('ok'):
        raise RuntimeError(response.get('error', 'browser observation unavailable'))
    return response['result']


class FoundryService:
    def __init__(self, space, root, *, projects=None, pwq=None, browser_call=None,
                 governance_guard=None, runtime=None):
        from .foundry_projects import FoundryProjects
        from .governor_change import ActiveGovernanceGuard
        from .foundry_runtime import FoundryRuntime, RUNTIME_ACTIONS
        from .foundry_memory import FoundryMemory
        self.space = space
        self.root = Path(root).resolve()
        self.fabric = CognitiveFabric(space.store, space._rebuild_engine)
        self.projects = projects or FoundryProjects(self.root)
        self.pwq = pwq or PWQStore(self.root / '.runtime' / 'pwq')
        self.browser_call = browser_call or _browser_call
        self.lock = threading.RLock()
        self.native_lock = threading.RLock()
        self.running = {}
        self.guard = governance_guard or ActiveGovernanceGuard(self.root.parent, self._active_governance)
        self.native_units = None
        self.native_rules_digest = None
        self.runtime = runtime or FoundryRuntime(self.root)
        self.action_types = set(ACTIONS) | set(RUNTIME_ACTIONS)
        self.memory = FoundryMemory(self.root)

    def _active_governance(self):
        access = Access('platform.governor_reader', frozenset({'control'}), frozenset())
        atom = self.fabric.snapshot(['control'], access)['views']['control'].get('active-governance')
        return read_record('FoundryGovernanceActivationV1', atom) if atom else None

    def _check_guard(self):
        from metta_server import _logical_units
        with self.native_lock:
            captured = self.guard.capture()
            if self.native_rules_digest != captured['ruleset_digest']:
                self.native_units = tuple(unit for name in SEEDS for unit in
                    _logical_units(captured['source_bytes']['iter/' + name].decode('utf-8')))
                self.native_rules_digest = captured['ruleset_digest']
            return {**captured, 'seed_units': self.native_units}

    def _access(self, project_id, work_id, parent_id=None):
        names = {'control', 'personal', 'learning', 'project/' + identity(project_id),
                 'scratch/' + identity(work_id)}
        if parent_id and parent_id != 'none':
            names.add('scratch/' + identity(parent_id))
        return Access('platform.foundry', frozenset(names), frozenset(names - {'personal'}))

    def _native(self, atoms, code):
        captured = self._check_guard()
        # No application/user rules or broad default-space atoms enter governance.
        state = self.space.store.state_copy()
        state.update(atoms=atoms, seed_units=captured['seed_units'])
        with self.space.engine_lock:
            return {'ok': True, 'result': self.space._run_query_worker(state, code),
                    'ruleset_digest': captured['ruleset_digest']}

    def _put(self, name, key, kind, value, access, txid, immutable=False):
        snapshot = self.fabric.snapshot([name], access)
        atom = record_atom(kind, value)
        if snapshot['views'][name].get(key) == atom:
            return
        if immutable and key in snapshot['views'][name]:
            raise RuntimeError('independent observation identity already binds different content')
        self.fabric.transact(name, [{'op': 'add' if immutable else 'upsert', 'key': key, 'atom': atom}],
            access=access, expected=snapshot, transaction_id=txid,
            source='foundry_service', metadata={'kind': kind})

    def _project_context(self, project_id):
        if not (self.root / 'apps' / project_id / 'app.json').exists():
            return {'app_id': project_id, 'exists': False,
                    'source_context_hash': digest(['absent', project_id])}
        return self.projects.inspect(project_id)

    def _refresh_context(self, project_id, work_id, access):
        rules = self._check_guard()['source_hashes']
        context = self._project_context(project_id)
        self._put('project/' + project_id, 'repository-context', 'FoundryRepositoryContextV1',
                  context, access, 'foundry-project-context:' + digest(context))
        # An observed source identity is not a self-issued approval certificate.
        self._put('control', 'foundry-rules-observed', 'FoundryRulesObservedV1', rules,
                  access, 'foundry-rules-observed:' + digest(rules))
        return context

    def _capture_memory(self, work_id, intention, origin='submit'):
        # Preserve the observed memory slice for this work, not another memory
        # authority. Ordinary history/experience appends must not make each next
        # tool call invalidate its own decision. A new work intake reads fresh
        # sources; explicit recall always rechecks actual source identities.
        access = Access('platform.memory_projection', frozenset({'personal'}), frozenset({'personal'}))
        key = 'foundry-memory:' + work_id
        prior = self.fabric.snapshot(['personal'], access)['views']['personal'].get(key)
        if prior:
            projection = read_record('FoundryMemoryProjectionV1', prior)
            if (origin == 'submit' and projection.get('intake_origin') == 'submit'
                    and projection.get('intake_query_hash') != digest(intention[:2048])):
                raise ValueError('work identity already binds another memory intention; use a new work identity')
            return projection
        observed = self.memory.query(self.space.store.state_copy(), intention[:2048])
        observed.update(intake_origin=origin, intake_query=intention[:2048],
                        intake_query_hash=digest(intention[:2048]))
        self._put('personal', key, 'FoundryMemoryProjectionV1', observed, access,
                  'foundry-memory-intake:' + work_id, immutable=True)
        return observed

    def _observation(self, work_id, observation_id, access):
        view = self.fabric.snapshot(['scratch/' + work_id], access)['views']['scratch/' + work_id]
        atom = view.get('raw-observation:' + observation_id)
        return read_record('FoundryObservationV1', atom) if atom else None

    def _work_memory(self, work_id):
        access = Access('platform.memory_reader', frozenset({'personal'}), frozenset())
        view = self.fabric.snapshot(['personal'], access)['views']['personal']
        atom = view.get('foundry-memory:' + identity(work_id))
        return read_record('FoundryMemoryProjectionV1', atom) if atom else None

    def _governor(self, work):
        from .foundry_governor import FoundryGovernor
        access = self._access(work['project_id'], work['work_id'], work.get('parent_id'))
        reader = lambda oid: self._observation(work['work_id'], oid, access)
        learning = EngineeringLearning(self.fabric, access, self._native, reader)
        return FoundryGovernor(self.fabric, access, learning, self._native,
                               self._authorize, reader, action_registry=self.action_types,
                               memory_reader=self._work_memory), access

    def _authorize(self, work, alternative, snapshot_set):
        reference = work['authorization_ref']
        board = self.pwq.read()
        item = next((i for i in board['items'] if
                     reference == 'pwq:' + i['id'] + ':' + str(i.get('dispatch_authorization'))), None)
        if not item or item.get('status') not in ('approved', 'in_progress') or not (
                item.get('approval_status') or {}).get('ready'):
            raise PermissionError('current threshold-approved PWQ work authorization is required')
        scope = item.get('authorization_scope') or {}
        action = alternative['action']
        if (scope.get('action') != 'foundry.build' or scope.get('project_id') != work['project_id']
                or action['type'] not in scope.get('allowed_actions', []) or action['type'] not in self.action_types):
            raise PermissionError('selected action exceeds the approved project scope')
        payload = action.get('payload') or {}
        if action['type'] in ('project.create', 'project.revise'):
            target_blueprint = payload.get('blueprint')
        else:
            target_blueprint = self._project_context(work['project_id']).get('blueprint')
        if not target_blueprint or digest(target_blueprint) != scope.get('blueprint_hash'):
            raise PermissionError('the current or proposed blueprint is not the approved intention')
        return {'authorization_ref': reference, 'valid': True,
                'scope_digest': digest({'scope': scope, 'proposal_digest': item['proposal_digest'],
                                        'action': action})}

    def propose(self, project_id, blueprint, proposal_id, allowed_actions=None):
        identity(project_id)
        requested = set(ACTIONS if allowed_actions is None else allowed_actions)
        if not requested or not requested.issubset(self.action_types):
            raise ValueError('proposal names unavailable executor capabilities')
        return self.pwq.command('propose', proposal_id, actor='iter', payload={
            'title': 'Build or revise ' + project_id,
            'ask': 'Authorize the stated blueprint and explicitly listed capability effects. Application and managed-runtime activation retain separate exact-candidate approval and external rollback.',
            'work_class': 'build',
            'governance_refs': {'atlas_slices': ['BUILD-LOOP-1', 'APP-FACTORY-1', 'COG-LEARN-1'],
                                'invariants': ['INV-35', 'INV-36', 'INV-37', 'INV-38']},
            'authorization_scope': {'action': 'foundry.build', 'project_id': project_id,
                                    'blueprint_hash': digest(blueprint), 'allowed_actions': sorted(requested)},
        }, command_id='foundry-propose:' + digest([proposal_id, project_id, blueprint]))

    def help(self, section='overview'):
        """Read-only, bounded schema discovery; never a policy/approval receipt.

        Iter's tool descriptions are capped at 500 characters and results at
        5,000. Keep each section below that result boundary instead of silently
        truncating one large schema. Existing executors remain authoritative.
        """
        from .foundry_governor import WORK_FIELDS, MEMORY_USE_FIELDS
        from .foundry_runtime import RUNTIME_ACTION_REGISTRY
        sections = ('overview', 'work', 'actions', 'blueprint', 'memory', 'runtime', 'browser')
        pages = {
            'overview': {
                'operations': {
                    'help': {'optional': ['section'], 'identities': []},
                    'projects': {'identities': []}, 'recall': {'optional': ['query'], 'identities': []},
                    'propose': {'required': ['blueprint', 'proposal_id'], 'optional': ['allowed_actions'], 'identities': ['project_id']},
                    'open': {'identities': ['project_id']},
                    'context': {'optional': ['query'], 'identities': ['project_id', 'work_id']},
                    'submit': {'required': ['work'], 'identities': ['project_id', 'work_id']},
                    'decide': {'identities': ['project_id', 'work_id']},
                    'execute': {'required': ['decision_id'], 'identities': ['project_id', 'work_id']},
                    'status': {'identities': ['project_id', 'work_id']},
                    'recover': {'identities': ['project_id', 'work_id']},
                },
                'workflow': [
                    'Call context(query=intention) before constructing alternatives. Use its repository_context and current project.source_context_hash; inspect its pinned semantic/episodic memory.',
                    'Read the work, blueprint and relevant action help sections. Retain the human intention and acceptance examples in the blueprint.',
                    'Propose the blueprint and bounded allowed_actions; await actual PWQ approval. Submit work with the current authorization_ref.',
                    'Decide, execute the returned decision_id once, then poll status. Recover reconciles interrupted effects; it never blindly repeats an action.',
                    'Native outcomes accept/iterate/escalate/rollback concern the bounded action, not completion of the entire Product Build Contract.',
                    'After app.stage, use existing app_revision_control validate and propose. Exact-candidate split approval and external supervision remain necessary for app.activate.',
                ],
                'boundaries': 'No caller observations, capabilities, signatures, arbitrary shell or success flags. The action catalogue is additive, not a restriction on existing tools or future code categories. Help does not require governor activation; governed planning/dispatch does.',
            },
            'work': {
                'required': sorted(WORK_FIELDS), 'optional': ['memory_uses'],
                'identity': {'project_id': 'Use an app-compatible slug: lowercase letter then lowercase letters/digits/hyphens, at most 63 characters.',
                             'work_id': 'Lowercase letters/digits/underscore/hyphen, starts alphanumeric, at most 64 characters; immutable per submission.',
                             'parent_id': 'Empty string for root; otherwise same-project/same-authorization work ID. A child retains all parent invariants and obligations.',
                             'recovery_ref': 'String, empty when no recovery target is applicable.'},
                'text_fields': ['intention', 'current_state', 'unresolved_gap', 'authorization_ref', 'repository_context', 'change_class'],
                'text_constraint': 'Nonempty text, at most 32000 characters per field. change_class describes the defect/change; repository_context must be copied from context, never invented.',
                'invariants': {'type': 'nonempty unique string list', 'executable_ids': list(SUPPORTED_INVARIANTS),
                               'note': 'Unknown/free-text duties stay unresolved. Human intent and semantic invariants also belong in the blueprint; do not pretend executable checks prove them.'},
                'obligations': 'Unique string list, may be empty; native rules add action-specific and learned proof duties.',
                'authorization_ref': 'pwq:<proposal_id>:<current dispatch_authorization>, obtained only from a threshold-approved current proposal.',
                'alternatives': {'count': 2, 'distinct_strategy_ids': True,
                    'fields': {'strategy': 'letters/digits/_.:- only', 'action': {'type': 'registered action name', 'payload': 'object; see actions/runtime help'},
                               'predicted_outcome': 'nonempty expected postcondition, see action help', 'risks': 'unique string list; may be empty'}},
                'memory_uses': 'Optional verified citations; see memory help. No citation is required for irrelevant memory.',
                'response_note': 'decide returns decision.decision_id; execute returns running/action_id/observation_id. status exposes durable work, decision and observation/evidence when available.',
            },
            'actions': {'payloads': {
                'project.create': {'required': ['blueprint'], 'optional': ['research'], 'postcondition': 'project-created'},
                'project.inspect': {'required': [], 'optional': [], 'postcondition': 'project-inspected'},
                'project.research': {'required': ['research', 'expected_context_hash'], 'optional': [], 'postcondition': 'research-recorded'},
                'project.revise': {'required': ['blueprint', 'expected_context_hash'], 'optional': [], 'postcondition': 'blueprint-revised'},
                'source.write': {'required': ['files', 'expected_context_hash'], 'optional': ['directory', 'deletions'], 'postcondition': 'source-written'},
                'app.stage': {'required': ['expected_context_hash', 'purpose', 'source_pressure'], 'optional': ['artifact_files'], 'postcondition': 'candidate-staged'},
                'test.static': {'required': ['expected_context_hash'], 'optional': ['files'], 'postcondition': 'static-observed'},
                'test.browser': {'required': ['revision_id'], 'optional': ['steps', 'assertions', 'timeout_ms', 'data_expectations'], 'postcondition': 'browser-observed'},
                'app.activate': {'required': ['candidate_id', 'proposal_id', 'dispatch_authorization'], 'optional': [], 'postcondition': 'candidate-promoted'},
                'app.rollback': {'required': ['reason'], 'optional': [], 'postcondition': 'rollback-observed'},
            }, 'field_notes': {
                'expected_context_hash': 'Copy current context.project.source_context_hash; stale writes/staging/tests refuse.',
                'files': 'source.write maps safe relative filenames to UTF-8 content; test.static optionally lists exact src-relative files. Unchecked formats remain unvalidated, not passed.',
                'directory': 'src (default), tests or migrations. Arbitrary source languages may be owned here; renderer staging is a separate artifact boundary.',
                'deletions': 'Existing relative filenames in selected directory; cannot overlap files. Pass files={} for deletions only.',
                'artifact_files': 'Optional map of renderer-bundle output filename to observed src-relative source filename.',
                'app.activate': 'Use separate exact-candidate authorization, not the broad build token. A pointer update is not health; independent supervisor must promote.',
                'test.browser': 'Read browser help; at least one assertion is required by the observer despite optional transport defaults.',
            }, 'runtime_actions': 'See runtime help for the additive managed self-repair adapter.'},
            'blueprint': {
                'required': {'title': 'nonempty string', 'intention': 'nonempty string',
                             'invariants': 'nonempty list of nonempty strings', 'acceptance': 'nonempty list of nonempty strings'},
                'additional_fields': 'Allowed; retain user conversation provenance, data model, constraints and Given/When/Then acceptance examples as useful.',
                'limit': '65536 UTF-8 bytes of canonical JSON.',
                'research': {'type': 'list, at most 100 entries / 262144 canonical UTF-8 bytes',
                             'entry_required': {'url': 'HTTPS source URL', 'retrieved_at': 'nonempty retrieval timestamp', 'license': 'nonempty audited license/usage disposition', 'adopted_pattern': 'nonempty source-to-design notes; explicitly say what was or was not reused'}},
                'scope': 'The approved blueprint hash binds every action. Revising it needs a new matching blueprint approval; a work description cannot silently widen scope.',
                'ownership': 'apps/<project_id>/src, tests and migrations are user-owned code; blueprint/research/manifests are source metadata. App domain records stay in the journaled app contract; data/ is export projection only.',
            },
            'memory': {
                'intake': 'context(query=intention) pins existing semantic and episodic memory before alternatives. Submit and decide return that same captured projection; use a new work ID for fresh intake. recall(query) independently reads current memory.',
                'memory_uses': {'type': 'optional list of objects', 'exact_fields': sorted(MEMORY_USE_FIELDS),
                    'kind': ['semantic', 'episode', 'excerpt'], 'target': ['gap', 'alternative', 'prediction', 'obligation'],
                    'source_ref': 'returned atom_key for semantic/episode, source_path for excerpt',
                    'source_hash': 'returned atom_hash for semantic/episode, source_hash for excerpt',
                    'strategy': 'The corresponding alternative strategy, or empty string for shared gap/obligation.',
                    'rationale': 'Bounded nonempty text explaining actual use; invented/stale citations refuse.'},
                'authority': 'Recalled prose is context, not executable policy, authorization or fabricated evidence. Native ranking/proof strengthening uses uniquely identified observed EngineeringEvidence separately. Memory storage and existing memory tools are preserved.',
            },
            'runtime': {
                'payloads': {name: {'required': list(spec['required']), 'optional': list(spec['optional'])}
                             for name, spec in RUNTIME_ACTION_REGISTRY.items()},
                'postconditions': {'runtime.status': 'runtime-status', 'runtime.stage': 'runtime-staged',
                    'runtime.validate': 'runtime-validated or runtime-validation-failed', 'runtime.propose': 'runtime-awaiting-approval',
                    'runtime.activate': 'runtime-promoted or runtime-rolled-back', 'runtime.rollback': 'runtime-rolled-back or runtime-rollback-noop'},
                'changes': 'Map exact tools/*.py, transformations/*.py or channels/*.py paths to source text (null deletes). No nested files, state relocation or protected-kernel modifications.',
                'contract_required': ['module_id', 'version', 'purpose', 'source_pressure', 'atlas_slice', 'allowed_writes', 'allowed_effects', 'tests', 'rollback_target', 'provenance'],
                'contract_notes': 'allowed_writes exactly matches changes; allowed_effects is [] or [managed-component-runtime]; tests are python_compile/component_contract; rollback_target is exact active generation. Service replaces provenance with actual work/action attribution.',
                'activation': 'Requires validated candidate, exact current split-role PWQ approval, live healthy parent heartbeat, independent Electron supervision. Do not activate while parent is stopped/erroring. Existing self_improve/revision_control remain available.',
            },
            'browser': {
                'revision_id': 'Exact apprev- plus 64 hexadecimal characters; must match the observed active application revision.',
                'steps': {'max': 30, 'shapes': [{'kind': 'click', 'selector': 'CSS selector'}, {'kind': 'fill', 'selector': 'input/textarea/select selector', 'value': 'string <=8192 characters'}]},
                'assertions': {'min': 1, 'max': 30, 'shape': {'kind': 'text|value|count|visible', 'selector': 'nonempty CSS selector <=512 characters', 'expected': 'string for text/value, nonnegative integer for count, boolean for visible'},
                               'comparison': 'Exact equality, not substring. Page must also expose document.body.dataset.iterReady === true.'},
                'timeout_ms': 'Observer clamps to 100..10000 ms; asynchronous interactions have bounded settling, not arbitrary scripting.',
                'data_expectations': {'type': 'optional list', 'exact_fields': ['collection', 'record_id', 'before', 'after'],
                                     'before_after': 'Exact full record objects with matching id; null means absent, never wildcard. Observe intended changes and preserve every other record.'},
                'boundary': 'Service independently observes DOM and app records. Test instructions are not success evidence or authorization; data expectations do not implement automatic domain-data rollback.',
            },
        }
        if section not in pages:
            raise ValueError('unknown help section; choose ' + ', '.join(sections))
        return {'schema_version': 1, 'section': section, 'sections': list(sections),
                'read_only': True, 'content': pages[section]}

    def request(self, params):
        operation = params.get('operation', 'projects')
        with self.lock:
            if operation == 'help':
                return self.help(params.get('section', 'overview'))
            if operation == 'projects':
                return self.projects.list_projects()
            if operation == 'recall':
                return self.memory.query(self.space.store.state_copy(), params.get('query', ''))
            project_id = identity(params.get('project_id'))
            if operation == 'propose':
                return self.propose(project_id, params['blueprint'], params['proposal_id'], params.get('allowed_actions'))
            if operation == 'open':
                return self.browser_call('openApp', appId=project_id)
            work_id = identity(params.get('work_id'))
            if operation == 'context':
                access = self._access(project_id, work_id)
                context = self._refresh_context(project_id, work_id, access)
                # Present the exact memory intake BEFORE Iter constructs its
                # alternatives. Later work observes fresh memory; this work
                # retains a reproducible slice, not a drifting context cache.
                memory = self._capture_memory(work_id, params.get('query', ''), origin='context')
                return {'project': context, 'snapshot_set': self.fabric.snapshot_set(
                    self.fabric.snapshot(sorted(access.reads), access)),
                    'action_types': sorted(self.action_types), 'observations_are_service_owned': True,
                    'repository_context': digest(['foundry-v1', project_id]),
                    'supported_invariants': list(SUPPORTED_INVARIANTS),
                    'memory': memory}
            if operation == 'submit':
                work = params['work']
                if work.get('project_id') != project_id or work.get('work_id') != work_id:
                    raise ValueError('work identity differs from requested project/work')
                if work.get('repository_context') != digest(['foundry-v1', project_id]):
                    raise ValueError('repository_context must be the service-provided identity; prior evidence cannot be renamed away')
                governor, access = self._governor(work)
                self._refresh_context(project_id, work_id, access)
                memory = self._capture_memory(work_id, work['intention'])
                return {**governor.submit(work), 'memory': memory}
            # Stored work, not the new request, determines parent scope.
            governor, access = self._governor({'project_id': project_id, 'work_id': work_id})
            state = governor.status(work_id)
            work = state['work']
            if work['project_id'] != project_id:
                raise PermissionError('work belongs to another project')
            governor, access = self._governor(work)
            if operation == 'decide':
                self._refresh_context(project_id, work_id, access)
                return {**governor.decide(work_id), 'memory': self._work_memory(work_id)}
            if operation == 'status':
                return governor.status(work_id)
            if operation == 'recover':
                if work_id in self.running:
                    return {'running': True, 'work_id': work_id}
                return governor.reconcile(work_id)
            if operation == 'execute':
                if work_id in self.running:
                    return {'running': True, 'work_id': work_id}
                self._refresh_context(project_id, work_id, access)
                claim = governor.claim(work_id, params['decision_id'])
                thread = threading.Thread(target=self._execute, args=(governor, work, claim, access), daemon=True)
                self.running[work_id] = thread
                thread.start()
                return {'running': True, 'work_id': work_id, 'action_id': claim['action_id'],
                        'observation_id': claim['observation_id']}
            raise ValueError('unknown foundry operation')

    def _execute(self, governor, work, claim, access):
        from .foundry_observation import compare_app_data
        work_id = work['work_id']
        try:
            try:
                before = self._domain_data(work['project_id'])
                expected_effects = (claim['action']['payload'].get('data_expectations')
                    if claim['action']['type'] == 'test.browser' else None)
                # Validate expectation schema and exact preconditions BEFORE
                # sending browser interactions. None is absence, not wildcard.
                checked = compare_app_data(before, before, expected_effects)
                for expected in checked['expected_effects']:
                    current = next((row for row in before.get(expected['collection'], [])
                                    if row['id'] == expected['record_id']), None)
                    if current != expected['before']:
                        raise ValueError('browser data expectation has a stale precondition')
                self._authorize(work, {'action': claim['action']}, claim['evaluated_snapshot'])
                facts = self._perform(work, claim)
                after = self._domain_data(work['project_id'])
                data_observation = compare_app_data(before, after, expected_effects)
                self._project_context(work['project_id'])  # Includes path/symlink/manifest integrity.
                facts.setdefault('proofs', {}).update({
                    'source-boundary': 'passed',
                    **data_observation['proofs']})
                facts['data_observation'] = data_observation
                try:
                    self._authorize(work, {'action': claim['action']}, claim['evaluated_snapshot'])
                    facts['proofs']['authorization-current'] = 'passed'
                except PermissionError:
                    facts['proofs']['authorization-current'] = 'failed'
            except Exception as exc:
                facts = {'process_state': 'exited', 'exit_code': 1, 'postcondition': 'action-error',
                         'proofs': {}, 'detail': '%s: %s' % (type(exc).__name__, exc)}
            for proof in claim['required_proofs']:
                if proof not in ('process-exit', 'prediction-match'):
                    facts.setdefault('proofs', {}).setdefault(proof, 'unknown')
            snapshot = self.space.store.state_copy()
            observation = {**facts, 'observation_id': claim['observation_id'],
                'work_id': work_id, 'action_id': claim['action_id'],
                'authorization_ref': work['authorization_ref'],
                'snapshot': {k: snapshot[k] for k in ('epoch', 'commit', 'state_hash')}}
            self._put('scratch/' + work_id, 'raw-observation:' + claim['observation_id'],
                      'FoundryObservationV1', observation, access, 'observation:' + claim['action_id'], immutable=True)
            governor.observe(work_id, claim['observation_id'])
        finally:
            with self.lock:
                self.running.pop(work_id, None)

    def _domain_data(self, project_id):
        from .app_contract import read_context
        def call(method, **params):
            state = self.space.store.state_copy()
            if method == 'status':
                return {k: state[k] for k in ('epoch', 'commit', 'state_hash')}
            if method == 'subscribe':
                return {'events': self.space.store.events_after(params.get('after_commit', 0), params.get('limit', 1000)),
                        'current_commit': state['commit'], 'epoch': state['epoch']}
            raise ValueError('memory/data observer is read-only')
        return read_context(project_id, call_fn=call)['records']

    def _perform(self, work, claim):
        kind = claim['action']['type']
        data = claim['action'].get('payload') or {}
        project = work['project_id']
        provenance = {'actor': 'iter', 'work_id': work['work_id'], 'action_id': claim['action_id'],
                      'authorization_ref': work['authorization_ref']}
        if kind.startswith('runtime.'):
            before = self.runtime.manager.status()['active']
            result = self.runtime.execute(kind, data, provenance)
            if kind == 'runtime.activate':
                candidate = self.runtime.manager._read_candidate(data['candidate_id'])
                return self._await_runtime_supervision(candidate)
            facts = {'process_state': 'exited', 'exit_code': 0,
                     'postcondition': result['postcondition'], 'proofs': result['proofs'], 'result': result}
            if kind == 'runtime.rollback':
                restored = self.runtime.manager.status()['active']
                exact = restored['generation_id'] == before.get('previous_generation_id')
                facts['proofs']['recovery-exact'] = 'passed' if exact else 'unknown'
            return facts
        allowed = {
            'project.create': {'blueprint', 'research'},
            'project.inspect': set(),
            'project.research': {'research', 'expected_context_hash'},
            'project.revise': {'blueprint', 'expected_context_hash'},
            'source.write': {'files', 'expected_context_hash', 'directory', 'deletions'},
            'app.stage': {'expected_context_hash', 'purpose', 'source_pressure', 'artifact_files'},
            'test.static': {'expected_context_hash', 'files'},
            'test.browser': {'revision_id', 'steps', 'assertions', 'timeout_ms', 'data_expectations'},
            'app.activate': {'candidate_id', 'proposal_id', 'dispatch_authorization'},
            'app.rollback': {'reason'},
        }
        if kind not in allowed or not isinstance(data, dict) or set(data) - allowed[kind]:
            raise ValueError('action payload exceeds the fixed executor schema')
        if kind == 'project.create':
            result = self.projects.create(project, data['blueprint'], research=data.get('research', []), provenance=provenance)
            postcondition = 'project-created'
        elif kind == 'project.inspect':
            result, postcondition = self.projects.inspect(project), 'project-inspected'
        elif kind == 'project.research':
            result = self.projects.record_research(project, data['research'], data['expected_context_hash'], provenance=provenance)
            postcondition = 'research-recorded'
        elif kind == 'project.revise':
            result = self.projects.revise_blueprint(project, data['blueprint'], data['expected_context_hash'], provenance=provenance)
            postcondition = 'blueprint-revised'
        elif kind == 'source.write':
            result = self.projects.write_source(project, data['files'], data['expected_context_hash'],
                directory=data.get('directory', 'src'), deletions=data.get('deletions'), provenance=provenance)
            postcondition = 'source-written'
        elif kind == 'app.stage':
            result = self.projects.stage(project, data['expected_context_hash'], data['purpose'],
                                         data['source_pressure'], provenance=provenance,
                                         artifact_files=data.get('artifact_files'))
            postcondition = 'candidate-staged'
        elif kind == 'test.static':
            return self._static(project, data['expected_context_hash'], data.get('files'))
        elif kind == 'test.browser':
            result = self.browser_call('inspectApp', appId=project, revisionId=data['revision_id'],
                steps=data.get('steps', []), assertions=data.get('assertions', []),
                timeoutMs=data.get('timeout_ms', 10000))
            # Raw individual matches only. Native rules own their semantic use.
            return {'process_state': 'exited', 'exit_code': 0, 'postcondition': 'browser-observed',
                    'proofs': {'browser-workflow': result.get('proofs', {}).get('browser-workflow', 'unknown')}, 'result': result}
        elif kind == 'app.activate':
            candidate = self.projects.revisions._read_candidate(data['candidate_id'])
            if candidate['app_id'] != project:
                raise PermissionError('candidate belongs to another project')
            result = self.projects.revisions.activate(data['candidate_id'], data['proposal_id'], data['dispatch_authorization'])
            self.browser_call('openApp', appId=project)
            return self._await_app_supervision(project, candidate)
        else:
            previous = self.projects.revisions.status(project)
            result = self.projects.revisions.rollback_probation(project, data['reason'])
            postcondition = 'rollback-observed'
            restored = self.projects.revisions.status(project)
            exact = restored['revision_id'] == previous['active'].get('previous_revision_id')
            return {'process_state': 'exited', 'exit_code': 0, 'postcondition': postcondition,
                    'proofs': {'recovery-exact': 'passed' if exact else 'unknown'}, 'result': result}
        return {'process_state': 'exited', 'exit_code': 0, 'postcondition': postcondition,
                'proofs': {}, 'result': result}

    def _await_app_supervision(self, project, candidate):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            status = self.projects.revisions.status(project)
            if status['active'].get('status') == 'stable':
                promoted = status['revision_id'] == candidate['revision_id']
                return {'process_state': 'exited', 'exit_code': 0 if promoted else 1,
                    'postcondition': 'candidate-promoted' if promoted else 'candidate-rolled-back',
                    'proofs': {'activation-health': 'passed' if promoted else 'failed',
                              'recovery-exact': 'passed' if status['revision_id'] == candidate['parent_revision_id'] else 'unknown'},
                    'result': status}
            threading.Event().wait(0.5)
        return {'process_state': 'timed_out', 'exit_code': -1, 'postcondition': 'supervisor-pending',
                'proofs': {'activation-health': 'unknown'}, 'result': self.projects.revisions.status(project)}

    def _await_runtime_supervision(self, candidate):
        # Only the already existing independent supervisor can promote/restore.
        deadline = time.monotonic() + float(candidate.get('heartbeat_timeout') or 720) + 10
        while time.monotonic() < deadline:
            status = self.runtime.manager.status()
            active = status['active']
            if active['status'] == 'stable':
                promoted = active['generation_id'] == candidate['generation_id']
                return {'process_state': 'exited', 'exit_code': 0 if promoted else 1,
                    'postcondition': 'runtime-promoted' if promoted else 'runtime-rolled-back',
                    'proofs': {'activation-health': 'passed' if promoted else 'failed',
                        'recovery-exact': 'passed' if active['generation_id'] == candidate['parent_generation_id'] else 'unknown'},
                    'result': status}
            threading.Event().wait(0.5)
        return {'process_state': 'timed_out', 'exit_code': -1, 'postcondition': 'runtime-supervisor-pending',
                'proofs': {'activation-health': 'unknown'}, 'result': self.runtime.manager.status()}

    def _static(self, project, expected, files=None):
        from .foundry_observation import observe_static
        context = self.projects.inspect(project)
        if context['source_context_hash'] != expected:
            raise RuntimeError('source context changed before static observation')
        root = self.root / 'apps' / project / 'src'
        results = observe_static(root, files=files)
        if self.projects.inspect(project)['source_context_hash'] != expected:
            raise RuntimeError('source changed during static observation')
        return {'process_state': 'exited', 'exit_code': results['exit_code'], 'postcondition': 'static-observed',
                'proofs': results['proofs'], 'result': results}
