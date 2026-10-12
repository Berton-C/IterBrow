import os
import sys



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _dirname(path):
    value = str(path).rstrip("/")
    pos = value.rfind("/")
    return value[:pos] if pos > 0 else ("/" if pos == 0 else "")


def _mkdirs(path):
    current = ""
    for part in str(path).split("/"):
        if not part:
            current = "/" if not current else current
            continue
        current = (current.rstrip("/") + "/" + part) if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass

DESCRIPTION = "Regenerate space.metta from the formalizations of current semantic memories (AtomSpace authority)"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
SPACE_PATH = ROOT + "/transformations/.runtime/space.metta"
HEADER = ";; === Formalizations (auto-updated) ===\n"
MAX_LINES = 500

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def check_parens(s):
    depth = 0
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
    return depth == 0

def is_valid_metta(line):
    s = line.strip()
    if not s or s.startswith(';;'):
        return False
    if not check_parens(s):
        return False
    if not s.startswith('('):
        return False
    if not s.endswith(')'):
        return False
    if '"' in s:
        return False
    depth = 0
    for i in range(len(s)):
        ch = s[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and i != len(s) - 1:
                return False
    return True

def wrap_default_stv(line):
    s = line.strip()
    if '(stv ' in s:
        return s
    return "(" + s + " (stv 1.0 0.5))"


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def current_formalizations():
    """Formalization lines of the semantic memories the authority holds now.

    space.metta is a projection: regenerating it from current atoms (instead of
    merging what chroma_query happened to print) makes forgotten memories'
    formalizations disappear and keeps stv values current.  Returns None when
    the authority is unreachable.
    """
    try:
        from iterbrow_runtime.cognitive_events import (
            _call_atomspace, parse_semantic_atom, SEMANTIC_PREFIX)
        atoms = _call_atomspace("read_atoms", timeout=10, prefix=SEMANTIC_PREFIX)["atoms"]
    except Exception:
        return None
    best = {}
    for key in sorted(atoms):
        try:
            _, _, metadata = parse_semantic_atom(key, atoms[key])
        except ValueError:
            continue
        formalization = str(metadata.get("formalization") or "").strip()
        if not is_valid_metta(formalization):
            continue
        strength = _number(metadata.get("strength", 1.0), 1.0)
        confidence = _number(metadata.get("confidence", 0.5), 0.5)
        line = "(%s (stv %s %s))" % (formalization, strength, confidence)
        if not check_parens(line):
            continue
        # One line per formalization: keep the most confident memory's stv.
        if formalization not in best or confidence > best[formalization][0]:
            best[formalization] = (confidence, line)
    return [best[key][1] for key in sorted(best)][:MAX_LINES]


def transform(messages, tools):
    lines = current_formalizations()
    if lines is None:
        return messages, tools  # authority unreachable: leave the projection as it is
    content = HEADER + "".join(line + "\n" for line in lines)
    try:
        with open(SPACE_PATH, "r") as f:
            if f.read() == content:
                return messages, tools
    except Exception:
        pass
    try:
        _mkdirs(_dirname(SPACE_PATH))
        tmp = SPACE_PATH + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, SPACE_PATH)
    except Exception:
        pass
    return messages, tools
