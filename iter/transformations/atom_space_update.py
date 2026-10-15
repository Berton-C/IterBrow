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

DESCRIPTION = "Regenerate space.metta (unloaded projection) from the knowledge-base statement atoms in the AtomSpace authority"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
SPACE_PATH = ROOT + "/transformations/.runtime/space.metta"
HEADER = ";; === Knowledge-base statements (projection of kb atoms; NOT loaded into the engine) ===\n"
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
    """Statement lines of the knowledge base the authority holds now.

    space.metta is a projection of the `(kb <statement> (stv f c))` atoms
    (Milestone 5): one line per statement, with the truth value revised over
    all of its evidence memories.  Memory metadata is never read here, so a
    memory's text and the statement atom cannot disagree in the projection.
    The engine does not load this file.  Returns None when the authority is
    unreachable.
    """
    try:
        from iterbrow_runtime.cognitive_events import _call_atomspace
        from iterbrow_runtime import kb_terms
        atoms = _call_atomspace("read_atoms", timeout=10, prefix=kb_terms.STATEMENT_PREFIX)["atoms"]
    except Exception:
        return None
    lines = []
    for key in sorted(atoms):
        try:
            statement, stv = kb_terms.parse_statement_atom(atoms[key])
        except ValueError:
            continue
        lines.append("(%s %s)" % (statement, kb_terms.stv_text(stv)))
    return sorted(lines)[:MAX_LINES]


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
