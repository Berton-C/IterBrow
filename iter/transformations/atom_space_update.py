import re
import os



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

DESCRIPTION = "Auto-update space.metta with formalizations from chroma_query results"

SPACE_PATH = "transformations/.runtime/space.metta"

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

def transform(messages, tools):

    runtime_dir = _dirname(SPACE_PATH)
    try:
        _mkdirs(runtime_dir)
    except OSError:
        pass
    if not _exists(SPACE_PATH):
        try:
            with open(SPACE_PATH, "w") as file:
                file.write(";; === Formalizations (auto-updated) ===\n")
        except Exception:
            return messages, tools

    formalizations = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    parts.append(str(p.get("text", "")))
                else:
                    parts.append(str(p))
            content = "\n".join(parts)
        if not isinstance(content, str):
            content = str(content)
        if "Formalization:" not in content:
            continue
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if "Formalization:" in line:
                idx = line.index("Formalization:")
                formalization = line[idx + len("Formalization:"):].strip()
                if not is_valid_metta(formalization):
                    i += 1
                    continue
                stv_str = None
                for j in range(i - 1, max(i - 10, -1), -1):
                    if j >= 0 and "STV:" in lines[j]:
                        stv_str = lines[j].strip()
                        break
                if stv_str:
                    stv_match = re.search(r'STV:\s*\(([^,]+),\s*([^)]+)\)', stv_str)
                    if stv_match:
                        strength = stv_match.group(1).strip()
                        confidence = stv_match.group(2).strip()
                        wrapped = "(" + formalization + " (stv " + strength + " " + confidence + "))"
                    else:
                        wrapped = wrap_default_stv(formalization)
                else:
                    wrapped = wrap_default_stv(formalization)
                if check_parens(wrapped) and '"' not in wrapped:
                    formalizations.append(wrapped)
            i += 1

    try:
        with open(SPACE_PATH, "r") as f:
            existing_lines = f.readlines()
    except Exception:
        existing_lines = []

    header = ";; === Formalizations (auto-updated) ===\n"
    formalization_lines = [fl + "\n" for fl in formalizations]

    existing_non_header = []
    for l in existing_lines:
        stripped = l.strip()
        if stripped.startswith(";;"):
            continue
        if not stripped:
            continue
        if not check_parens(stripped):
            continue
        if '"' in stripped:
            continue
        if not stripped.startswith('('):
            continue
        if '(stv ' not in stripped:
            stripped = wrap_default_stv(stripped)
        existing_non_header.append(stripped + "\n")

    all_lines = [header] + formalization_lines + existing_non_header

    seen = {}
    deduped = []
    for l in all_lines:
        stripped = l.strip()
        if not stripped:
            continue
        # Dedup by formalization without STV, keep highest confidence
        key = re.sub(r'\s*\(stv\s+[^)]+\)\s*\)', ')', stripped).strip()
        stv_match = re.search(r'stv\s+([\d.]+)\s+([\d.]+)', stripped)
        conf = float(stv_match.group(2)) if stv_match else 0.0
        if key not in seen or conf > seen[key]:
            seen[key] = conf
            # Replace any previous entry for this key
            deduped = [d for d in deduped if re.sub(r'\s*\(stv\s+[^)]+\)\s*\)', ')', d.strip()).strip() != key]
            deduped.append(l)

    if len(deduped) > 500:
        deduped = deduped[:500]

    try:
        try:
            _mkdirs(_dirname(SPACE_PATH))
        except OSError:
            pass
        with open(SPACE_PATH, "w") as f:
            for l in deduped:
                f.write(l)
    except Exception:
        pass

    return messages, tools
