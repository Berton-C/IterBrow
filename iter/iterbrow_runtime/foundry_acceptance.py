"""External Contract-v2 evidence binding; never candidate self-certification.

The host pins contract bytes and authenticates demonstration/evidence records
through read-only callbacks. This verifier checks identity, coverage and origin.
It does not infer product meaning from prose, generate observations, grant PWQ
authority or replace native reasoning. Semantic/human judgments remain explicit
authenticated assessment receipts; missing assessments remain unresolved.
"""
import hashlib
import json
import re

from .cognitive_fabric import digest


CONTRACT_ID = 'software-foundry-magic-v2'
CLAUSES = frozenset('BC-%02d' % n for n in range(1, 14))
FIRST = frozenset('BC-%02d' % n for n in (*range(1, 9), 11, 12, 13))
HASH = re.compile(r'^[0-9a-f]{64}$')
BINDINGS = ('demo_id', 'project_id', 'contract_hash', 'intention_hash', 'blueprint_hash',
            'baseline_source_hash', 'source_revision_hash', 'factory_contract_hash')
HASH_BINDINGS = frozenset(BINDINGS) - {'demo_id', 'project_id'}
HUMAN_ASSESSMENTS = frozenset({'primary_user_workflow', 'material_user_requested_change',
                             'second_materially_different_app'})
AUTHORSHIP = frozenset({'iter_tool_call_provenance', 'feature_source_diff',
                       'no_codex_feature_repairs', 'iter_authorship'})
RECEIPT_FIELDS = frozenset({'evidence_id', 'kind', 'producer_id', 'qualification', 'context',
                          'result', 'run_kind', 'details', 'artifact_hash'})


class AcceptanceError(ValueError):
    pass


