import re, json

atoms = {}
edges = []
details = {}

def clean(s):
    return s.strip('()').strip()

def add_atom(name, atype="atom"):
    name = clean(name)
    if not name:
        return None
    if name not in atoms:
        atoms[name] = {"label": name, "type": atype}
    return name

for fname in ["space.metta", "nace_beliefs.metta"]:
    with open(fname, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            core = re.sub(r'<\s*stv[^>]*>', '', line).strip()
            # nace belief lines: (cap-efficacy tool (stv f c)) etc.
            m = re.search(r'^\((\w[\w-]*)-efficacy\s+(\S+)\s*\(stv\s+([\d.]+)\s+([\d.]+)\)\)?$', line)
            if m:
                kind, subj, f, c = m.group(1), m.group(2), m.group(3), m.group(4)
                sid = add_atom(subj)
                if sid:
                    atoms[sid].setdefault("stvs", []).append({"kind": kind + "-efficacy", "f": f, "c": c})
                continue
            m = re.search(r'\(-->\s+([^\s(]+)\s*\(?\[\]\s+([^\s"]+)\s+"(.*)"', core)
            if m:
                add_atom(m.group(1))
                details.setdefault(clean(m.group(1)), {})[clean(m.group(2))] = m.group(3)
                continue
            m = re.search(r'\(-->\s+([^\s(]+)\s*\(?\[\]\s+([^\s)]+)', core)
            if m:
                sid = add_atom(m.group(1)); cid = add_atom(m.group(2), "class")
                if sid and cid and sid != cid:
                    edges.append({"source": sid, "target": cid, "label": cid, "kind": "class"})
                continue
            m = re.search(r'\(==>\s+\(-->\s+\$\w+\s*\(?\[\]\s+(\S+?)\)?\s+\(-->\s+\$\w+\s*\(?\[\]\s+(\S+?)\)?', core)
            if m:
                a = add_atom(m.group(1), "class"); b = add_atom(m.group(2), "class")
                if a and b and a != b:
                    edges.append({"source": a, "target": b, "label": "==>", "kind": "implies"})
                continue
            m = re.search(r'\(==>\s+\(-->\s+\$\w+\s+(\S+?)\)?\s+\(-->\s+\$\w+\s+(\S+?)\)?', core)
            if m:
                a = add_atom(m.group(1), "class"); b = add_atom(m.group(2), "class")
                if a and b and a != b:
                    edges.append({"source": a, "target": b, "label": "==>", "kind": "implies"})
                continue
            m = re.search(r'\(-->\s+([^\s(]+)\s+([^\s)]+)\)?\)?$', core)
            if m:
                sid = add_atom(m.group(1)); pid = add_atom(m.group(2), "class")
                if sid and pid and sid != pid:
                    edges.append({"source": sid, "target": pid, "label": "-->", "kind": "is-a"})
                continue

valid = set(atoms)
edges = [e for e in edges if e["source"] in valid and e["target"] in valid]

nodes = []
for k, v in atoms.items():
    node = {"id": k, "label": k, "type": v["type"], "details": details.get(k, {})}
    if "stvs" in v:
        node["stvs"] = v["stvs"]
    nodes.append(node)

with open("atomspace_data.json", "w") as fh:
    json.dump({"nodes": nodes, "edges": edges}, fh)
print("nodes:", len(nodes), "edges:", len(edges), "details:", len(details))
print("nodes with stvs:", sum(1 for n in nodes if "stvs" in n))
