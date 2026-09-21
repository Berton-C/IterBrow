#!/usr/bin/env python3
"""pwq_write.py — the ONE canonical writer for .runtime/pwq.json (proposal A, user-approved 2026-09-20 20:10).
FAIL-CLOSED KB GATE (proposal B): parses (card-invariant <name> <check>) atoms from kb_substrate.metta
Layer 7 and enforces every one against the payload BEFORE writing. KB missing/unreadable/no Layer-7
atoms => REFUSAL. Unknown check name in KB => REFUSAL. The KB content drives enforcement; this is
not advisory. Lesson retrieval (proposal C): PWQ lessons from chroma_db/memories.json printed on
every successful write so the operator sees violated-lesson context at the moment of action.
Audit: every attempt appended to .runtime/pwq_audit.log. Atomic write via tmp+os.replace. Reread
after mutation (invariant no_reread_after_mutation). No other writer may touch pwq.json."""
import json, hashlib, re, sys, time, os

KB = 'kb_substrate.metta'; PWQ = '.runtime/pwq.json'; AUDIT = '.runtime/pwq_audit.log'

DESCRIPTION = "The ONE canonical gated writer for .runtime/pwq.json (user-approved 2026-09-20 20:10, proposals A-C). FAIL-CLOSED: parses (card-invariant <name> <check>) atoms from kb_substrate.metta Layer 7 and enforces every one against the payload BEFORE writing; KB missing/unreadable/no-atoms/unknown-check => REFUSAL. Params: payload (dict or path to payload json), caller (string, default pwq_write.py). Audit log: .runtime/pwq_audit.log. Every PWQ data mutation must go through this tool."
KNOWN_STATUS = ('waiting', 'orders given', 'done', 'negotiating')

def load_kb():
    txt = open(KB).read()  # unreadable => exception => no write (fail-closed)
    atoms = re.findall(r'\(card-invariant\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)', '\n'.join(l for l in txt.splitlines() if not l.strip().startswith(';')))
    if not atoms:
        raise RuntimeError('KB Layer 7 missing: fail-closed REFUSAL')
    return dict(atoms)

CHECKS = {
 'options_are_objects': lambda i: all(isinstance(o, dict) and isinstance(o.get('label'), str)
                                      and isinstance(o.get('desc'), str) for o in (i.get('options') or [])),
 'negotiation_log_is_list': lambda i: isinstance(i.get('negotiation_log'), list),
 'status_is_known': lambda i: i.get('status') in KNOWN_STATUS,
 'id_is_nonempty_string': lambda i: isinstance(i.get('id'), str) and len(i.get('id')) > 0,
 'write_goes_through_pwq_write': lambda i: True,  # caller identity checked separately below
}

def lessons():
    """Proposal C: content-based retrieval of PWQ lessons (not timestamp-based) from the
    chroma dump {ids, documents, metadatas}. Advisory (non-blocking) but MUST show real
    lessons on every successful write. Matches on PWQ + (file:// bridge | lesson | invariant)."""
    try:
        m = json.load(open('chroma_db/memories.json'))
        ids = m.get('ids', []); docs = m.get('documents', [])
        hits = []
        for mid, doc in zip(ids, docs):
            d = doc if isinstance(doc, str) else str(doc)
            if 'PWQ' in d and ('file://' in d or 'lesson' in d.lower() or 'invariant' in d.lower() or 'pwq_write' in d.lower()):
                hits.append(f'[{mid[:8]}] {d[:220]}')
        return hits[:4] or ['(no PWQ lesson items matched)']
    except Exception as e:
        return ['lessons retrieval failed (advisory, non-blocking): %s' % e]

def gate(payload, kb, caller):
    violations = []
    for inv, check in kb.items():
        if check not in CHECKS:
            return [f'UNKNOWN CHECK {inv}->{check}: KB changed but writer not updated (fail-closed REFUSAL)']
        for i in payload.get('items', []):
            if not CHECKS[check](i):
                violations.append(f'{i.get("id", "?")} violated {inv} ({check})')
    if caller != 'pwq_write.py':
        violations.append(f'write_goes_through_pwq_write: REFUSED, caller={caller}')
    return violations

def write(payload, caller='pwq_write.py'):
    kb = load_kb()
    v = gate(payload, kb, caller)
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    if v:
        with open(AUDIT, 'a') as f: f.write(f'[{ts}] REFUSED caller={caller} violations={v}\n')
        print('REFUSED:', v); sys.exit(2)
    cur = json.load(open(PWQ)); cur.update(payload)
    tmp = PWQ + '.tmp'
    with open(tmp, 'w') as f: json.dump(cur, f, indent=1)
    os.replace(tmp, PWQ)
    ok = json.load(open(PWQ))
    assert ok == cur, 'reread mismatch after write'
    for L in lessons(): print('LESSON:', L)
    with open(AUDIT, 'a') as f:
        f.write(f'[{ts}] WROTE caller={caller} items={len(cur["items"])} '
                f'sha={hashlib.sha256(json.dumps(cur, sort_keys=True).encode()).hexdigest()[:12]}\n')
    print('WROTE ok, items:', len(cur['items']))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: pwq_write.py <payload.json> [caller]'); sys.exit(1)
    p = json.load(open(sys.argv[1]))
    write(p, sys.argv[2] if len(sys.argv) > 2 else 'pwq_write.py')


def run(**kwargs):
    """Bridge-tool interface so the canonical gated writer is also callable as the
    pwq_write tool. Delegates to write(); the fail-closed KB gate applies identically.
    Accepts the bridge's single-kwargs-string convention: run(kwargs='{"payload": ...}')
    as well as direct kwargs. payload may be a dict or a path string to payload json."""
    if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], str):
        try:
            kwargs = json.loads(kwargs['kwargs'])
        except ValueError as e:
            return 'REFUSED: kwargs is not valid JSON: %s' % e
    action = kwargs.get('action', 'write')
    if action not in ('write', None):
        return 'REFUSED: pwq_write.run only implements action="write" (canonical gated writer), got action=%r' % action
    p = kwargs.get('payload')
    if isinstance(p, str):
        p = json.load(open(p))
    if not isinstance(p, dict):
        return 'REFUSED: payload must be dict or path to payload json'
    caller = kwargs.get('caller', 'pwq_write.py')
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            write(p, caller)
        return buf.getvalue().strip()
    except SystemExit as e:
        return 'GATE REFUSED (exit %s)' % e.code
