#!/usr/bin/env python3
"""
backlog_meter.py - measure chroma->atom sync backlog (pass-89 protocol).
Proper paren scanner, NOT regex stv-stripping.
Root cause fixed (from pass 88): raw lines are ( STMT (stv f c) ) - cutting
the stv chunk with regex leaves an unbalanced string missing the wrapper's
closing paren. Correct approach: tokenize into top-level children with a
paren scanner; statement = child[0] with stv children dropped.
Usage: python3 tools/scratch/backlog_meter.py
"""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def top_level_children(s):
    s = s.strip()
    children = []
    i = 0
    while i < len(s):
        if s[i] == '(':
            depth = 0; j = i
            while j < len(s):
                if s[j] == '(': depth += 1
                elif s[j] == ')':
                    depth -= 1
                    if depth == 0: break
                j += 1
            if depth != 0:
                children.append(s[i:]); return children
            children.append(s[i:j+1]); i = j + 1
        elif s[i].isspace(): i += 1
        else:
            j = i
            while j < len(s) and not s[j].isspace(): j += 1
            children.append(s[i:j]); i = j
    return children

def extract_statement(line):
    line = line.strip()
    if not line or line.startswith(';'): return None
    kids = top_level_children(line)
    if not kids: return None
    if len(kids) == 1:
        inner = top_level_children(kids[0][1:-1]) if kids[0].startswith('(') else [kids[0]]
        inner = [k for k in inner if not re.match(r'^\(stv\b', k)]
        if not inner: return None
        stmt = ' '.join(inner)
        if len(inner) == 1 and inner[0].startswith('('):
            sub = top_level_children(inner[0][1:-1])
            sub = [k for k in sub if not re.match(r'^\(stv\b', k)]
            if len(sub) == 1 and sub[0].startswith('('):
                stmt = sub[0]
        return re.sub(r'\s+', ' ', stmt).strip()
    kids2 = [k for k in kids if not re.match(r'^\(stv\b', k)]
    if not kids2: return None
    return re.sub(r'\s+', ' ', ' '.join(kids2)).strip()

def measure():
    c = json.load(open(os.path.join(ROOT, 'chroma_db/memories.json')))
    ids = c['ids']; metas = c['metadatas']
    chroma_formals = {}
    for i in range(len(ids)):
        f = metas[i].get('formalization') or metas[i].get('metta') or ''
        if f:
            chroma_formals[re.sub(r'\s+', ' ', f).strip()] = ids[i][:8]
    sp = open(os.path.join(ROOT, 'transformations/.runtime/space.metta')).read()
    space_formals = set()
    for raw in sp.splitlines():
        stmt = extract_statement(raw)
        if stmt: space_formals.add(stmt)
    missing = {k: v for k, v in chroma_formals.items() if k not in space_formals}
    return len(chroma_formals), len(space_formals), missing

if __name__ == '__main__':
    total, synced, missing = measure()
    print(f'chroma formalizations: {total}')
    print(f'atom statements: {synced}')
    print(f'BACKLOG (exact statement match): {len(missing)}/{total} = {100*len(missing)/total:.0f}%')
    for stmt, mid in sorted(missing.items(), key=lambda kv: kv[1]):
        print(f'  {mid}  {stmt[:100]}')
