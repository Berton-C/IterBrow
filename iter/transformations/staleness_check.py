"""
Staleness Detection for AGENTS.md.

Compares actual files on disk (tools, channels, transformations) against
what AGENTS.md documents. If discrepancies are found, appends a warning
block to the system message so the agent knows AGENTS.md needs updating.

Checks:
  - Tools: .py files in ./tools/ not starting with _
  - Channels: .py files in ./channels/ not starting with _
  - Transformations: .py files in ./transformations/ not starting with _

Matching logic:
  - Strips .py extension, checks if base name appears in AGENTS.md
  - Also checks full filename (with .py)
  - Handles glob patterns in AGENTS.md (e.g. dashboard_*.py matches dashboard_atomspace.py)
"""
import os
import fnmatch

DESCRIPTION = "Detect staleness in AGENTS.md by comparing disk vs documented files."

BASE = "."
AGENTS_MD = os.path.join(BASE, "AGENTS.md")

DIRS = {
    "tools": os.path.join(BASE, "tools"),
    "channels": os.path.join(BASE, "channels"),
    "transformations": os.path.join(BASE, "transformations"),
}

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _list_active_py(directory):
    """Return set of active .py filenames (not starting with _) in a directory."""
    result = set()
    try:
        for entry in os.listdir(directory):
            if entry.endswith(".py") and not entry.startswith("_"):
                result.add(entry)
    except OSError:
        pass
    return result

def _is_documented(fname, md_content):
    """Check if fname (e.g. 'chroma_query.py') is referenced in AGENTS.md.

    Matches if any of these appear in md_content:
      - The full filename: 'chroma_query.py'
      - The base name: 'chroma_query'
      - A glob pattern that matches: e.g. 'chroma_*.py' or '*.py'
    """
    if fname in md_content:
        return True
    base = fname[:-3] if fname.endswith(".py") else fname  # strip .py
    if base in md_content:
        return True
    # Check glob patterns in the markdown (e.g. dashboard_*.py)
    # Extract all glob-like patterns from the markdown
    for token in md_content.replace("`", " ").split():
        if "*" in token and fnmatch.fnmatch(fname, token):
            return True
    return False

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        if not _exists(AGENTS_MD):
            return messages, tools

        with open(AGENTS_MD, "r") as f:
            md_content = f.read()

        warnings = []
        for label, dirpath in DIRS.items():
            on_disk = _list_active_py(dirpath)
            if not on_disk:
                continue
            undocumented = []
            for fname in sorted(on_disk):
                if not _is_documented(fname, md_content):
                    undocumented.append(fname)
            if undocumented:
                warnings.append("  {} not in AGENTS.md: {}".format(label, ", ".join(undocumented)))

        if warnings:
            block = "\n\n--- \u26a0\ufe0f AGENTS.md STALENESS WARNING ---\n"
            block += "The following active files are not documented in AGENTS.md:\n"
            block += "\n".join(warnings)
            block += "\nConsider updating AGENTS.md to include them.\n"

            first_msg = messages[0]
            if isinstance(first_msg, dict):
                fc = first_msg.get("content", "")
                if isinstance(fc, str):
                    first_msg["content"] = fc.rstrip() + block
                elif isinstance(fc, list):
                    first_msg["content"] = fc + [{"type": "text", "text": block}]

    except Exception:
        pass

    return messages, tools