def _identity(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise AcceptanceError(field + ' must be a bounded identity')
    return value


class ProductContractVerifier:
    def __init__(self, contract_bytes, expected_contract_sha256, *, demo_reader,
                 evidence_reader, producer_registry):
        """Callbacks/registry are trusted host dependencies, never RPC fields.

        demo_reader(id) returns the authority-pinned demonstration identities,
        run_kind, request_owner and domain_cognition declaration. evidence_reader
        returns authenticated immutable receipts or None—not candidate JSON.
        Registry values contain role observer|human_assessor|authorship_auditor
        and independent_of_candidate=True. Authentication belongs to the reader.
        """
        if not isinstance(contract_bytes, bytes) or not HASH.fullmatch(str(expected_contract_sha256)):
            raise AcceptanceError('pinned contract bytes and SHA-256 are required')
        if hashlib.sha256(contract_bytes).hexdigest() != expected_contract_sha256:
            raise AcceptanceError('contract differs from the externally pinned hash')
        contract = json.loads(contract_bytes)
        if contract.get('schema_version') != 2 or contract.get('contract_id') != CONTRACT_ID:
            raise AcceptanceError('unsupported product contract schema or identity')
        clauses = contract.get('clauses', [])
        if not isinstance(clauses, list) or len(clauses) != len(CLAUSES) or {c.get('id') for c in clauses} != CLAUSES:
            raise AcceptanceError('Contract v2 must retain all thirteen clauses')
        first = contract.get('first_demo', {})
        if (set(first.get('required_clauses', [])) != FIRST
                or first.get('conditional_clauses') != {'BC-09': 'requested application domain cognition'}
                or first.get('generality_required_before_platform_completion') != 'BC-10'
                or first.get('app_request_owner') != 'human_at_runtime'
                or first.get('codex_feature_authorship_forbidden') is not True):
            raise AcceptanceError('Contract v2 demonstration boundary changed')
        for clause in clauses:
            requirements = clause.get('evidence')
            if not isinstance(requirements, list) or not requirements or len(set(requirements)) != len(requirements):
                raise AcceptanceError('invalid clause evidence schema')
            for kind in requirements:
                _identity(kind, 'evidence kind')
        policy = contract.get('change_policy', {})
        if policy.get('human_approval_required_for_meaning_change') is not True or policy.get('candidate_may_not_edit_contract_or_verifier') is not True:
            raise AcceptanceError('contract/verifier ownership cannot be weakened')
        self.contract, self.contract_hash = contract, expected_contract_sha256
        self.clauses = {c['id']: c for c in clauses}
        self.demo_reader, self.evidence_reader = demo_reader, evidence_reader
        self.producers = dict(producer_registry)

    def _demo(self, demo_id):
        _identity(demo_id, 'demo_id')
        demo = self.demo_reader(demo_id)
        if not isinstance(demo, dict) or demo.get('demo_id') != demo_id:
            raise AcceptanceError('demonstration has no authenticated authority binding')
        for field in BINDINGS:
            _identity(demo.get(field), field)
            if field in HASH_BINDINGS and not HASH.fullmatch(demo[field]):
                raise AcceptanceError('invalid demonstration hash: ' + field)
        if demo['contract_hash'] != self.contract_hash or type(demo.get('domain_cognition')) is not bool:
            raise AcceptanceError('demonstration contract or cognition declaration is unbound')
        return demo

    def _receipt(self, reference, kind, demo):
        _identity(reference, 'evidence reference')
        receipt = self.evidence_reader(reference)
        if receipt is None:
            return 'unresolved', 'authenticated evidence has not arrived', None
        if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
            return 'invalid', 'receipt schema is invalid; candidate pass flags are not evidence', None
        if receipt['evidence_id'] != reference or receipt['kind'] != kind:
            return 'invalid', 'evidence identity or assertion kind differs', None
        producer = self.producers.get(receipt['producer_id'])
        if (not isinstance(producer, dict) or producer.get('independent_of_candidate') is not True
                or producer.get('role') not in {'observer', 'human_assessor', 'authorship_auditor'}):
            return 'invalid', 'producer is not a registered independent observer', None
        if not isinstance(receipt['context'], dict) or any(receipt['context'].get(k) != demo[k] for k in BINDINGS):
            return 'invalid', 'evidence belongs to a different intention, project, revision or contract', None
        if receipt['run_kind'] != 'live-build':
            return 'unresolved', 'component tests and simulations cannot complete a live demonstration', None
        if receipt['qualification'] == 'declaration':
            return 'unresolved', 'a declaration is not an independent observation or assessment', None
        if receipt['qualification'] not in {'observation', 'assessment'}:
            return 'invalid', 'unrecognized evidence qualification', None
        if kind in HUMAN_ASSESSMENTS and (producer['role'] != 'human_assessor' or receipt['qualification'] != 'assessment'):
            return 'unresolved', 'the required human assessment has not been supplied', None
        details = receipt['details']
        if not isinstance(details, dict) or receipt['artifact_hash'] != digest(details):
            return 'invalid', 'evidence artifact identity is inconsistent', None
        if receipt['result'] not in {'supported', 'contradicted', 'unresolved'}:
            return 'invalid', 'unrecognized independent evidence result', None
        if receipt['result'] != 'supported':
            return ('contradicted' if receipt['result'] == 'contradicted' else 'unresolved'), 'independent result is ' + receipt['result'], receipt
        if kind == 'versioned_intention_and_examples':
            blueprint = details.get('blueprint')
            required = {'version', 'intention', 'examples', 'data_ownership', 'domain_cognition',
                        'non_goals', 'completion_conditions'}
            if not isinstance(blueprint, dict) or not required.issubset(blueprint):
                return 'unresolved', 'the externally observed blueprint lacks the complete declared schema', None
            if (not isinstance(blueprint['version'], (str, int)) or isinstance(blueprint['version'], bool)
                    or not isinstance(blueprint['intention'], str) or not blueprint['intention'].strip()
                    or not isinstance(blueprint['data_ownership'], str) or not blueprint['data_ownership'].strip()
                    or type(blueprint['domain_cognition']) is not bool
                    or not isinstance(blueprint['non_goals'], list)
                    or any(not isinstance(blueprint[k], list) or not blueprint[k] for k in ('examples', 'completion_conditions'))):
                return 'unresolved', 'the externally observed blueprint schema is incomplete', None
            if (digest(blueprint) != demo['blueprint_hash'] or digest(blueprint['intention']) != demo['intention_hash']
                    or blueprint['domain_cognition'] != demo['domain_cognition']):
                return 'invalid', 'blueprint, intention or cognition declaration differs from authority binding', None
        if kind in AUTHORSHIP:
            if producer['role'] != 'authorship_auditor' or receipt['qualification'] != 'observation':
                return 'unresolved', 'independent feature authorship audit is missing', None
            events = details.get('feature_changes')
            if details.get('coverage') != 'complete-build-and-revision' or not isinstance(events, list) or not events:
                return 'unresolved', 'feature diff and full build/revision authorship coverage are required', None
            for event in events:
                if not isinstance(event, dict) or event.get('actor') != 'iter':
                    return 'contradicted', 'feature code includes non-Iter authorship', receipt
                if any(not isinstance(event.get(k), str) or not event[k] for k in ('path', 'tool_call_id', 'event_id')) or not HASH.fullmatch(str(event.get('content_hash'))):
                    return 'invalid', 'feature change lacks source/tool-call identity', None
            if len({event['event_id'] for event in events}) != len(events):
                return 'invalid', 'authorship audit repeats event identities', None
        return 'supported', 'authenticated independent evidence bound to the exact demonstration', receipt

    def verify(self, demo_id, clause_refs, *, mode='first_demo', second_demo=None):
        """Read-only report. References map clause -> required evidence kind -> id.

        For platform completion second_demo is {demo_id, clause_refs}; its full
        first-demo surface is verified recursively. BC-10 additionally requires
        a human assessment of material category difference and observer receipts
        that name that second demonstration. No receipt or report grants consent.
        """
        if mode not in {'first_demo', 'platform'}:
            raise AcceptanceError('unknown completion boundary')
        if not isinstance(clause_refs, dict) or set(clause_refs) - CLAUSES:
            raise AcceptanceError('only known clause evidence references are accepted')
        demo = self._demo(demo_id)
        required = set(FIRST)
        if demo['domain_cognition']:
            required.add('BC-09')
        if mode == 'platform':
            required.add('BC-10')
        report = {'contract_id': CONTRACT_ID, 'contract_hash': self.contract_hash, 'demo_id': demo_id,
            'mode': mode, 'required_clauses': sorted(required), 'clauses': {},
            'completion': 'unresolved', 'dispatch_authority': False}
        for cid in sorted(CLAUSES):
            if cid not in required:
                report['clauses'][cid] = {'status': 'not_applicable' if cid == 'BC-09' else 'not_required_for_first_demo'}
                continue
            references = clause_refs.get(cid, {})
            requirements = self.clauses[cid]['evidence']
            if not isinstance(references, dict) or set(references) - set(requirements):
                raise AcceptanceError('clause contains unknown evidence kinds: ' + cid)
            findings = {}
            for kind in requirements:
                if kind not in references:
                    findings[kind] = {'status': 'unresolved', 'reason': 'required evidence reference is missing'}
                    continue
                status, reason, _ = self._receipt(references[kind], kind, demo)
                findings[kind] = {'status': status, 'reason': reason, 'evidence_id': references[kind]}
            statuses = {f['status'] for f in findings.values()}
            status = 'invalid' if 'invalid' in statuses else ('contradicted' if 'contradicted' in statuses else (
                'unresolved' if 'unresolved' in statuses else 'supported'))
            report['clauses'][cid] = {'status': status, 'evidence': findings}
        if (demo.get('run_kind') != 'live-build' or demo.get('request_owner') != 'human_at_runtime'
                or demo.get('request_preparation') != 'unprepared'):
            report['demonstration_origin'] = 'unresolved: an unprepared human-runtime request and live build are required'
        else:
            report['demonstration_origin'] = 'bound'
        if mode == 'platform':
            self._verify_second(report, demo, clause_refs.get('BC-10', {}), second_demo)
        required_states = {report['clauses'][cid]['status'] for cid in required}
        if 'invalid' in required_states:
            report['completion'] = 'invalid'
        elif 'contradicted' in required_states:
            report['completion'] = 'contradicted'
        elif required_states == {'supported'} and report['demonstration_origin'] == 'bound':
            report['completion'] = 'supported'
        report['report_hash'] = digest(report)
        return report

    def _verify_second(self, report, first, references, second_demo):
        clause = report['clauses']['BC-10']
        if clause['status'] in {'invalid', 'contradicted'}:
            return
        if not isinstance(second_demo, dict) or set(second_demo) != {'demo_id', 'clause_refs'}:
            clause.update(status='unresolved', generality_reason='second complete demonstration is missing')
            return
        second = self._demo(second_demo['demo_id'])
        if second['demo_id'] == first['demo_id'] or second['project_id'] == first['project_id']:
            clause.update(status='contradicted', generality_reason='generality requires a distinct app demonstration')
            return
        if second['factory_contract_hash'] != first['factory_contract_hash']:
            clause.update(status='contradicted', generality_reason='factory interfaces changed between demonstrations')
            return
        child = self.verify(second['demo_id'], second_demo['clause_refs'], mode='first_demo')
        report['second_demo'] = child
        for kind, reference in references.items():
            status, _, receipt = self._receipt(reference, kind, first)
            if status == 'supported' and receipt['details'].get('related_demo_id') != second['demo_id']:
                clause.update(status='invalid', generality_reason='generality evidence names another demonstration')
                return
        if child['completion'] != 'supported':
            clause.update(status='unresolved', generality_reason='second app has not satisfied the complete first-demo surface')
