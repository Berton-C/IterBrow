import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = """Assign a MeTTa statement (a term, NOT a sentence -- no stv) to an LTM item in chroma_db. LTM_item must be a UUID from chroma_query results. Returns success or error.

Statement types (NAL):
  - Inheritance:        (--> raven bird)
  - Relational:         (--> (x Anna Bob) friend)
  - Property (with []): (--> channel_people ([] prefer_brief_response))
  - Implication:        (==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))"""

def check_parens(s):
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return False, f"Extra closing paren at position {i}"
    if depth != 0:
        return False, f"Unbalanced: {depth} unclosed opening paren(s)"
    return True, ""

def run(LTM_item, formalization):
    ok, msg = check_parens(formalization)
    if not ok:
        return f"Error: Formalization has unbalanced parentheses: {msg}\n  Input: {formalization}"

    s = formalization.strip()
    if not s.startswith('(') or not s.endswith(')'):
        return f"Error: Formalization must start with ( and end with ). Input: {formalization}"

    depth = 0
    for idx, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and idx != len(s) - 1:
                return f"Error: Extra content after closing paren. Input: {formalization}"

    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")

    def assign(document, metadata):
        metadata["formalization"] = formalization
        return document, metadata, f"SUCCESS: Assigned MeTTa statement to LTM item {LTM_item}:\n  {formalization}"

    result = petta_db.modify_memory(LTM_item, assign)
    return result if result is not None else f"Error: LTM item {LTM_item} not found in chroma_db."
